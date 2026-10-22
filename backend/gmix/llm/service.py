"""Service IA : exécute une tâche du catalogue avec le bon modèle, les bonnes options et un budget de tokens.

Leviers d'économie de tokens appliqués ici :
- routage par tâche vers le plus petit modèle suffisant (ai/models.yaml), repli si absent ;
- budget d'entrée vérifié AVANT l'appel (Ollama tronquerait le prompt système sans prévenir) ;
- sorties JSON par décodage contraint (schéma) : pas de prose, pas de re-génération pour un JSON cassé ;
- questions fermées envoyées à un modèle de décision (tev1) plutôt qu'à un LLM génératif ;
- cache exact des tâches déterministes (`cache: true`) ;
- `think` désactivé par défaut sur les modèles qui raisonnent.
"""

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from gmix.db import get_sessionmaker
from gmix.db.models import LLMCache
from gmix.llm import schemas
from gmix.llm.catalog import AICatalog, ModelSpec, TaskProfile, load_catalog
from gmix.llm.ollama import ChatResult, OllamaClient, Usage
from gmix.llm.tokens import estimate_messages
from gmix.settings import get_settings

log = logging.getLogger("gmix.llm")


class ModelUnavailable(RuntimeError):
    pass


class BudgetExceeded(ValueError):
    pass


class InvalidOutput(ValueError):
    def __init__(self, task: str, errors: list[str], raw: str) -> None:
        super().__init__(f"Tâche {task} : sortie invalide ({len(errors)} erreur(s)) : {errors[:3]}")
        self.errors = errors
        self.raw = raw


class LLMCacheStore:
    """Cache exact en base (table llm_cache)."""

    async def get(self, key: str) -> dict[str, Any] | None:
        async with get_sessionmaker()() as session:
            row = await session.get(LLMCache, key)
            if row is None:
                return None
            row.hits += 1
            await session.commit()
            return row.response

    async def put(self, key: str, task: str, usage: Usage, response: dict[str, Any]) -> None:
        async with get_sessionmaker()() as session:
            await session.execute(
                insert(LLMCache)
                .values(
                    key=key,
                    task=task,
                    model=usage.model,
                    response=response,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )
                .on_conflict_do_nothing()
            )
            await session.commit()


