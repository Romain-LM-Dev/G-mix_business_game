"""API FastAPI : passerelle REST + WebSocket entre le client Godot et le pipeline Kafka / IA.

Lancement dev : scripts\\api.ps1  (uvicorn --reload)  -> http://127.0.0.1:8000/docs
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gmix import __version__
from gmix.api import ws
from gmix.api.deps import ensure_producer
from gmix.api.routes import accounts, catalog, games, lobbies, system
from gmix.db import get_engine
from gmix.game.servers import GameServers
from gmix.llm.service import LLMService
from gmix.logging_setup import setup_logging
from gmix.settings import get_settings

log = logging.getLogger("gmix.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(get_settings().log_level)
    app.state.hub = ws.WebSocketHub()
    app.state.llm = LLMService.from_settings()
    app.state.game_servers = GameServers()
    app.state.producer = None
    if await ensure_producer(app) is None:
        log.warning("Kafka injoignable au démarrage : API en mode dégradé (nouvel essai à chaque publication)")
    relay = asyncio.create_task(ws.run_relay(app.state.hub), name="kafka-ws-relay")
    yield
    relay.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await relay
    app.state.game_servers.stop_all()
    if app.state.producer is not None:
        await app.state.producer.stop()
    await app.state.llm.aclose()
    await get_engine().dispose()


app = FastAPI(title="G-mix Open World API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system.router)
app.include_router(accounts.router)
app.include_router(games.router)
app.include_router(lobbies.router)
app.include_router(catalog.router)
app.include_router(ws.router)
