"""Noyau de simulation d'usine (gmix.game.factory) : critères 1 à 6 de la tranche 1 de l'annexe 0007 sur les quatre
machines de l'exemple du cahier (docs/references/usine-3d). Les valeurs viennent du cahier ou du pack v0 ; chaque test
choisit celles qu'il neutralise (pannes, pauses, réglages, tables) pour isoler la règle qu'il vérifie."""

import copy
import hashlib
import json
import time
from typing import Any

import pytest

from gmix.game import factory
from gmix.game.spec import COUNTERS, Timeline

BREAKS = [(120, 10), (240, 20), (360, 10)]  # pack v0 : 2 x 10 + 1 x 20 min sur 480
CYCLES, MTBF_H, MTTR_H = (2, 1.5, 3, 1), (40, 80, 60, 100), (1, 0.5, 1, 0.5)
SETUPS, DEFECTS = (10, 5, 0, 5), (0.02, 0.01, 0.03, 0.02)
NEVER = 1e9  # MTBF « infini » : machine sans panne
OFFER = {"id": "o1", "component_id": "c1", "lead_time": 2, "reliability": 100, "unit_cost": 11, "min_order": 1}


def machine(line: int, rank: int, cycle_scale: float = 1, **change: Any) -> dict[str, Any]:
    i = rank - 1
    return {
        "id": f"l{line}-m{rank}", "line_id": f"l{line}", "rank": rank, "name": f"M{rank}", "operation": "op",
        "cycle_min": CYCLES[i] * cycle_scale, "run_min": 480, "stop_min": 0, "mtbf_h": MTBF_H[i],
        "weibull_shape": 2.0, "mttr_h": MTTR_H[i], "setup_min": SETUPS[i], "tool_life": None, "tool_change_min": 0,
        "defect_rate": DEFECTS[i], "buffer": 10, "transfer_min": 0.5 if rank < 4 else 0, "operators": 1,
        "asset": "prop_machine",
    } | change  # fmt: skip


def make_spec(
    lines: int = 1,
    *,
    seed: int = 1,
    days: int = 5,
    breaks: list[tuple[int, int]] = BREAKS,
    cycle_scale: float = 1,
    frame_min: float = 5,
    mp0: int = 100000,
    pf0: int = 0,
    machine_change: dict[str, Any] | None = None,
    resources: dict[str, int] | None = None,
    **logistics: Any,
) -> dict[str, Any]:
    """Spec minimale (clés lues par le noyau) : `lines` lignes de 4 machines du cahier, 24 produits par lot."""
    change = machine_change or {}
    machines = [machine(ln, r, cycle_scale, **change) for ln in range(1, lines + 1) for r in range(1, 5)]
    lg = {
        "units_per_pallet_mp": 100, "unload_min_per_pallet": 2, "inspect_min_per_pallet": 5,
        "supplier_nonconform_rate": 0.02, "delivery_window_min": [0, 120], "mp_capacity_pallets": 24,
        "kit_min": 8, "qc_min_per_unit": 0.7, "qc_block_threshold": 0.15, "units_per_case": 4, "cases_per_pallet": 6,
        "pack_min_per_case": 2, "wrap_min_per_pallet": 5, "pf_capacity_pallets": 20, "load_min_per_pallet": 2,
        "repair_travel_min": 3, "preventive_min": 20,
    } | logistics  # fmt: skip
    return {
        "seed": seed,
        "factory": {
            "product_id": "p1", "lot_size": 24, "pf_min": 40, "bom": [{"component_id": "c1", "per_unit": 1}],
            "machines": machines, "crew": [],
            "clock": {"days_per_turn": days, "minutes_per_day": 480, "day_start_h": 8, "frame_min": frame_min,
                      "breaks": [list(b) for b in breaks]},
            "logistics": lg,
            "customer": {"demand_per_day": 100, "variability": 0.1, "promised_days": 2, "orders_per_day": 1,
                         "pickup_window_min": [360, 450]},
            "resources": {"docks": 1, "forklifts": 1, "technicians": 1, "line_leads": 1} | (resources or {}),
            "costs": {"repair_per_h": 75, "preventive_per_intervention": 50, "operator_per_h": 28},
            "protect_buffer": 30,
        },
        "lines": [{"id": f"l{ln}"} for ln in range(1, lines + 1)],
        "components": [{"id": "c1", "initial_stock": mp0}],
        "products": [{"id": "p1", "initial_stock": pf0}],
        "agents": [{"id": "agent_maintenance"}, {"id": "agent_production"}],
    }  # fmt: skip


