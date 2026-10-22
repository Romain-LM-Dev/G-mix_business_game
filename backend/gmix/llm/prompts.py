"""Gabarits de prompts versionnés : ai/prompts/<tâche>.md.

Format : front matter YAML (task, version, variables) puis sections « ## system » et « ## user ».
Variables en $nom / ${nom} (string.Template), compatible avec du JSON dans le texte ; « $$ » pour un « $ ».
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from string import Template
from typing import Any

import yaml

from gmix.settings import get_settings

_SECTION = re.compile(r"^##\s+(system|user)\s*$", re.MULTILINE | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    task: str
    version: int
    variables: tuple[str, ...]
    system: str
    user: str

    def render(self, **values: object) -> list[dict[str, str]]:
        missing = set(self.variables) - values.keys()
        if missing:
            raise KeyError(f"Prompt {self.task} v{self.version} : variables manquantes {sorted(missing)}")
        messages = []
        if self.system:
            messages.append({"role": "system", "content": Template(self.system).substitute(values)})
        messages.append({"role": "user", "content": Template(self.user).substitute(values)})
        return messages


@lru_cache
def load_prompt(name: str) -> PromptTemplate:
    raw = (get_settings().gmix_ai_dir / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front)
    parts = _SECTION.split(body)  # [préambule, 'system', texte, 'user', texte]
    sections = {parts[i].lower(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return PromptTemplate(
        task=meta["task"],
        version=int(meta["version"]),
        variables=tuple(meta.get("variables") or ()),
        system=sections.get("system", ""),
        user=sections["user"],
    )


@lru_cache
def _questions_file(name: str) -> dict[str, Any]:
    path = get_settings().gmix_ai_dir / "prompts" / f"{name}.questions.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_questions(name: str) -> dict[str, dict[str, Any]]:
    """Questions fermées d'une tâche de décision : ai/prompts/<tâche>.questions.yaml (format Jev / SystemOne)."""
    return _questions_file(name)["questions"]


def load_thresholds(name: str) -> dict[str, float]:
    """Seuils d'interprétation des probabilités du même fichier (jamais envoyés au modèle)."""
    return _questions_file(name).get("thresholds") or {}
