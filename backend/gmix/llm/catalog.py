"""Catalogue des modèles et des profils de tâches IA (ai/models.yaml).

Le code ne référence jamais un modèle en dur : il demande une tâche (ex. "npc.dialogue") et le
catalogue fournit le modèle, les options Ollama, le budget de tokens, le RAG et le modèle de repli.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from gmix.settings import get_settings

ModelKind = Literal["chat", "embedding", "decision"]
OutputKind = Literal["text", "json", "decision", "embedding"]

_OUTPUTS_BY_KIND: dict[str, set[str]] = {
    "chat": {"text", "json"},
    "embedding": {"embedding"},
    "decision": {"decision"},
}


class ModelSpec(BaseModel):
    name: str  # tag Ollama
    kind: ModelKind
    vram_gb: float | None = None
    num_ctx: int | None = None  # chat : contexte FIXE par modèle (le faire varier force Ollama à recharger)
    thinking: bool = False  # le modèle accepte le paramètre `think` (sinon il n'est pas envoyé)
    dims: int | None = None  # embeddings
    query_prefix: str = ""  # embeddings : préfixe des requêtes
    document_prefix: str = ""  # embeddings : préfixe des documents ({title} remplacé)
    required: bool = True  # False : optionnel, la tâche bascule sur son repli s'il est absent
    notes: str = ""

    @property
    def tag(self) -> str:
        """Nom tel que listé par Ollama (`:latest` implicite)."""
        return self.name if ":" in self.name else f"{self.name}:latest"


class RagSpec(BaseModel):
    top_k: int = 4
    max_context_tokens: int = 1200
    hybrid: bool = True


class TaskProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    description: str
    model: str  # alias dans `models`
    fallback: str | None = None
    output: OutputKind = "text"
    schema_ref: str | None = Field(default=None, alias="schema")  # "fichier" ou "fichier#/$defs/x"
    think: bool = False
    stream: bool = False
    cache: bool = False
    options: dict[str, Any] = Field(default_factory=dict)  # options Ollama (num_ctx, num_predict, temperature…)
    max_input_tokens: int | None = None
    rag: RagSpec | None = None


class AICatalog(BaseModel):
    version: int
    keep_alive: str = "10m"
    models: dict[str, ModelSpec]
    tasks: dict[str, TaskProfile]

    @model_validator(mode="after")
    def _check_consistency(self) -> "AICatalog":
        errors: list[str] = []
        for alias, spec in self.models.items():
            if spec.kind == "chat" and not spec.num_ctx:
                errors.append(f"modèle {alias} : num_ctx obligatoire pour un modèle de chat")
        for name, t in self.tasks.items():
            primary = self.models.get(t.model)
            if primary is None:
                errors.append(f"{name} : modèle inconnu '{t.model}'")
                continue
            if t.output not in _OUTPUTS_BY_KIND[primary.kind]:
                errors.append(f"{name} : sortie '{t.output}' impossible avec un modèle {primary.kind}")
            if t.fallback is not None:
                fb = self.models.get(t.fallback)
                if fb is None:
                    errors.append(f"{name} : repli inconnu '{t.fallback}'")
                elif fb.kind != primary.kind and not (primary.kind == "decision" and fb.kind == "chat"):
                    errors.append(f"{name} : repli {fb.kind} impossible pour un modèle {primary.kind}")
            if t.output == "json" and not t.schema_ref:
                errors.append(f"{name} : sortie json sans `schema`")
            if t.cache and t.options.get("temperature") != 0:
                errors.append(f"{name} : `cache: true` exige `temperature: 0` (sortie déterministe)")
            if "num_ctx" in t.options:
                errors.append(f"{name} : num_ctx se règle sur le modèle, pas sur la tâche (sinon rechargements)")
            needed = (t.max_input_tokens or 0) + t.options.get("num_predict", 0)
            for alias in filter(None, (t.model, t.fallback)):
                spec = self.models.get(alias)
                if spec and spec.num_ctx and needed > spec.num_ctx:
                    errors.append(
                        f"{name} : max_input_tokens + num_predict > num_ctx de {alias} (troncature silencieuse)"
                    )
            if t.rag and t.max_input_tokens and t.rag.max_context_tokens >= t.max_input_tokens:
                errors.append(f"{name} : le contexte RAG doit laisser de la place au prompt")
        if "rag.embed" not in self.tasks:
            errors.append("tâche obligatoire manquante : rag.embed")
        if errors:
            raise ValueError("ai/models.yaml invalide :\n- " + "\n- ".join(errors))
        return self

    def task(self, name: str) -> TaskProfile:
        try:
            return self.tasks[name]
        except KeyError:
            raise KeyError(f"Tâche IA inconnue '{name}' (voir ai/models.yaml)") from None

    def embedding_model(self) -> ModelSpec:
        return self.models[self.task("rag.embed").model]

    def required_tags(self) -> list[str]:
        return sorted({m.tag for m in self.models.values() if m.required})


@lru_cache
def load_catalog(path: Path | None = None) -> AICatalog:
    file = path or get_settings().gmix_ai_dir / "models.yaml"
    return AICatalog.model_validate(yaml.safe_load(file.read_text(encoding="utf-8")))