class LLMService:
    def __init__(self, catalog: AICatalog, client: OllamaClient, cache: LLMCacheStore | None = None) -> None:
        self.catalog = catalog
        self.client = client
        self.cache = cache
        self._installed: set[str] | None = None

    @classmethod
    def from_settings(cls, *, with_cache: bool = True) -> "LLMService":
        settings = get_settings()
        client = OllamaClient(settings.ollama_base_url, api_key=settings.ollama_api_key)
        return cls(load_catalog(), client, LLMCacheStore() if with_cache else None)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def installed(self, *, refresh: bool = False) -> set[str]:
        if self._installed is None or refresh:
            self._installed = await self.client.installed_models()
        return self._installed

    async def resolve(self, task_name: str) -> tuple[TaskProfile, ModelSpec]:
        """Modèle principal s'il est installé, sinon le repli ; ModelUnavailable sinon."""
        task = self.catalog.task(task_name)
        installed = await self.installed()
        for alias in filter(None, (task.model, task.fallback)):
            spec = self.catalog.models[alias]
            if spec.tag in installed:
                if alias != task.model:
                    log.warning("tâche=%s : %s absent, repli sur %s", task_name, task.model, spec.name)
                return task, spec
        raise ModelUnavailable(
            f"Tâche {task_name} : aucun modèle installé ({task.model} / {task.fallback}). Voir scripts\\models.ps1"
        )

    # --- génération ------------------------------------------------------------------------------

    async def text(self, task_name: str, messages: list[dict[str, str]]) -> ChatResult:
        task, model = await self.resolve(task_name)
        self._check_budget(task_name, task, model, messages)
        key = self._cache_key(task_name, task, model, messages)
        if key and (hit := await self.cache.get(key)) is not None:  # type: ignore[union-attr]
            log.info("tâche=%s cache=hit", task_name)
            return ChatResult(content=hit["content"], usage=Usage(model=model.name), cached=True)
        result = await self.client.chat(
            model.name,
            messages,
            options=self._options(task, model),
            think=self._think(task, model),
            keep_alive=self.catalog.keep_alive,
        )
        self._log(task_name, result)
        if key:
            await self.cache.put(key, task_name, result.usage, {"content": result.content})  # type: ignore[union-attr]
        return result

    async def json(
        self, task_name: str, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], ChatResult]:
        """Sortie JSON contrainte par schéma puis validée. `schema` permet de restreindre dynamiquement
        (ex. enum des ids d'assets candidats) le schéma déclaré dans le catalogue."""
        task, model = await self.resolve(task_name)
        if task.output != "json" or not task.schema_ref:
            raise ValueError(f"Tâche {task_name} : output n'est pas json")
        self._check_budget(task_name, task, model, messages)
        fmt = schema or schemas.resolve(task.schema_ref)
        key = self._cache_key(task_name, task, model, messages, extra=fmt)
        if key and (hit := await self.cache.get(key)) is not None:  # type: ignore[union-attr]
            log.info("tâche=%s cache=hit", task_name)
            return hit, ChatResult(content=json.dumps(hit), usage=Usage(model=model.name), cached=True)
        result = await self.client.chat(
            model.name,
            messages,
            options=self._options(task, model),
            fmt=fmt,
            think=self._think(task, model),
            keep_alive=self.catalog.keep_alive,
        )
        self._log(task_name, result)
        try:
            data = json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise InvalidOutput(task_name, [f"JSON illisible : {exc}"], result.content) from exc
        if errors := schemas.validation_errors(fmt, data):
            raise InvalidOutput(task_name, errors, result.content)
        if key:
            await self.cache.put(key, task_name, result.usage, data)  # type: ignore[union-attr]
        return data, result

    async def stream(self, task_name: str, messages: list[dict[str, str]]) -> AsyncIterator[str | Usage]:
        task, model = await self.resolve(task_name)
        self._check_budget(task_name, task, model, messages)
        async for item in self.client.chat_stream(
            model.name,
            messages,
            options=self._options(task, model),
            think=self._think(task, model),
            keep_alive=self.catalog.keep_alive,
        ):
            if isinstance(item, Usage):
                self._log_usage(task_name, item)
            yield item

    # --- décisions (questions fermées) ---------------------------------------------------------------

    async def decide(
        self, task_name: str, state: str | dict[str, Any] | list[Any], questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Questions fermées (choice / noul / score) au format Jev / SystemOne.

        Modèle de décision si installé (tev1 : rapide, quelques centaines de ms, pas de texte généré),
        sinon émulation par un modèle de chat contraint par schéma (réponse au même format, `emulated`).
        """
        task, model = await self.resolve(task_name)
        if model.kind == "decision":
            data = await self.client.decide(model.name, state, questions, keep_alive=self.catalog.keep_alive)
            usage = data.get("usage") or {}
            log.info(
                "tâche=%s modèle=%s questions=%d tokens_entrée=%s tokens_sortie=%s",
                task_name,
                model.name,
                len(questions),
                usage.get("input_tokens", "?"),
                usage.get("output_tokens", 0),
            )
            return data
        return await self.decide_with_chat(task_name, model, state, questions)

    async def decide_with_chat(
        self, task_name: str, model: ModelSpec, state: Any, questions: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        lines = []
        for name, q in questions.items():
            criteria = q.get("criteria")
            if q["type"] == "choice":
                properties[name] = {"enum": list(criteria)}
                detail = "; ".join(f"{k} = {v or k}" for k, v in criteria.items())
            elif q["type"] == "noul":
                properties[name] = {"type": "boolean"}
                detail = "vrai / faux"
            else:
                properties[name] = {"type": "integer", "minimum": 0, "maximum": len(criteria) - 1}
                detail = "; ".join(f"{i} = {c}" for i, c in enumerate(criteria))
            lines.append(f"- {name} : {q['instructions']} ({detail})")
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(questions),
            "additionalProperties": False,
        }
        state_text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": "Tu réponds à des questions fermées sur un texte. Réponds uniquement en JSON.",
            },
            {"role": "user", "content": f"Texte :\n{state_text}\n\nQuestions :\n" + "\n".join(lines)},
        ]
        result = await self.client.chat(
            model.name,
            messages,
            options={"temperature": 0, "num_ctx": model.num_ctx, "num_predict": 32 + 16 * len(questions)},
            fmt=schema,
            keep_alive=self.catalog.keep_alive,
        )
        self._log(task_name, result)
        raw = json.loads(result.content)
        answers: dict[str, Any] = {}
        for name, q in questions.items():
            value = raw.get(name)
            if q["type"] == "choice":
                answers[name] = {"choice": value}
            elif q["type"] == "noul":
                answers[name] = {"noul": 1.0 if value else 0.0}
            else:
                answers[name] = {"score": value}
        return {"answers": answers, "emulated": True, "model": model.name}

    # --- embeddings ----------------------------------------------------------------------------------

    async def embed_documents(
        self, texts: list[str], *, title: str = "none", titles: list[str] | None = None
    ) -> list[list[float]]:
        """`title` commun (passages d'un même document) ou `titles` un par texte (ex. nom de chaque asset)."""
        _, model = await self.resolve("rag.embed")
        per_text = titles if titles is not None else [title] * len(texts)
        inputs = [
            model.document_prefix.replace("{title}", t or "none") + text
            for t, text in zip(per_text, texts, strict=True)
        ]
        vectors, usage = await self.client.embed(model.name, inputs, keep_alive=self.catalog.keep_alive)
        self._log_usage("rag.embed", usage)
        self._check_dims(model, vectors)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        _, model = await self.resolve("rag.embed")
        vectors, usage = await self.client.embed(
            model.name, [model.query_prefix + text], keep_alive=self.catalog.keep_alive
        )
        self._log_usage("rag.embed", usage)
        self._check_dims(model, vectors)
        return vectors[0]

    # --- utilitaires ---------------------------------------------------------------------------------

    @staticmethod
    def _think(task: TaskProfile, model: ModelSpec) -> bool | None:
        return task.think if model.thinking else None

    @staticmethod
    def _options(task: TaskProfile, model: ModelSpec) -> dict[str, Any]:
        """Options de la tâche + contexte FIXE du modèle : un num_ctx qui varie entre deux appels
        oblige Ollama à recharger le modèle (plusieurs secondes perdues à chaque fois)."""
        return {**task.options, "num_ctx": model.num_ctx}

    @staticmethod
    def _check_budget(task_name: str, task: TaskProfile, model: ModelSpec, messages: list[dict[str, str]]) -> int:
        estimated = estimate_messages(messages)
        limit = task.max_input_tokens or (model.num_ctx or 0) - task.options.get("num_predict", 512)
        if estimated > limit:
            raise BudgetExceeded(f"Tâche {task_name} : ~{estimated} tokens en entrée > budget {limit}")
        return estimated

    def _cache_key(
        self, task_name: str, task: TaskProfile, model: ModelSpec, messages: list[dict[str, str]], extra: Any = None
    ) -> str | None:
        if not (task.cache and self.cache):
            return None
        payload = json.dumps([task_name, model.name, messages, task.options, extra], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _check_dims(model: ModelSpec, vectors: list[list[float]]) -> None:
        if model.dims and vectors and len(vectors[0]) != model.dims:
            raise ValueError(f"{model.name} renvoie {len(vectors[0])} dimensions, catalogue = {model.dims}")

    def _log(self, task_name: str, result: ChatResult) -> None:
        self._log_usage(task_name, result.usage)
        if result.done_reason == "length":
            log.warning("tâche=%s : sortie tronquée par num_predict", task_name)

    @staticmethod
    def _log_usage(task_name: str, usage: Usage) -> None:
        log.info(
            "tâche=%s modèle=%s tokens_entrée=%d tokens_sortie=%d durée=%.0fms chargement=%.0fms",
            task_name,
            usage.model,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.duration_ms,
            usage.load_ms,
        )
