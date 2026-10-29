"""Noyau de simulation d'usine (docs/decisions/0007, annexe §1 à §3) : un tour est une suite de jours de
`minutes_per_day` minutes simulées, calculée par événements discrets (`heapq`). Fonction pure : l'état JSON d'entrée
n'est pas modifié, l'état de sortie est un nouveau dictionnaire, la chronologie (`Timeline`) est rendue à part.
Ni entrée-sortie, ni horloge, ni modèle : le hasard vient de flux `random.Random` par source (machine, fournisseur,
client), dérivés de la graine de la spec par une chaîne de caractères (stable d'un processus à l'autre).

Le temps est continu d'un tour au suivant (la nuit et le week-end n'existent pas) : les événements qui dépassent la
fin du tour sont gardés dans l'état, avec des dates relatives, et reprennent au tour suivant.

Flux : commande d'achat -> camion (quai) -> déchargement -> contrôle des palettes (quarantaine) -> stock MP -> kit
d'un lot (chariot) -> machine 1 -> ... -> machine k (tables d'attente) -> contrôle (bon ou rebut) -> emballage ->
entrepôt PF -> camion du client (quai). Les postes (réception, chariot, contrôle, emballage, entrepôt) s'arrêtent
aux pauses `Clock.breaks` ; le technicien et le quai non. Tout nombre vient de la spec (donc du pack) ; les seules
règles propres au moteur sont écrites en constantes ci-dessous.
"""

import bisect
import copy
import heapq
import math
import random
from collections import deque
from typing import Any, get_args

from gmix.game.spec import COUNTERS, MachineState, frame_times

STATES = get_args(MachineState)
ARRET, MARCHE, PAUSE, REGLAGE, PANNE, ATTENTE, PLEINE = range(7)  # index dans STATES
IDLE, SETUP, RUN, BLOCKED = range(4)  # phase du produit tenu par une machine
SUPPLIER_LATE_DAYS = 1  # pack usine : fournisseur.retard_jours (calibre) ; une livraison en retard arrive le lendemain
KEPT_ORDERS = 10  # commandes et OF clos gardés dans l'état
KEPT_LOTS = 60  # correspondances lot -> OF gardées
INF = float("inf")
FRAME_PRIO = 9  # un instantané voit l'état après tous les événements datés du même instant
SPAN_KINDS = {"mdone", "mfail", "msetup", "mostop"}  # événements de machine qui portent un jeton de génération


class Plant:
    """Constantes d'une usine, lues une fois dans `spec["factory"]` (le moteur peut la garder pour tous les tours)."""

    def __init__(self, spec: dict[str, Any]) -> None:
        f = spec["factory"]
        if len(f["bom"]) != 1:
            raise ValueError(
                "Une seule matière par produit en tranche 1 (nomenclature à plusieurs articles : tranche 3)"
            )
        clock, self.lg, self.cu, self.rs, self.costs = (
            f["clock"],
            f["logistics"],
            f["customer"],
            f["resources"],
            f["costs"],
        )
        self.seed = spec["seed"]
        self.mpd, self.days, self.start_h, self.frame_min = (
            clock["minutes_per_day"], clock["days_per_turn"], clock["day_start_h"], clock["frame_min"],
        )  # fmt: skip
        self.T = self.days * self.mpd
        self.breaks = sorted((s, d) for s, d in clock["breaks"])
        self.lot_size, self.pf_min, self.protect = f["lot_size"], f["pf_min"], f["protect_buffer"]
        self.component, self.per_unit = f["bom"][0]["component_id"], f["bom"][0]["per_unit"]
        self.need = math.ceil(self.lot_size * self.per_unit)  # matière d'un kit (un lot)
        self.upp = self.lg["units_per_pallet_mp"]
        self.pallet_pf = self.lg["units_per_case"] * self.lg["cases_per_pallet"]
        used = {m["line_id"] for m in f["machines"]}
        self.line_ids = [line["id"] for line in spec["lines"] if line["id"] in used]
        rank = {lid: i for i, lid in enumerate(self.line_ids)}
        self.machines = sorted(f["machines"], key=lambda m: (rank[m["line_id"]], m["rank"]))
        self.mids = [m["id"] for m in self.machines]
        self.n, self.nl = len(self.machines), len(self.line_ids)
        self.line_machines: list[list[int]] = [[] for _ in self.line_ids]
        self.line_of = []
        for i, m in enumerate(self.machines):
            self.line_of.append(rank[m["line_id"]])
            self.line_machines[rank[m["line_id"]]].append(i)
        self.first = [ms[0] for ms in self.line_machines]
        self.last = [ms[-1] for ms in self.line_machines]
        self.bottleneck = [  # le goulot est la machine la plus lente de la ligne (la première en cas d'égalité)
            max(ms, key=lambda i: self.machines[i]["cycle_min"]) for ms in self.line_machines
        ]
        self.scale = [m["mtbf_h"] * 60 / math.gamma(1 + 1 / m["weibull_shape"]) for m in self.machines]
        self.agents = {a["id"] for a in spec["agents"]} | {c["id"] for c in f["crew"]}
        self.mp0 = next(c["initial_stock"] for c in spec["components"] if c["id"] == self.component)
        self.pf0 = next(p["initial_stock"] for p in spec["products"] if p["id"] == f["product_id"])


def _rng(plant: Plant, *key: Any) -> random.Random:
    return random.Random(":".join(str(k) for k in (plant.seed, *key)))


def _hazard(rng: random.Random) -> float:
    """Seuil de risque cumulé tiré à chaque remise à zéro de l'âge : la panne arrive quand (âge / échelle)^forme
    l'atteint (loi de Weibull ; avec une forme de 1, loi exponentielle sans mémoire)."""
    return -math.log(1.0 - rng.random())


