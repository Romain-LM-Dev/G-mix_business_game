import pytest

from gmix.game.coherence import check_spec, evaluate_formula
from gmix.llm import schemas


def test_example_matches_schema(example_spec) -> None:
    assert schemas.validation_errors(schemas.resolve("business_game"), example_spec) == []


def test_example_is_coherent(example_spec) -> None:
    assert check_spec(example_spec) == []


def test_example_outline_matches_stage_schema(example_spec) -> None:
    outline = {key: example_spec[key] for key in ("meta", "learning_objectives", "context", "roles", "kpis")}
    outline["phases"] = [
        {key: phase[key] for key in ("id", "title", "duration_minutes", "goal")} for phase in example_spec["phases"]
    ]
    assert schemas.validation_errors(schemas.resolve("business_game#/$defs/outline"), outline) == []


def test_coherence_detects_options_without_real_choice(example_spec) -> None:
    options = example_spec["phases"][0]["decisions"][0]["options"]
    options[1]["effects"] = list(options[0]["effects"])
    assert any("effets identiques" in issue for issue in check_spec(example_spec))


def test_coherence_detects_broken_references_and_formulas(example_spec) -> None:
    example_spec["phases"][0]["decisions"][0]["role"] = "inconnu"
    example_spec["kpis"][4]["initial"] = 80  # bfr_jours = dso + dio - dpo = 90
    example_spec["phases"][1]["decisions"][0]["options"][0]["effects"].append(
        {"kpi": "bfr_jours", "operation": "add", "value": -5}
    )
    issues = check_spec(example_spec)
    assert any("rôle inconnu" in issue for issue in issues)
    assert any("bfr_jours" in issue and "formule" in issue for issue in issues)
    assert any("KPI dérivé" in issue for issue in issues)


def test_formula_only_allows_arithmetic() -> None:
    assert evaluate_formula("(a + b) * 2 - c / 4", {"a": 1, "b": 2, "c": 8}) == 4
    for expression in ("__import__('os')", "a.real", "[a]", "a if a else 0"):
        with pytest.raises(ValueError):
            evaluate_formula(expression, {"a": 1})
