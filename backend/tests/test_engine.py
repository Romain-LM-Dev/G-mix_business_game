"""Moteur des business games simulés : règles des actions, simulation d'une semaine, aléas, agents, débrief."""

import pytest

from gmix.game import engine
from gmix.game.engine import GameRuleError
from gmix.game.generation import generate
from gmix.game.spec import GameParams


def _running(spec):
    return engine.start(spec, engine.initial_state(spec))


def _act(spec, state, module, action, values, *, role=None, occupied=(), manager=False):
    actor = {"user_id": "u1", "name": "Alice", "role": role}
    return engine.act(spec, state, module, action, values, actor=actor, manager=manager, occupied_roles=set(occupied))


def _offer(spec, component_id, profile):
    return next(o for o in spec["offers"] if o["component_id"] == component_id and o["profile"] == profile)


def test_order_is_delivered_after_its_lead_time(sim_spec) -> None:
    offer = _offer(sim_spec, "c1", "rapide")
    offer["reliability"] = 100
    state, summary = _act(
        sim_spec, _running(sim_spec), "approvisionnement", "commander", {"offer": offer["id"], "quantity": 500}
    )
    assert "arrivée prévue semaine 2" in summary and state["log"][-1]["name"] == "Alice"
    order = state["pending"][-1]
    state = engine.advance(sim_spec, state)
    assert order["id"] not in {d["order"] for d in state["last"]["deliveries"]}
    stock = state["components"]["c1"]
    state = engine.advance(sim_spec, state)
    assert order["id"] in {d["order"] for d in state["last"]["deliveries"]}
    assert state["components"]["c1"] >= stock + 500 - state["last"]["lines"]["l1"]["produced"]


def test_unreliable_supplier_is_late_and_agents_say_so(sim_spec) -> None:
    offer = _offer(sim_spec, "c2", "rapide")
    offer["reliability"] = 0
    state, _ = _act(
        sim_spec, _running(sim_spec), "approvisionnement", "commander", {"offer": offer["id"], "quantity": 500}
    )
    state = engine.advance(sim_spec, engine.advance(sim_spec, state))
    late = next(o for o in state["pending"] if o["offer_id"] == offer["id"])
    assert late["delays"] == 1 and late["arrival_week"] == 3
    briefings = engine.public_state(sim_spec, state)["briefings"]
    assert briefings["agent_approvisionnement"]["urgent"] and "retard" in " ".join(
        briefings["agent_approvisionnement"]["facts"]
    )
    assert briefings["agent_fournisseur"]["line"].startswith(
        next(a for a in sim_spec["agents"] if a["kind"] == "fournisseur")["personality"]["prefix"]
    )


def test_minimum_order_and_cash_are_enforced(sim_spec) -> None:
    cheap = _offer(sim_spec, "c1", "economique")
    state = _running(sim_spec)
    with pytest.raises(GameRuleError, match="pas moins de"):
        _act(
            sim_spec,
            state,
            "approvisionnement",
            "commander",
            {"offer": cheap["id"], "quantity": cheap["min_order"] - 50},
        )
    state["cash"] = 0
    order = {"offer": cheap["id"], "quantity": cheap["min_order"]}
    with pytest.raises(GameRuleError, match="Trésorerie insuffisante"):
        _act(sim_spec, state, "approvisionnement", "commander", order)
    state, _ = _act(sim_spec, state, "finance", "decouvert", {"limit": "50000"})
    _act(sim_spec, state, "approvisionnement", "commander", order)

    no_finance = generate(GameParams(theme="industrie", modules=["approvisionnement"], seed=4))
    state = _running(no_finance)
    state["cash"] = -100_000  # sans module finance, la trésorerie est seulement constatée
    _act(no_finance, state, "approvisionnement", "commander", {"offer": no_finance["offers"][0]["id"], "quantity": 500})


