"""Chronologie d'un tour (ADR 0007, annexe §3 et §4) : `advance` la range dans lobby_timelines et la retire de l'état,
la route la sert avec les mêmes règles de visibilité que le lobby. Le moteur d'usine n'est pas nécessaire : une
chronologie bouchon (valide, de la taille du pire cas : 3 lignes x 4 machines, 5 jours) est posée dans
`state["last"]["timeline"]` par un `engine.advance` enveloppé. La base PostgreSQL est réelle (intégration)."""

import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any, get_args

import httpx
import pytest
from sqlalchemy import delete, func, select

from gmix.api.auth import create_access_token
from gmix.api.main import app
from gmix.api.routes import lobbies
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import BusinessGame, Lobby, LobbyTimeline, User, UserRole
from gmix.game import engine
from gmix.game.spec import MachineState, Timeline
from gmix.tools.create_user import create_user

pytestmark = pytest.mark.integration

COUNTERS = ["mp", "en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie"]
BUDGET_BYTES = 200_000  # annexe §6, critère 8


def stub_timeline(week: int, lines: int = 3) -> dict[str, Any]:
    """Chronologie valide au format de l'annexe §3 : 481 instantanés (5 min sur 5 x 480 min) et 500 événements."""
    machines = [f"l{line}-m{rank}" for line in range(1, lines + 1) for rank in range(1, 5)]
    count = len(machines)
    frames = [
        [float(t), [(i + t // 25) % 7 for i in range(count)], [(i * 3 + t // 5) % 11 for i in range(count)],
         [1800 - t // 3, 17 + t % 9, 2 + t % 5, 5 + t // 40, 0, 3 + t // 90, 6 + t // 60, 240 + t // 10, t // 120]]
        for t in range(0, 2401, 5)
    ]  # fmt: skip
    events = [
        [round(i * 4.8 + 0.5, 2), "agent", "agent_maintenance",
         {"state": "deplacement", "at": machines[i % count], "until": round(i * 4.8 + 3.5, 2)}]
        for i in range(500)
    ]  # fmt: skip
    return {
        "week": week, "days": 5, "minutes_per_day": 480, "day_start_h": 8, "frame_min": 5.0,
        "states": list(get_args(MachineState)), "machines": machines, "counters": COUNTERS, "frames": frames,
        "events": events,
    }  # fmt: skip


def as_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_stub_is_a_valid_timeline_within_budget() -> None:
    stub = stub_timeline(1)
    Timeline.model_validate(stub)
    assert len(stub["frames"]) == 481 and len(stub["frames"][0][1]) == len(stub["machines"]) == 12
    assert len(json.dumps(stub, separators=(",", ":"))) < BUDGET_BYTES


@pytest.fixture
async def world(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SimpleNamespace]:
    """Un lobby démarré (formateur, un membre) et trois étrangers (joueur, autre formateur, admin) ; nettoyé en fin."""
    suffix = uuid.uuid4().hex[:8]
    users = {
        name: await create_user(f"{name}-{suffix}", f"mdp-{name}-1", role)
        for name, role in {
            "formateur": UserRole.TRAINER, "autre-formateur": UserRole.TRAINER, "membre": UserRole.PLAYER,
            "etranger": UserRole.PLAYER, "admin": UserRole.ADMIN,
        }.items()
    }  # fmt: skip
    published: list[Any] = []

    async def fake_publish(request: Any, topic: Any, event: Any, *, required: bool = False) -> bool:
        published.append(event)
        return True

    monkeypatch.setattr(lobbies, "publish", fake_publish)  # ni Kafka ni relais dans ce test
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        ):
            as_trainer = _auth(users["formateur"])
            params = {"theme": "industrie", "modules": ["approvisionnement", "production"], "weeks": 4,
                      "products": 2, "events": "aucun", "seed": 3}  # fmt: skip
            game = (await client.post("/api/v1/games", json=params, headers=as_trainer)).json()
            body = {"name": "Groupe usine", "business_game_id": game["id"]}
            lobby = (await client.post("/api/v1/lobbies", json=body, headers=as_trainer)).json()
            joined = await client.post(
                "/api/v1/lobbies/join", json={"code": lobby["join_code"]}, headers=_auth(users["membre"])
            )
            assert joined.status_code == 200, joined.text
            url = f"/api/v1/lobbies/{lobby['id']}"
            assert (await client.post(f"{url}/start", headers=as_trainer)).status_code == 200

            def timeline(who: str, week: int, lobby_url: str = url) -> Any:
                return client.get(f"{lobby_url}/weeks/{week}/timeline", headers=_auth(users[who]))

            yield SimpleNamespace(
                client=client, users=users, lobby_id=uuid.UUID(lobby["id"]), url=url, published=published,
                trainer=as_trainer, timeline=timeline,
            )  # fmt: skip
    finally:
        async with get_sessionmaker()() as session:
            ids = [users["formateur"].id, users["autre-formateur"].id]
            await session.execute(delete(Lobby).where(Lobby.trainer_id.in_(ids)))  # cascade : membres, chronologies
            await session.execute(delete(BusinessGame).where(BusinessGame.created_by.in_(ids)))
            await session.execute(delete(User).where(User.username.like(f"%-{suffix}")))
            await session.commit()
        await get_engine().dispose()


def stub_advance(real: Any) -> Any:
    """`engine.advance` qui place la chronologie bouchon dans state["last"]["timeline"], comme le moteur d'usine."""

    def advance(spec: dict[str, Any], state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        new = real(spec, state, **kwargs)
        new["last"]["timeline"] = stub_timeline(state["week"])
        return new

    return advance


async def test_advance_stores_the_timeline_and_removes_it_from_the_state(world, monkeypatch) -> None:
    real = engine.advance
    monkeypatch.setattr(engine, "advance", stub_advance(real))
    assert (await world.timeline("formateur", 1)).status_code == 404  # rien avant le premier tour

    advanced = await world.client.post(f"{world.url}/advance", headers=world.trainer)
    assert advanced.status_code == 200
    assert "timeline" not in advanced.json()["state"]["last"] and advanced.json()["state"]["week"] == 2
    assert len(advanced.content) < 64_000  # état public < 64 Ko (annexe §6, critère 8)

    async with get_sessionmaker()() as session:
        lobby = await session.get(Lobby, world.lobby_id)
        row = await session.get(LobbyTimeline, (world.lobby_id, 1))
        rows = await session.scalar(select(func.count()).where(LobbyTimeline.lobby_id == world.lobby_id))
    assert "timeline" not in lobby.state["last"] and rows == 1
    assert row.timeline == as_json(stub_timeline(1))  # JSONB tel quel

    view = (await world.client.get(world.url, headers=world.trainer)).json()
    assert "timeline" not in view["state"]["last"]
    sent = [json.dumps(e.payload) for e in world.published if e.type == "lobby.state"]
    assert sent and all("timeline" not in p and "frames" not in p for p in sent)

    served = await world.timeline("formateur", 1)
    assert served.status_code == 200 and served.json() == as_json(stub_timeline(1))
    assert len(served.content) < BUDGET_BYTES
    assert (await world.timeline("formateur", 2)).status_code == 404  # le tour 2 n'est pas encore simulé

    monkeypatch.setattr(engine, "advance", real)  # moteur sans chronologie (pack atelier) : le tour 2 n'écrit rien
    assert (await world.client.post(f"{world.url}/advance", headers=world.trainer)).status_code == 200
    assert (await world.timeline("formateur", 2)).status_code == 404

    async with get_sessionmaker()() as session:  # la suppression du lobby emporte ses chronologies
        await session.execute(delete(Lobby).where(Lobby.id == world.lobby_id))
        await session.commit()
        assert await session.get(LobbyTimeline, (world.lobby_id, 1)) is None


async def test_timeline_route_access_rules(world, monkeypatch) -> None:
    monkeypatch.setattr(engine, "advance", stub_advance(engine.advance))
    assert (await world.client.post(f"{world.url}/advance", headers=world.trainer)).status_code == 200
    expected = as_json(stub_timeline(1))

    for who in ("membre", "formateur", "admin"):  # membre, formateur du lobby, admin
        answer = await world.timeline(who, 1)
        assert answer.status_code == 200 and answer.json() == expected, who
    for who in ("etranger", "autre-formateur"):  # pas d'énumération : 404 comme pour GET /lobbies/{id}
        assert (await world.timeline(who, 1)).status_code == 404, who
    assert (await world.timeline("etranger", 2)).status_code == 404
    assert (await world.timeline("membre", 2)).status_code == 404  # tour non simulé
    assert (await world.timeline("membre", 0)).status_code == 422
    assert (await world.client.get(f"{world.url}/weeks/1/timeline")).status_code in (401, 403)  # sans jeton
    assert (await world.timeline("admin", 1, f"/api/v1/lobbies/{uuid.uuid4()}")).status_code == 404

    async with get_sessionmaker()() as session:  # partie d'avant l'ADR 0006 : 410 comme le reste du lobby
        lobby = await session.get(Lobby, world.lobby_id)
        lobby.spec = {"kind": "legacy"}
        await session.commit()
    assert (await world.timeline("membre", 1)).status_code == 410
