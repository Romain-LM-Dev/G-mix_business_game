"""Jeu d'évaluation de la conception par l'IA (ai/evals/game.design.jsonl, annexe 0008 §8) : 24 cas bien formés,
cohérents avec les packs, et qui couvrent ce que l'annexe demande. Les cas ne sont jamais retouchés après mesure."""

import json
from collections import Counter

import pytest

from gmix.game.spec import Audience, DesignRequest, load_pack

from .conftest import AI_DIR

CASES = [json.loads(line) for line in (AI_DIR / "evals" / "game.design.jsonl").read_text("utf-8").splitlines() if line]
EXPECT_KEYS = {"modules_include", "modules_exclude", "notions_any", "difficulty_in", "weeks", "unmet_nonempty"}
AUDIENCES = set(Audience.__args__)  # type: ignore[attr-defined]
DIFFICULTIES = {"decouverte", "equilibre", "expert"}


def test_the_set_has_24_cases_in_two_series_and_two_packs() -> None:
    assert len({c["id"] for c in CASES}) == len(CASES) == 24
    assert Counter(c["series"] for c in CASES) == {"R": 12, "C": 12}
    assert Counter(c["pack"] for c in CASES) == {"atelier": 16, "usine": 8}
    assert all(c["id"].startswith(c["series"]) for c in CASES)
    assert len({c["brief"] for c in CASES}) == 24


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_well_formed_and_matches_its_pack(case: dict) -> None:
    assert set(case) == {"id", "series", "pack", "audience", "brief", "fixed", "expect"}
    DesignRequest(pack=case["pack"], brief=case["brief"], audience=case["audience"], fixed=case["fixed"])
    pack = load_pack(case["pack"])
    expect = case["expect"]
    assert set(expect) == EXPECT_KEYS
    assert set(expect["modules_include"]) | set(expect["modules_exclude"]) <= pack["modules"].keys()
    assert not set(expect["modules_include"]) & set(expect["modules_exclude"])
    assert set(expect["notions_any"]) <= pack["notions"].keys()
    assert expect["difficulty_in"] and set(expect["difficulty_in"]) <= DIFFICULTIES
    low, high = expect["weeks"]
    pack_low, pack_high, _ = pack.get("limits", {}).get("weeks", (4, 12, 8))
    assert pack_low <= low <= high <= pack_high
    assert isinstance(expect["unmet_nonempty"], bool)
    if "weeks" in case["fixed"]:  # une contrainte du formateur ne se négocie pas
        assert expect["weeks"] == [case["fixed"]["weeks"]] * 2
    if "difficulty" in case["fixed"]:
        assert expect["difficulty_in"] == [case["fixed"]["difficulty"]]


def test_the_set_covers_what_the_annex_asks_for() -> None:
    control = [c for c in CASES if c["series"] == "C"]
    for pack_id in ("atelier", "usine"):  # chaque module est mesuré sur la série de contrôle
        wanted = {m for c in control if c["pack"] == pack_id for m in c["expect"]["modules_include"]}
        assert wanted == load_pack(pack_id)["modules"].keys()
    assert Counter(c["audience"] for c in CASES).keys() == AUDIENCES
    assert all(n >= 2 for n in Counter(c["audience"] for c in CASES).values())
    lengths = {len(c["brief"]) for c in control}
    assert {25, 2000} <= lengths  # brief le plus court (annexe : 25 caractères) et le plus long permis
    briefs = {c["id"]: c["brief"].lower() for c in control}
    assert any("douze semaines" in b and "trois lignes" in b for b in briefs.values())
    assert any(any(ch.isdigit() for ch in b) for b in briefs.values())  # un brief avec des chiffres
    assert any(
        "marketing digital" in b and c["expect"]["unmet_nonempty"]
        for c, b in zip(control, briefs.values(), strict=True)
    )
    assert any("ignore tes règles" in b and "poème" in b for b in briefs.values())
    assert any(c["expect"]["unmet_nonempty"] for c in CASES if c["series"] == "R")
