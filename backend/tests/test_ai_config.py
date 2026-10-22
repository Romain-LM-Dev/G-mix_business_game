"""Cohérence des fichiers de configuration IA (ai/) : catalogue, schémas, prompts, domaines."""

import json
import re

import pytest
from jsonschema import Draft202012Validator

from gmix.assets_catalog import load_assets_catalog
from gmix.db.models import EMBED_DIM
from gmix.domains import load_domains
from gmix.game.world import load_world_templates, template_zones
from gmix.llm import schemas
from gmix.llm.catalog import load_catalog
from gmix.llm.prompts import load_prompt, load_questions
from gmix.llm.tokens import estimate_tokens

from .conftest import AI_DIR

PROMPT_FILES = sorted(p for p in (AI_DIR / "prompts").glob("*.md") if p.name != "README.md")


def test_catalog_is_consistent() -> None:
    assert load_catalog().tasks  # le validateur pydantic lève si le catalogue est incohérent


def test_embedding_dims_match_database_column() -> None:
    assert load_catalog().embedding_model().dims == EMBED_DIM


def test_every_schema_file_is_valid() -> None:
    for path in (AI_DIR / "schemas").glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_json_tasks_point_to_existing_schemas() -> None:
    for task in load_catalog().tasks.values():
        if task.output == "json":
            Draft202012Validator.check_schema(schemas.resolve(task.schema_ref))


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.stem)
def test_prompt_renders_and_matches_a_task(path) -> None:
    prompt = load_prompt(path.stem)
    assert prompt.task == path.stem
    load_catalog().task(prompt.task)
    messages = prompt.render(**{name: f"<{name}>" for name in prompt.variables})
    assert messages[-1]["role"] == "user"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.stem)
def test_system_prompt_stays_short(path) -> None:
    """Règle d'économie : le prompt système (hors variables) est repayé à chaque appel."""
    assert estimate_tokens(load_prompt(path.stem).system) < 300


def test_missing_prompt_variable_is_an_error() -> None:
    with pytest.raises(KeyError):
        load_prompt("npc.dialogue").render(npc_name="Claire")


def test_decision_questions_belong_to_decision_tasks() -> None:
    for path in (AI_DIR / "prompts").glob("*.questions.yaml"):
        task_name = path.name.removesuffix(".questions.yaml")
        assert load_catalog().task(task_name).output == "decision"
        for question in load_questions(task_name).values():
            assert question["type"] in {"choice", "noul", "score"}


def test_domains_are_valid_and_cover_the_example(example_spec) -> None:
    slugs = {d.slug for d in load_domains()}
    assert len(slugs) >= 10
    assert example_spec["meta"]["domain"] in slugs


def test_world_templates_use_catalog_assets(example_spec) -> None:
    catalog = load_assets_catalog().by_id()
    categories = {a.category for a in catalog.values()}
    for template in load_world_templates().values():
        zones = template["zones"]
        assert len(zones) <= 8 and len({z["id"] for z in zones}) == len(zones)
        for zone in zones:
            assert re.fullmatch(r"^[a-z][a-z0-9_]*$", zone["id"])
            assert set(zone["categories"]) <= categories
            assert zone["defaults"] and set(zone["defaults"]) <= catalog.keys(), zone["id"]
            assert catalog[zone["defaults"][0]].category == "building"  # le bâtiment principal ouvre la liste
    world = example_spec["world"]
    assert {z["id"] for z in world["zones"]} <= template_zones(world["template"]).keys()
    assert {a for z in world["zones"] for a in z["asset_ids"]} <= catalog.keys()