def no_failure(**kw: Any) -> dict[str, Any]:
    return make_spec(machine_change={"mtbf_h": NEVER} | kw.pop("machine_change", {}), **kw)


def play(spec: dict[str, Any], turns: int = 1, *, lots: int = 0, setting: dict | None = None, decide: Any = None,
         roundtrip: bool = False) -> tuple[Any, dict[str, Any], list[Any], list[Any]]:  # fmt: skip
    """Joue `turns` tours. Décisions : `lots` lots sur chaque ligne à chaque tour, ou `decide(plant, fs, turn)`."""
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    fs["settings"].update(setting or {})
    timelines, reports = [], []
    for turn in range(turns):
        for lid in plant.line_ids if lots else []:
            factory.launch_of(plant, fs, lid, lots)
        if decide:
            decide(plant, fs, turn)
        fs, timeline, report = factory.simulate(plant, fs, week=turn + 1)
        if roundtrip:
            fs = json.loads(json.dumps(fs))  # l'état passe par la base entre deux tours
        timelines.append(timeline)
        reports.append(report)
    return plant, fs, timelines, reports


def fingerprint(*objects: Any) -> str:
    return hashlib.sha256(json.dumps(objects, sort_keys=True).encode()).hexdigest()


def events(timeline: dict[str, Any], *kinds: str) -> list[list[Any]]:
    return [e for e in timeline["events"] if e[1] in kinds]


def force_failure(plant: factory.Plant, fs: dict[str, Any], machine_id: str, age_min: float) -> None:
    """Fait tomber une machine en panne quand elle a marché `age_min` minutes (seuil de risque cumulé fixé)."""
    i = plant.mids.index(machine_id)
    m = plant.machines[i]
    fs["machines"][i]["hazard"] = (age_min / plant.scale[i]) ** m["weibull_shape"]


# --- 1. Reproductibilité ---------------------------------------------------------------------------------------------


def busy_scenario(plant: factory.Plant, fs: dict[str, Any], turn: int) -> None:
    for lid in plant.line_ids:
        factory.launch_of(plant, fs, lid, 20)
    factory.order_mp(plant, fs, OFFER | {"reliability": 80}, 3)
    fs["settings"]["preventive"]["l1"] = "toutes"
    fs["settings"]["protect"]["l2"] = "releve_pauses"
    fs["settings"]["protect"]["l3"] = "tampon_avant"


def test_same_spec_and_decisions_give_the_same_state_and_timeline() -> None:
    spec = make_spec(lines=3, seed=7, machine_change={"mtbf_h": 3})
    runs = [play(spec, 3, decide=busy_scenario) for _ in range(2)]
    assert fingerprint(runs[0][1:]) == fingerprint(runs[1][1:])
    assert sum(len(t["events"]) for t in runs[0][2]) > 500  # le scénario fait vraiment quelque chose
    assert sum(m["failures"] for r in runs[0][3] for m in r["machines"].values()) > 5
    other = play(make_spec(lines=3, seed=8, machine_change={"mtbf_h": 3}), 3, decide=busy_scenario)
    assert fingerprint(other[1:]) != fingerprint(runs[0][1:])  # une autre graine, d'autres pannes et d'autre demande


