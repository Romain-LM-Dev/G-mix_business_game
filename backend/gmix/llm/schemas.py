"""Schémas JSON des sorties IA (ai/schemas) : sous-schéma autonome pour Ollama + validation stricte."""

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from gmix.settings import get_settings


@lru_cache
def load_schema_file(name: str) -> dict[str, Any]:
    path = get_settings().gmix_ai_dir / "schemas" / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(ref: str) -> dict[str, Any]:
    """'business_game#/$defs/outline' -> schéma autonome (sous-schéma + $defs) utilisable par Ollama."""
    name, _, pointer = ref.partition("#")
    root = load_schema_file(name)
    if not pointer:
        return root
    node: Any = root
    for part in pointer.strip("/").split("/"):
        node = node[part]
    return {"$defs": root.get("$defs", {}), **node}


def validation_errors(schema: dict[str, Any], data: Any) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '<racine>'} : {e.message}"
        for e in sorted(validator.iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))
    ]
