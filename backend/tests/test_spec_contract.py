"""Contrat de spec de l'usine 3D (ADR 0007, annexe section 1) : les anciennes specs restent valides, une spec usine
écrite à la main passe, et chaque référence cassée est refusée. Le pack « usine » de ce fichier est minimal et local
(ai/packs/usine.yaml est celui du game-designer : il n'est pas lu ici)."""

import copy
from typing import Any, get_args

import pytest
import yaml
from pydantic import ValidationError

from gmix.game import engine
from gmix.game.spec import (
    COUNTERS,
    EVENT_DATA,
    PUBLIC_ROOTS,
    Clock,
    Customer,
    EventKind,
    Factory,
    GameParams,
    MachineState,
    Provenance,
    SimSpec,
    Timeline,
    frame_times,
    load_pack,
    load_sim_catalog,
    pack_station_kinds,
)
from gmix.settings import get_settings

TOUCHSTONE = "wikipedia-en-theory-of-constraints"  # fiche du corpus dont l'en-tête « > Source : » sert de citation
PACK = {
    "version": 1, "id": "usine", "domain": "supply-chain", "engine": "factory",
    "limits": {"weeks": [4, 12, 6], "products": [1, 1, 1]},
    "params": [
        {"id": "lines", "label": "Lignes", "type": "int", "min": 1, "max": 3, "default": 2},
        {"id": "plan", "label": "Plan", "type": "choice", "options": [{"id": "u", "label": "U"}]},
    ],
    "themes": {"industrie": {"label": "Industrie"}},
    "modules": {
        "pilotage": {"stations": ["pilotage"]},
        "maintenance": {"stations": ["maintenance"]},
    },
    "extra_agents": {"client": {}},
    "departments": [{"id": "production", "stations": [{"kind": "tableau_ligne", "label": "Tableau de ligne"}]}],
    "notions": {
        "goulot": {"title": "Goulot", "text": "...", "source": TOUCHSTONE},
        "weibull": {"title": "Weibull", "text": "..."},  # « à sourcer » : ni source ni citation
    },
}  # fmt: skip