def test_the_state_survives_a_json_round_trip_and_is_not_modified() -> None:
    spec = make_spec(lines=2, machine_change={"mtbf_h": 3})
    direct = play(spec, 3, decide=busy_scenario)
    stored = play(spec, 3, decide=busy_scenario, roundtrip=True)
    assert fingerprint(direct[1:]) == fingerprint(stored[1:])
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    factory.launch_of(plant, fs, "l1", 5)
    before = copy.deepcopy(fs)
    factory.simulate(plant, fs, 1)
    assert fs == before  # fonction pure


def test_two_teams_with_the_same_spec_have_the_same_breakdowns_whatever_they_decide() -> None:
    """Un flux de hasard par source : acheter ou non de la matière ne change ni les pannes ni la demande."""
    spec = make_spec(lines=1, seed=3, machine_change={"mtbf_h": 3})
    quiet = play(spec, 1, lots=20)
    busy = play(spec, 1, lots=20, decide=lambda p, fs, t: factory.order_mp(p, fs, OFFER, 2))
    failures = lambda run: [m["failures"] for m in run[3][0]["machines"].values()]  # noqa: E731
    assert failures(quiet) == failures(busy)
    orders = lambda run: [(e[2], e[3]) for e in events(run[2][0], "commande_client")]  # noqa: E731
    assert orders(quiet) == orders(busy) and len(orders(quiet)) == 5


# --- 2. Temps de lot et cadence --------------------------------------------------------------------------------------


def test_a_lot_of_20_takes_the_cahier_time_without_failures_breaks_or_setups() -> None:
    spec = no_failure(breaks=[], machine_change={"buffer": 500, "setup_min": 0}, kit_min=0)
    spec["factory"]["lot_size"] = 20
    _, _, timelines, _ = play(spec, 1, lots=1)
    start = events(timelines[0], "kit_livre")[0][0]
    end = events(timelines[0], "lot_termine")[0][0]
    # premier produit : 2 + 1,5 + 3 + 1 min de cycle + 3 transferts de 0,5 = 9 min, puis un produit toutes les 3 min
    assert end - start == pytest.approx(9 + 19 * 3)
    assert abs((end - start) - 67) <= 1


def test_setups_delay_the_first_products_of_a_lot() -> None:
    spec = no_failure(breaks=[], machine_change={"buffer": 500}, kit_min=0)
    _, _, timelines, _ = play(spec, 1, lots=1)
    first = events(timelines[0], "reglage")
    assert [e[2] for e in first] == ["l1-m1", "l1-m2", "l1-m4"]  # 10, 5 et 5 min ; aucun sur le goulot
    assert [e[3]["duration_min"] for e in first] == [10, 5, 5]
    end = events(timelines[0], "lot_termine")[0][0]
    # réglage de M1 (10), cycle (2), transfert (0,5), réglage de M2 (5), cycle (1,5), transfert, 1er cycle de M3 (3),
    # puis 23 produits de plus au rythme du goulot, transfert (0,5) et cycle de M4 (1) du dernier produit
    assert end == pytest.approx(10 + 2 + 0.5 + 5 + 1.5 + 0.5 + 3 + 23 * 3 + 0.5 + 1)


@pytest.mark.parametrize(
    ("change", "breaks", "share"),
    [({}, [], 1), ({"run_min": 110, "stop_min": 10}, [], 110 / 120), ({}, BREAKS, 440 / 480)],
    ids=["sans arrêt", "marche 110 / arrêt 10", "pauses 2 x 10 + 1 x 20"],
)
def test_a_line_runs_at_the_bottleneck_rate_times_the_share_of_working_time(change, breaks, share) -> None:
    spec = no_failure(breaks=breaks, machine_change={"buffer": 500} | change)
    _, _, _, reports = play(spec, 2, lots=40)  # tables larges ; le 2e tour est en régime établi
    out_h = reports[1]["lines"]["l1"]["out"] / 40
    assert out_h == pytest.approx(20 * share, abs=0.5)


