"""Routage, budgets, repli et validation du service IA, avec un faux client Ollama (aucun appel réseau)."""

from typing import Any

import pytest

from gmix.llm.catalog import load_catalog
from gmix.llm.ollama import ChatResult, OllamaError, Usage
from gmix.llm.prompts import REPAIR_MAX_TOKENS, load_prompt, load_questions
from gmix.llm.service import BudgetExceeded, LLMService, ModelUnavailable
from gmix.llm.tokens import estimate_tokens

DESIGN_TASKS = ["game.design.concept", "game.design.cast", "game.design.journey"]
DESIGN_VARIABLES = {  # annexe 0008 §4.3 : les variables que fournissent design.*_variables
    "game.design.concept": "domain_name pack_label pack_description audience_label brief fixed limits themes modules "
    "extra_agents difficulties tunables events events_levels notions indicators network",
    "game.design.cast": "company pitch audience_label agents personalities objectives",
    "game.design.journey": "company audience_label objectives notions modules_actions panels tools anchors",
}
SCHEMA = {"type": "object", "properties": {"titre": {"type": "string"}}, "required": ["titre"]}
MESSAGES = [{"role": "user", "content": "Conçois un jeu."}]


class FakeOllama:
    def __init__(self, installed: set[str], reply: str = "{}", done_reason: str | None = None) -> None:
        self._installed = installed
        self.reply = reply
        self.done_reason = done_reason
        self.calls: list[dict[str, Any]] = []

    async def installed_models(self) -> set[str]:
        return set(self._installed)

    async def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        self.calls.append({"model": model, "messages": messages, **kwargs})
        return ChatResult(content=self.reply, usage=Usage(model=model), done_reason=self.done_reason)

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


# --- conception par l'IA : sorties JSON contraintes (ADR 0008) ----------------------------------------------