@pytest.fixture
def usine_pack(tmp_path, monkeypatch):
    """Pack « usine » minimal placé dans un dossier ai/ temporaire."""
    load_sim_catalog()  # lu avant le changement de dossier
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "usine.yaml").write_text(yaml.safe_dump(PACK, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(get_settings(), "gmix_ai_dir", tmp_path)
    load_pack.cache_clear()
    yield
    load_pack.cache_clear()


def machine(line: int, rank: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"l{line}-m{rank}", "line_id": f"l{line}", "rank": rank, "name": f"M{rank}", "operation": "Usinage",
        "cycle_min": 3, "run_min": 110, "stop_min": 10, "mtbf_h": 40, "weibull_shape": 2, "mttr_h": 1.5,
        "setup_min": 5, "defect_rate": 0.02, "buffer": 20, "transfer_min": 0.5, "asset": "prop_machine",
    } | extra  # fmt: skip


def factory_spec() -> dict[str, Any]:
    """Spec usine complète écrite à la main : 2 lignes de 2 machines, 3 départements, 2 modules."""
    prefix = {"id": "p", "label": "L", "traits": "t", "style": "s", "prefix": "Point :"}
    return {
        "kind": "simulation", "version": 2, "seed": 1,
        "meta": {
            "title": "Usine test", "company": "Test SA", "client": "Client", "theme": "industrie",
            "theme_label": "Industrie", "pitch": "...", "difficulty": "equilibre", "difficulty_label": "Équilibré",
            "weeks": 6, "players": {"min": 2, "max": 6}, "domain": "supply-chain", "pack": "usine",
        },
        "params": {"pack": "usine", "theme": "industrie", "modules": ["pilotage", "maintenance"], "products": 1,
                   "extra_agents": ["client"], "options": {"lines": 2}, "weeks": 6, "seed": 1},
        "products": [{"id": "p1", "name": "Pompe", "category": "Pompes", "price": 100, "unit_cost": 20, "demand": 100,
                      "component_id": "c1", "line_id": "l1", "initial_stock": 50, "safety_stock": 20}],
        "components": [{"id": "c1", "name": "Carter", "unit_cost": 10, "usage": 100, "initial_stock": 200,
                        "safety_stock": 50, "product_id": "p1"}],
        "suppliers": [{"id": "s1", "name": "Fonderie Test", "region": "Lyon"}],
        "offers": [{"id": "o1", "supplier_id": "s1", "component_id": "c1", "profile": "standard", "lead_time": 2,
                    "reliability": 92, "unit_cost": 10, "min_order": 10, "label": "Standard"}],
        "lines": [{"id": f"l{i}", "name": f"Ligne {i}", "product_id": "p1", "capacity": 100, "trs": 85, "label": "L"}
                  for i in (1, 2)],
        "modules": [
            {"id": "pilotage", "title": "Pilotage", "description": "...", "role_id": "resp_prod",
             "stations": ["pilotage"], "autopilot": "OF quand le stock PF baisse", "notions": ["goulot"],
             "actions": [{"id": "lancer_of", "label": "Lancer un OF", "fields": [
                 {"id": "line", "label": "Ligne", "type": "choice", "source": "lines"},
                 {"id": "lots", "label": "Lots", "type": "int", "min": 1, "max": 20}]}]},
            {"id": "maintenance", "title": "Maintenance", "description": "...", "role_id": "resp_maint",
             "stations": ["maintenance"], "autopilot": "préventif sur le goulot", "notions": [],
             "actions": [{"id": "preventif", "label": "Préventif", "fields": [
                 {"id": "machine", "label": "Machine", "type": "choice", "source": "machines"}]}]},
        ],
        "roles": [{"id": "resp_prod", "title": "Responsable de production", "mission": "...", "module_id": "pilotage"},
                  {"id": "resp_maint", "title": "Responsable maintenance", "mission": "...",
                   "module_id": "maintenance"}],
        "agents": [{"id": "agent_pilotage", "name": "Léa", "job": "Responsable de production",
                    "kind": "departement", "module_id": "pilotage", "department_id": "pilotage",
                    "facts": "pilotage", "personality": prefix, "tasks": ["lancer les OF"],
                    "character": "char_manager_f", "zone": "bureau", "route": [(0, 0)], "notions": ["goulot"]}],
        "stations": [
            {"id": "machine_l1-m1", "kind": "machine", "label": "M1", "position": (0, -6), "ref": "l1-m1",
             "modules": [], "department_id": "production"},
            {"id": "st_p", "kind": "pilotage", "label": "Pilotage", "position": (5, -12), "modules": ["pilotage"],
             "department_id": "pilotage"},
            {"id": "st_t", "kind": "maintenance", "label": "Maintenance", "position": (-5, -12),
             "modules": ["maintenance"]},
        ],
        "world": {
            "template": "usine", "size": (48, 30), "spawn": (0, 20),
            "objects": [{"asset": "prop_machine", "position": (0, -6), "ref": "machine:l1-m1"},
                        {"asset": "prop_buffer_table", "position": (2, -6), "ref": "buffer:l1-m1"},
                        {"asset": "prop_pallet_rack", "position": (-20, -10), "ref": "mp:c1"},
                        {"asset": "prop_floor_zone", "position": (0, -6), "ref": "dept:production"},
                        {"asset": "prop_pallet_rack", "position": (20, 10), "ref": "pf"},
                        {"asset": "prop_dock_door", "position": (0, 15), "ref": "dock"},
                        {"asset": "prop_scrap_bin", "position": (10, -2), "ref": "scrap"},
                        {"asset": "prop_floor_zone", "position": (-10, 8), "ref": "quarantine"}],
        },
        "notions": [{"id": "goulot", "title": "Goulot", "text": "...", "citation": "Goldratt, Le But"}],
        "events": [{"id": "panne_grave", "title": "Panne", "description": "...", "weight": 1,
                    "effects": {"breakdown": 1}, "modules": ["maintenance"]}],
        "economy": {
            "initial_cash": 50000, "holding_rate_week": 0.005, "maintenance_rate": {"aucune": 0}, "trs_drift": {},
            "control_cost_rate": 0.08, "interest_rate_week": 0.004, "price_elasticity": 1.5, "defect_rate": 0.03,
            "demand_noise": 0.08, "events_probability": 0.1, "transport": {"standard": {"on_time": 0.97}},
        },
        "targets": {"otif": 95, "trs": 85, "stockouts": 0, "cash_final": 50000},
        "departments": [
            {"id": "production", "label": "Production", "area": (-11, -9, 11, 4)},
            {"id": "pilotage", "label": "Pilotage", "area": (2, -15, 11, -11)},
            {"id": "fournisseur", "label": "Fournisseur", "external": True, "area": (-40, 15, -26, 28)},
        ],
        "factory": {
            "product_id": "p1", "lot_size": 20, "pf_min": 40,
            "clock": {"breaks": [(240, 20), (120, 10), (360, 10)]},  # 2 x 10 + 1 x 20 min, désordre toléré
            "bom": [{"component_id": "c1", "per_unit": 1}],
            "machines": [machine(line, rank) for line in (1, 2) for rank in (1, 2)],
            "crew": [{"id": "op1", "job": "operateur", "department_id": "production", "machine_id": "l1-m1",
                      "character": "char_worker_m"},
                     {"id": "ch1", "job": "chauffeur_fournisseur", "department_id": "fournisseur",
                      "character": "char_driver_m"}],
            "logistics": {
                "units_per_pallet_mp": 50, "unload_min_per_pallet": 5, "inspect_min_per_pallet": 3,
                "supplier_nonconform_rate": 0.02, "mp_capacity_pallets": 20, "kit_min": 10, "qc_min_per_unit": 0.5,
                "units_per_case": 10, "cases_per_pallet": 8, "pack_min_per_case": 2, "wrap_min_per_pallet": 5,
                "pf_capacity_pallets": 30, "load_min_per_pallet": 6, "repair_travel_min": 5, "preventive_min": 30,
            },
            "customer": {"demand_per_day": 20, "variability": 0.1, "promised_days": 3},
            "costs": {"repair_per_h": 60, "preventive_per_intervention": 40, "operator_per_h": 25},
        },
        "panels": [
            {"id": "otif", "type": "kpis", "title": "OTIF", "placement": "bandeau", "source": "kpis",
             "columns": [{"key": "otif", "label": "OTIF", "format": "pct", "target": "targets.otif"}]},
            {"id": "machines", "type": "table", "title": "Machines", "placement": "poste",
             "station_kinds": ["machine"], "source": "factory.machines", "match": "id",
             "columns": [{"key": "state", "label": "État", "format": "state", "labels": {"marche": "En marche"}}]},
        ],
        "provenance": {
            "machine.mtbf_h": {"status": "exemple", "note": "valeur du cahier, non sourcée"},
            "machine.defect_rate": {"status": "calibre", "note": "choisi pour la jouabilité"},
            "client.promised_days": {"status": "source", "citation": "NF E60-182"},
        },
    }  # fmt: skip


def refused(spec: dict[str, Any], *words: str) -> None:
    with pytest.raises(ValidationError) as caught:
        SimSpec.model_validate(spec)
    assert all(word in str(caught.value) for word in words), str(caught.value)


# --- Anciennes specs ---------------------------------------------------------------------------------------------


def test_atelier_spec_stays_valid_with_empty_factory_fields(sim_spec) -> None:
    spec = SimSpec.model_validate(sim_spec)
    assert (spec.departments, spec.factory, spec.panels, spec.provenance) == ([], None, [], {})
    assert (spec.meta.pack, spec.meta.domain, spec.params.pack, spec.world.template) == (
        "atelier", "supply-chain", "atelier", "atelier",
    )  # fmt: skip
    assert SimSpec.model_validate(spec.model_dump(mode="json")) == spec  # aller-retour de l'API


def test_atelier_keeps_its_old_refusals(sim_spec) -> None:
    for path, value in (("modules.0.id", "inconnu"), ("stations.0.kind", "hangar"), ("meta.pack", "usine")):
        broken = copy.deepcopy(sim_spec)
        node: Any = broken
        *head, last = path.split(".")
        for key in head:
            node = node[int(key)] if key.isdigit() else node[key]
        node[int(last) if last.isdigit() else last] = value
        with pytest.raises(ValidationError):
            SimSpec.model_validate(broken)
    broken = copy.deepcopy(sim_spec)
    broken["world"]["objects"][0]["ref"] = "machine:l1-m1"  # références de l'usine : réservées à `factory`
    refused(broken, "référence inconnue")
    for bad in ({"products": 1}, {"weeks": 3}, {"options": {"lines": 2}}, {"extra_agents": ["x_y"]}):
        with pytest.raises(ValidationError):
            GameParams(theme="industrie", modules=["production"], **bad)


def test_public_roots_are_the_keys_of_the_public_state(sim_spec) -> None:
    keys = set(engine.public_state(sim_spec, engine.initial_state(sim_spec)))
    assert keys | {"factory"} == PUBLIC_ROOTS  # la clé « factory » n'existe qu'avec une spec usine (étape 6)


# --- Chargeur de pack --------------------------------------------------------------------------------------------


def test_load_pack(usine_pack) -> None:
    assert load_pack("atelier") is load_sim_catalog()
    pack = load_pack("usine")
    assert pack["notions"]["goulot"]["citation"].startswith("Wikipédia (en), « Theory of constraints »")
    assert "citation" not in pack["notions"]["weibull"]  # à sourcer : jamais inventée
    assert load_pack("usine") is pack  # lru_cache
    for unknown in ("absent", "../ai/simulation", "A_b", ""):
        with pytest.raises(ValueError, match="pack inconnu"):
            load_pack(unknown)


def test_load_pack_refuses_a_source_without_citation(usine_pack, tmp_path) -> None:
    broken = copy.deepcopy(PACK) | {"id": "casse", "notions": {"n": {"title": "n", "text": "n", "source": "absente"}}}
    (tmp_path / "packs" / "casse.yaml").write_text(yaml.safe_dump(broken), encoding="utf-8")
    with pytest.raises(FileNotFoundError):  # une fiche citée qui n'existe pas est une erreur, pas un « à sourcer »
        load_pack("casse")


def write_pack(tmp_path, **changes: Any) -> None:
    broken = copy.deepcopy(PACK) | {"id": "casse"} | changes
    (tmp_path / "packs" / "casse.yaml").write_text(yaml.safe_dump(broken, allow_unicode=True), encoding="utf-8")


@pytest.mark.parametrize(
    "changes",
    [
        {"limits": {"weeks": [4, 12]}},  # deux entiers : l'ancien format
        {"limits": {"weeks": {"min": 4, "max": 12}}},
        {"limits": {"weeks": [4, 12, 13]}},  # défaut hors bornes
        {"limits": {"weeks": [12, 4, 6]}},
        {"limits": {"weeks": [4, 12, "6"]}},
        {"limits": {"weeks": [4, 12, 6.5]}},
        {"limits": {"weeks": [4, 12, True]}},
        {"departments": [{"id": "d", "stations": [{"kind": "a_b"}]}]},  # label absent
        {"departments": [{"id": "d", "stations": [{"kind": "a_b", "label": "x", "ref": "r"}]}]},  # clé en trop
        {"departments": [{"id": "d", "stations": [{"kind": "Bad Kind", "label": "x"}]}]},
        {"departments": [{"id": "d", "stations": [{"kind": "machine", "label": "x"}]}]},  # type réservé
        {"departments": [  # un kind n'apparaît qu'une fois dans tout le pack
            {"id": "d", "stations": [{"kind": "a_b", "label": "x"}]},
            {"id": "e", "stations": [{"kind": "a_b", "label": "y"}]},
        ]},
    ],
)  # fmt: skip
def test_load_pack_refuses_unexpected_formats(usine_pack, tmp_path, changes: dict[str, Any]) -> None:
    write_pack(tmp_path, **changes)
    with pytest.raises(ValueError, match="pack casse"):
        load_pack("casse")


def test_machine_station_kind_comes_with_a_factory_engine(usine_pack, tmp_path) -> None:
    write_pack(tmp_path, engine="weekly")
    assert "machine" in pack_station_kinds("usine", load_pack("usine"))
    assert "machine" not in pack_station_kinds("casse", load_pack("casse"))


# --- Paramètres vérifiés contre le pack --------------------------------------------------------------------------


def params(**changes: Any) -> dict[str, Any]:
    return {"pack": "usine", "theme": "industrie", "modules": ["pilotage"], "products": 1} | changes


def test_game_params_accept_the_pack_choices(usine_pack) -> None:
    assert GameParams(**params(options={"lines": 3, "plan": "u"}, extra_agents=["client"])).pack == "usine"
    assert GameParams(**params()).options == {}


@pytest.mark.parametrize(
    "bad",
    [
        {"theme": "spatial"},
        {"modules": ["finance"]},  # module de l'atelier, pas de l'usine
        {"extra_agents": ["direction"]},
        {"products": 2},  # limites du pack : [1, 1, 1]
        {"weeks": 20},
        {"weeks": 3},
        {"options": {"inconnue": 1}},
        {"options": {"lines": 4}},
        {"options": {"lines": 0}},
        {"options": {"lines": "2"}},
        {"options": {"plan": "z"}},
        {"pack": "absent"},
    ],
)
def test_game_params_refuse_what_the_pack_does_not_offer(usine_pack, bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GameParams(**params(**bad))


# --- Spec usine --------------------------------------------------------------------------------------------------


def test_hand_written_factory_spec_is_valid(usine_pack) -> None:
    spec = SimSpec.model_validate(factory_spec())
    assert spec.factory is not None and len(spec.factory.machines) == 4
    assert SimSpec.model_validate(spec.model_dump(mode="json")) == spec
    assert spec.factory.clock.days_per_turn == 5 and spec.factory.resources.technicians == 1  # défauts du cahier
    assert Clock().breaks == []  # facultatif : sans pauses du personnel, l'horloge reste celle du cahier


def test_lines_may_differ_in_length_and_a_panel_may_have_no_column(usine_pack) -> None:
    spec = factory_spec()
    spec["factory"]["machines"].append(machine(2, 3))
    spec["panels"].append({"id": "vide", "type": "flow", "title": "Flux", "placement": "tableau_de_bord",
                           "source": "factory.flow"})  # fmt: skip
    assert len(SimSpec.model_validate(spec).factory.machines) == 5


def edit(mutation) -> dict[str, Any]:
    spec = factory_spec()
    mutation(spec)
    return spec


@pytest.mark.parametrize(
    ("mutation", "words"),
    [
        # ligne
        (lambda s: s["factory"]["machines"].append(machine(3, 1)), ("ligne inconnue", "l3")),
        (lambda s: s["lines"].append({**s["lines"][0], "id": "l3"}), ("ligne l3 sans machine",)),
        (lambda s: s["factory"].update(product_id="zz"), ("produit inconnu",)),
        # rang
        (lambda s: s["factory"]["machines"].__setitem__(1, machine(1, 3)), ("rangs", "non contigus")),
        (lambda s: s["factory"]["machines"].__setitem__(1, machine(1, 1)), ("en double",)),
        (lambda s: s["factory"]["machines"][1].update(rank=1), ("incohérent",)),
        # nomenclature
        (lambda s: s["factory"]["bom"].append({"component_id": "zz", "per_unit": 2}), ("nomenclature", "zz")),
        # provenance
        (lambda s: s["provenance"].update({"x.y": {"status": "source"}}), ("sans citation",)),
        (lambda s: s["provenance"].update({"x.y": {"status": "calibre", "citation": "c"}}), ("sans note",)),
        (lambda s: s["provenance"].update({"x.y": {"status": "inventee", "note": "n"}}), ("status",)),
        # panneau
        (lambda s: s["panels"][0].update(source="inconnu.kpis"), ("panneau otif", "source inconnue")),
        (lambda s: s["panels"][1].update(station_kinds=["ecran_kpi"]), ("aucun poste de type ecran_kpi",)),
        (lambda s: s["panels"][0].update(source="Kpis"), ("source",)),
        (lambda s: s["panels"][0]["columns"][0].update(target="nope.otif"), ("panneau otif", "cible inconnue")),
        (lambda s: s["panels"].append(s["panels"][0]), ("panneau en double",)),
        (
            lambda s: (
                s["products"].append({**s["products"][0], "id": "p2", "line_id": "l2"})
                or s["lines"][1].update(product_id="p2")
            ),
            ("ligne l2", "différent de celui de l'usine"),
        ),
        # référence du monde
        (lambda s: s["world"]["objects"][0].update(ref="machine:l9-m9"), ("référence inconnue", "machine:l9-m9")),
        (lambda s: s["world"]["objects"][0].update(ref="mp:zz"), ("référence inconnue",)),
        (lambda s: s["world"]["objects"][0].update(ref="dept:zz"), ("référence inconnue",)),
        # créneaux du camion du client et des livraisons
        (lambda s: s["factory"]["customer"].update(pickup_window_min=(450, 360)), ("créneau d'enlèvement",)),
        (lambda s: s["factory"]["customer"].update(pickup_window_min=(0, 500)), ("créneau d'enlèvement", "480")),
        (lambda s: s["factory"]["logistics"].update(delivery_window_min=(100, 100)), ("créneau de livraison",)),
        (lambda s: s["factory"]["logistics"].update(delivery_window_min=(-5, 100)), ("créneau de livraison",)),
        # figurants, départements, monde
        (lambda s: s["factory"]["crew"][0].update(machine_id="l9-m1"), ("machine inconnue",)),
        (lambda s: s["factory"]["crew"][1].update(department_id="zz"), ("figurant ch1", "département inconnu")),
        (lambda s: s["agents"][0].update(department_id="zz"), ("agent agent_pilotage", "département inconnu")),
        (lambda s: s["stations"][0].update(department_id="zz"), ("poste machine_l1-m1", "département inconnu")),
        (lambda s: s["departments"].append(s["departments"][0]), ("département en double",)),
        (lambda s: s["departments"][0].update(area=(5, 0, 5, 3)), ("zone vide",)),
        (lambda s: s["world"].update(template="atelier"), ("world.template",)),
        # pack
        (lambda s: s["stations"][0].update(kind="hangar"), ("poste inconnu du pack usine", "hangar")),
        (lambda s: s["modules"][0].update(id="finance"), ("module inconnu du pack usine", "finance")),
        (lambda s: s["meta"].update(pack="atelier"), ("meta.pack",)),
    ],
)
def test_factory_spec_refuses_broken_references(usine_pack, mutation, words: tuple[str, ...]) -> None:
    refused(edit(mutation), *words)


def test_factory_ranges_are_checked_by_the_models() -> None:
    for change in ({"cycle_min": 0}, {"rank": 9}, {"defect_rate": 0.9}, {"weibull_shape": 0.5}, {"id": "L1-M1"}):
        with pytest.raises(ValidationError):
            SimSpec.model_validate(edit(lambda s, c=change: s["factory"]["machines"][0].update(c)))


@pytest.mark.parametrize(
    "breaks",
    [[(-5, 10)], [(100, 0)], [(100, -10)], [(470, 20)], [(100, 30), (120, 10)], [(100, 20), (100, 10)]],
)
def test_clock_breaks_stay_inside_the_day_without_overlap(breaks: list[tuple[int, int]]) -> None:
    with pytest.raises(ValidationError, match="pauses du personnel"):
        Clock(breaks=breaks)
    assert Clock(breaks=[(460, 20), (0, 10), (10, 5)]).breaks == [(460, 20), (0, 10), (10, 5)]  # bords et contiguïté


def test_new_factory_fields_have_their_defaults_and_bounds() -> None:
    customer = factory_spec()["factory"]["customer"]
    assert Customer(**customer).orders_per_day == 1 and Customer(**customer).pickup_window_min == (360, 450)
    for bad in ({"orders_per_day": 0}, {"orders_per_day": 11}):
        with pytest.raises(ValidationError):
            Customer(**customer | bad)
    assert Customer(**customer | {"orders_per_day": 10}).orders_per_day == 10
    factory = factory_spec()["factory"]
    assert Factory(**factory).protect_buffer == 30
    for bad in (0, 501):
        with pytest.raises(ValidationError):
            Factory(**factory | {"protect_buffer": bad})


def test_game_params_take_the_pack_defaults_for_absent_products_and_weeks(usine_pack) -> None:
    params = GameParams(pack="usine", theme="industrie", modules=["pilotage"])
    assert (params.products, params.weeks) == (1, 6)  # limits du pack : products [1, 1, 1], weeks [4, 12, 6]
    atelier = GameParams(theme="industrie", modules=["production"])
    assert (atelier.products, atelier.weeks) == (3, 8)  # défauts de l'atelier inchangés
    assert GameParams(pack="usine", theme="industrie", modules=["pilotage"], weeks=9).weeks == 9  # explicite gagne
    with pytest.raises(ValidationError):
        GameParams(pack="usine", theme="industrie", modules=["pilotage"], products=2)  # explicite hors limites
    with pytest.raises(ValidationError):
        GameParams(pack="absent", theme="industrie", modules=["pilotage"])  # pack inconnu dit par _check


def test_a_department_may_have_no_agent_and_no_station(usine_pack, tmp_path) -> None:
    quai = {"id": "quai", "label": "Quai partagé", "area": [-6, 8.5, 6, 15], "stations": [], "elements": []}
    write_pack(tmp_path, departments=[quai, {"id": "autre", "label": "Sans clé stations", "area": [0, 0, 1, 1]}])
    assert [d["id"] for d in load_pack("casse")["departments"]] == ["quai", "autre"]


def test_provenance_requires_its_origin() -> None:
    assert Provenance(status="source", citation="NF E60-182").note is None
    for bad in ({"status": "source"}, {"status": "calibre"}, {"status": "exemple", "citation": "c"}):
        with pytest.raises(ValidationError):
            Provenance(**bad)


# --- Chronologie -------------------------------------------------------------------------------------------------

# Exemple de l'annexe 0007 §3 : M3 en panne depuis 118,5 (une ligne ; une vraie chronologie a 481 instantanés)
STATES = ["arret", "marche", "pause", "reglage", "panne", "attente_matiere", "sortie_pleine"]
ANNEX_TIMELINE = {
    "week": 3, "days": 5, "minutes_per_day": 480, "day_start_h": 8, "frame_min": 5, "states": STATES,
    "machines": ["l1-m1", "l1-m2", "l1-m3", "l1-m4"], "counters": COUNTERS,
    "frames": [[125.0, [1, 6, 4, 5], [4, 10, 0, 2], [1840, 17, 2, 5, 0, 3, 6, 240, 0]]],
    "events": [
        [118.5, "panne", "l1-m3", {"duration_min": 60.0}],
        [118.5, "agent", "agent_maintenance", {"state": "deplacement", "at": "l1-m3", "until": 121.5}],
        [121.5, "reparation_debut", "l1-m3", {"by": "agent_maintenance"}],
    ],
}  # fmt: skip


def timeline(**changes: Any) -> dict[str, Any]:
    return copy.deepcopy(ANNEX_TIMELINE) | changes


def test_timeline_accepts_the_annex_example_and_the_fixed_codes() -> None:
    assert Timeline.model_validate(ANNEX_TIMELINE).frames[0][1] == [1, 6, 4, 5]
    assert STATES == list(get_args(MachineState))
    assert COUNTERS == ["mp", "en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf",
                        "expedie"]  # fmt: skip


def test_timeline_of_a_default_week_has_481_frames() -> None:
    times = frame_times(5, 480, 5)
    assert (len(times), times[0], times[-1], times[1]) == (481, 0, 2400, 5)
    assert frame_times(1, 100, 30) == [0, 30, 60, 90, 100]  # dernier instantané à la fin du tour
    frames = [[t, [1, 1, 1, 1], [0, 0, 0, 0], [0] * 9] for t in times]
    assert len(Timeline.model_validate(timeline(frames=frames)).frames) == 481


@pytest.mark.parametrize(
    "changes",
    [
        {"states": STATES[::-1]},  # l'index est la valeur des instantanés : ordre fixe
        {"states": STATES[:3]},
        {"counters": COUNTERS[:-1]},
        {"counters": COUNTERS[::-1]},
        {"frames": [[5, [1, 1, 1], [0, 0, 0, 0], [0] * 9]]},  # 3 états pour 4 machines
        {"frames": [[5, [1, 1, 1, 1], [0, 0, 0], [0] * 9]]},  # 3 tables
        {"frames": [[5, [1, 1, 1, 1], [0, 0, 0, 0], [0] * 8]]},  # 8 compteurs
        {"frames": [[5, [1, 1, 1, 7], [0, 0, 0, 0], [0] * 9]]},  # état 7 : hors de 0 à 6
        {"frames": [[5, [1, 1, 1, -1], [0, 0, 0, 0], [0] * 9]]},
        {"frames": [[5, [1, 1, 1, 1], [0, 0, 0, -1], [0] * 9]]},
        {"frames": [[5, [1] * 4, [0] * 4, [0] * 9], [5, [1] * 4, [0] * 4, [0] * 9]]},  # t pas strictement croissant
        {"frames": [[2401, [1] * 4, [0] * 4, [0] * 9]]},  # après la fin du tour
        {"frames": [[5, "marche", [0] * 4, [0] * 9]]},
        {"events": [[10, "panne", "l1-m1", {"duration_min": 5}], [9, "reglage", "l1-m1", {"duration_min": 5}]]},
        {"events": [[1, "explosion", "l1-m1", {}]]},
        {"events": [[1, "panne", "l1-m1", {}]]},  # données incomplètes
        {"events": [[1, "panne", "l1-m1", {"duration_min": 5, "extra": 1}]]},
        {"events": [[1, "agent", "a", {"state": "dort", "at": None, "until": None}]]},
    ],
)  # fmt: skip
def test_timeline_refuses_a_broken_shape(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Timeline.model_validate(timeline(**changes))


def test_every_event_kind_has_its_data_keys_and_agent_nulls_are_allowed() -> None:
    assert set(EVENT_DATA) == set(get_args(EventKind))
    event = [1, "agent", "chauffeur_client", {"state": "disponible", "at": None, "until": None}]
    assert Timeline.model_validate(timeline(events=[event])).events[0][3]["at"] is None
