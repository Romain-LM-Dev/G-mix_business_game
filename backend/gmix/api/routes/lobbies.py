"""Lobbies : création par le formateur, entrée des joueurs par code, actions par module, semaines simulées,
dialogues avec les agents PNJ (mémorisés) et débrief.

L'état de partie vit dans lobbies.state. Chaque action relit le lobby sous verrou de ligne (SELECT … FOR UPDATE),
applique gmix.game.engine puis diffuse l'état public au lobby (Kafka gmix.game.events -> relais WebSocket).
"""

import secrets
import uuid
from collections.abc import Callable
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from gmix.api.auth import CurrentUser, Session, Staff, create_presence_ticket
from gmix.api.deps import publish
from gmix.api.routes.games import owned_game
from gmix.db.models import GameStatus, Lobby, LobbyMember, LobbyStatus, LobbyTimeline, NpcMemory, User, UserRole
from gmix.game import engine
from gmix.game.engine import GameRuleError
from gmix.game.npc import MEMORY_TURNS, agent_reply
from gmix.game.spec import Timeline
from gmix.llm.ollama import OllamaError
from gmix.llm.service import ModelUnavailable
from gmix.messaging.envelope import Actor, Envelope
from gmix.messaging.topics import AUDIT, GAME_EVENTS, NPC_TRANSCRIPTS

router = APIRouter(prefix="/api/v1/lobbies", tags=["lobbies"])
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I : le code se dicte à l'oral


class LobbyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    business_game_id: uuid.UUID


class JoinRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class RoleChoice(BaseModel):
    game_role: str = Field(min_length=1, max_length=64)


class ActionRequest(BaseModel):
    module: str = Field(min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=40)
    values: dict[str, str | int] = Field(default_factory=dict, max_length=10)


class TalkRequest(BaseModel):
    message: str = Field(min_length=1, max_length=300)


def _manages(user: User, lobby: Lobby) -> bool:
    return user.role == UserRole.ADMIN or lobby.trainer_id == user.id