class FakeCache:
    """Cache exact en mémoire (même interface que LLMCacheStore)."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self.rows.get(key)

    async def put(self, key: str, task: str, usage: Usage, response: dict[str, Any]) -> None:
        self.rows[key] = response


def _cached_service(client: FakeOllama) -> tuple[LLMService, FakeCache]:
    cache = FakeCache()
    return LLMService(load_catalog(), client, cache), cache  # type: ignore[arg-type]


def test_design_tasks_share_one_json_model() -> None:
    catalog = load_catalog()
    tasks = [catalog.task(name) for name in DESIGN_TASKS]
    assert {t.model for t in tasks} == {tasks[0].model} and {t.fallback for t in tasks} == {tasks[0].fallback}
    assert all(t.output == "json" and t.cache and t.rag is None for t in tasks)
    assert all(t.max_input_tokens and t.options["num_predict"] for t in tasks)


async def test_structured_sends_schema_seed_and_fixed_context() -> None:
    client = FakeOllama({"qwen2.5:3b"}, reply='{"titre": "Atelier"}')
    result = await _service(client).structured("game.design.concept", MESSAGES, SCHEMA, seed=7)
    assert result.data == {"titre": "Atelier"} and result.error is None and not result.cached
    call = client.calls[0]
    catalog = load_catalog()
    task = catalog.task("game.design.concept")
    assert call["fmt"] == SCHEMA
    assert call["options"] == {**task.options, "num_ctx": catalog.models[task.model].num_ctx, "seed": 7}


async def test_structured_cache_key_includes_schema_and_seed() -> None:
    client = FakeOllama({"qwen2.5:3b"}, reply='{"titre": "Atelier"}')
    service, cache = _cached_service(client)
    first = await service.structured("game.design.concept", MESSAGES, SCHEMA, seed=1)
    again = await service.structured("game.design.concept", MESSAGES, SCHEMA, seed=1)
    assert len(client.calls) == 1 and again.cached and again.data == first.data and again.raw == first.raw
    await service.structured("game.design.concept", MESSAGES, SCHEMA, seed=2)
    await service.structured("game.design.concept", MESSAGES, {**SCHEMA, "additionalProperties": False}, seed=1)
    assert len(client.calls) == 3 and len(cache.rows) == 3


@pytest.mark.parametrize(
    ("reply", "done_reason", "error"),
    [
        ('{"titre": "Atel', "length", "tronque"),
        ("pas du json", None, "json_invalide"),
        ("[1, 2]", None, "json_invalide"),
    ],
)
async def test_structured_reports_truncated_and_invalid_output_without_caching_it(
    reply: str, done_reason: str | None, error: str
) -> None:
    client = FakeOllama({"qwen2.5:3b"}, reply=reply, done_reason=done_reason)
    service, cache = _cached_service(client)
    result = await service.structured("game.design.cast", MESSAGES, SCHEMA, seed=3)
    assert (result.data, result.raw, result.error) == (None, reply, error)
    assert cache.rows == {}


async def test_structured_refuses_a_task_that_is_not_json_and_checks_the_budget() -> None:
    client = FakeOllama({"qwen2.5:1.5b", "qwen2.5:3b"})
    with pytest.raises(ValueError, match="output: json"):
        await _service(client).structured("npc.bark", MESSAGES, SCHEMA, seed=1)
    with pytest.raises(BudgetExceeded):
        await _service(client).structured(
            "game.design.cast", [{"role": "user", "content": "mot " * 3000}], SCHEMA, seed=1
        )
    assert client.calls == []


async def test_structured_falls_back_to_the_task_fallback_model() -> None:
    catalog = load_catalog()
    fallback = catalog.models[catalog.task("game.design.journey").fallback].name
    client = FakeOllama({fallback}, reply='{"titre": "x"}')
    await _service(client).structured("game.design.journey", MESSAGES, SCHEMA, seed=1)
    assert client.calls[0]["model"] == fallback


@pytest.mark.parametrize("task", DESIGN_TASKS)
def test_design_prompts_follow_the_contract(task: str) -> None:
    prompt = load_prompt(task)
    assert set(prompt.variables) == set(DESIGN_VARIABLES[task].split())
    assert estimate_tokens(prompt.system) < 250  # règle d'économie : repayé à chaque appel
    messages = prompt.render(**{name: f"<{name}>" for name in prompt.variables})
    assert "$" not in messages[0]["content"] + messages[-1]["content"]
    repair = prompt.render_repair(messages, "- un chiffre dans le titre")
    assert [m["role"] for m in repair] == ["system", "user", "user"]  # sans la sortie brute
    assert "- un chiffre dans le titre" in repair[2]["content"]
    errors = "\n".join(f"- erreur {i} : texte du champ fautif" for i in range(500))
    long = prompt.render_repair(messages, errors)
    assert estimate_tokens(long[2]["content"]) <= REPAIR_MAX_TOKENS and "omises" in long[2]["content"]


def test_concept_budget_leaves_room_for_the_answer_in_the_model_context() -> None:
    catalog = load_catalog()
    task = catalog.task("game.design.concept")
    assert task.max_input_tokens == 4500
    for alias in (task.model, task.fallback):
        assert task.max_input_tokens + task.options["num_predict"] <= catalog.models[alias].num_ctx
    assert "$network" in load_prompt("game.design.concept").user


async def test_an_ollama_error_is_not_swallowed_by_structured() -> None:
    # annexe 0008 §5 : la tentative ratée est comptée par le worker (pipeline-kafka), pas par le service
    class Boom(FakeOllama):
        async def chat(self, *args: Any, **kwargs: Any) -> ChatResult:
            raise OllamaError("/api/chat -> HTTP 500: token repeat limit")

    with pytest.raises(OllamaError):
        await _service(Boom({"qwen2.5:3b"})).structured("game.design.concept", MESSAGES, SCHEMA, seed=1)


def test_a_prompt_without_repair_section_cannot_be_repaired() -> None:
    with pytest.raises(KeyError):
        load_prompt("npc.dialogue").render_repair(MESSAGES, "erreur")