def test_measured_throughput_matches_the_expected_formula() -> None:
    """expected_h (disponibilité x rendement cumulé) retrouve la cadence mesurée sur 40 graines, pannes comprises."""
    good = []
    for seed in range(40):
        _, _, _, reports = play(make_spec(seed=seed, cycle_scale=3), 3, lots=40)
        good += [r["lines"]["l1"]["good"] / 40 for r in reports[1:]]
    expected = reports[0]["lines"]["l1"]["expected_h"]  # cycles triplés : 6,67 / h x 0,9167 x 0,9828 x 0,9223
    assert sum(good) / len(good) == pytest.approx(expected, rel=0.05)


def test_expected_formulas_of_the_annex() -> None:
    plant = factory.Plant(make_spec(lines=2))
    factors = factory.trs_factors(plant, 0)
    assert factory.theoretical_h(plant, 0) == 20
    assert factors["disponibilite"] == pytest.approx((1 - 40 / 480) * 60 / (60 + 3 / 60 + 1))
    assert factors["qualite"] == pytest.approx(0.98 * 0.99 * 0.97 * 0.98)
    assert factory.expected_h(plant, 0) == pytest.approx(20 * factors["disponibilite"] * factors["qualite"])
    assert factory.expected_h(plant, 0, mtbf_factor=0.6) < factory.expected_h(plant, 0)
    assert plant.bottleneck == [2, 6]  # M3 de chaque ligne


# --- 3. Débit borné par le goulot, tables pleines et vides -----------------------------------------------------------


def test_a_line_never_beats_its_bottleneck_whatever_the_seed() -> None:
    for seed in range(10):
        _, _, _, reports = play(make_spec(lines=2, seed=seed), 2, lots=40)
        for report in reports:
            for line in report["lines"].values():
                assert line["out"] <= 2400 / 3 + 1  # un produit toutes les 3 min au plus, sur 2400 min
                assert line["good"] <= line["out"]


def test_a_full_table_stops_the_upstream_machine_and_an_empty_one_starves_the_downstream() -> None:
    spec = no_failure(breaks=[], machine_change={"buffer": 5})
    spec["factory"]["machines"][2]["cycle_min"] = 10  # M3 très lente : tout se bloque derrière elle
    _, _, timelines, _ = play(spec, 1, lots=20)
    frame = timelines[0]["frames"][40]  # t = 200 min
    states, tables = frame[1], frame[2]
    assert states == [6, 6, 1, 5]  # M1 et M2 : sortie_pleine ; M3 : marche ; M4 : attente_matiere
    assert tables[:2] == [5, 5] and tables[3] == 0


def test_a_line_without_work_is_stopped_not_starved() -> None:
    _, _, timelines, _ = play(no_failure(), 1)
    assert set(timelines[0]["frames"][100][1]) == {0}  # arret : aucun OF, rien à attendre


def test_protecting_the_bottleneck_with_a_buffer_enlarges_the_table_in_front_of_it() -> None:
    spec = no_failure(breaks=[], machine_change={"buffer": 10})
    spec["factory"]["machines"][2]["cycle_min"] = 10
    peaks = {}
    for mode in ("aucune", "tampon_avant"):
        _, _, timelines, _ = play(spec, 1, lots=20, setting={"protect": {"l1": mode}})
        peaks[mode] = max(f[2][1] for f in timelines[0]["frames"])  # table de sortie de M2, devant M3
    assert peaks == {"aucune": 10, "tampon_avant": 30}


def test_the_relief_keeps_the_bottleneck_running_during_the_breaks() -> None:
    spec = no_failure(machine_change={"buffer": 500})
    outs = {}
    for mode in ("aucune", "releve_pauses"):
        _, _, timelines, reports = play(spec, 2, lots=40, setting={"protect": {"l1": mode}})
        outs[mode] = reports[1]["lines"]["l1"]["out"]
    assert outs["releve_pauses"] / outs["aucune"] == pytest.approx(480 / 440, rel=0.02)  # +9 % de goulot
    assert reports[1]["relief_min"] == 200  # 5 jours x 40 min de pause relevés pour une ligne