def initial_state(plant: Plant) -> dict[str, Any]:
    ids = plant.line_ids
    return {
        "day": 0,
        "seq": 0,
        "ids": {"lot": 0, "of": 0, "po": 0, "co": 0},
        "settings": {
            "preventive": dict.fromkeys(ids, "aucune"),
            "priority": "arrivee",
            "protect": dict.fromkeys(ids, "aucune"),
        },
        "machines": [
            {
                "cur": None,
                "phase": IDLE,
                "rem_setup": 0.0,
                "rem_cycle": 0.0,
                "seg": None,
                "gen": 0,
                "ostop": False,
                "down": 0,
                "age": 0.0,
                "hazard": _hazard(_rng(plant, "panne", 0, mid)),
                "rsince": 0.0,
                "last_lot": None,
                "fail_t": None,
                "wake": None,
            }
            for mid in plant.mids
        ],  # fmt: skip
        "tables": [[] for _ in plant.mids],
        "pools": [[] for _ in ids],
        "ofs": [],
        "lot_of": {},
        "lot_left": {},
        "mp": {"units": plant.mp0, "staged": 0, "quarantine": 0, "reserved": 0},
        "inflight": [0] * plant.nl,
        "starve": [None] * plant.nl,
        "pending": [],
        "receiving": {},
        "dock": {"busy": 0, "queue": []},
        "insp": {"busy": False, "queue": []},
        "orders": [],
        "loading": {},
        "pf": {"units": plant.pf0},
        "qc": {"busy": False, "wake": None},
        "pack": {"conf": 0, "busy": None, "cases": 0, "units": 0, "wait": False},
        "tech": {"busy": 0, "queue": []},
        "fk": {"busy": 0},
        "events": [],
        "totals": {"launched": 0, "scrap": 0, "good": 0, "out": 0, "shipped": 0, "received": 0},
    }


# --- Décisions des joueurs (appelées par les handlers du moteur sur un état déjà copié) ----------------------------


def launch_of(plant: Plant, fs: dict[str, Any], line_id: str, lots: int) -> str:
    """Ordre de fabrication de `lots` lots sur une ligne ; les OF d'une ligne passent dans l'ordre de lancement."""
    if line_id not in plant.line_ids or lots < 1:
        raise ValueError("Ligne inconnue ou nombre de lots invalide")
    fs["ids"]["of"] += 1
    of_id = f"of{fs['ids']['of']}"
    fs["ofs"].append(
        {"id": of_id, "line_id": line_id, "quantity": lots * plant.lot_size, "lots": lots, "kitted": 0, "out": 0,
         "good": 0, "status": "attente"}
    )  # fmt: skip
    return of_id


def order_mp(plant: Plant, fs: dict[str, Any], offer: dict[str, Any], pallets: int) -> str:
    """Commande d'achat d'un camion de `pallets` palettes ; livrée `lead_time` jours ouvrés plus tard (si le fournisseur
    est à l'heure : fiabilité de l'offre)."""
    if pallets < offer["min_order"] or offer["component_id"] != plant.component:
        raise ValueError("Commande inférieure au minimum du fournisseur ou matière inconnue")
    fs["ids"]["po"] += 1
    po_id = f"po{fs['ids']['po']}"
    fs["pending"].append(
        {"id": po_id, "offer_id": offer["id"], "component_id": offer["component_id"], "pallets": pallets,
         "ordered_day": fs["day"], "due_day": fs["day"] + offer["lead_time"], "reliability": offer["reliability"],
         "unit_cost": offer["unit_cost"], "eta_day": None, "eta_min": None}
    )  # fmt: skip
    return po_id


# --- Formules attendues (annexe §2) -------------------------------------------------------------------------------


def break_share(plant: Plant) -> float:
    return sum(d for _, d in plant.breaks) / plant.mpd


def trs_factors(plant: Plant, line: int, mtbf_factor: float = 1.0) -> dict[str, float]:
    """Disponibilité, performance et qualité attendues d'une ligne, mesurées sur son goulot (le TRS est leur produit).
    Disponibilité = part du temps hors pauses x marche entre arrêts propres x MTBF / (MTBF + trajet + MTTR)."""
    b = plant.machines[plant.bottleneck[line]]
    own = b["run_min"] / (b["run_min"] + b["stop_min"]) if b["stop_min"] > 0 else 1.0
    mtbf_h = b["mtbf_h"] * mtbf_factor
    repair = mtbf_h / (mtbf_h + plant.lg["repair_travel_min"] / 60 + b["mttr_h"])
    quality = math.prod(1 - plant.machines[i]["defect_rate"] for i in plant.line_machines[line])
    return {"disponibilite": (1 - break_share(plant)) * own * repair, "performance": 1.0, "qualite": quality}


def theoretical_h(plant: Plant, line: int) -> float:
    return 60 / plant.machines[plant.bottleneck[line]]["cycle_min"]


def expected_h(plant: Plant, line: int, mtbf_factor: float = 1.0) -> float:
    """Bons par heure attendus : 60 / cycle du goulot x disponibilité x rendement cumulé de la ligne (annexe §2)."""
    f = trs_factors(plant, line, mtbf_factor)
    return theoretical_h(plant, line) * f["disponibilite"] * f["qualite"]


# --- Simulation d'un tour -----------------------------------------------------------------------------------------


class _M:
    """Une machine pendant un tour (les constantes viennent de la spec, le reste de l'état)."""

    __slots__ = (
        "i", "id", "line", "is_first", "is_last", "cycle", "setup", "defect", "transfer", "scale", "shape", "mttr",
        "run_min", "stop_min", "cur", "phase", "rem_setup", "rem_cycle", "seg", "gen", "ostop", "down", "age", "hazard",
        "rsince", "last_lot", "fail_t", "wake", "st", "st_t", "bk", "produced", "defects", "failures", "rng",
    )  # fmt: skip


