"""Serveurs de partie Godot (ADR 0005) : un processus headless par lobby, lancé par l'API à la demande.

Le serveur fait autorité sur la présence (positions, animations) et n'accepte un joueur qu'avec un ticket de
présence signé par l'API (JWT HS256, 60 s). Le secret lui parvient par variable d'environnement, jamais par la
ligne de commande (visible des autres comptes de la machine). Les règles du jeu restent dans l'API.
"""

import logging
import os
import socket
import subprocess
from pathlib import Path

from gmix.settings import REPO_ROOT, get_settings

log = logging.getLogger("gmix.game.servers")


class GameServers:
    """shortcut: processus enfants de l'API, perdus si elle redémarre ; un orchestrateur s'imposera au-delà
    d'une machine (jeu à distance avec plusieurs hôtes)."""

    def __init__(self) -> None:
        self._running: dict[str, tuple[subprocess.Popen[bytes], int]] = {}

    def available(self) -> bool:
        exe = get_settings().godot_console_exe
        return bool(exe) and Path(exe).is_file()

    def ensure(self, lobby_id: str) -> int:
        """Port UDP du serveur du lobby, démarré s'il ne tourne pas déjà."""
        entry = self._running.get(lobby_id)
        if entry is not None and entry[0].poll() is None:
            return entry[1]
        settings = get_settings()
        port = self._free_port()
        process = subprocess.Popen(  # noqa: S603 : exécutable et arguments maîtrisés (pas d'entrée utilisateur)
            [
                settings.godot_console_exe,
                "--headless",
                "--path",
                str(REPO_ROOT / "godot"),
                "--",
                "--server",
                f"--lobby={lobby_id}",
                f"--port={port}",
            ],
            env=os.environ | {"GMIX_JWT_SECRET": settings.jwt_secret},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._running[lobby_id] = (process, port)
        log.info("Serveur de partie du lobby %s : port %d (pid %d)", lobby_id, port, process.pid)
        return port

    def stop(self, lobby_id: str) -> None:
        entry = self._running.pop(lobby_id, None)
        if entry is not None and entry[0].poll() is None:
            entry[0].terminate()

    def stop_all(self) -> None:
        for lobby_id in list(self._running):
            self.stop(lobby_id)

    def _free_port(self) -> int:
        low, _, high = get_settings().game_server_ports.partition("-")
        used = {port for process, port in self._running.values() if process.poll() is None}
        for port in range(int(low), int(high or low) + 1):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(("0.0.0.0", port))  # libre aussi pour un serveur orphelin d'un redémarrage
                except OSError:
                    continue
            return port
        raise RuntimeError(f"Aucun port libre dans GAME_SERVER_PORTS={get_settings().game_server_ports}")