async def _access(
    session: Session, lobby_id: uuid.UUID, user: User, *, lock: bool = False
) -> tuple[Lobby, LobbyMember | None]:
    """Lobby visible par ses membres, son formateur et l'admin ; 404 pour les autres (pas d'énumération)."""
    query = select(Lobby).where(Lobby.id == lobby_id)
    lobby = await session.scalar(query.with_for_update() if lock else query)
    member = await session.get(LobbyMember, (lobby_id, user.id)) if lobby else None
    if lobby is None or (member is None and not _manages(user, lobby)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lobby introuvable")
    if (lobby.spec or {}).get("kind") != "simulation":  # créé avant l'ADR 0006 (migration 5b1d2e7a9c40)
        raise HTTPException(status.HTTP_410_GONE, "Partie créée avec l'ancien modèle de jeu : elle n'est plus jouable")
    return lobby, member


def _require_manager(user: User, lobby: Lobby) -> None:
    if not _manages(user, lobby):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seul le formateur du lobby pilote la partie")


def _apply(rule: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return rule(*args, **kwargs)
    except GameRuleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


async def _members(session: Session, lobby_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(LobbyMember, User.display_name)
        .join(User, User.id == LobbyMember.user_id)
        .where(LobbyMember.lobby_id == lobby_id)
        .order_by(LobbyMember.joined_at)
    )
    return [{"user_id": str(m.user_id), "display_name": name, "game_role": m.game_role} for m, name in rows]


async def _view(session: Session, lobby: Lobby, user: User, member: LobbyMember | None) -> dict[str, Any]:
    """Vue complète d'un lobby : spec (une simulation n'a pas de réponse cachée) et état public."""
    manager = _manages(user, lobby)
    return {
        "id": str(lobby.id),
        "name": lobby.name,
        "status": lobby.status,
        "join_code": lobby.join_code if manager else None,
        "is_manager": manager,
        "my_role": member.game_role if member else None,
        "members": await _members(session, lobby.id),
        "spec": lobby.spec,
        "state": engine.public_state(lobby.spec, lobby.state),
    }


async def _broadcast(request: Request, lobby: Lobby, user: User, event_type: str, payload: dict[str, Any]) -> None:
    event = Envelope(
        type=event_type,
        source="api",
        lobby_id=lobby.id,
        actor=Actor(user_id=user.id, role=user.role.value),
        payload=payload,
    )
    await publish(request, GAME_EVENTS, event)


async def _broadcast_state(request: Request, lobby: Lobby, user: User, action: dict[str, Any]) -> dict[str, Any]:
    state = engine.public_state(lobby.spec, lobby.state)
    await _broadcast(
        request,
        lobby,
        user,
        "lobby.state",
        {"lobby_status": lobby.status, "state": state, "action": action | {"by": user.display_name}},
    )
    return state


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_lobby(body: LobbyCreate, actor: Staff, session: Session, request: Request) -> dict[str, Any]:
    game = await owned_game(session, body.business_game_id, actor)
    if game.status != GameStatus.READY or game.spec is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce business game n'est pas prêt")
    for _ in range(5):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not await session.scalar(select(Lobby.id).where(Lobby.join_code == code)):
            break
    lobby = Lobby(
        name=body.name,
        join_code=code,
        trainer_id=actor.id,
        business_game_id=game.id,
        status=LobbyStatus.READY,
        spec=game.spec,
        state=engine.initial_state(game.spec),
    )
    session.add(lobby)
    await session.commit()
    audit = {"lobby_id": str(lobby.id), "game_id": str(game.id), "spec_version": game.spec_version}
    await publish(
        request, AUDIT, Envelope(type="lobby.created", source="api", actor=Actor(user_id=actor.id), payload=audit)
    )
    return await _view(session, lobby, actor, None)


@router.get("")
async def list_lobbies(user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    """Formateur : ses lobbies ; joueur : ceux qu'il a rejoints ; admin : tous."""
    query = select(Lobby).order_by(Lobby.created_at.desc()).limit(100)
    if user.role == UserRole.TRAINER:
        query = query.where(Lobby.trainer_id == user.id)
    elif user.role == UserRole.PLAYER:
        query = query.join(LobbyMember, LobbyMember.lobby_id == Lobby.id).where(LobbyMember.user_id == user.id)
    return [
        {
            "id": str(lobby.id),
            "name": lobby.name,
            "status": lobby.status,
            "game_title": (lobby.spec or {}).get("meta", {}).get("title"),
            "join_code": lobby.join_code if _manages(user, lobby) else None,
            "week": lobby.state.get("week"),
            "weeks": (lobby.spec or {}).get("meta", {}).get("weeks"),
            "game_status": lobby.state.get("status"),
        }
        for lobby in await session.scalars(query)
    ]


@router.post("/join")
async def join_lobby(body: JoinRequest, user: CurrentUser, session: Session, request: Request) -> dict[str, Any]:
    code = body.code.strip().upper()
    lobby = await session.scalar(select(Lobby).where(Lobby.join_code == code).with_for_update())
    if lobby is None or lobby.status not in (LobbyStatus.READY, LobbyStatus.RUNNING):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Code inconnu ou partie terminée")
    member = await session.get(LobbyMember, (lobby.id, user.id))
    if member is None:
        count = await session.scalar(select(func.count()).where(LobbyMember.lobby_id == lobby.id))
        if count >= lobby.spec["meta"]["players"]["max"]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Lobby complet")
        member = LobbyMember(lobby_id=lobby.id, user_id=user.id)
        session.add(member)
        await session.commit()
        await _broadcast(request, lobby, user, "lobby.members", {"members": await _members(session, lobby.id)})
    return await _view(session, lobby, user, member)


@router.get("/{lobby_id}")
async def get_lobby(lobby_id: uuid.UUID, user: CurrentUser, session: Session) -> dict[str, Any]:
    lobby, member = await _access(session, lobby_id, user)
    return await _view(session, lobby, user, member)


@router.put("/{lobby_id}/role")
async def choose_role(
    lobby_id: uuid.UUID, body: RoleChoice, user: CurrentUser, session: Session, request: Request
) -> dict[str, Any]:
    lobby, member = await _access(session, lobby_id, user, lock=True)
    if member is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Rejoignez le lobby avant de choisir un rôle")
    if body.game_role not in {r["id"] for r in lobby.spec["roles"]}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Rôle inconnu dans ce business game")
    if member.game_role and lobby.state["status"] != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, "Le rôle ne change plus une fois la partie lancée")
    member.game_role = body.game_role
    await session.commit()
    await _broadcast(request, lobby, user, "lobby.members", {"members": await _members(session, lobby.id)})
    return await _view(session, lobby, user, member)


@router.post("/{lobby_id}/start")
async def start_game(lobby_id: uuid.UUID, user: Staff, session: Session, request: Request) -> dict[str, Any]:
    lobby, _ = await _access(session, lobby_id, user, lock=True)
    _require_manager(user, lobby)
    lobby.state = _apply(engine.start, lobby.spec, lobby.state)
    lobby.status = LobbyStatus.RUNNING
    await session.commit()
    return {"state": await _broadcast_state(request, lobby, user, {"type": "start"})}


@router.post("/{lobby_id}/advance")
async def advance_week(lobby_id: uuid.UUID, user: Staff, session: Session, request: Request) -> dict[str, Any]:
    """Simule la semaine en cours (livraisons, production, demande, coûts) et ouvre la suivante."""
    lobby, _ = await _access(session, lobby_id, user, lock=True)
    _require_manager(user, lobby)
    week = lobby.state["week"]
    state = _apply(engine.advance, lobby.spec, lobby.state)
    # La chronologie (pack usine) est trop lourde pour lobbies.state et pour lobby.state : table à part (ADR 0007)
    timeline = state["last"].pop("timeline", None)
    lobby.state = state
    if timeline is not None:
        session.add(LobbyTimeline(lobby_id=lobby.id, week=week, timeline=timeline))
    if lobby.state["status"] == "finished":
        lobby.status = LobbyStatus.CLOSED
        request.app.state.game_servers.stop(str(lobby.id))
    await session.commit()
    return {"state": await _broadcast_state(request, lobby, user, {"type": "advance"})}


@router.get("/{lobby_id}/weeks/{week}/timeline", response_model=Timeline)
async def get_timeline(
    lobby_id: uuid.UUID, week: Annotated[int, Path(ge=1, le=32767)], user: CurrentUser, session: Session
) -> Any:
    """Chronologie du tour `week` (pack usine), rejouée par le client. Même visibilité que le lobby ; 404 aussi
    pour un tour pas encore simulé ou d'un pack sans chronologie."""
    lobby, _ = await _access(session, lobby_id, user)
    row = await session.get(LobbyTimeline, (lobby.id, week))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tour non simulé")
    return row.timeline


@router.post("/{lobby_id}/actions")
async def module_action(
    lobby_id: uuid.UUID, body: ActionRequest, user: CurrentUser, session: Session, request: Request
) -> dict[str, Any]:
    """Action d'un module (commande, plan, entretien…). Un rôle tenu par un joueur garde la main sur son module ;
    le formateur peut agir partout."""
    lobby, member = await _access(session, lobby_id, user, lock=True)
    occupied = set(
        await session.scalars(
            select(LobbyMember.game_role).where(LobbyMember.lobby_id == lobby.id, LobbyMember.game_role.is_not(None))
        )
    )
    actor = {"user_id": str(user.id), "name": user.display_name, "role": member.game_role if member else None}
    lobby.state, summary = _apply(
        engine.act, lobby.spec, lobby.state, body.module, body.action, body.values,
        actor=actor, manager=_manages(user, lobby), occupied_roles=occupied,
    )  # fmt: skip
    await session.commit()
    action = {"type": "action", "module": body.module, "summary": summary}
    return {"state": await _broadcast_state(request, lobby, user, action), "summary": summary}


@router.post("/{lobby_id}/npcs/{npc_id}/talk")
async def talk_to_agent(
    lobby_id: uuid.UUID, npc_id: str, body: TalkRequest, user: CurrentUser, session: Session, request: Request
) -> dict[str, Any]:
    """Réplique d'un agent : ses informations essentielles de la semaine, son caractère et la mémoire des
    derniers échanges du lobby avec lui. L'échange est enregistré (npc_memories) sauf si le moteur de dialogue le
    juge douteux (`remember` faux : injection, hors-sujet) : il ne doit pas être rejoué aux autres joueurs."""
    lobby, _ = await _access(session, lobby_id, user)
    agent = next((a for a in lobby.spec["agents"] if a["id"] == npc_id), None)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent introuvable")
    rows = await session.scalars(
        select(NpcMemory)
        .where(NpcMemory.lobby_id == lobby.id, NpcMemory.npc_id == npc_id)
        .order_by(NpcMemory.id.desc())
        .limit(MEMORY_TURNS)
    )
    memory = [{"speaker": m.speaker, "message": m.message, "reply": m.reply} for m in reversed(list(rows))]
    view = engine.public_state(lobby.spec, lobby.state)
    try:
        result = await agent_reply(
            request.app.state.llm, session, spec=lobby.spec, view=view, agent=agent, message=body.message,
            speaker=user.display_name, memory=memory,
        )  # fmt: skip
    except (ModelUnavailable, OllamaError, httpx.HTTPError) as exc:
        detail = f"{agent['name']} ne répond pas : IA indisponible ({exc})"
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail) from exc
    remember = result.pop("remember")  # décision serveur : le client ne la voit pas
    if remember:
        session.add(
            NpcMemory(lobby_id=lobby.id, npc_id=npc_id, user_id=user.id, speaker=user.display_name,
                      message=body.message, reply=result["reply"], week=view["week"])
        )  # fmt: skip
        await session.commit()
    transcript = {"npc_id": npc_id, "message": body.message, "remember": remember} | result
    envelope = Envelope(
        type="npc.exchange", source="api", lobby_id=lobby.id, actor=Actor(user_id=user.id), payload=transcript
    )
    await publish(request, NPC_TRANSCRIPTS, envelope)
    return result


@router.get("/{lobby_id}/npcs/{npc_id}/memory")
async def agent_memory(lobby_id: uuid.UUID, npc_id: str, user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    """Vos échanges passés avec cet agent dans ce lobby (le fil du dialogue survit à la déconnexion)."""
    lobby, _ = await _access(session, lobby_id, user)
    rows = await session.scalars(
        select(NpcMemory)
        .where(NpcMemory.lobby_id == lobby.id, NpcMemory.npc_id == npc_id, NpcMemory.user_id == user.id)
        .order_by(NpcMemory.id.desc())
        .limit(30)
    )
    return [{"message": m.message, "reply": m.reply, "week": m.week} for m in reversed(list(rows))]


@router.post("/{lobby_id}/presence")
async def presence_ticket(lobby_id: uuid.UUID, user: CurrentUser, session: Session, request: Request) -> dict[str, Any]:
    """Accès au serveur de partie Godot du lobby (positions des joueurs, ADR 0005), lancé à la demande.
    Le client se connecte à l'hôte de l'API sur `port` et présente `ticket` (valable 60 s)."""
    lobby, member = await _access(session, lobby_id, user)
    if lobby.status == LobbyStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Partie terminée")
    servers = request.app.state.game_servers
    if not servers.available():
        detail = "Serveur de partie indisponible (GODOT_CONSOLE_EXE absent du .env) : partie sans présence"
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)
    port = servers.ensure(str(lobby.id))
    return {"port": port, "ticket": create_presence_ticket(user, lobby.id, member.game_role if member else None)}


@router.get("/{lobby_id}/debrief")
async def get_debrief(lobby_id: uuid.UUID, user: CurrentUser, session: Session) -> dict[str, Any]:
    lobby, _ = await _access(session, lobby_id, user)
    if not _manages(user, lobby) and lobby.state["status"] != "finished":
        raise HTTPException(status.HTTP_409_CONFLICT, "Le débrief s'ouvre à la fin de la partie")
    return engine.debrief(lobby.spec, lobby.state)
