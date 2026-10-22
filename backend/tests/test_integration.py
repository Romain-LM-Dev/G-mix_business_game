"""Tests d'intégration : nécessitent l'infra Docker + Ollama. Lancer avec : pytest -m integration"""

import pytest

from gmix.db import get_engine
from gmix.health import full_health
from gmix.llm.service import LLMService

pytestmark = pytest.mark.integration


async def test_all_services_are_healthy() -> None:
    llm = LLMService.from_settings(with_cache=False)
    try:
        report = await full_health(llm)
    finally:
        await llm.aclose()
        await get_engine().dispose()
    failing = {name: result for name, result in report["services"].items() if not result["ok"]}
    assert not failing, failing
