"""Routage, budgets, repli et validation du service IA, avec un faux client Ollama (aucun appel réseau)."""

from typing import Any

import pytest

from gmix.llm.catalog import load_catalog
from gmix.llm.ollama import ChatResult, Usage
from gmix.llm.prompts import load_questions
from gmix.llm.service import BudgetExceeded, InvalidOutput, LLMService, ModelUnavailable


class FakeOllama:
    def __init__(self, installed: set[str], reply: str = "{}") -> None:
        self._installed = installed
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    async def installed_models(self) -> set[str]:
        return set(self._installed)

    async def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        self.calls.append({"model": model, "messages": messages, **kwargs})
        return ChatResult(content=self.reply, usage=Usage(model=model))

    async def decide(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("le modèle de décision n'est pas installé : ne doit pas être appelé")

    async def aclose(self) -> None:
        pass


def _service(client: FakeOllama) -> LLMService:
    return LLMService(load_catalog(), client)  # type: ignore[arg-type]


async def test_decision_falls_back_to_constrained_chat() -> None:
    client = FakeOllama({"qwen2.5:1.5b"}, reply='{"intent": "decision", "injection": false}')
    questions = load_questions("player.intent")
    result = await _service(client).decide("player.intent", "Je choisis l'affacturage.", questions)
    assert result["emulated"] is True
    assert result["answers"]["intent"]["choice"] == "decision"
    assert result["answers"]["injection"]["noul"] == 0.0
    call = client.calls[0]
    assert call["model"] == "qwen2.5:1.5b"
    assert call["fmt"]["properties"]["intent"]["enum"] == list(questions["intent"]["criteria"])


async def test_missing_models_raise_model_unavailable() -> None:
    with pytest.raises(ModelUnavailable):
        await _service(FakeOllama(set())).text("npc.bark", [{"role": "user", "content": "Bonjour"}])


async def test_budget_is_checked_before_calling_ollama() -> None:
    client = FakeOllama({"qwen2.5:1.5b"})
    with pytest.raises(BudgetExceeded):
        await _service(client).text("npc.bark", [{"role": "user", "content": "mot " * 2000}])
    assert client.calls == []


async def test_json_output_is_validated_against_the_task_schema() -> None:
    client = FakeOllama({"qwen2.5:3b"}, reply='{"npcs": []}')
    with pytest.raises(InvalidOutput):
        await _service(client).json("game.npcs", [{"role": "user", "content": "PNJ pour une PME"}])


async def test_think_is_not_sent_to_models_without_thinking() -> None:
    client = FakeOllama({"qwen2.5:1.5b"}, reply="pong")
    result = await _service(client).text("system.ping", [{"role": "user", "content": "ping"}])
    assert result.content == "pong"
    assert client.calls[0]["think"] is None
    assert client.calls[0]["options"]["num_predict"] == 8
    assert client.calls[0]["options"]["num_ctx"] == load_catalog().models["nano"].num_ctx


async def test_decision_emulation_reuses_the_model_context() -> None:
    """Même num_ctx que les autres tâches du modèle : pas de rechargement entre deux appels."""
    client = FakeOllama({"qwen2.5:1.5b"}, reply='{"intent": "social", "injection": false}')
    await _service(client).decide("player.intent", "Bonjour !", load_questions("player.intent"))
    assert client.calls[0]["options"]["num_ctx"] == load_catalog().models["nano"].num_ctx
