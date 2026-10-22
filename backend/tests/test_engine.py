"""Moteur de partie, déroulé sur l'exemple de référence (trésorerie sous tension)."""

import pytest

from gmix.game import engine
from gmix.game.engine import GameRuleError


def _play(spec):
    state = engine.start(spec, engine.initial_state(spec))
    return engine.decide(spec, state, "d_priorite", "o_clients", user_id="u1", game_role="daf")


def test_initial_state_and_derived_kpi(example_spec) -> None:
    state = engine.initial_state(example_spec)
    assert "bfr_jours" not in state["kpis"]  # KPI dérivé : jamais stocké, toujours calculé
    assert engine.kpi_values(example_spec, state)["bfr_jours"] == 90


def test_immediate_and_delayed_effects(example_spec) -> None:
    state = _play(example_spec)
    assert state["kpis"]["frais_financiers"] == 70  # immédiat
    assert state["kpis"]["dso"] == 75  # différé d'une phase
    state = engine.advance(example_spec, state)
    assert state["phase_index"] == 1
    assert state["kpis"]["dso"] == 65
    assert state["kpis"]["tresorerie"] == 483


def test_rules_refuse_wrong_role_repeat_and_unknown_option(example_spec) -> None:
    state = _play(example_spec)
    with pytest.raises(GameRuleError):
        engine.decide(example_spec, state, "d_priorite", "o_stocks", user_id="u1", game_role="daf")
    state = engine.advance(example_spec, state)
    with pytest.raises(GameRuleError):
        engine.decide(example_spec, state, "d_fournisseurs", "o_dpo_60", user_id="u2", game_role="daf")
    with pytest.raises(GameRuleError):
        engine.decide(example_spec, state, "d_fournisseurs", "o_inconnue", user_id="u2", game_role="resp_achats")


def test_triggered_and_phase_events_then_debrief(example_spec) -> None:
    state = engine.advance(example_spec, _play(example_spec))
    state = engine.decide(example_spec, state, "d_fournisseurs", "o_dpo_90", user_id="u2", game_role="resp_achats")
    assert state["pending_events"] == ["e_dgccrf"]
    state = engine.advance(example_spec, state)  # phase 3 : retard client + contrôle DGCCRF
    assert state["events"] == ["e_retard_client", "e_dgccrf"]
    assert state["kpis"]["tresorerie"] == 483 + 750 - 350 - 300
    assert engine.kpi_values(example_spec, state)["bfr_jours"] == 75 + 60 - 90
    state = engine.advance(example_spec, state)
    assert state["status"] == "finished"
    report = engine.debrief(example_spec, state)
    tresorerie = next(k for k in report["kpis"] if k["id"] == "tresorerie")
    assert tresorerie["final"] == 583 and tresorerie["met"] is False
    crise = next(d for d in report["decisions"] if d["id"] == "d_crise")
    assert crise["chosen"] is None and all(o["rationale"] for o in crise["options"])


def test_player_view_hides_answers(example_spec) -> None:
    view = engine.player_spec(example_spec)
    options = [o for p in view["phases"] for d in p["decisions"] for o in d["options"]]
    assert options and all(set(o) == {"id", "label"} for o in options)
    assert "debrief" not in view and all(p["events"] == [] for p in view["phases"])
    assert "debrief" in example_spec  # la spec d'origine n'est pas modifiée
