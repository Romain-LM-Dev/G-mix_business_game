"""Moteur de partie : applique décisions et aléas d'une spec de business game aux KPI.

Fonctions pures (aucune entrée/sortie) : l'API lit l'état dans lobbies.state, appelle le moteur et enregistre le
résultat sous verrou de ligne. Chaque fonction renvoie un nouvel état, l'ancien n'est jamais modifié.

État : {"status": waiting|running|finished, "phase_index", "kpis": {id: valeur de base}, "decisions": {...},
        "pending": [effets différés avec due_phase], "pending_events": [ids], "events": [ids survenus],
        "history": [KPI à la fin de chaque phase]}
"""

import copy
from datetime import UTC, datetime
from typing import Any

from gmix.game.coherence import evaluate_formula


class GameRuleError(ValueError):
    """Action refusée par les règles du jeu ; le message est affichable au joueur."""


def initial_state(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "waiting",
        "phase_index": 0,
        "kpis": {k["id"]: float(k["initial"]) for k in spec["kpis"] if not k.get("formula")},
        "decisions": {},
        "pending": [],
        "pending_events": [],
        "events": [],
        "history": [],
    }


def start(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if state["status"] != "waiting":
        raise GameRuleError("La partie a déjà commencé")
    new = copy.deepcopy(state)
    new["status"] = "running"
    _enter_phase(spec, new, 0)
    return new


def decide(
    spec: dict[str, Any],
    state: dict[str, Any],
    decision_id: str,
    option_id: str,
    *,
    user_id: str,
    game_role: str | None,
) -> dict[str, Any]:
    """`game_role` None : le formateur décide à la place d'une équipe (animation de séance)."""
    if state["status"] != "running":
        raise GameRuleError("La partie n'est pas en cours")
    index = state["phase_index"]
    decision = next((d for d in spec["phases"][index]["decisions"] if d["id"] == decision_id), None)
    if decision is None:
        raise GameRuleError("Cette décision n'appartient pas à la phase en cours")
    if decision_id in state["decisions"]:
        raise GameRuleError("Cette décision a déjà été prise")
    if game_role is not None and decision["role"] != game_role:
        raise GameRuleError("Cette décision revient à un autre rôle")
    option = next((o for o in decision["options"] if o["id"] == option_id), None)
    if option is None:
        raise GameRuleError("Option inconnue")
    new = copy.deepcopy(state)
    for effect in option["effects"]:
        _schedule(new, effect, index)
    new["pending_events"] += [e for e in option.get("triggers_events", []) if e not in new["events"]]
    new["decisions"][decision_id] = {"option_id": option_id, "by": user_id, "at": datetime.now(UTC).isoformat()}
    return new


def advance(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Passe à la phase suivante, ou termine la partie après la dernière."""
    if state["status"] != "running":
        raise GameRuleError("La partie n'est pas en cours")
    new = copy.deepcopy(state)
    new["history"].append({"phase_index": new["phase_index"], "kpis": kpi_values(spec, new)})
    if new["phase_index"] + 1 < len(spec["phases"]):
        _enter_phase(spec, new, new["phase_index"] + 1)
    else:  # fin : les effets différés et aléas restants s'appliquent pour que le bilan soit complet
        for effect in new["pending"]:
            _apply_effect(new, effect)
        new["pending"] = []
        _fire_events(spec, new, new["pending_events"])
        new["pending_events"] = []
        new["status"] = "finished"
    return new


def kpi_values(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, float | None]:
    values: dict[str, float | None] = dict(state["kpis"])
    derived = {k["id"]: k["formula"] for k in spec["kpis"] if k.get("formula")}
    for _ in range(len(derived)):  # plusieurs passes : un KPI dérivé peut dépendre d'un autre
        for kpi_id, formula in derived.items():
            known = {k: v for k, v in values.items() if v is not None and k != kpi_id}
            try:
                values[kpi_id] = round(evaluate_formula(formula, known), 4)
            except ValueError:
                values.setdefault(kpi_id, None)
    return values


def public_state(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Ce que voient tous les membres du lobby : sans effets différés ni aléas à venir."""
    index = state["phase_index"]
    phase = spec["phases"][index]
    events = {e["id"]: e for p in spec["phases"] for e in p["events"]}
    return {
        "status": state["status"],
        "phase_index": index,
        "phase_count": len(spec["phases"]),
        "phase": {k: phase[k] for k in ("id", "title", "goal", "duration_minutes")},
        "kpis": kpi_values(spec, state),
        "decisions": {d: {"option_id": v["option_id"]} for d, v in state["decisions"].items()},
        "events": [{k: events[e][k] for k in ("id", "title", "description")} for e in state["events"] if e in events],
    }


def player_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Spec sans les réponses : effets et explications des options, aléas et débrief restent cachés."""
    view = copy.deepcopy(spec)
    for phase in view["phases"]:
        for decision in phase["decisions"]:
            decision["options"] = [{"id": o["id"], "label": o["label"]} for o in decision["options"]]
        phase["events"] = []
    view.pop("debrief", None)
    return view


def debrief(spec: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    values = kpi_values(spec, state)
    kpis = []
    for kpi in spec["kpis"]:
        final = values.get(kpi["id"])
        met = None
        if final is not None:
            met = final >= kpi["target"] if kpi["direction"] == "higher_is_better" else final <= kpi["target"]
        kpis.append({k: kpi[k] for k in ("id", "name", "unit", "initial", "target")} | {"final": final, "met": met})
    decisions = []
    for phase in spec["phases"]:
        for decision in phase["decisions"]:
            chosen = state["decisions"].get(decision["id"], {}).get("option_id")
            decisions.append(
                {
                    "id": decision["id"],
                    "phase": phase["title"],
                    "role": decision["role"],
                    "prompt": decision["prompt"],
                    "chosen": chosen,
                    "options": [
                        {"id": o["id"], "label": o["label"], "rationale": o["rationale"], "chosen": o["id"] == chosen}
                        for o in decision["options"]
                    ],
                }
            )
    return {
        "status": state["status"],
        "kpis": kpis,
        "decisions": decisions,
        "events": public_state(spec, state)["events"],
        "key_takeaways": spec["debrief"]["key_takeaways"],
        "questions": spec["debrief"]["questions"],
        "sources": spec["sources"],
    }


def _enter_phase(spec: dict[str, Any], state: dict[str, Any], index: int) -> None:
    state["phase_index"] = index
    due = [p for p in state["pending"] if p["due_phase"] <= index]
    state["pending"] = [p for p in state["pending"] if p["due_phase"] > index]
    for effect in due:
        _apply_effect(state, effect)
    phase_events = [
        e["id"] for e in spec["phases"][index]["events"] if e.get("trigger", "phase_start") == "phase_start"
    ]
    _fire_events(spec, state, phase_events + state["pending_events"], index)
    state["pending_events"] = []


def _fire_events(spec: dict[str, Any], state: dict[str, Any], event_ids: list[str], index: int | None = None) -> None:
    events = {e["id"]: e for p in spec["phases"] for e in p["events"]}
    for event_id in event_ids:
        if event_id in state["events"] or event_id not in events:
            continue
        for effect in events[event_id]["effects"]:
            if index is None:
                _apply_effect(state, effect)
            else:
                _schedule(state, effect, index)
        state["events"].append(event_id)


def _schedule(state: dict[str, Any], effect: dict[str, Any], index: int) -> None:
    delay = effect.get("delay_phases", 0) or 0
    if delay == 0:
        _apply_effect(state, effect)
    else:
        state["pending"].append({**effect, "due_phase": index + delay})


def _apply_effect(state: dict[str, Any], effect: dict[str, Any]) -> None:
    kpis = state["kpis"]
    kpi = effect["kpi"]
    if kpi not in kpis:  # KPI dérivé ou inconnu : refusé en amont par gmix.game.coherence
        return
    value = float(effect["value"])
    match effect["operation"]:
        case "add":
            kpis[kpi] += value
        case "multiply":
            kpis[kpi] *= value
        case "set":
            kpis[kpi] = value
    kpis[kpi] = round(kpis[kpi], 4)