# --- 4. Un seul technicien -------------------------------------------------------------------------------------------


def repairs(timeline: dict[str, Any]) -> list[tuple[float, float, float, str]]:
    """(panne, début de l'intervention y compris le trajet, fin, machine) de chaque réparation terminée."""
    out = []
    for fail in events(timeline, "panne"):
        end = next((e for e in events(timeline, "reparation_fin") if e[2] == fail[2] and e[0] >= fail[0]), None)
        start = next((e for e in events(timeline, "reparation_debut") if e[2] == fail[2] and e[0] >= fail[0]), None)
        if start and end:
            out.append((fail[0], start[0] - 3, end[0], fail[2]))
    return sorted(out, key=lambda r: r[1])


@pytest.mark.parametrize(("technicians", "overlap"), [(1, False), (2, True)])
def test_a_single_technician_never_repairs_two_machines_at_once(technicians, overlap) -> None:
    spec = make_spec(lines=3, machine_change={"mtbf_h": 0.5, "weibull_shape": 1.0, "mttr_h": 0.25},
                     resources={"technicians": technicians})  # fmt: skip
    _, _, timelines, _ = play(spec, 1, lots=20)
    done = repairs(timelines[0])
    assert len(done) > 20
    for fail, start, end, _ in done:
        assert end - start == pytest.approx(3 + 15, abs=0.03)  # trajet 3 min + MTTR 15 min
        assert start >= fail - 0.03
    clashes = sum(1 for a, b in zip(done, done[1:], strict=False) if b[1] < a[2] - 0.03)
    assert (clashes > 0) is overlap
    waited = sum(1 for fail, start, *_ in done if start > fail + 0.03)
    assert waited > 0 or technicians == 2  # avec un seul technicien, des pannes attendent


def test_repairs_follow_the_arrival_order_or_the_bottlenecks_first() -> None:
    spec = no_failure(lines=3, breaks=[])
    order = {}
    for priority in ("arrivee", "goulot"):
        plant = factory.Plant(spec)
        fs = factory.initial_state(plant)
        for lid in plant.line_ids:
            factory.launch_of(plant, fs, lid, 5)
        fs["settings"]["priority"] = priority
        for mid, age in (("l2-m1", 1.5), ("l3-m1", 1.0), ("l1-m3", 9.0)):  # tombent vers 27,5, 35 et 36,5 min
            force_failure(plant, fs, mid, age)
        _, timeline, _ = factory.simulate(plant, fs, 1)
        order[priority] = [e[2] for e in events(timeline, "reparation_debut")][:3]
    assert order == {"arrivee": ["l2-m1", "l3-m1", "l1-m3"], "goulot": ["l2-m1", "l1-m3", "l3-m1"]}


# --- 5. Préventif ----------------------------------------------------------------------------------------------------


def test_preventive_maintenance_reduces_wear_failures_but_not_random_ones() -> None:
    """Sur 50 graines : avec une loi de Weibull de forme 2 (usure) le préventif divise les pannes ; avec une forme de 1
    (loi sans mémoire, pannes au hasard) il ne change rien de significatif."""
    totals: dict[tuple[float, str], int] = {}
    for shape in (2.0, 1.0):
        for mode in ("aucune", "toutes"):
            count = 0
            for seed in range(50):
                spec = make_spec(seed=seed, cycle_scale=8, frame_min=60, machine_change={"weibull_shape": shape})
                _, _, _, reports = play(spec, 3, lots=10, setting={"preventive": {"l1": mode}})
                count += sum(m["failures"] for r in reports for m in r["machines"].values())
            totals[shape, mode] = count
    wear = 1 - totals[2.0, "toutes"] / totals[2.0, "aucune"]
    random_ = 1 - totals[1.0, "toutes"] / totals[1.0, "aucune"]
    assert wear > 0.30, totals
    assert abs(random_) < 0.20, totals
    assert wear > random_ + 0.2


