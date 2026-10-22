"""Gabarits de carte (ai/world_templates.yaml) : zones typées où la génération pose des assets du catalogue."""

from functools import lru_cache
from typing import Any

import yaml

from gmix.settings import get_settings

DEFAULT_TEMPLATE = "parc_activites"


@lru_cache
def load_world_templates() -> dict[str, dict[str, Any]]:
    path = get_settings().gmix_ai_dir / "world_templates.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["templates"]


def template_zones(template_id: str = DEFAULT_TEMPLATE) -> dict[str, dict[str, Any]]:
    return {zone["id"]: zone for zone in load_world_templates()[template_id]["zones"]}
