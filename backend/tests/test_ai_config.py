"""Cohérence des fichiers de configuration IA (ai/) : catalogue, prompts, domaines, contenu des simulations."""

import pytest

from gmix.assets_catalog import load_assets_catalog
from gmix.db.models import EMBED_DIM
from gmix.domains import load_domains
from gmix.game import engine
from gmix.game.generation import ZONE_ROUTES
from gmix.game.spec import load_sim_catalog
from gmix.llm.catalog import load_catalog
from gmix.llm.prompts import load_prompt, load_questions
from gmix.llm.tokens import estimate_tokens

from .conftest import AI_DIR

PROMPT_FILES = sorted(p for p in (AI_DIR / "prompts").glob("*.md") if p.name != "README.md")


def test_catalog_is_consistent() -> None:
    assert load_catalog().tasks  # le validateur pydantic lève si le catalogue est incohérent


def test_embedding_dims_match_database_column() -> None:
    assert load_catalog().embedding_model().dims == EMBED_DIM


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


def test_domains_are_valid() -> None:
    slugs = {d.slug for d in load_domains()}
    assert len(slugs) >= 10 and "supply-chain" in slugs


def test_simulation_catalog_matches_the_engine_and_the_assets() -> None:
    """ai/simulation.yaml se modifie à la main : chaque action, option, agent et aléa doit exister côté moteur."""
    catalog = load_sim_catalog()
    assets = load_assets_catalog().by_id()
    options = {
        ("maintenance", "level"): set(catalog["economy"]["maintenance_rate"]),
        ("qualite", "rate"): set(engine.CONTROL_RATES),
        ("commercial", "price"): set(engine.PRICE_LEVELS),
        ("transport", "mode"): set(catalog["economy"]["transport"]),
        ("finance", "limit"): set(engine.OVERDRAFTS),
    }
    for module_id, module in catalog["modules"].items():
        for action in module["actions"]:
            assert (module_id, action["id"]) in engine._HANDLERS
            for field in action["fields"]:
                if field.get("options"):
                    assert {o["id"] for o in field["options"]} == options[(module_id, field["id"])]
    agents = [m["agent"] | {"notions": m["notions"]} for m in catalog["modules"].values()]
    for agent in agents + list(catalog["extra_agents"].values()):
        assert assets[agent["character"]].category == "character"
        assert agent["zone"] in ZONE_ROUTES or agent["zone"] in {"lignes_avant", "lignes_arriere"}
        assert set(agent["notions"]) <= catalog["notions"].keys()
    assert all(n["citation"] for n in catalog["notions"].values())
    for tone in catalog["agent_tones"].values():
        assert set(tone["personalities"]) <= catalog["personalities"].keys()
    for event in catalog["events"].values():
        assert set(event["modules"]) <= catalog["modules"].keys()
        assert set(event["effects"]) <= {"delay_risk", "demand", "cost", "breakdown", "on_time", "defects"}
    for theme in catalog["themes"].values():
        assert len(theme["products"]) >= 4  # GameParams.products va jusqu'à 4
        assert all(len(p["component"]["suppliers"]) == len(catalog["supplier_profiles"]) for p in theme["products"])
