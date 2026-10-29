"""Génération par paramètres : tout secteur, toute combinaison de modules donne un jeu valide, jouable et dont
les agents circulent dans les allées libres de l'atelier."""

import itertools
import math

import pytest
from pydantic import ValidationError

from gmix.assets_catalog import load_assets_catalog
from gmix.game.generation import autopilot_check, generate
from gmix.game.spec import GameParams, SimSpec, load_sim_catalog

from .conftest import ALL_MODULES

THEMES = list(load_sim_catalog()["themes"])
CLEARANCE = 0.35  # demi-largeur d'un personnage


@pytest.mark.parametrize(
    ("theme", "difficulty"), list(itertools.product(THEMES, ["decouverte", "equilibre", "expert"]))
)
def test_every_theme_and_difficulty_gives_a_coherent_game(theme: str, difficulty: str) -> None:
    spec = generate(GameParams(theme=theme, modules=ALL_MODULES, difficulty=difficulty, products=4, seed=3))
    SimSpec.model_validate(spec)
    assert len(spec["products"]) == len(spec["lines"]) == len(spec["components"]) == 4
    for component in spec["components"]:
        profiles = [o["profile"] for o in spec["offers"] if o["component_id"] == component["id"]]
        assert profiles == ["rapide", "standard", "economique"]  # un vrai arbitrage coût / délai / fiabilité
    for line, product in zip(spec["lines"], spec["products"], strict=True):
        assert line["capacity"] * 0.85 >= product["demand"]  # la capacité nominale sert la demande à 85 % de TRS
    assert {m["role_id"] for m in spec["modules"]} == {r["id"] for r in spec["roles"]}
    assert {a["module_id"] for a in spec["agents"] if a["module_id"]} == set(ALL_MODULES)
    kinds = {s["kind"] for s in spec["stations"]}
    assert all(set(m["stations"]) <= kinds for m in spec["modules"])
    assert spec["targets"]["cash_final"] >= spec["economy"]["initial_cash"]


@pytest.mark.parametrize("modules", [[m] for m in ALL_MODULES] + [["approvisionnement", "production"]])
def test_any_module_selection_is_playable(modules: list[str]) -> None:
    spec = generate(GameParams(theme="agroalimentaire", modules=modules, products=2, seed=11))
    assert [m["id"] for m in spec["modules"]] == modules
    assert {a["module_id"] for a in spec["agents"]} == set(modules)
    assert autopilot_check(spec)["weeks"] == spec["meta"]["weeks"]


def test_same_seed_same_game_and_company_name_kept() -> None:
    params = GameParams(theme="sante", modules=["approvisionnement"], seed=99, company_name="Labo Test")
    assert generate(params) == generate(params)
    assert generate(params)["meta"]["company"] == "Labo Test"
    other = generate(params.model_copy(update={"seed": 100}))
    assert other["seed"] != 99


def test_reference_autopilot_wins_on_discovery_and_struggles_on_expert() -> None:
    easy = autopilot_check(
        generate(GameParams(theme="industrie", modules=ALL_MODULES, difficulty="decouverte", seed=5))
    )
    hard = autopilot_check(generate(GameParams(theme="industrie", modules=ALL_MODULES, difficulty="expert", seed=5)))
    assert easy["otif_mean"] >= 95 and easy["stockout_weeks"] == 0
    assert hard["otif_mean"] < easy["otif_mean"]


def test_invalid_parameters_are_refused() -> None:
    with pytest.raises(ValidationError):
        GameParams(theme="spatial", modules=["production"])
    with pytest.raises(ValidationError):
        GameParams(theme="industrie", modules=["production", "production"])
    with pytest.raises(ValidationError):
        GameParams(theme="industrie", modules=["production"], players_min=8, players_max=4)


def test_world_uses_catalog_assets_and_agents_walk_in_free_aisles(sim_spec) -> None:
    catalog = load_assets_catalog().by_id()
    obstacles = []
    for item in sim_spec["world"]["objects"]:
        assert item["asset"] in catalog, item["asset"]
        footprint = catalog[item["asset"]].footprint
        w, d = (footprint.d, footprint.w) if abs(item["rotation"]) == 90 else (footprint.w, footprint.d)
        x, z = item["position"]
        obstacles.append((x - w / 2 - CLEARANCE, x + w / 2 + CLEARANCE, z - d / 2 - CLEARANCE, z + d / 2 + CLEARANCE))
    for agent in sim_spec["agents"]:
        assert catalog[agent["character"]].category == "character"
        points = agent["route"]
        for start, end in zip(points, points[1:] + points[:1], strict=True):
            for step in range(21):  # trajet échantillonné tous les 5 %
                x = start[0] + (end[0] - start[0]) * step / 20
                z = start[1] + (end[1] - start[1]) * step / 20
                assert -15.6 < x < 15.6 and -11.6 < z < 11.6, (agent["id"], x, z)
                hit = [o for o in obstacles if o[0] < x < o[1] and o[2] < z < o[3]]
                assert not hit, (agent["id"], (x, z), hit)
    for station in sim_spec["stations"]:
        x, z = station["position"]
        assert not [
            o for o in obstacles if o[0] + CLEARANCE < x < o[1] - CLEARANCE and o[2] + CLEARANCE < z < o[3] - CLEARANCE
        ]
        assert math.hypot(x, z) < 20


def test_notions_are_sourced(sim_spec) -> None:
    assert sim_spec["notions"] and all(n["citation"] for n in sim_spec["notions"])
    wiki = [n for n in sim_spec["notions"] if "wikipedia.org" in n["citation"]]
    assert len(wiki) >= len(sim_spec["notions"]) - 1  # une seule notion cite une norme hors corpus (TRS)