def test_a_line_without_components_stops_and_its_chief_warns(sim_spec) -> None:
    state = _running(sim_spec)
    state["components"]["c1"] = 30
    briefing = engine.public_state(sim_spec, state)["briefings"]["agent_production"]
    assert briefing["urgent"] and "va s'arrêter" in briefing["facts"][0]
    line = engine.advance(sim_spec, state)["last"]["lines"]["l1"]
    assert line["produced"] == 30 and line["starved"]


def test_roles_keep_their_module_but_free_roles_are_shared(sim_spec) -> None:
    state = _running(sim_spec)
    values = {"rate": "100"}
    _act(sim_spec, state, "qualite", "controler", values)  # rôle libre : toute l'équipe peut agir
    with pytest.raises(GameRuleError, match="revient au rôle"):
        _act(sim_spec, state, "qualite", "controler", values, role="acheteur", occupied={"responsable_qualite"})
    _act(sim_spec, state, "qualite", "controler", values, role="responsable_qualite", occupied={"responsable_qualite"})
    _act(
        sim_spec, state, "qualite", "controler", values, role="acheteur", occupied={"responsable_qualite"}, manager=True
    )


@pytest.mark.parametrize(
    ("module", "action", "values"),
    [
        ("approvisionnement", "commander", {"offer": "o999", "quantity": 500}),
        ("approvisionnement", "commander", {"offer": "o1", "quantity": 10}),
        ("approvisionnement", "commander", {"offer": "o1", "quantity": "beaucoup"}),
        ("qualite", "controler", {"rate": "75"}),
        ("production", "planifier", {"line": "l9", "quantity": 100}),
        ("production", "inventer", {}),
        ("marketing", "fixer_prix", {}),
    ],
)
def test_invalid_actions_are_refused(sim_spec, module, action, values) -> None:
    with pytest.raises(GameRuleError):
        _act(sim_spec, _running(sim_spec), module, action, values)


def test_actions_need_a_running_game(sim_spec) -> None:
    with pytest.raises(GameRuleError, match="pas en cours"):
        _act(sim_spec, engine.initial_state(sim_spec), "qualite", "controler", {"rate": "0"})
    with pytest.raises(GameRuleError):
        engine.start(sim_spec, _running(sim_spec))


def test_maintenance_level_drives_the_trs(sim_spec) -> None:
    state = _running(sim_spec)
    worn, kept = state["lines"]["l1"]["trs"], state["lines"]["l2"]["trs"]
    state, _ = _act(sim_spec, state, "maintenance", "entretenir", {"line": "l1", "level": "aucune"})
    state, _ = _act(sim_spec, state, "maintenance", "entretenir", {"line": "l2", "level": "renforcee"})
    for _ in range(3):
        state = engine.advance(sim_spec, state)
    assert state["lines"]["l1"]["trs"] == round(worn - 3 * 2.5, 1)
    assert state["lines"]["l2"]["trs"] > kept
    assert engine.public_state(sim_spec, state)["briefings"]["agent_maintenance"]["urgent"]


def test_quality_control_stops_defects_before_the_client(sim_spec) -> None:
    def week_with(rate):
        state, _ = _act(sim_spec, _running(sim_spec), "qualite", "controler", {"rate": rate})
        return engine.advance(sim_spec, state)["last"]

    none, full = week_with("0"), week_with("100")
    assert sum(s["returns"] for s in none["sales"].values()) > 0
    assert sum(s["returns"] for s in full["sales"].values()) == 0
    assert full["costs"]["controle"] > none["costs"]["controle"] == 0


def test_express_transport_raises_otif_at_a_cost(sim_spec) -> None:
    weeks = {}
    for mode in ("economique", "express"):
        state, _ = _act(sim_spec, _running(sim_spec), "transport", "choisir_mode", {"mode": mode})
        weeks[mode] = engine.advance(sim_spec, state)["last"]
    assert weeks["express"]["kpis"]["otif"] > weeks["economique"]["kpis"]["otif"]
    assert weeks["express"]["costs"]["transport"] > weeks["economique"]["costs"]["transport"]


