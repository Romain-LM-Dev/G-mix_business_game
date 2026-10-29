"""Génération d'un business game simulé à partir de paramètres seulement (docs/decisions/0006).

Aucun texte libre ni appel à un modèle : le secteur, les modules, les agents, la difficulté et la durée choisis
par le formateur suffisent à assembler un jeu cohérent à partir de ai/simulation.yaml. La même graine donne
le même jeu. Capacités, stocks et trésorerie sont calibrés sur la demande, puis le jeu est vérifié par une partie
jouée en pilote automatique (`autopilot_check`).

Plan de l'atelier (repère Godot, 1 unité = 1 m, hall de 32 x 24 m ouvert vers +Z), repris du jeu de référence :
produits finis au fond, composants le long des murs, lignes au centre, quais devant, bureau à gauche.
"""

import math
import random
from typing import Any

from gmix.game import engine
from gmix.game.spec import GameParams, Point, SimSpec, load_sim_catalog

HALL_DEPTH = 24
PRODUCT_RACK_Z = -9.8
LINE_Z = -2.2
LINE_APPROACH_Z = 1.4
DOCK_IN_X, DOCK_OUT_X = 10.0, 2.5
DOCK_STACK_Z, DOCK_APPROACH_Z = 10.6, 8.6
OFFICE = (-12.0, 9.3)
KPI_SCREEN = (-6.5, 10.6)
QUALITY_DESK = (11.0, 3.8)

# Points de patrouille des agents, par zone : tous dans les allées libres (vérifié par les tests).
ZONE_ROUTES: dict[str, list[tuple[float, float]]] = {
    "quai_reception": [(10.0, 8.4), (7.8, 7.2), (12.4, 7.2)],
    "quai_expedition": [(2.5, 8.4), (0.4, 7.2), (4.6, 7.2)],
    "qualite": [(9.4, 3.8), (9.4, 2.4), (6.6, 2.6)],
    "bureau": [(-12.0, 6.6), (-9.6, 6.2), (-7.6, 7.4)],
}


def _spread(count: int, spacing: float) -> list[float]:
    return [round((i - (count - 1) / 2) * spacing, 2) for i in range(count)]


def _money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def generate(params: GameParams) -> dict[str, Any]:
    catalog = load_sim_catalog()
    seed = params.seed if params.seed is not None else random.SystemRandom().randrange(2**31)
    rng = random.Random(seed)
    theme = catalog["themes"][params.theme]
    level = catalog["difficulties"][params.difficulty]
    economy = catalog["economy"]
    company = params.company_name or rng.choice(theme["companies"])
    picked = sorted(rng.sample(range(len(theme["products"])), params.products))
    sources = [theme["products"][i] for i in picked]

    products, components, lines, suppliers, offers = [], [], [], {}, []
    for index, item in enumerate(sources, start=1):
        demand = int(item["demand"])
        capacity = math.ceil(demand * 1.12 / 0.85 / 10) * 10  # 85 % de TRS couvrent la demande, avec 12 % de marge
        stock = round(demand * level["stock_weeks"])
        products.append(
            {
                "id": f"p{index}", "name": item["name"], "category": item["category"], "price": float(item["price"]),
                "unit_cost": float(item["cost"]), "demand": demand, "component_id": f"c{index}", "line_id": f"l{index}",
                "initial_stock": stock, "safety_stock": round(demand * 0.8),
            }
        )  # fmt: skip
        part = item["component"]
        components.append(
            {
                "id": f"c{index}", "name": part["name"], "unit_cost": float(part["cost"]), "usage": demand,
                "initial_stock": stock, "safety_stock": round(demand * 0.8), "product_id": f"p{index}",
            }
        )  # fmt: skip
        trs = max(50.0, min(96.0, level["trs"] + rng.choice([-2, -1, 0, 1, 2])))
        lines.append(
            {
                "id": f"l{index}", "name": item["line"], "product_id": f"p{index}", "capacity": capacity, "trs": trs,
                "label": f"{item['line']} · {item['name']} · {capacity} u./sem. à 100 %",
            }
        )  # fmt: skip
        for (name, region), profile in zip(part["suppliers"], catalog["supplier_profiles"], strict=True):
            supplier_id = suppliers.setdefault(name, {"id": f"s{len(suppliers) + 1}", "name": name, "region": region})[
                "id"
            ]
            reliability = max(50.0, min(99.0, profile["reliability"] + level["reliability_shift"]))
            cost = round(part["cost"] * profile["cost"], 2)
            minimum = max(50, math.ceil(demand * profile["min_weeks"] / 50) * 50)
            offers.append(
                {
                    "id": f"o{len(offers) + 1}", "supplier_id": supplier_id, "component_id": f"c{index}",
                    "profile": profile["label"], "lead_time": profile["lead_time"], "reliability": reliability,
                    "unit_cost": cost, "min_order": minimum,
                    "label": f"{part['name']} · {name} ({region}) · {profile['lead_time']} sem. · {reliability:.0f} % "
                    f"· {_money(cost)} €/u. · min. {minimum}",
                }
            )  # fmt: skip

    modules, roles = [], []
    for module_id in params.modules:
        source = catalog["modules"][module_id]
        modules.append(
            {
                "id": module_id, "title": source["title"], "description": source["description"],
                "role_id": source["role"]["id"], "stations": source["stations"], "actions": source["actions"],
                "autopilot": source["autopilot"], "notions": source["notions"],
            }
        )  # fmt: skip
        roles.append({**source["role"], "module_id": module_id})

    weekly_purchases = sum(c["usage"] * c["unit_cost"] for c in components)
    spec = {
        "kind": "simulation",
        "version": 2,
        "seed": seed,
        "meta": _meta(params, catalog, theme, level, company),
        "params": params.model_dump(),
        "products": products,
        "components": components,
        "suppliers": list(suppliers.values()),
        "offers": offers,
        "lines": lines,
        "modules": modules,
        "roles": roles,
        "agents": _agents(params, catalog, rng, company),
        "stations": [],
        "world": {},
        "notions": [{"id": key, **value} for key, value in catalog["notions"].items()],
        "events": [{"id": key, **value} for key, value in catalog["events"].items()],
        "economy": {
            "initial_cash": round(weekly_purchases * level["cash_weeks"], -2),
            "holding_rate_week": economy["holding_rate_week"],
            "maintenance_rate": economy["maintenance_rate"],
            "trs_drift": economy["trs_drift"],
            "control_cost_rate": economy["control_cost_rate"],
            "interest_rate_week": economy["interest_rate_week"],
            "price_elasticity": economy["price_elasticity"],
            "defect_rate": level["defect_rate"],
            "demand_noise": level["demand_noise"],
            "events_probability": catalog["events_levels"][params.events]["probability"],
            "transport": economy["transport"],
        },
        "targets": {},
    }
    initial_cash = spec["economy"]["initial_cash"]
    spec["targets"] = {
        "otif": catalog["targets"]["otif"],
        "trs": catalog["targets"]["trs"],
        "stockouts": catalog["targets"]["stockouts"],
        "cash_final": initial_cash,
    }
    spec["stations"], spec["world"] = _layout(spec)
    for notion in spec["notions"]:  # la spec ne garde que la citation résolue, pas le nom de fiche
        notion.pop("source", None)
    spec = SimSpec.model_validate(spec).model_dump(mode="json")
    # Objectif de trésorerie calé sur la partie de référence : faire au moins 60 % de ce que gagne le pilote.
    gain = max(0, autopilot_check(spec)["final_cash"] - initial_cash)
    spec["targets"]["cash_final"] = round(initial_cash + catalog["targets"]["cash_share"] * gain, -2)
    return spec