def test_a_preventive_in_a_pause_costs_no_production_and_resets_the_age() -> None:
    spec = no_failure()
    outs, ages = {}, {}
    for mode in ("aucune", "goulot"):
        _, _, timelines, reports = play(spec, 1, lots=40, setting={"preventive": {"l1": mode}})
        outs[mode] = reports[0]["lines"]["l1"]["out"]
        ages[mode] = reports[0]["machines"]["l1-m3"]["age_min"]
    assert outs["goulot"] == outs["aucune"]  # la pause de 20 min est la durée du préventif
    assert ages["goulot"] < ages["aucune"]
    done = events(timelines[0], "preventif")
    assert [(e[0], e[2], e[3]["duration_min"]) for e in done] == [(260, "l1-m3", 20)]  # pause de 12 h 00 du jour 1
    assert reports[0]["costs"]["preventive"] == 50


def test_a_breakdown_comes_before_a_preventive_which_moves_to_the_next_slot() -> None:
    spec = no_failure()
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    factory.launch_of(plant, fs, "l1", 20)
    fs["settings"]["preventive"]["l1"] = "goulot"
    force_failure(
        plant, fs, "l1-m3", 190
    )  # tombe vers 228 min, avant la pause de 240 : le technicien répare jusqu'à 291
    _, timeline, report = factory.simulate(plant, fs, 1)
    panne = events(timeline, "panne")[0][0]
    assert 220 < panne < 240
    fin = events(timeline, "reparation_fin")[0][0]
    assert fin > 280
    prev = events(timeline, "preventif")
    assert [(e[0], e[2]) for e in prev] == [(380, "l1-m3")]  # pause de 14 h 00 du jour 1 (10 min) + 20 min de préventif
    assert report["preventive"] == {"done": ["l1-m3"], "skipped": []}


def test_a_preventive_with_no_free_slot_is_reported_as_skipped() -> None:
    spec = no_failure(breaks=[(120, 10)], days=1)
    _, _, _, reports = play(spec, 1, lots=5, setting={"preventive": {"l1": "toutes"}})
    assert reports[0]["preventive"]["done"] == ["l1-m3"]  # un seul créneau dans le tour
    assert reports[0]["preventive"]["skipped"] == ["l1-m1", "l1-m2", "l1-m4"]


# --- 6. Bilan matière ------------------------------------------------------------------------------------------------


def test_material_balance_each_turn() -> None:
    """MP consommée = nomenclature x unités lancées ; unités lancées = encours + bons + rebut (partout dans l'usine)."""
    spec = make_spec(lines=3, seed=5, machine_change={"mtbf_h": 4})
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    launched = 0
    for turn in range(4):
        for lid in plant.line_ids:
            factory.launch_of(plant, fs, lid, 25)
        fs, timeline, report = factory.simulate(plant, fs, turn + 1)
        launched_turn = fs["totals"]["launched"] - launched
        launched = fs["totals"]["launched"]
        assert report["consumed_mp"] == 1 * launched_turn  # per_unit = 1
        assert fs["mp"]["units"] == 100000 - 1 * launched
        last = dict(zip(COUNTERS, timeline["frames"][-1][3], strict=True))
        in_plant = last["en_cours"] + last["a_controler"] + last["conforme"] + last["emballe"] + last["stock_pf"]
        assert launched == in_plant + fs["totals"]["shipped"] + fs["totals"]["scrap"]
        assert fs["totals"]["good"] + fs["totals"]["scrap"] <= launched
        assert launched > 0 and fs["totals"]["scrap"] > 0


