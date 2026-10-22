"""Contrôles de cohérence déterministes d'une spec de business game : 0 token, exécutés AVANT toute revue IA.

Le schéma JSON garantit la forme ; ici on vérifie le fond : références croisées, KPI dérivés,
durées, rôles sans décision, événements jamais déclenchés.
"""

import ast
from collections import Counter
from typing import Any

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.UAdd,
    ast.USub,
    ast.Constant,
    ast.Name,
    ast.Load,
)


def check_spec(spec: dict[str, Any]) -> list[str]:
    """Liste des incohérences (vide si la spec est cohérente). Suppose la spec valide pour le schéma."""
    issues: list[str] = []
    kpis = {k["id"]: k for k in spec["kpis"]}
    roles = {r["id"] for r in spec["roles"]}
    npcs = {n["id"] for n in spec["npcs"]}
    zones = {z["id"] for z in spec["world"]["zones"]}
    sources = {s["id"] for s in spec["sources"]}
    questions = {q["id"] for q in spec["debrief"]["questions"]}
    decisions = [d for phase in spec["phases"] for d in phase["decisions"]]
    events = {e["id"]: e for phase in spec["phases"] for e in phase["events"]}

    ids = [x["id"] for key in ("learning_objectives", "roles", "kpis", "phases", "npcs", "sources") for x in spec[key]]
    ids += list(zones) + list(questions)
    ids += [d["id"] for d in decisions] + [o["id"] for d in decisions for o in d["options"]]
    ids += [e["id"] for phase in spec["phases"] for e in phase["events"]]
    issues += [f"id en double : {dup} (x{n})" for dup, n in Counter(ids).items() if n > 1]

    def check_effects(owner: str, effects: list[dict[str, Any]]) -> None:
        for effect in effects:
            kpi = kpis.get(effect["kpi"])
            if kpi is None:
                issues.append(f"{owner} : KPI inconnu '{effect['kpi']}'")
            elif kpi.get("formula"):
                issues.append(f"{owner} : '{effect['kpi']}' est un KPI dérivé, il ne se modifie pas directement")

    triggered: set[str] = set()
    for decision in decisions:
        if decision["role"] not in roles:
            issues.append(f"{decision['id']} : rôle inconnu '{decision['role']}'")
        if decision.get("advisor_npc") and decision["advisor_npc"] not in npcs:
            issues.append(f"{decision['id']} : PNJ conseiller inconnu '{decision['advisor_npc']}'")
        signatures = [sorted(map(str, option["effects"])) for option in decision["options"]]
        if len({str(s) for s in signatures}) < len(signatures):
            issues.append(f"{decision['id']} : options aux effets identiques (pas de vrai choix)")
        for option in decision["options"]:
            owner = f"{decision['id']}/{option['id']}"
            check_effects(owner, option["effects"])
            for event_id in option.get("triggers_events", []):
                if event_id not in events:
                    issues.append(f"{owner} : déclenche un événement inconnu '{event_id}'")
                triggered.add(event_id)
            issues += [
                f"{owner} : source inconnue '{ref}'" for ref in option.get("source_refs", []) if ref not in sources
            ]

    for event_id, event in events.items():
        check_effects(event_id, event["effects"])
        if event.get("trigger", "phase_start") == "on_option" and event_id not in triggered:
            issues.append(f"{event_id} : événement on_option qu'aucune option ne déclenche")

    issues += [f"rôle {role} : aucune décision à prendre" for role in sorted(roles - {d["role"] for d in decisions})]

    assessable = set(kpis) | {d["id"] for d in decisions} | questions
    for objective in spec["learning_objectives"]:
        issues += [
            f"{objective['id']} : évalué par un id inconnu '{ref}'"
            for ref in objective["assessed_by"]
            if ref not in assessable
        ]
    issues += [f"{n['id']} : zone inconnue '{n['zone']}'" for n in spec["npcs"] if n["zone"] not in zones]

    total = sum(phase["duration_minutes"] for phase in spec["phases"])
    if total > spec["meta"]["duration_minutes"]:
        issues.append(f"durée des phases ({total} min) > durée du jeu ({spec['meta']['duration_minutes']} min)")
    if spec["meta"]["players"]["min"] > spec["meta"]["players"]["max"]:
        issues.append("meta.players : min > max")

    initials = {kpi_id: kpi["initial"] for kpi_id, kpi in kpis.items()}
    for kpi_id, kpi in kpis.items():
        if not kpi.get("formula"):
            continue
        try:
            value = evaluate_formula(kpi["formula"], {k: v for k, v in initials.items() if k != kpi_id})
        except ValueError as exc:
            issues.append(f"KPI {kpi_id} : formule invalide ({exc})")
            continue
        if abs(value - kpi["initial"]) > max(1e-6, 0.01 * abs(kpi["initial"])):
            issues.append(f"KPI {kpi_id} : valeur initiale {kpi['initial']} différente de la formule ({value:g})")
    return issues


def evaluate_formula(expression: str, values: dict[str, float]) -> float:
    """Évalue une expression arithmétique (+ - * / parenthèses) sur des ids de KPI. Rien d'autre n'est autorisé."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"syntaxe : {exc.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"élément interdit : {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in values:
            raise ValueError(f"KPI inconnu '{node.id}'")
        if isinstance(node, ast.Constant) and not isinstance(node.value, int | float):
            raise ValueError("constante non numérique")
    try:
        return float(eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, dict(values)))
    except ZeroDivisionError:
        raise ValueError("division par zéro") from None