def autopilot_check(spec: dict[str, Any]) -> dict[str, Any]:
    """Partie jouée par le pilote automatique sur tous les modules (règles simples : point de commande, plan à
    trois semaines de couverture, entretien préventif) : prouve que le jeu se gagne avec une gestion sensée et
    donne au formateur l'ordre de grandeur des indicateurs."""
    state = engine.start(spec, engine.initial_state(spec))
    while state["status"] == "running":
        state = engine.advance(spec, state, autopilot_all=True)
    history = state["history"]
    return {
        "weeks": len(history),
        "otif_mean": round(sum(h["otif"] for h in history) / len(history), 1),
        "trs_mean": round(sum(h["trs"] for h in history) / len(history), 1),
        "stockout_weeks": sum(1 for h in history if h["stockouts"]),
        "final_cash": round(state["cash"]),
    }


def _meta(
    params: GameParams, catalog: dict[str, Any], theme: dict[str, Any], level: dict[str, Any], company: str
) -> dict:
    titles = [catalog["modules"][m]["title"].lower() for m in params.modules]
    modules_text = ", ".join(titles[:-1]) + (" et " if len(titles) > 1 else "") + titles[-1]
    return {
        "title": f"{company} · {theme['label']}",
        "company": company,
        "client": theme["client"],
        "theme": params.theme,
        "theme_label": theme["label"],
        "pitch": f"{theme['description']} Pendant {params.weeks} semaines, votre équipe pilote {modules_text} "
        f"pour livrer {theme['client']} à l'heure et complet, sans immobiliser trop de stock ni de trésorerie. "
        f"Niveau {level['label'].lower()} : {level['detail']}.",
        "difficulty": params.difficulty,
        "difficulty_label": level["label"],
        "weeks": params.weeks,
        "players": {"min": params.players_min, "max": params.players_max},
        "language": "fr",
    }


def _agents(params: GameParams, catalog: dict[str, Any], rng: random.Random, company: str) -> list[dict[str, Any]]:
    personalities = catalog["agent_tones"][params.agent_tone]["personalities"]
    offset = rng.randrange(len(personalities))
    sources = [("module", m, catalog["modules"][m]["agent"], catalog["modules"][m]["notions"]) for m in params.modules]
    sources += [
        (kind, None, catalog["extra_agents"][kind], catalog["extra_agents"][kind]["notions"])
        for kind in params.extra_agents
    ]
    agents = []
    for index, (kind, module_id, source, notions) in enumerate(sources):
        personality_id = personalities[(offset + index) % len(personalities)]
        personality = {"id": personality_id, **catalog["personalities"][personality_id]}
        agents.append(
            {
                "id": f"agent_{module_id or kind}", "name": source["name"], "job": source["job"], "kind": kind,
                "module_id": module_id, "personality": personality, "tasks": source["tasks"],
                "character": source["character"], "zone": source["zone"], "route": [], "notions": notions,
            }
        )  # fmt: skip
    return agents


