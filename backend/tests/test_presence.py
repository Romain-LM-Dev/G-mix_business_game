"""Présence multijoueur (ADR 0005) : le serveur de partie Godot, lancé comme le fait l'API, accepte un ticket
signé par l'API pour son lobby et refuse celui d'un autre lobby. Vérifie la compatibilité HS256 PyJWT / Godot.
Nécessite Godot (GODOT_CONSOLE_EXE dans .env)."""

import subprocess
import time
import uuid

import pytest

from gmix.api.auth import create_presence_ticket
from gmix.db.models import User, UserRole
from gmix.game.servers import GameServers
from gmix.settings import REPO_ROOT, get_settings

pytestmark = pytest.mark.integration


def _probe(port: int, ticket: str) -> int:
    command = [
        get_settings().godot_console_exe, "--headless", "--path", str(REPO_ROOT / "godot"), "--",
        "--presence-probe", "--host=127.0.0.1", f"--port={port}", f"--ticket={ticket}",
    ]  # fmt: skip
    return subprocess.run(command, capture_output=True, timeout=90, check=False).returncode


def test_game_server_checks_presence_tickets() -> None:
    servers = GameServers()
    if not servers.available():
        pytest.skip("GODOT_CONSOLE_EXE absent du .env")
    lobby_id = uuid.uuid4()
    player = User(id=uuid.uuid4(), username="testeur", display_name="Testeur", role=UserRole.PLAYER)
    port = servers.ensure(str(lobby_id))
    try:
        time.sleep(3)  # démarrage du serveur headless
        assert _probe(port, create_presence_ticket(player, lobby_id, "daf")) == 0
        assert _probe(port, create_presence_ticket(player, uuid.uuid4(), "daf")) == 1  # ticket d'un autre lobby
        assert servers.ensure(str(lobby_id)) == port  # déjà lancé : même serveur
    finally:
        servers.stop(str(lobby_id))
