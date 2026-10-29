"""Client Ollama : un serveur injoignable doit échouer vite (l'agent PNJ répond alors par son secours)."""

import socket
import time

import httpx
import pytest

from gmix.llm.ollama import CONNECT_TIMEOUT_S, OllamaClient


def test_connect_timeout_is_one_second() -> None:
    client = OllamaClient("http://127.0.0.1:11434")
    assert client._http.timeout.connect == CONNECT_TIMEOUT_S == 1.0
    assert client._http.timeout.read > 60  # la génération reste patiente : seule la connexion est brève


async def test_unreachable_server_fails_in_about_a_second() -> None:
    """Port local fermé : Windows refuse après ~2 s (ConnectError), le délai de connexion coupe à 1 s."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]  # libéré à la sortie : plus personne n'écoute dessus
    client = OllamaClient(f"http://127.0.0.1:{port}")
    start = time.perf_counter()
    try:
        with pytest.raises(httpx.HTTPError):
            await client.version()
    finally:
        await client.aclose()
    assert time.perf_counter() - start < 1.6
