"""WebSocket : canal temps réel API -> Godot (événements Kafka relayés) et Godot -> API (abonnements).

Messages JSON {type, payload[, meta]}. Les positions des joueurs dans le monde 3D ne passent pas ici :
voir docs/architecture.md (réseau temps réel Godot).
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gmix.api.auth import decode_token
from gmix.db import get_sessionmaker
from gmix.db.models import Lobby, LobbyMember, User, UserRole
from gmix.messaging.envelope import Envelope
from gmix.messaging.kafka import consume
from gmix.messaging.topics import GAME_EVENTS, GENERATION_EVENTS, SYSTEM_PONG

log = logging.getLogger("gmix.ws")

RELAYED_TOPICS = (SYSTEM_PONG, GENERATION_EVENTS, GAME_EVENTS)


class WebSocketHub:
    def __init__(self) -> None:
        self._clients: dict[str, WebSocket] = {}
        self._lobbies: defaultdict[str, set[str]] = defaultdict(set)

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        previous = self._clients.get(client_id)
        if previous is not None:
            with contextlib.suppress(Exception):
                await previous.close(code=4000, reason="session remplacée")
        self._clients[client_id] = websocket

    def disconnect(self, client_id: str, websocket: WebSocket) -> None:
        if self._clients.get(client_id) is websocket:
            del self._clients[client_id]
            for members in self._lobbies.values():
                members.discard(client_id)

    def subscribe(self, client_id: str, lobby_id: str) -> None:
        """Une session suit un seul lobby à la fois : l'abonnement remplace le précédent."""
        for members in self._lobbies.values():
            members.discard(client_id)
        self._lobbies[lobby_id].add(client_id)

    async def send(self, client_id: str, message: dict[str, Any]) -> bool:
        websocket = self._clients.get(client_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            self.disconnect(client_id, websocket)
            return False

    async def dispatch(self, event: Envelope) -> None:
        message = event.to_client()
        if event.client_id:
            await self.send(event.client_id, message)
        if event.lobby_id:
            for client_id in list(self._lobbies.get(str(event.lobby_id), ())):
                await self.send(client_id, message)


router = APIRouter()


async def _authenticate(websocket: WebSocket) -> User | None:
    scheme, _, token = websocket.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        claims = decode_token(token)
        async with get_sessionmaker()() as session:
            user = await session.get(User, uuid.UUID(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return user if user is not None and user.is_active else None


async def _can_watch(user: User, lobby_id: str) -> bool:
    try:
        lobby_uuid = uuid.UUID(lobby_id)
    except ValueError:
        return False
    async with get_sessionmaker()() as session:
        lobby = await session.get(Lobby, lobby_uuid)
        if lobby is None:
            return False
        if user.role == UserRole.ADMIN or lobby.trainer_id == user.id:
            return True
        return await session.get(LobbyMember, (lobby_uuid, user.id)) is not None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Connexion avec l'en-tête `Authorization: Bearer <jeton>` (ADR 0004) : la session est celle de l'utilisateur,
    jamais un identifiant choisi par le client."""
    user = await _authenticate(websocket)
    if user is None:
        await websocket.close(code=4401, reason="Connexion requise ou expirée")
        return
    client_id = str(user.id)
    hub: WebSocketHub = websocket.app.state.hub
    await hub.connect(client_id, websocket)
    await websocket.send_json({"type": "session.welcome", "payload": {"client_id": client_id}})
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
                kind, payload = message.get("type"), message.get("payload") or {}
            except (json.JSONDecodeError, AttributeError):
                await websocket.send_json({"type": "error", "payload": {"message": "JSON {type, payload} attendu"}})
                continue
            if kind == "lobby.subscribe" and payload.get("lobby_id"):
                lobby_id = str(payload["lobby_id"])
                if not await _can_watch(user, lobby_id):
                    await websocket.send_json({"type": "error", "payload": {"message": "Lobby introuvable"}})
                    continue
                hub.subscribe(client_id, lobby_id)
                await websocket.send_json({"type": "lobby.subscribed", "payload": {"lobby_id": lobby_id}})
            elif kind == "ping":
                await websocket.send_json({"type": "pong", "payload": payload})
            else:
                await websocket.send_json({"type": "error", "payload": {"message": f"type inconnu : {kind}"}})
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(client_id, websocket)


async def run_relay(hub: WebSocketHub) -> None:
    """Relaie vers les WebSockets les événements Kafka destinés aux clients ; se reconnecte si Kafka tombe."""
    delay = 2.0
    while True:
        try:
            await consume(RELAYED_TOPICS, hub.dispatch, group_id=None, from_latest=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Relais Kafka -> WebSocket interrompu (%s), nouvel essai dans %.0f s", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