class _Sim:
    def __init__(self, plant: Plant, fs: dict[str, Any], week: int, effects: dict[str, float]) -> None:
        P = self.P = plant
        self.fs = fs
        self.week = week
        self.effects = effects
        self.T = float(P.T)
        self.now = 0.0
        self.in_break = False
        self.mtbf_factor = effects.get("mtbf", 1.0)
        self.h: list[tuple[Any, ...]] = []
        for dt, prio, seq, kind, a, b in fs["events"]:
            self.h.append((dt, prio, seq, kind, a, b))
        heapq.heapify(self.h)
        self.seq = fs["seq"]
        self.events: list[list[Any]] = []
        self.astate: dict[str, tuple[Any, ...]] = {}
        # calendrier des pauses (un jour de plus que le tour : une tâche de fin de tour peut le déborder)
        self.cal = [(d * P.mpd + s, d * P.mpd + s + dur) for d in range(P.days + 1) for s, dur in P.breaks]
        self.cal_e = [e for _, e in self.cal]
        self.slots = self.cal[: P.days * len(P.breaks)]
        settings = fs["settings"]
        self.settings = settings
        # tables d'attente : tampon avant le goulot
        self.cap = [m["buffer"] for m in P.machines]
        self.relieved: set[int] = set()
        self.slot_owner: dict[int, int] = {}
        for ln, lid in enumerate(P.line_ids):
            mode = settings["protect"].get(lid, "aucune")
            b = P.bottleneck[ln]
            if mode == "tampon_avant" and b != P.first[ln]:
                self.cap[b - 1] = max(self.cap[b - 1], P.protect)
            elif mode == "releve_pauses":
                self.relieved.add(b)
        self.M: list[_M] = []
        for i, (mc, ms) in enumerate(zip(P.machines, fs["machines"], strict=True)):
            m = _M()
            m.i, m.id, m.line = i, mc["id"], P.line_of[i]
            m.is_first, m.is_last = P.first[m.line] == i, P.last[m.line] == i
            m.cycle, m.setup, m.defect, m.transfer = (
                mc["cycle_min"],
                mc["setup_min"],
                mc["defect_rate"],
                mc["transfer_min"],
            )
            m.scale, m.shape, m.mttr = P.scale[i], mc["weibull_shape"], mc["mttr_h"] * 60
            m.run_min, m.stop_min = mc["run_min"], mc["stop_min"]
            for key in ("cur", "phase", "rem_setup", "rem_cycle", "seg", "gen", "ostop", "down", "age", "hazard",
                        "rsince", "last_lot", "fail_t", "wake"):  # fmt: skip
                setattr(m, key, ms[key])
            m.bk, m.produced, m.defects, m.failures = [0.0] * 7, 0, 0, 0
            m.rng = _rng(P, "machine", week, mc["id"])
            m.st, m.st_t = ARRET, 0.0
            self.M.append(m)
        self.tables = [deque((r, c) for r, c in t) for t in fs["tables"]]
        self.pools = [deque([lot, n] for lot, n in pool) for pool in fs["pools"]]
        self.pool_n = [sum(n for _, n in pool) for pool in self.pools]
        self.ofd = {of["id"]: of for of in fs["ofs"]}
        self.ofq = [
            deque(of for of in fs["ofs"] if of["line_id"] == lid and of["kitted"] < of["lots"]) for lid in P.line_ids
        ]
        self.lots_left = [sum(of["lots"] - of["kitted"] for of in q) for q in self.ofq]
        self.inline = [sum(len(self.tables[i]) + (self.M[i].cur is not None) for i in ms) for ms in P.line_machines]
        self.lot_of = {int(k): v for k, v in fs["lot_of"].items()}
        self.lot_left = {int(k): v for k, v in fs["lot_left"].items()}
        mp = fs["mp"]
        self.mp, self.staged, self.quar, self.res = mp["units"], mp["staged"], mp["quarantine"], mp["reserved"]
        self.inflight = fs["inflight"]
        self.starve = fs["starve"]
        self.pending = fs["pending"]
        self.receiving = fs["receiving"]
        self.dock_busy, self.dock_q = fs["dock"]["busy"], fs["dock"]["queue"]
        self.insp_busy, self.insp_q = fs["insp"]["busy"], deque(tuple(x) for x in fs["insp"]["queue"])
        self.orders = fs["orders"]
        self.loading = fs["loading"]
        self.pf = fs["pf"]["units"]
        self.qc_busy, self.qc_wake = fs["qc"]["busy"], fs["qc"]["wake"]
        pk = fs["pack"]
        self.conf, self.pk_busy, self.pk_cases, self.pk_units, self.pk_wait = (
            pk["conf"], pk["busy"], pk["cases"], pk["units"], pk["wait"],
        )  # fmt: skip
        self.tech_busy, self.repair_q = fs["tech"]["busy"], [tuple(x) for x in fs["tech"]["queue"]]
        self.fk_busy = fs["fk"]["busy"]
        self.totals = fs["totals"]
        # compteurs du tour
        self.out = [0] * P.nl
        self.good = [0] * P.nl
        self.scrap = [0] * P.nl
        self.entered = [0] * P.nl
        self.kits = [0] * P.nl
        self.starve_min = [0.0] * P.nl
        self.starve_days: set[tuple[int, int]] = set()
        self.scrap_turn = self.shipped_turn = 0
        self.consumed = 0
        self.received = {"trucks": 0, "pallets": 0, "accepted": 0, "quarantined": 0, "wait_min": 0.0}
        self.tech_stats = {"repairs": 0, "wait_min": 0.0, "waited": 0, "busy_min": 0.0}
        self.prev_done: list[str] = []
        self.prev_skipped: list[str] = []
        self.costs = {"repair": 0.0, "preventive": 0.0}
        self.dock_stats = {"wait_min": 0.0, "busy_min": 0.0}
        self.fk_busy_min = 0.0
        self.relief_min = 0.0
        self.frames: list[list[Any]] = []
        self.qc_count = 0
        self.packed = {"cases": 0, "pallets": 0}
        self.not_last = [i for i in range(P.n) if i not in P.last]
        self.disp = {
            "mdone": self._mdone, "mfail": self._mfail, "msetup": self._msetup, "mostop": self._mostop,
            "moresume": self._moresume, "mwake": self._mwake, "bs": self._bs, "be": self._be, "day": self._day,
            "pick": self._pick, "truck": self._truck, "unl": self._unl, "insp": self._insp, "kit": self._kit,
            "qc": self._qc, "qcw": self._qcw, "case": self._case, "wrap": self._wrap, "load": self._load,
            "rstart": self._rstart, "rep": self._rep, "prv": self._prv, "frame": self._frame,
        }  # fmt: skip

    # -- mécanique ---------------------------------------------------------------------------------------------------

    def _push(self, t: float, kind: str, a: Any = 0, b: Any = 0, prio: int = 0) -> None:
        heapq.heappush(self.h, (t, prio, self.seq, kind, a, b))
        self.seq += 1

    def _work_end(self, t: float, dur: float) -> float:
        """Fin d'une tâche de poste de `dur` minutes de travail commencée à t : le travail saute les pauses."""
        cal = self.cal
        for k in range(bisect.bisect_right(self.cal_e, t), len(cal)):
            s, e = cal[k]
            if t >= s:
                t = e
            elif t + dur <= s:
                break
            else:
                dur -= s - t
                t = e
        return t + dur

    def _ev(self, now: float, kind: str, subject: str, **data: Any) -> None:
        self.events.append([round(now, 2), kind, subject, data])

    def _agent(self, now: float, agent: str, state: str, at: str | None, until: float | None = None) -> None:
        if agent in self.P.agents and self.astate.get(agent) != (state, at):
            self.astate[agent] = (state, at)
            self._ev(now, "agent", agent, state=state, at=at, until=None if until is None else round(until, 2))

    def _vis(self, m: _M) -> int:
        if m.down == 1:
            return PANNE
        if m.down == 2:
            return PAUSE if self.in_break else ARRET
        if (self.in_break and m.i not in self.relieved) or m.ostop:
            return PAUSE
        if m.phase == SETUP:
            return REGLAGE
        if m.phase == RUN:
            return MARCHE
        if m.phase == BLOCKED:
            return PLEINE
        ln = m.line
        return ATTENTE if self.lots_left[ln] or self.pool_n[ln] or self.inline[ln] else ARRET

    def _refresh(self, m: _M, now: float) -> None:
        s = self._vis(m)
        if s != m.st:
            m.bk[m.st] += now - m.st_t
            m.st, m.st_t = s, now

    # -- machines ----------------------------------------------------------------------------------------------------

    def _fail_age(self, m: _M) -> float:
        return m.scale * self.mtbf_factor * m.hazard ** (1 / m.shape)

    def _accrue(self, m: _M, now: float) -> None:
        """Arrête la progression en cours (pause, panne, préventif) et compte le travail fait."""
        if m.seg is None:
            return
        el = now - m.seg
        m.seg = None
        m.gen += 1
        if m.phase == SETUP:
            m.rem_setup = max(0.0, m.rem_setup - el)
        elif m.phase == RUN:
            m.rem_cycle = max(0.0, m.rem_cycle - el)
            m.age += el
            m.rsince += el

    def _try(self, m: _M, now: float) -> None:
        if m.down or m.ostop or m.seg is not None or m.phase == BLOCKED or (m.i not in self.relieved and self.in_break):
            return
        if m.cur is None:
            code = self._pull(m, now)
            if code is None:
                self._refresh(m, now)
                return
            lot = code >> 1
            m.cur = code
            m.rem_cycle = m.cycle
            m.rem_setup = m.setup if m.setup > 0 and lot != m.last_lot else 0.0
            m.last_lot = lot
            if m.rem_setup:
                self._ev(now, "reglage", m.id, duration_min=round(m.rem_setup, 2))
        m.seg = now
        if m.rem_setup > 1e-9:
            m.phase = SETUP
            self._push(now + m.rem_setup, "msetup", m.i, m.gen)
        else:
            m.rem_setup = 0.0
            self._cycle(m, now)
        self._refresh(m, now)

    def _cycle(self, m: _M, now: float) -> None:
        m.phase = RUN
        c = m.rem_cycle
        fail_in = self._fail_age(m) - m.age
        ostop_in = m.run_min - m.rsince if m.stop_min > 0 else INF
        if fail_in < c and fail_in <= ostop_in:
            self._push(now + max(fail_in, 0.0), "mfail", m.i, m.gen)
        elif ostop_in < c:
            self._push(now + max(ostop_in, 0.0), "mostop", m.i, m.gen)
        else:
            self._push(now + c, "mdone", m.i, m.gen)

    def _pull(self, m: _M, now: float) -> int | None:
        ln = m.line
        if m.is_first:
            pool = self.pools[ln]
            if not pool:
                return None
            head = pool[0]
            code = head[0] << 1
            head[1] -= 1
            if not head[1]:
                pool.popleft()
            self.pool_n[ln] -= 1
            self.inline[ln] += 1
            self.entered[ln] += 1
            if len(pool) < 2 and not self.inflight[ln] and self.lots_left[ln]:
                self._kit_try(now)  # le lot d'avance est entamé : le chariot prépare le suivant
            return code
        tbl = self.tables[m.i - 1]
        if not tbl:
            return None
        ready, code = tbl[0]
        if ready > now:
            if m.wake is None or ready < m.wake:
                m.wake = ready
                self._push(ready, "mwake", m.i)
            return None
        tbl.popleft()
        up = self.M[m.i - 1]
        if up.phase == BLOCKED:
            self._unblock(up, now)
        return code

    def _unblock(self, up: _M, now: float) -> None:
        self._place(up, up.cur, now, notify=False)  # type: ignore[arg-type]
        self._refresh(up, now)
        self._try(up, now)

    def _place(self, m: _M, code: int, now: float, notify: bool = True) -> None:
        """Le produit fini quitte la machine pour sa table de sortie (il y arrive après le temps de transfert)."""
        self.tables[m.i].append((now + m.transfer, code))
        m.cur = None
        m.phase = IDLE
        if m.is_last:
            self._exit(m, code, now)
            if notify:
                self._qc_try(now)
        elif notify:
            self._try(self.M[m.i + 1], now)

    def _exit(self, m: _M, code: int, now: float) -> None:
        lot, ln = code >> 1, m.line
        self.out[ln] += 1
        self.totals["out"] += 1
        of = self.ofd[self.lot_of[lot]]
        of["out"] += 1
        left = self.lot_left[lot] - 1
        if left:
            self.lot_left[lot] = left
        else:
            del self.lot_left[lot]
            self._ev(now, "lot_termine", of["id"], line_id=of["line_id"], quantity=self.P.lot_size)
        if of["out"] == of["quantity"]:
            of["status"] = "termine"

    def _mdone(self, now: float, i: int, gen: int) -> None:
        m = self.M[i]
        if gen != m.gen:
            return
        m.age += m.rem_cycle
        m.rsince += m.rem_cycle
        m.rem_cycle = 0.0
        m.seg = None
        m.gen += 1
        code = m.cur
        if m.rng.random() < m.defect:
            code |= 1  # type: ignore[operator]
            m.defects += 1
        m.produced += 1
        if len(self.tables[i]) >= self.cap[i]:
            m.cur, m.phase = code, BLOCKED
            self._refresh(m, now)
            return
        self._place(m, code, now)  # type: ignore[arg-type]
        self._try(m, now)

    def _msetup(self, now: float, i: int, gen: int) -> None:
        m = self.M[i]
        if gen != m.gen:
            return
        m.rem_setup = 0.0
        m.seg = now
        m.gen += 1
        self._cycle(m, now)
        self._refresh(m, now)

    def _mfail(self, now: float, i: int, gen: int) -> None:
        m = self.M[i]
        if gen != m.gen:
            return
        delta = max(self._fail_age(m) - m.age, 0.0)
        m.age += delta
        m.rsince += delta
        m.rem_cycle = max(m.rem_cycle - delta, 0.0)
        m.seg = None
        m.gen += 1
        m.down, m.fail_t = 1, now
        m.failures += 1
        self._ev(now, "panne", m.id, duration_min=round(m.mttr, 2))
        self.repair_q.append((now, i))
        self._refresh(m, now)
        self._tech_try(now)

    def _mostop(self, now: float, i: int, gen: int) -> None:
        m = self.M[i]
        if gen != m.gen:
            return
        self._accrue(m, now)
        m.rsince = 0.0
        m.ostop = True
        self._push(now + m.stop_min, "moresume", i)
        self._refresh(m, now)

    def _moresume(self, now: float, i: int, _: Any) -> None:
        m = self.M[i]
        m.ostop = False
        self._try(m, now)

    def _mwake(self, now: float, i: int, _: Any) -> None:
        m = self.M[i]
        m.wake = None
        self._try(m, now)

    # -- pauses et préventif -----------------------------------------------------------------------------------------

    def _bs(self, now: float, s: int, _: Any) -> None:
        self.in_break = True
        for m in self.M:
            if m.i not in self.relieved:
                self._accrue(m, now)
                self._refresh(m, now)
        for b in self.relieved:
            self._agent(now, "agent_production", "occupe", self.M[b].id, self.slots[s][1])
        self._slot(now, s)

    def _be(self, now: float, s: int, _: Any) -> None:
        self.in_break = False
        if self.relieved:
            self.relief_min += len(self.relieved) * (self.slots[s][1] - self.slots[s][0])
            self._agent(now, "agent_production", "disponible", "production")
        for m in self.M:
            self._refresh(m, now)
            self._try(m, now)

    def _slot(self, now: float, s: int) -> None:
        """Début d'une pause : le préventif prévu pour ce créneau démarre si le technicien est libre."""
        mi = self.slot_owner.pop(s, None)
        if mi is None:
            return
        m, P = self.M[mi], self.P
        if self.tech_busy >= P.rs["technicians"] or m.down:
            later = next((k for k in range(s + 1, len(self.slots)) if k not in self.slot_owner), None)
            if later is None:
                self.prev_skipped.append(m.id)
            else:
                self.slot_owner[later] = mi
            return
        self._accrue(m, now)
        m.down = 2
        self.tech_busy += 1
        dur = P.lg["preventive_min"]
        self._agent(now, "agent_maintenance", "occupe", m.id, now + dur)
        self._push(now + dur, "prv", mi)
        self._refresh(m, now)

    def _prv(self, now: float, mi: int, _: Any) -> None:
        m, P = self.M[mi], self.P
        m.down, m.age, m.hazard = 0, 0.0, _hazard(m.rng)
        self.tech_busy -= 1
        dur = P.lg["preventive_min"]
        self.tech_stats["busy_min"] += dur
        self.costs["preventive"] += P.costs["preventive_per_intervention"]
        self.prev_done.append(m.id)
        self._ev(now, "preventif", m.id, by="agent_maintenance", duration_min=round(dur, 2))
        self._refresh(m, now)
        self._try(m, now)
        self._tech_try(now)

    # -- réparations -------------------------------------------------------------------------------------------------

    def _tech_try(self, now: float) -> None:
        P = self.P
        while self.tech_busy < P.rs["technicians"] and self.repair_q:
            if self.settings["priority"] == "goulot":
                k = next((k for k, (_, i) in enumerate(self.repair_q) if i in P.bottleneck), 0)
            else:
                k = 0
            t0, i = self.repair_q.pop(k)
            m = self.M[i]
            self.tech_busy += 1
            travel = P.lg["repair_travel_min"]
            self.tech_stats["wait_min"] += now - t0
            self.tech_stats["waited"] += now > t0 + 1e-9
            self._agent(now, "agent_maintenance", "deplacement", m.id, now + travel)
            self._push(now + travel, "rstart", i)

    def _rstart(self, now: float, i: int, _: Any) -> None:
        m = self.M[i]
        self._ev(now, "reparation_debut", m.id, by="agent_maintenance")
        self._agent(now, "agent_maintenance", "occupe", m.id, now + m.mttr)
        self._push(now + m.mttr, "rep", i)

    def _rep(self, now: float, i: int, _: Any) -> None:
        m, P = self.M[i], self.P
        self._ev(now, "reparation_fin", m.id, by="agent_maintenance")
        m.down, m.age, m.hazard, m.fail_t = 0, 0.0, _hazard(m.rng), None
        self.tech_busy -= 1
        self.tech_stats["repairs"] += 1
        self.tech_stats["busy_min"] += m.mttr + P.lg["repair_travel_min"]
        self.costs["repair"] += m.mttr / 60 * P.costs["repair_per_h"]
        self._agent(now, "agent_maintenance", "disponible", "maintenance")
        self._refresh(m, now)
        self._try(m, now)
        self._tech_try(now)

    # -- kits : matière d'un lot, du stock à la tête de ligne --------------------------------------------------------

    def _kit_try(self, now: float) -> None:
        """Le chariot prépare le kit de la ligne la moins approvisionnée (un lot d'avance au plus par ligne)."""
        P = self.P
        while self.fk_busy < P.rs["forklifts"]:
            wanting = [
                ln for ln in range(P.nl) if not self.inflight[ln] and len(self.pools[ln]) < 2 and self.lots_left[ln]
            ]
            if not wanting:
                return
            if self.mp - self.res < P.need:  # pas assez de matière : les lignes sans kit s'arrêtent
                for ln in wanting:
                    if not self.pools[ln] and self.starve[ln] is None:
                        self.starve[ln] = now
                return
            ln = min(wanting, key=lambda x: (len(self.pools[x]), x))
            if self.starve[ln] is not None:
                self._close_starve(ln, now)
            of = self.ofq[ln][0]
            of["kitted"] += 1
            self.lots_left[ln] -= 1
            if of["kitted"] == of["lots"]:
                self.ofq[ln].popleft()
            if of["status"] == "attente":
                of["status"] = "en_cours"
                self._ev(now, "of_lance", of["id"], line_id=of["line_id"], quantity=of["quantity"])
            self.fs["ids"]["lot"] += 1
            lot = self.fs["ids"]["lot"]
            self.lot_of[lot], self.lot_left[lot] = of["id"], P.lot_size
            self.res += P.need
            self.inflight[ln] += 1
            self.fk_busy += 1
            end = self._work_end(now, P.lg["kit_min"])
            self.fk_busy_min += end - now
            self._agent(now, "agent_stock_mp", "occupe", "stock_mp", end)
            self._push(end, "kit", ln, lot)

    def _close_starve(self, ln: int, now: float) -> None:
        t0 = self.starve[ln]
        self.starve[ln] = None
        self.starve_min[ln] += now - max(t0, 0.0)
        d0, d1 = int(max(t0, 0.0) // self.P.mpd), int(now // self.P.mpd)
        self.starve_days.update((ln, d) for d in range(d0, d1 + 1) if d < self.P.days)

    def _kit(self, now: float, ln: int, lot: int) -> None:
        P = self.P
        self.fk_busy -= 1
        self.inflight[ln] -= 1
        self.mp -= P.need
        self.res -= P.need
        self.consumed += P.need
        self.kits[ln] += 1
        self.pools[ln].append([lot, P.lot_size])
        self.pool_n[ln] += P.lot_size
        self.totals["launched"] += P.lot_size
        self._ev(now, "kit_livre", self.lot_of[lot], line_id=P.line_ids[ln], quantity=P.need)
        if not self.fk_busy:
            self._agent(now, "agent_stock_mp", "disponible", "stock_mp")
        self._flush_staged(now)
        self._kit_try(now)
        self._try(self.M[P.first[ln]], now)

    # -- réception ---------------------------------------------------------------------------------------------------

    def _places(self, units: int) -> int:
        return -(-units // self.P.upp)

    def _flush_staged(self, now: float) -> None:
        while self.staged and self._places(self.mp + self.P.upp) <= self.P.lg["mp_capacity_pallets"]:
            self.staged -= 1
            self.mp += self.P.upp

    def _dock_take(self, now: float, what: str, key: Any, since: float) -> None:
        """Un camion prend le quai (fournisseur : déchargement ; client : chargement)."""
        P = self.P
        self.dock_busy += 1
        self.dock_stats["wait_min"] += now - since
        if what == "po":
            po = self.receiving[key]
            self.received["wait_min"] += now - since
            end = self._work_end(now, po["pallets"] * P.lg["unload_min_per_pallet"])
            self._agent(now, "chauffeur_fournisseur", "occupe", "quai", end)
            self._agent(now, "agent_reception", "occupe", "reception", end)
            self.dock_stats["busy_min"] += end - now
            self._push(end, "unl", key)
        else:
            info = self.loading[str(key)]
            pallets = sum(-(-q // P.pallet_pf) for _, q in info["ship"])
            end = self._work_end(now, pallets * P.lg["load_min_per_pallet"])
            self._agent(now, "chauffeur_client", "occupe", "quai", end)
            self.dock_stats["busy_min"] += end - now
            self._push(end, "load", key)

    def _dock_next(self, now: float) -> None:
        while self.dock_busy < self.P.rs["docks"] and self.dock_q:
            what, key, since = self.dock_q.pop(0)
            self._dock_take(now, what, key, since)

    def _truck(self, now: float, po_id: str, _: Any) -> None:
        po = next(p for p in self.pending if p["id"] == po_id)
        self.pending.remove(po)
        self.receiving[po_id] = {**po, "left": po["pallets"], "accepted": 0, "quarantined": 0}
        self.received["trucks"] += 1
        self.received["pallets"] += po["pallets"]
        if self.dock_busy < self.P.rs["docks"]:
            self._dock_take(now, "po", po_id, now)
        else:
            self.dock_q.append(["po", po_id, now])

    def _unl(self, now: float, po_id: str, _: Any) -> None:
        self.dock_busy -= 1
        self._agent(now, "chauffeur_fournisseur", "disponible", "fournisseur")
        for k in range(self.receiving[po_id]["pallets"]):
            self.insp_q.append((po_id, k))
        self._dock_next(now)
        self._insp_try(now)

    def _insp_try(self, now: float) -> None:
        if self.insp_busy or not self.insp_q:
            return
        po_id, k = self.insp_q.popleft()
        self.insp_busy = True
        self._push(self._work_end(now, self.P.lg["inspect_min_per_pallet"]), "insp", po_id, k)

    def _insp(self, now: float, po_id: str, k: int) -> None:
        P = self.P
        self.insp_busy = False
        po = self.receiving[po_id]
        rate = min(0.5, P.lg["supplier_nonconform_rate"] + self.effects.get("nonconform", 0.0))
        if _rng(P, "fournisseur", po_id, "palette", k).random() < rate:
            po["quarantined"] += P.upp
            self.quar += P.upp
        else:
            po["accepted"] += P.upp
            if self.staged == 0 and self._places(self.mp + P.upp) <= P.lg["mp_capacity_pallets"]:
                self.mp += P.upp
            else:
                self.staged += 1
        po["left"] -= 1
        if not po["left"]:
            del self.receiving[po_id]
            self.received["accepted"] += po["accepted"]
            self.received["quarantined"] += po["quarantined"]
            self.totals["received"] += po["accepted"]
            self._ev(now, "livraison_mp", po_id, component_id=po["component_id"], quantity=po["accepted"])
            if po["quarantined"]:
                self._ev(now, "non_conforme", po_id, component_id=po["component_id"], quantity=po["quarantined"])
            self._agent(now, "agent_reception", "disponible", "reception")
        self._kit_try(now)
        self._insp_try(now)

    # -- contrôle, emballage, entrepôt ------------------------------------------------------------------------------

    def _qc_try(self, now: float) -> None:
        if self.qc_busy:
            return
        P = self.P
        best, best_r = -1, INF
        for ln in range(P.nl):
            tbl = self.tables[P.last[ln]]
            if tbl and tbl[0][0] < best_r:
                best, best_r = ln, tbl[0][0]
        if best < 0:
            return
        if best_r > now:
            if self.qc_wake is None or best_r < self.qc_wake:
                self.qc_wake = best_r
                self._push(best_r, "qcw")
            return
        mi = P.last[best]
        _, code = self.tables[mi].popleft()
        self.inline[best] -= 1
        up = self.M[mi]
        if up.phase == BLOCKED:
            self._unblock(up, now)
        self.qc_busy = True
        self._push(self._work_end(now, P.lg["qc_min_per_unit"]), "qc", code, best)

    def _qcw(self, now: float, _a: Any, _b: Any) -> None:
        self.qc_wake = None
        self._qc_try(now)

    def _qc(self, now: float, code: int, ln: int) -> None:
        self.qc_busy = False
        self.qc_count += 1
        if code & 1:
            self.scrap[ln] += 1
            self.scrap_turn += 1
            self.totals["scrap"] += 1
            self._ev(now, "rebut", self.P.line_ids[ln], quantity=1)
        else:
            self.good[ln] += 1
            self.totals["good"] += 1
            self.ofd[self.lot_of[code >> 1]]["good"] += 1
            self.conf += 1
            self._pack_try(now)
        self._qc_try(now)

    def _pack_try(self, now: float) -> None:
        if self.pk_busy or self.pk_wait:
            return
        lg = self.P.lg
        if self.pk_cases == lg["cases_per_pallet"]:
            self.pk_busy = "wrap"
            self._push(self._work_end(now, lg["wrap_min_per_pallet"]), "wrap")
        elif self.conf >= lg["units_per_case"]:
            self.conf -= lg["units_per_case"]
            self.pk_units += lg["units_per_case"]
            self.pk_busy = "case"
            self._push(self._work_end(now, lg["pack_min_per_case"]), "case")

    def _case(self, now: float, _a: Any, _b: Any) -> None:
        self.pk_busy = None
        self.pk_cases += 1
        self.packed["cases"] += 1
        self._pack_try(now)

    def _wrap(self, now: float, _a: Any, _b: Any) -> None:
        self.pk_busy = None
        self.pk_wait = True
        self._store(now)

    def _store(self, now: float) -> None:
        """La palette filmée entre à l'entrepôt PF s'il y a une place ; sinon l'emballage attend."""
        P = self.P
        if not self.pk_wait or -(-(self.pf + P.pallet_pf) // P.pallet_pf) > P.lg["pf_capacity_pallets"]:
            return
        self.pk_wait = False
        self.pf += P.pallet_pf
        self.pk_units -= P.pallet_pf
        self.pk_cases = 0
        self.packed["pallets"] += 1
        self._ev(now, "palette", "pf", quantity=P.pallet_pf)
        self._pack_try(now)

    # -- client ------------------------------------------------------------------------------------------------------

    def _day(self, now: float, day: int, _: Any) -> None:
        P, cu = self.P, self.P.cu
        rng = _rng(P, "demande", day)
        base = cu["demand_per_day"] / cu["orders_per_day"] * self.effects.get("demand", 1.0)
        for _k in range(cu["orders_per_day"]):
            self.fs["ids"]["co"] += 1
            q = max(1, round(base * (1 + cu["variability"] * (2 * rng.random() - 1))))
            order = {"id": f"c{self.fs['ids']['co']}", "quantity": q, "day": day, "due_day": day + cu["promised_days"],
                     "shipped_day": None, "status": "ouverte", "on_time": None}  # fmt: skip
            self.orders.append(order)
            self._ev(now, "commande_client", order["id"], quantity=q, due_day=order["due_day"])
        lo, hi = cu["pickup_window_min"]
        self._push(now + lo + rng.random() * (hi - lo), "pick", day)

    def _pick(self, now: float, day: int, _: Any) -> None:
        """Le camion du client arrive : il emporte, dans l'ordre, les commandes que le stock PF couvre en entier."""
        P = self.P
        stock, ship = self.pf, []
        for o in self.orders:
            if o["shipped_day"] is None and o["quantity"] <= stock:
                ship.append([o["id"], o["quantity"]])
                stock -= o["quantity"]
        if not ship:
            return
        self.loading[str(day)] = {"ship": ship}
        if self.dock_busy < P.rs["docks"]:
            self._dock_take(now, "pick", day, now)
        else:
            self.dock_q.append(["pick", day, now])

    def _load(self, now: float, day: int, _: Any) -> None:
        P = self.P
        self.dock_busy -= 1
        info = self.loading.pop(str(day))
        today = self.fs["day"] + int(now // P.mpd)
        by_id = {o["id"]: o for o in self.orders}
        for oid, q in info["ship"]:
            o = by_id[oid]
            self.pf -= q
            self.shipped_turn += q
            self.totals["shipped"] += q
            o["shipped_day"], o["status"], o["on_time"] = today, "livree", today <= o["due_day"]
            self._ev(now, "expedition", oid, quantity=q, on_time=o["on_time"])
        self._agent(now, "chauffeur_client", "disponible", "client")
        self._store(now)
        self._dock_next(now)

    # -- instantanés -------------------------------------------------------------------------------------------------

    def _counters(self) -> list[int]:
        tables = self.tables
        en_cours, control = sum(self.pool_n), self.qc_busy
        for i in self.not_last:
            en_cours += len(tables[i])
        for i in self.P.last:
            control += len(tables[i])
        for m in self.M:
            if m.cur is not None:
                en_cours += 1
        return [self.mp, en_cours, control, self.conf, 0, self.scrap_turn, self.pk_units, self.pf, self.shipped_turn]

    def _frame(self, now: float, k: int, _: Any) -> None:
        self.frames.append(
            [round(now, 2), [self._vis(m) for m in self.M], [len(t) for t in self.tables], self._counters()]
        )
        if k + 1 < len(self.ftimes):
            self._push(self.ftimes[k + 1], "frame", k + 1, 0, FRAME_PRIO)

    # -- tour --------------------------------------------------------------------------------------------------------

    def run(self) -> None:
        P, fs = self.P, self.fs
        day0 = fs["day"]
        # pauses
        for s, (b, e) in enumerate(self.slots):
            self._push(b, "bs", s)
            self._push(e, "be", s)
        # jours : commandes du client
        for d in range(P.days):
            self._push(d * P.mpd, "day", day0 + d)
        # camions des commandes d'achat qui tombent dans ce tour
        for po in self.pending:
            if po["eta_day"] is None and po["due_day"] < day0 + P.days:
                rng = _rng(P, "fournisseur", po["id"])
                delay_risk = self.effects.get("delay_risk", 0.0)
                late = rng.random() >= po["reliability"] / 100 * (1 - delay_risk)
                lo, hi = P.lg["delivery_window_min"]
                po["eta_day"] = po["due_day"] + (SUPPLIER_LATE_DAYS if late else 0)
                po["eta_min"] = lo + rng.random() * (hi - lo)
            if po["eta_day"] is not None and po["eta_day"] < day0 + P.days:
                self._push((po["eta_day"] - day0) * P.mpd + po["eta_min"], "truck", po["id"])
        # préventif : une intervention par machine ciblée, dans l'ordre des créneaux (les plus longs d'abord)
        targets, others = [], []
        for ln, lid in enumerate(P.line_ids):
            mode = self.settings["preventive"].get(lid, "aucune")
            if mode != "aucune":
                targets.append(P.bottleneck[ln])
                if mode == "toutes":
                    others += [i for i in P.line_machines[ln] if i != P.bottleneck[ln]]
        targets += others
        order = sorted(range(len(self.slots)), key=lambda s: (-(self.slots[s][1] - self.slots[s][0]), self.slots[s][0]))
        self.slot_owner = dict(zip(order, targets, strict=False))
        self.prev_skipped += [self.M[i].id for i in targets[len(order) :]]
        self.ftimes = frame_times(P.days, P.mpd, P.frame_min)
        self._push(0.0, "frame", 0, 0, FRAME_PRIO)
        # reprise : tout ce qui peut démarrer démarre
        self._kit_try(0.0)
        for m in self.M:
            self._try(m, 0.0)
        self._qc_try(0.0)
        self._pack_try(0.0)
        self._insp_try(0.0)
        self._tech_try(0.0)
        self._store(0.0)
        h, T, disp = self.h, self.T, self.disp
        while h and h[0][0] <= T:
            t, _, _, kind, a, b = heapq.heappop(h)
            self.now = t
            disp[kind](t, a, b)

    def dump(self) -> dict[str, Any]:
        P, fs, T = self.P, self.fs, self.T
        for m in self.M:  # dernière tranche de temps de chaque machine
            m.bk[m.st] += T - m.st_t
        for ln in range(P.nl):
            if self.starve[ln] is not None:
                self._close_starve(ln, T)
                self.starve[ln] = 0.0  # le manque continue au tour suivant (date relative)
        fs["day"] += P.days
        fs["seq"] = self.seq
        fs["events"] = [
            [t - T, prio, seq, kind, a, b]
            for t, prio, seq, kind, a, b in self.h
            if t > T and (kind not in SPAN_KINDS or b == self.M[a].gen)
        ]
        for m, ms in zip(self.M, fs["machines"], strict=True):
            for key in ("cur", "phase", "rem_setup", "rem_cycle", "gen", "ostop", "down", "age", "hazard", "rsince",
                        "last_lot"):  # fmt: skip
                ms[key] = getattr(m, key)
            ms["seg"] = None if m.seg is None else m.seg - T
            ms["fail_t"] = None if m.fail_t is None else m.fail_t - T
            ms["wake"] = None if m.wake is None else m.wake - T
        fs["tables"] = [[[r - T, c] for r, c in t] for t in self.tables]
        fs["pools"] = [[list(x) for x in p] for p in self.pools]
        keep_lots = sorted(self.lot_of)[-KEPT_LOTS:]
        fs["lot_of"] = {str(k): self.lot_of[k] for k in keep_lots}
        fs["lot_left"] = {str(k): v for k, v in self.lot_left.items()}
        fs["mp"] = {"units": self.mp, "staged": self.staged, "quarantine": self.quar, "reserved": self.res}
        fs["dock"] = {"busy": self.dock_busy, "queue": [[w, k, s - T] for w, k, s in self.dock_q]}
        fs["insp"] = {"busy": self.insp_busy, "queue": [list(x) for x in self.insp_q]}
        fs["pf"] = {"units": self.pf}
        fs["qc"] = {"busy": self.qc_busy, "wake": None if self.qc_wake is None else self.qc_wake - T}
        fs["pack"] = {"conf": self.conf, "busy": self.pk_busy, "cases": self.pk_cases, "units": self.pk_units,
                      "wait": self.pk_wait}  # fmt: skip
        fs["tech"] = {"busy": self.tech_busy, "queue": [[t - T, i] for t, i in self.repair_q]}
        fs["fk"] = {"busy": self.fk_busy}
        # commandes : statut du jour, puis on ne garde que les ouvertes et les dernières closes
        today = fs["day"]
        day0_ = today - P.days
        for o in self.orders:
            if o["shipped_day"] is None and o["due_day"] < today:
                o["status"] = "en_retard"
        due = [o for o in self.orders if day0_ <= o["due_day"] < today]
        self.otif = {"due": len(due), "on_time": sum(1 for o in due if o["on_time"])}
        closed = [o for o in self.orders if o["shipped_day"] is not None]
        fs["orders"] = [o for o in self.orders if o["shipped_day"] is None] + closed[-KEPT_ORDERS:]
        done = [of for of in fs["ofs"] if of["status"] == "termine"]
        fs["ofs"] = [of for of in fs["ofs"] if of["status"] != "termine"] + done[-KEPT_ORDERS:]
        return fs

    def timeline(self, week: int) -> dict[str, Any]:
        P = self.P
        return {
            "week": week, "days": P.days, "minutes_per_day": P.mpd, "day_start_h": P.start_h,
            "frame_min": P.frame_min, "states": list(STATES), "machines": list(P.mids), "counters": list(COUNTERS),
            "frames": self.frames, "events": self.events,
        }  # fmt: skip

    def report(self, day0: int) -> dict[str, Any]:
        P = self.P
        due, on_time = self.otif["due"], self.otif["on_time"]
        return {
            "minutes": P.T,
            "day": day0,
            "lines": {
                lid: {"out": self.out[ln], "good": self.good[ln], "scrap": self.scrap[ln], "entered": self.entered[ln],
                      "kits": self.kits[ln], "stockout_min": round(self.starve_min[ln], 2),
                      "stockout_days": len({d for ll, d in self.starve_days if ll == ln}),
                      "expected_h": expected_h(P, ln), "theoretical_h": theoretical_h(P, ln)}
                for ln, lid in enumerate(P.line_ids)
            },
            "machines": {
                m.id: {"produced": m.produced, "defects": m.defects, "failures": m.failures,
                       "minutes": {STATES[s]: round(v, 2) for s, v in enumerate(m.bk)}, "age_min": round(m.age, 2)}
                for m in self.M
            },
            "orders": {"due": due, "on_time": on_time, "late": due - on_time,
                       "otif": 100 * on_time / due if due else None},
            "reception": self.received,
            "technician": self.tech_stats,
            "preventive": {"done": self.prev_done, "skipped": self.prev_skipped},
            "dock": self.dock_stats,
            "forklift_busy_min": round(self.fk_busy_min, 2),
            "relief_min": self.relief_min,
            "consumed_mp": self.consumed,
            "controlled": self.qc_count,
            "packed": self.packed,
            "shipped": self.shipped_turn,
            "costs": self.costs,
        }  # fmt: skip


def simulate(
    plant: Plant, fs: dict[str, Any], week: int, effects: dict[str, float] | None = None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Joue un tour : (nouvel état, chronologie, rapport). L'état d'entrée n'est pas modifié ; le hasard ne dépend
    que de la graine, du numéro de semaine et de l'état."""
    sim = _Sim(plant, copy.deepcopy(fs), week, effects or {})
    day0 = sim.fs["day"]
    sim.run()
    new = sim.dump()
    return new, sim.timeline(week), sim.report(day0)