def _layout(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Postes d'interaction et objets 3D de l'atelier, puis trajets des agents dans les allées."""
    stations: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []

    def station(station_id: str, kind: str, label: str, position: Point, ref: str | None = None) -> None:
        modules = [m["id"] for m in spec["modules"] if kind in m["stations"]]
        stations.append(
            {"id": station_id, "kind": kind, "label": label, "position": position, "ref": ref, "modules": modules}
        )

    def place(
        asset: str, position: Point, rotation: float = 0, label: str | None = None, ref: str | None = None
    ) -> None:
        objects.append({"asset": asset, "position": position, "rotation": rotation, "label": label, "ref": ref})

    for product, x in zip(spec["products"], _spread(len(spec["products"]), 6.4), strict=True):
        pid, name = product["id"], product["name"]
        place("prop_pallet_rack", (x, PRODUCT_RACK_Z), 0, f"Produits finis · {name}", f"stock:{pid}")
        station(f"rack_{pid}", "rack_produit", f"Stock de {name}", (x, PRODUCT_RACK_Z + 1.6), pid)
    # Composants : trois emplacements le long du mur gauche, le quatrième sur le mur droit.
    slots = [(-14.9, z, 90, -13.2) for z in _spread(min(3, len(spec["components"])), 6.4)] + [(14.9, -6.4, -90, 13.2)]
    for component, (x, z, rotation, approach_x) in zip(spec["components"], slots, strict=False):
        cid, name = component["id"], component["name"]
        place("prop_pallet_rack", (x, z), rotation, f"Composants · {name}", f"component:{cid}")
        station(f"rack_{cid}", "rack_composant", f"Stock de {name}", (approach_x, z), cid)
    line_xs = _spread(len(spec["lines"]), 5.0)
    for line, x in zip(spec["lines"], line_xs, strict=True):
        place("prop_production_line", (x, LINE_Z), 0, line["name"], f"line:{line['id']}")
        station(f"ligne_{line['id']}", "ligne", line["name"], (x, LINE_APPROACH_Z), line["id"])
    place("prop_desk_computer", QUALITY_DESK, -90, "Poste qualité", "quality")
    place("prop_andon_light", (QUALITY_DESK[0], QUALITY_DESK[1] - 1.6))
    place("prop_site_office", OFFICE, 180, "Bureau")
    place("prop_kpi_screen", KPI_SCREEN, 180, ref="kpi")
    place("prop_pallet_stack", (DOCK_IN_X, DOCK_STACK_Z), 0, "Quai de réception", "dock_in")
    place("veh_box_truck", (DOCK_IN_X, 17.0))
    place("prop_pallet_stack", (DOCK_OUT_X, DOCK_STACK_Z), 0, "Quai d'expédition", "dock_out")
    place("veh_van", (DOCK_OUT_X, 16.0))
    station("poste_qualite", "poste_qualite", "Poste qualité", (QUALITY_DESK[0] - 1.5, QUALITY_DESK[1]))
    station("bureau", "bureau", "Bureau de direction", (OFFICE[0], OFFICE[1] - 2.6))
    station("ecran_kpi", "ecran_kpi", "Écran des indicateurs", (KPI_SCREEN[0], KPI_SCREEN[1] - 1.6))
    station("quai_reception", "quai_reception", "Quai de réception", (DOCK_IN_X, DOCK_APPROACH_Z))
    station("quai_expedition", "quai_expedition", "Quai d'expédition", (DOCK_OUT_X, DOCK_APPROACH_Z))

    routes = ZONE_ROUTES | {
        "lignes_avant": [(x, LINE_APPROACH_Z + 0.4) for x in (line_xs[0], line_xs[-1])],
        "lignes_arriere": [(x, LINE_Z - 2.4) for x in (line_xs[0], line_xs[-1])],
    }
    crowd: dict[str, int] = {}
    for agent in spec["agents"]:  # plusieurs agents dans une zone : trajets décalés et départs à des points différents
        rank = crowd.get(agent["zone"], 0)
        crowd[agent["zone"]] = rank + 1
        points = [(round(x + rank * 1.4, 2), z) for x, z in routes[agent["zone"]]]
        agent["route"] = points[rank % len(points) :] + points[: rank % len(points)]
    world = {
        "template": "atelier",
        "size": (32, HALL_DEPTH),
        "spawn": (-4.0, 14.0),  # sur l'aire de livraison, face au hall : l'atelier se découvre en entrant
        "objects": objects,
        "forklift_route": [(-10.5, 4.8), (8.0, 4.8)],
    }
    return stations, world