def test_the_material_stock_follows_the_deliveries_and_the_kits() -> None:
    spec = no_failure(mp0=0, supplier_nonconform_rate=0.3)

    def buy(plant, fs, turn):
        if turn == 0:
            factory.order_mp(plant, fs, OFFER | {"lead_time": 1}, 6)
        factory.launch_of(plant, fs, "l1", 5)

    plant, fs, timelines, reports = play(spec, 2, decide=buy)
    delivered = sum(e[3]["quantity"] for t in timelines for e in events(t, "livraison_mp"))
    quarantined = sum(e[3]["quantity"] for t in timelines for e in events(t, "non_conforme"))
    assert delivered + quarantined == 600
    assert 0 < quarantined < 600
    consumed = sum(r["consumed_mp"] for r in reports)
    assert fs["mp"]["units"] == delivered - consumed and fs["mp"]["quarantine"] == quarantined
    assert fs["totals"]["received"] == delivered


# --- Autres règles de la tranche 1 -----------------------------------------------------------------------------------


def test_purchase_orders_arrive_after_their_lead_time_inside_the_delivery_window() -> None:
    spec = no_failure(mp0=0, supplier_nonconform_rate=0)

    def buy(plant, fs, turn):
        factory.order_mp(plant, fs, OFFER | {"lead_time": 2}, 4)

    _, fs, timelines, _ = play(spec, 1, decide=buy)
    delivery = events(timelines[0], "livraison_mp")[0]
    # camion le jour 2 (t de 960 à 1080), 4 palettes déchargées (2 min) puis contrôlées (5 min) l'une après l'autre
    assert 960 + 4 * 7 <= delivery[0] <= 1080 + 4 * 7 + 1
    assert delivery[3] == {"component_id": "c1", "quantity": 400}
    assert events(timelines[0], "non_conforme") == [] and fs["mp"]["units"] == 400 and fs["pending"] == []


def test_a_late_supplier_delivers_the_next_working_day() -> None:
    spec = no_failure(mp0=0, supplier_nonconform_rate=0)
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    factory.order_mp(plant, fs, OFFER | {"lead_time": 1}, 2)
    _, timeline, _ = factory.simulate(plant, fs, 1, effects={"delay_risk": 1.0})  # certitude du retard
    assert 2 * 480 <= events(timeline, "livraison_mp")[0][0] <= 2 * 480 + 120 + 14 + 1  # J+1 devient J+2
    _, timeline, _ = factory.simulate(plant, fs, 1)  # fiabilité 100 % : à l'heure
    assert 480 <= events(timeline, "livraison_mp")[0][0] <= 480 + 120 + 14 + 1


def test_the_nonconform_effect_sends_more_pallets_to_quarantine() -> None:
    spec = no_failure(mp0=0, supplier_nonconform_rate=0)
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    for _ in range(4):
        factory.order_mp(plant, fs, OFFER | {"lead_time": 1}, 6)
    clean, _, _ = factory.simulate(plant, fs, 1)
    dirty, _, report = factory.simulate(plant, fs, 1, effects={"nonconform": 0.5})
    assert clean["mp"]["quarantine"] == 0 and dirty["mp"]["quarantine"] > 600
    assert report["reception"]["quarantined"] == dirty["mp"]["quarantine"]


def test_a_line_without_material_waits_and_counts_the_days_it_is_stopped() -> None:
    spec = no_failure(mp0=0)
    _, _, timelines, reports = play(spec, 1, lots=5)
    line = reports[0]["lines"]["l1"]
    assert line["out"] == 0 and line["stockout_days"] == 5 and line["stockout_min"] == pytest.approx(2400)
    assert set(timelines[0]["frames"][30][1]) == {5}  # attente_matiere : un OF attend sa matière