def test_promotion_raises_demand(sim_spec) -> None:
    base = engine.advance(sim_spec, _running(sim_spec))["last"]["sales"]["p1"]["demand"]
    state, _ = _act(sim_spec, _running(sim_spec), "commercial", "fixer_prix", {"product": "p1", "price": "0.9"})
    assert engine.advance(sim_spec, state)["last"]["sales"]["p1"]["demand"] > base


def test_announced_breakdown_warns_the_right_agents_then_strikes(sim_spec) -> None:
    state = _running(sim_spec)
    state["event"] = "panne_ligne"
    view = engine.public_state(sim_spec, state)
    assert view["event"]["title"] == "Panne sur une ligne"
    assert "panne" in view["briefings"]["agent_maintenance"]["facts"][0]
    assert not any("panne" in fact for fact in view["briefings"]["agent_transport"]["facts"])
    state = engine.advance(sim_spec, state)
    assert any(line["down"] for line in state["last"]["lines"].values())
    assert state["history"][-1]["event"] == "panne_ligne"


def test_raw_material_increase_applies_to_later_orders(sim_spec) -> None:
    state = _running(sim_spec)
    state["event"] = "hausse_matieres"
    state = engine.advance(sim_spec, state)
    offer = _offer(sim_spec, "c3", "standard")
    state, _ = _act(sim_spec, state, "approvisionnement", "commander", {"offer": offer["id"], "quantity": 500})
    assert state["pending"][-1]["unit_cost"] == round(offer["unit_cost"] * 1.1, 2)


def test_events_are_rolled_from_week_two_and_deterministic() -> None:
    spec = generate(GameParams(theme="automobile", modules=["production"], events="frequents", weeks=12, seed=1))
    histories = []
    for _ in range(2):
        state = _running(spec)
        while state["status"] == "running":
            state = engine.advance(spec, state, autopilot_all=True)
        histories.append(state["history"])
    assert histories[0] == histories[1]
    assert histories[0][0]["event"] is None and any(h["event"] for h in histories[0])


def test_doing_nothing_leads_to_stockouts_while_the_autopilot_holds(sim_spec) -> None:
    passive = auto = _running(sim_spec)
    while passive["status"] == "running":
        passive, auto = engine.advance(sim_spec, passive), engine.advance(sim_spec, auto, autopilot_all=True)
    assert passive["history"][-1]["stockouts"] > 0
    assert auto["history"][-1]["otif"] > passive["history"][-1]["otif"]


def test_every_agent_gets_short_essential_facts(sim_spec) -> None:
    state = _running(sim_spec)
    state["components"]["c4"] = 0
    view = engine.public_state(sim_spec, state)
    assert set(view["briefings"]) == {a["id"] for a in sim_spec["agents"]}
    for agent in sim_spec["agents"]:
        brief = view["briefings"][agent["id"]]
        assert 1 <= len(brief["facts"]) <= 5
        assert (brief["line"] is not None) == brief["urgent"]
        assert brief["line"] is None or brief["line"].startswith(agent["personality"]["prefix"])
    assert "il faut commander" in view["briefings"]["agent_approvisionnement"]["line"]


def test_full_game_ends_with_a_sourced_debrief(sim_spec) -> None:
    state = _running(sim_spec)
    while state["status"] == "running":
        state = engine.advance(sim_spec, state, autopilot_all=True)
    with pytest.raises(GameRuleError):
        engine.advance(sim_spec, state)
    report = engine.debrief(sim_spec, state)
    assert report["weeks_played"] == sim_spec["meta"]["weeks"]
    assert [k["id"] for k in report["kpis"]] == ["otif", "trs", "stockouts", "cash"]
    assert all(k["met"] is not None for k in report["kpis"])
    assert report["lessons"] and report["notions"] and all(n["citation"] for n in report["notions"])
