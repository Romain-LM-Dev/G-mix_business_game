"""Comptes jetables des contrôles Godot : le nettoyage supprime lobbies, parties et comptes jetables, rien d'autre."""

import secrets
import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy import delete, func, select

from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import BusinessGame, Lobby, LobbyMember, User, UserRole
from gmix.tools import ui_accounts
from gmix.tools.create_user import create_user

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _fresh_pool():
    """Moteur mis en cache : un pool par test, sinon les connexions d'un test servent dans la boucle du suivant."""
    yield
    await get_engine().dispose()


async def _count(model, column, ids: list[uuid.UUID]) -> int:
    async with get_sessionmaker()() as session:
        return await session.scalar(select(func.count()).select_from(model).where(column.in_(ids)))


async def test_cleanup_removes_throwaway_rows_and_keeps_other_accounts() -> None:
    created = await ui_accounts.create("tour")
    assert set(created["env"]) == {"GMIX_TOUR_ADMIN_TOKEN", "GMIX_TOUR_PLAYER_TOKEN"}
    ids = [uuid.UUID(i) for i in created["ids"]]
    admin = ids[0]
    keep = await create_user(f"temoin_{secrets.token_hex(3)}", secrets.token_urlsafe(18), UserRole.ADMIN)
    try:
        async with get_sessionmaker()() as session:  # une partie et un lobby du compte jetable
            game = BusinessGame(domain_slug="supply-chain", title="Test", brief="Test", created_by=admin)
            session.add(game)
            await session.flush()
            join_code = secrets.token_hex(3).upper()
            session.add(Lobby(name="Test", join_code=join_code, trainer_id=admin, business_game_id=game.id))
            await session.commit()
        assert await _count(Lobby, Lobby.trainer_id, ids) == 1  # le décor existe bien avant le nettoyage
        await ui_accounts.cleanup([*ids, keep.id])
        assert await _count(User, User.id, ids) == 0
        assert await _count(Lobby, Lobby.trainer_id, ids) == 0
        assert await _count(BusinessGame, BusinessGame.created_by, ids) == 0
        assert await _count(User, User.id, [keep.id]) == 1  # identifiant sans préfixe jetable : intact
    finally:
        await ui_accounts.cleanup(ids)
        async with get_sessionmaker()() as session:
            await session.execute(delete(User).where(User.id == keep.id))
            await session.commit()


async def _add_game_and_lobby(owner: uuid.UUID, members: Sequence[uuid.UUID] = ()) -> tuple[uuid.UUID, uuid.UUID]:
    async with get_sessionmaker()() as session:
        game = BusinessGame(domain_slug="supply-chain", title="Test", brief="Test", created_by=owner)
        session.add(game)
        await session.flush()
        lobby = Lobby(name="Test", join_code=secrets.token_hex(3).upper(), trainer_id=owner, business_game_id=game.id)
        session.add(lobby)
        await session.flush()
        session.add_all(LobbyMember(lobby_id=lobby.id, user_id=member) for member in members)
        await session.commit()
        return game.id, lobby.id


async def _purge(user_ids: list[uuid.UUID]) -> None:
    """Ménage du test, par identifiants exacts (ne passe pas par le code testé)."""
    async with get_sessionmaker()() as session:
        await session.execute(delete(Lobby).where(Lobby.trainer_id.in_(user_ids)))
        await session.execute(delete(BusinessGame).where(BusinessGame.created_by.in_(user_ids)))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def test_cleanup_only_touches_the_listed_ids() -> None:
    """Un compte au préfixe jetable mais absent de la liste (autre lancement en cours) n'est pas supprimé."""
    created = await ui_accounts.create("tour")
    ids = [uuid.UUID(i) for i in created["ids"]]
    other = await create_user(f"uitour_autre_{secrets.token_hex(3)}", secrets.token_urlsafe(18), UserRole.ADMIN)
    try:
        await _add_game_and_lobby(other.id)
        await ui_accounts.cleanup(ids)
        assert await _count(User, User.id, [other.id]) == 1
        assert await _count(Lobby, Lobby.trainer_id, [other.id]) == 1
        assert await _count(BusinessGame, BusinessGame.created_by, [other.id]) == 1
    finally:
        await _purge([*ids, other.id])


async def test_cleanup_keeps_lobbies_and_games_of_non_throwaway_accounts() -> None:
    """Passer par erreur l'identifiant d'un vrai compte ne doit effacer ni ses lobbies ni ses parties."""
    real = await create_user(f"temoin_{secrets.token_hex(3)}", secrets.token_urlsafe(18), UserRole.TRAINER)
    try:
        game_id, lobby_id = await _add_game_and_lobby(real.id)
        message = await ui_accounts.cleanup([real.id])
        assert message.startswith("0 compte(s), 0 lobby(ies), 0 partie(s)")
        async with get_sessionmaker()() as session:
            assert await session.get(Lobby, lobby_id) is not None
            assert await session.get(BusinessGame, game_id) is not None
        assert await _count(User, User.id, [real.id]) == 1
    finally:
        await _purge([real.id])


async def test_cleanup_prefix_underscore_is_literal() -> None:
    """« uitour_ » ne doit pas s'écrire LIKE 'uitour_%' : le tiret bas jokerait « uitourX… » (autoescape)."""
    lookalike = await create_user(f"uitourX{secrets.token_hex(3)}", secrets.token_urlsafe(18), UserRole.PLAYER)
    try:
        await ui_accounts.cleanup([lookalike.id])
        assert await _count(User, User.id, [lookalike.id]) == 1
    finally:
        await _purge([lookalike.id])


async def test_cleanup_removes_lobby_of_throwaway_account_but_keeps_its_real_member_and_is_idempotent() -> None:
    created = await ui_accounts.create("tour")
    ids = [uuid.UUID(i) for i in created["ids"]]
    member = await create_user(f"temoin_{secrets.token_hex(3)}", secrets.token_urlsafe(18), UserRole.PLAYER)
    try:
        _, lobby_id = await _add_game_and_lobby(ids[0], [member.id])
        await ui_accounts.cleanup(ids)
        async with get_sessionmaker()() as session:
            assert await session.get(Lobby, lobby_id) is None
            assert await session.get(LobbyMember, (lobby_id, member.id)) is None
        assert await _count(User, User.id, [member.id]) == 1
        assert (await ui_accounts.cleanup(ids)).startswith("0 compte(s), 0 lobby(ies), 0 partie(s)")  # idempotent
    finally:
        await _purge([*ids, member.id])


async def test_create_rolls_back_when_a_later_account_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    first: list[uuid.UUID] = []
    real_create_user = ui_accounts.create_user

    async def second_account_fails(username: str, password: str, role: UserRole, name: str) -> User:
        if first:
            raise ValueError("compte refusé (test)")
        user = await real_create_user(username, password, role, name)
        first.append(user.id)
        return user

    monkeypatch.setattr(ui_accounts, "create_user", second_account_fails)
    with pytest.raises(ValueError):
        await ui_accounts.create("tour")
    assert await _count(User, User.id, first) == 0  # le premier compte, déjà créé, est retiré