def test_orders_are_shipped_complete_on_the_promised_day_or_counted_late() -> None:
    stocked = play(no_failure(pf0=2400), 1)[3][0]["orders"]
    assert stocked["due"] == 3 and stocked["otif"] == 100  # jours 0 à 2 : échéances J+2 à J+4 dans le tour
    empty = play(no_failure(pf0=0), 1)[3][0]["orders"]
    assert empty["on_time"] == 0 and empty["late"] == empty["due"] == 3 and empty["otif"] == 0
    _, fs, timelines, _ = play(no_failure(pf0=2400), 1)
    sent = events(timelines[0], "expedition")
    assert len(sent) == 5 and all(e[3]["on_time"] for e in sent)
    assert fs["pf"]["units"] == 2400 - sum(e[3]["quantity"] for e in sent)
    assert {o["status"] for o in fs["orders"]} == {"livree"}


def test_an_unshipped_order_is_late_once_its_day_has_passed() -> None:
    _, fs, _, _ = play(no_failure(pf0=0), 1)
    assert [o["status"] for o in fs["orders"]].count(
        "en_retard"
    ) == 3  # commandes des jours 0 à 2 échues (J+2) ; les 2 autres restent ouvertes


def test_a_lot_goes_through_control_packing_and_the_warehouse() -> None:
    _, fs, timelines, reports = play(no_failure(), 1, lots=5)
    good = reports[0]["lines"]["l1"]["good"]
    assert reports[0]["controlled"] == 120 and reports[0]["lines"]["l1"]["scrap"] == 120 - good
    assert reports[0]["packed"]["cases"] == good // 4
    pallets = events(timelines[0], "palette")
    assert all(e[3]["quantity"] == 24 for e in pallets) and len(pallets) == good // 24
    assert [e[1] for e in timelines[0]["events"] if e[1] in ("of_lance", "lot_termine")].count("lot_termine") == 5
    assert fs["ofs"][0]["status"] == "termine" and fs["ofs"][0]["good"] == good


def test_a_full_warehouse_blocks_the_packing_station() -> None:
    spec = no_failure(pf_capacity_pallets=2)
    _, fs, timelines, _ = play(spec, 2, lots=40)
    assert fs["pf"]["units"] <= 2 * 24
    assert fs["pack"]["wait"] is True and fs["pack"]["conf"] > 24  # des bons attendent l'emballage, la ligne s'arrête


def test_rack_capacity_keeps_extra_pallets_at_the_reception() -> None:
    spec = no_failure(mp0=0, mp_capacity_pallets=3, supplier_nonconform_rate=0)

    def buy(plant, fs, turn):
        factory.order_mp(plant, fs, OFFER | {"lead_time": 1}, 5)

    _, fs, _, _ = play(spec, 1, decide=buy)
    assert fs["mp"]["units"] == 300 and fs["mp"]["staged"] == 2  # 3 palettes au rack, 2 à la dépose
    plant = factory.Plant(spec)
    factory.launch_of(plant, fs, "l1", 5)
    fs, _, _ = factory.simulate(plant, fs, 2)
    # 5 kits de 24 : le rack (palettes entamées comprises) fait de la place pour une palette, pas pour la seconde
    assert fs["mp"]["staged"] == 1 and fs["mp"]["units"] == 300 - 120 + 100


def test_the_timeline_follows_the_contract_and_the_budgets() -> None:
    spec = make_spec(lines=3, seed=2, machine_change={"mtbf_h": 8})
    plant = factory.Plant(spec)
    fs = factory.initial_state(plant)
    fs["settings"]["preventive"] = dict.fromkeys(plant.line_ids, "goulot")
    durations = []
    for turn in range(12):
        busy_scenario(plant, fs, turn)
        started = time.perf_counter()
        fs, timeline, _ = factory.simulate(plant, fs, turn + 1)
        durations.append(time.perf_counter() - started)
        if turn in (0, 11):
            checked = Timeline.model_validate(timeline)
            assert len(checked.frames) == 481 and checked.machines == plant.mids
            assert len(json.dumps(timeline)) < 200_000
            assert len(json.dumps(fs)) < 64_000
    assert min(durations) < 0.150, durations  # advance < 150 ms (3 lignes x 4 machines, charge pleine)
    assert fs["day"] == 60
