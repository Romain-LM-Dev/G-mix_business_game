"""Business game simulé (docs/decisions/0006 et 0007) : paramètres de génération, spec produite par
gmix.game.generation et packs de domaine (ai/simulation.yaml = pack « atelier », ai/packs/<id>.yaml). Les modèles
valident aussi une spec importée ou modifiée à la main : toute référence croisée (offre, ligne, agent, poste,
machine, département) doit exister et les modules, secteurs et postes sont vérifiés contre le pack."""

import re
from functools import lru_cache
from typing import Annotated, Any, Literal, get_args

import yaml
from pydantic import BaseModel, Field, model_validator

from gmix.settings import REPO_ROOT, get_settings

CODE_PATTERN = r"^[a-z_]{2,30}$"
Code = Annotated[str, Field(pattern=CODE_PATTERN)]
ModuleId = Code  # vérifié contre le pack dans GameParams et SimSpec
StationKind = Code  # idem
ExtraAgentId = Code  # idem (client, fournisseur, direction pour l'atelier)
Difficulty = Literal["decouverte", "equilibre", "expert"]
EventsLevel = Literal["aucun", "rares", "frequents"]
Tone = Literal["bienveillant", "mixte", "exigeant"]
MachineState = Literal["arret", "marche", "pause", "reglage", "panne", "attente_matiere", "sortie_pleine"]
AgentState = Literal["disponible", "occupe", "deplacement", "pause", "absent"]
ProductState = Literal["en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie"]
ValueStatus = Literal["source", "calibre", "exemple"]
EventKind = Literal[
    "of_lance", "kit_livre", "lot_termine", "panne", "reparation_debut", "reparation_fin", "preventif", "reglage",
    "changement_outil", "livraison_mp", "non_conforme", "rebut", "palette", "commande_client", "expedition", "agent",
]  # fmt: skip
SOURCE_LINE = re.compile(r"^> Source : (.+)$", re.MULTILINE)
Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # x_min, z_min, x_max, z_max (m, repère du monde Godot)
# Toutes les clés de premier niveau de engine.public_state (un test garde l'égalité) : un panneau peut lire chacune
PUBLIC_ROOTS = frozenset(
    {"status", "week", "weeks", "cash", "overdraft", "kpis", "targets", "history", "stocks", "components", "lines",
     "pending", "settings", "event", "last", "log", "briefings", "factory"}
)  # fmt: skip
# Le pack « atelier » (ai/simulation.yaml) n'a ni limites ni liste de postes : ce qu'il acceptait avant l'ADR 0007.
# Limites au format `ranges` de GET /games/options : (min, max, défaut).
ATELIER_LIMITS = {"weeks": (4, 12, 8), "products": (2, 4, 3)}
ATELIER_STATION_KINDS = frozenset(
    {"rack_produit", "rack_composant", "ligne", "poste_qualite", "bureau", "ecran_kpi", "quai_reception",
     "quai_expedition"}
)  # fmt: skip


class GameParams(BaseModel):
    """Tout ce que choisit le formateur : aucun texte libre, la génération est entièrement paramétrée."""

    pack: Code = "atelier"
    theme: str = Field(min_length=1, max_length=40)
    modules: list[ModuleId] = Field(min_length=1, max_length=7)
    extra_agents: list[ExtraAgentId] = Field(default_factory=list, max_length=3)
    agent_tone: Tone = "mixte"
    difficulty: Difficulty = "equilibre"
    weeks: int = Field(default=8, ge=4, le=12)
    events: EventsLevel = "rares"
    products: int = Field(default=3, ge=1, le=4)  # bornes du pack vérifiées par _check
    options: dict[str, int | str] = Field(default_factory=dict, description="options du pack (ActionField)")
    company_name: str | None = Field(default=None, min_length=2, max_length=40)
    players_min: int = Field(default=2, ge=1, le=60)
    players_max: int = Field(default=6, ge=1, le=60)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @model_validator(mode="before")
    @classmethod
    def _pack_defaults(cls, data: Any) -> Any:
        """Durée et nombre de produits absents : défaut du pack (limits `[min, max, défaut]`)."""
        if not isinstance(data, dict) or not {"weeks", "products"} - data.keys():
            return data
        try:
            limits = load_pack(data.get("pack", "atelier")).get("limits", {})
        except (ValueError, TypeError, KeyError):
            return data  # pack inconnu : _check le dit
        absent = {k: limits.get(k, ATELIER_LIMITS[k])[2] for k in ("weeks", "products") if k not in data}
        return {**data, **absent}

    @model_validator(mode="after")
    def _check(self) -> "GameParams":
        if len(set(self.modules)) != len(self.modules) or len(set(self.extra_agents)) != len(self.extra_agents):
            raise ValueError("modules et agents en double")
        if self.players_min > self.players_max:
            raise ValueError("players_min doit être inférieur ou égal à players_max")
        pack = load_pack(self.pack)
        errors = [f"secteur inconnu : {self.theme}"] if self.theme not in pack["themes"] else []
        errors += [f"module inconnu du pack {self.pack} : {m}" for m in self.modules if m not in pack["modules"]]
        errors += [
            f"agent inconnu du pack {self.pack} : {a}"
            for a in self.extra_agents
            if a not in pack.get("extra_agents", {})
        ]
        for key, value in (("products", self.products), ("weeks", self.weeks)):
            low, high, _ = pack.get("limits", {}).get(key, ATELIER_LIMITS[key])  # format garanti par load_pack
            if not low <= value <= high:
                errors.append(f"{key} : entre {low} et {high} pour le pack {self.pack}")
        declared = {p["id"]: ActionField.model_validate(p) for p in pack.get("params", [])}
        for key, value in self.options.items():
            field = declared.get(key)
            if field is None:
                errors.append(f"option inconnue du pack {self.pack} : {key}")
            elif field.type == "int":
                if not isinstance(value, int) or value < (field.min or 0) or value > (field.max or 10**9):
                    errors.append(f"option {key} : entier entre {field.min} et {field.max} attendu")
            elif value not in {o.id for o in field.options or []}:
                errors.append(f"option {key} : valeur inconnue {value}")
        if errors:
            raise ValueError("; ".join(errors[:10]))
        return self


class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float = Field(gt=0)
    unit_cost: float = Field(ge=0, description="coût de transformation d'une unité (hors composant)")
    demand: int = Field(gt=0, description="demande de base par semaine")
    component_id: str
    line_id: str
    initial_stock: int = Field(ge=0)
    safety_stock: int = Field(ge=0)


class Component(BaseModel):
    id: str
    name: str
    unit_cost: float = Field(gt=0, description="prix d'achat de référence")
    usage: int = Field(gt=0, description="consommation par semaine (1 composant par produit fabriqué)")
    initial_stock: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    product_id: str


class Supplier(BaseModel):
    id: str
    name: str
    region: str


class Offer(BaseModel):
    id: str
    supplier_id: str
    component_id: str
    profile: str
    lead_time: int = Field(ge=1, le=8, description="semaines (atelier) ; jours ouvrés (usine)")
    reliability: float = Field(ge=30, le=100)
    unit_cost: float = Field(gt=0)
    min_order: int = Field(ge=1, description="unités (atelier) ; palettes (usine, une commande = un camion)")
    label: str


class Line(BaseModel):
    id: str
    name: str
    product_id: str
    capacity: int = Field(gt=0, description="unités par semaine à 100 % de TRS")
    trs: float = Field(ge=30, le=100)
    label: str


class Option(BaseModel):
    id: str
    label: str


class ActionField(BaseModel):
    id: str
    label: str
    type: Literal["choice", "int"]
    source: Literal["offers", "lines", "products", "machines"] | None = None
    options: list[Option] | None = None
    min: int | None = None
    max: int | None = None
    step: int | None = None
    default: int | None = None


class Action(BaseModel):
    id: str
    label: str
    fields: list[ActionField]


class Module(BaseModel):
    id: ModuleId
    title: str
    description: str
    role_id: str
    stations: list[StationKind]
    actions: list[Action]
    autopilot: str
    notions: list[str]


class Role(BaseModel):
    id: str
    title: str
    mission: str
    module_id: ModuleId


class Personality(BaseModel):
    id: str
    label: str
    traits: str
    style: str
    prefix: str


class Agent(BaseModel):
    id: str
    name: str
    job: str
    kind: Literal["module", "client", "fournisseur", "direction", "departement"]
    module_id: ModuleId | None = None
    department_id: str | None = None
    facts: str | None = Field(default=None, description="clé de engine._FACTS ; None = règle actuelle")
    personality: Personality
    tasks: list[str]
    character: str
    zone: str
    route: list[Point] = Field(min_length=1)
    notions: list[str]


class Station(BaseModel):
    id: str
    kind: StationKind
    label: str
    position: Point = Field(description="point d'interaction du joueur (x, z)")
    ref: str | None = None
    modules: list[ModuleId] = Field(default_factory=list)
    department_id: str | None = None


class WorldObject(BaseModel):
    asset: str
    position: Point
    rotation: float = 0
    label: str | None = None
    ref: str | None = Field(default=None, description="clé des mises à jour visuelles : stock:p1, line:l1, dock_in…")


class World(BaseModel):
    template: Literal["atelier", "usine"] = "atelier"
    size: Point = (32, 24)
    spawn: Point
    objects: list[WorldObject]
    forklift_route: list[Point] = Field(default_factory=list)


class Notion(BaseModel):
    id: str
    title: str
    text: str
    citation: str


class Event(BaseModel):
    id: str
    title: str
    description: str
    weight: float = Field(gt=0)
    effects: dict[str, float]
    modules: list[ModuleId]


class Economy(BaseModel):
    initial_cash: float
    holding_rate_week: float
    maintenance_rate: dict[str, float]
    trs_drift: dict[str, float]
    control_cost_rate: float
    interest_rate_week: float
    price_elasticity: float
    defect_rate: float
    demand_noise: float
    events_probability: float
    transport: dict[str, dict[str, float]]


class Targets(BaseModel):
    otif: float
    trs: float
    stockouts: int
    cash_final: float


class Meta(BaseModel):
    title: str
    company: str
    client: str
    theme: str
    theme_label: str
    pitch: str
    difficulty: Difficulty
    difficulty_label: str
    weeks: int
    players: dict[str, int]
    language: Literal["fr"] = "fr"
    domain: str = "supply-chain"  # slug de ai/domains.yaml (RAG des agents, menu)
    pack: Code = "atelier"


class Provenance(BaseModel):
    """D'où vient une valeur du pack : jamais de chiffre sans origine (exigence n° 1)."""

    status: ValueStatus
    citation: str | None = None  # obligatoire si status == "source"
    note: str | None = None  # obligatoire sinon : d'où vient la valeur, pourquoi ce choix

    @model_validator(mode="after")
    def _origin(self) -> "Provenance":
        if self.status == "source" and not self.citation:
            raise ValueError("valeur sourcée sans citation")
        if self.status != "source" and not self.note:
            raise ValueError(f"valeur « {self.status} » sans note d'origine")
        return self


class Department(BaseModel):
    id: Code
    label: str
    external: bool = False
    area: Rect

    @model_validator(mode="after")
    def _area(self) -> "Department":
        if self.area[0] >= self.area[2] or self.area[1] >= self.area[3]:
            raise ValueError(f"département {self.id} : zone vide ou inversée (x_min, z_min, x_max, z_max)")
        return self


class Machine(BaseModel):
    id: str = Field(pattern=r"^l\d-m\d$")  # « l1-m3 » (cahier : L1-M3)
    line_id: str
    rank: int = Field(ge=1, le=8)
    name: str  # « M3 · Soudage »
    operation: str
    cycle_min: float = Field(gt=0, le=240)
    run_min: float = Field(gt=0, description="marche avant une pause planifiée")
    stop_min: float = Field(ge=0, description="durée de la pause planifiée")
    mtbf_h: float = Field(gt=0, description="moyenne de la loi des pannes, en heures de marche")
    weibull_shape: float = Field(default=2.0, ge=1.0, le=5.0)
    mttr_h: float = Field(gt=0)
    setup_min: float = Field(ge=0, description="à chaque changement de lot")
    tool_life: int | None = Field(default=None, gt=0, description="produits avant changement d'outil")
    tool_change_min: float = Field(default=0, ge=0)
    defect_rate: float = Field(ge=0, le=0.5)
    buffer: int = Field(ge=1, le=500, description="capacité de la table d'attente en sortie")
    transfer_min: float = Field(ge=0)
    operators: int = Field(default=1, ge=0, le=4)
    asset: str


class BomItem(BaseModel):
    component_id: str
    per_unit: float = Field(gt=0)


class CrewMember(BaseModel):
    """Figurant : état animé, aucun dialogue."""

    id: str
    job: Code  # operateur, chauffeur_fournisseur, chauffeur_client
    department_id: str
    machine_id: str | None = None
    character: str


class Clock(BaseModel):
    days_per_turn: int = Field(default=5, ge=1, le=5)
    minutes_per_day: int = Field(default=480, ge=60, le=1440)
    day_start_h: int = Field(default=8, ge=0, le=23)
    frame_min: float = Field(default=5, gt=0, le=60)
    breaks: list[tuple[int, int]] = Field(
        default_factory=list, description="pauses du personnel : (début en min depuis day_start_h, durée en min)"
    )

    @model_validator(mode="after")
    def _breaks(self) -> "Clock":
        end = 0
        for start, length in sorted(self.breaks):
            if length <= 0 or start < end or start + length > self.minutes_per_day:
                raise ValueError("pauses du personnel : durée positive, dans la journée, sans chevauchement")
            end = start + length
        return self


class Logistics(BaseModel):
    units_per_pallet_mp: int = Field(gt=0)
    unload_min_per_pallet: float = Field(ge=0)
    inspect_min_per_pallet: float = Field(ge=0)
    supplier_nonconform_rate: float = Field(ge=0, le=0.5)
    delivery_window_min: tuple[int, int] = (0, 120)  # depuis le début de journée (cahier : 8 h - 10 h)
    mp_capacity_pallets: int = Field(gt=0)
    kit_min: float = Field(ge=0, description="préparation et livraison d'un kit d'OF")
    qc_min_per_unit: float = Field(ge=0)
    qc_block_threshold: float = Field(default=0.15, gt=0, le=1)
    units_per_case: int = Field(gt=0)
    cases_per_pallet: int = Field(gt=0)
    pack_min_per_case: float = Field(ge=0)
    wrap_min_per_pallet: float = Field(ge=0)
    pf_capacity_pallets: int = Field(gt=0)
    load_min_per_pallet: float = Field(ge=0)
    repair_travel_min: float = Field(ge=0)
    preventive_min: float = Field(ge=0)


class Customer(BaseModel):
    demand_per_day: int = Field(gt=0)
    variability: float = Field(ge=0, le=0.5)
    promised_days: int = Field(ge=1, le=20)
    orders_per_day: int = Field(default=1, ge=1, le=10, description="commandes passées par jour ouvré, à l'ouverture")
    pickup_window_min: tuple[int, int] = Field(
        default=(360, 450), description="camion du client, en minutes depuis day_start_h"
    )


class Resources(BaseModel):
    docks: int = Field(default=1, ge=1, le=4)
    forklifts: int = Field(default=1, ge=1, le=4)
    technicians: int = Field(default=1, ge=1, le=4)
    line_leads: int = Field(default=1, ge=1, le=3)


class FactoryCosts(BaseModel):
    repair_per_h: float = Field(ge=0)
    preventive_per_intervention: float = Field(ge=0)
    operator_per_h: float = Field(ge=0)


class Factory(BaseModel):
    """Usine à lignes de machines en série (modèle `factory` du moteur, ADR 0007)."""

    product_id: str  # toutes les lignes font ce produit (cahier) ; Product.line_id = l1
    lot_size: int = Field(gt=0, le=1000)
    pf_min: int = Field(ge=0, description="sous ce stock PF, le pilote automatique relance un OF")
    bom: list[BomItem] = Field(min_length=1)
    machines: list[Machine] = Field(min_length=1)
    crew: list[CrewMember] = Field(default_factory=list)
    clock: Clock = Field(default_factory=Clock)
    logistics: Logistics
    customer: Customer
    resources: Resources = Field(default_factory=Resources)
    costs: FactoryCosts
    protect_buffer: int = Field(
        default=30, ge=1, le=500, description="table devant le goulot en mode tampon_avant (proteger_goulot)"
    )


class PanelColumn(BaseModel):
    key: str  # clé d'un élément (table), d'un indicateur (kpis) ou de history (chart)
    label: str
    format: Literal["text", "int", "dec1", "pct", "money", "minutes", "state"] = "text"
    labels: dict[str, str] = Field(default_factory=dict, description="format state : code -> libellé affiché")
    target: str | None = Field(default=None, description="chemin de la cible, ex. targets.otif")


class Panel(BaseModel):
    id: Code
    type: Literal["kpis", "table", "gauge", "chart", "flow"]
    title: str
    placement: Literal["bandeau", "tableau_de_bord", "poste"]
    station_kinds: list[StationKind] = Field(default_factory=list, description="placement « poste »")
    source: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)*$", description="racine dans PUBLIC_ROOTS")
    match: str | None = Field(default=None, description="poste : garder les éléments dont item[match] == station.ref")
    columns: list[PanelColumn] = Field(default_factory=list)
    min: float | None = None  # gauge
    max: float | None = None


COUNTERS = ["mp", *get_args(ProductState)]  # ordre fixe des compteurs d'un instantané (C = 9)
# Clés de données de chaque type d'événement (annexe 0007 §3) : toutes présentes, `null` seulement où c'est indiqué
EVENT_DATA = {
    **dict.fromkeys(("of_lance", "kit_livre", "lot_termine"), {"line_id", "quantity"}),
    "panne": {"duration_min"},
    **dict.fromkeys(("reparation_debut", "reparation_fin"), {"by"}),
    "preventif": {"by", "duration_min"},
    **dict.fromkeys(("reglage", "changement_outil"), {"duration_min"}),
    **dict.fromkeys(("livraison_mp", "non_conforme"), {"component_id", "quantity"}),
    **dict.fromkeys(("rebut", "palette"), {"quantity"}),
    "commande_client": {"quantity", "due_day"},
    "expedition": {"quantity", "on_time"},
    "agent": {"state", "at", "until"},
}


def frame_times(days: int, minutes_per_day: int, frame_min: float) -> list[float]:
    """Instants des instantanés : 0, f, 2f… puis la fin du tour si ce n'est pas un multiple (481 par défaut)."""
    total = days * minutes_per_day
    times = [round(i * frame_min, 2) for i in range(int(total // frame_min) + 1)]
    return times if times[-1] == total else [*times, float(total)]


class Timeline(BaseModel):
    """Chronologie d'un tour, rendue par l'API et rejouée par Godot (jamais dans l'état public)."""

    week: int
    days: int
    minutes_per_day: int
    day_start_h: int
    frame_min: float
    states: list[MachineState]  # ordre des codes : l'index est la valeur des instantanés
    machines: list[str]  # ordre des colonnes machine
    counters: list[str]  # "mp" puis les ProductState
    frames: list[tuple[float, list[int], list[int], list[int]]]  # t, états, tables d'attente, compteurs
    events: list[tuple[float, EventKind, str, dict[str, Any]]]  # t, type, sujet (id), données

    @model_validator(mode="after")
    def _shape(self) -> "Timeline":
        """Forme exacte de l'annexe 0007 §3 (le calendrier complet des instantanés est `frame_times`)."""
        errors = (
            []
            if self.states == list(get_args(MachineState))
            else ["states : les 7 codes de MachineState, dans l'ordre"]
        )
        errors += [] if self.counters == COUNTERS else [f"counters : {COUNTERS} attendus"]
        m, horizon, last = len(self.machines), self.days * self.minutes_per_day, -1.0
        for t, states, tables, counters in self.frames:
            if not last < t <= horizon:
                errors.append(f"instantané t={t} : instants croissants dans le tour (0 à {horizon}) attendus")
            last = t
            if len(states) != m or len(tables) != m or len(counters) != len(COUNTERS):
                errors.append(f"instantané t={t} : {m} états, {m} tables et {len(COUNTERS)} compteurs attendus")
            if any(not 0 <= s < len(self.states) for s in states) or any(v < 0 for v in tables + counters):
                errors.append(f"instantané t={t} : état hors de 0 à {len(self.states) - 1} ou valeur négative")
        last = 0.0
        for t, kind, subject, data in self.events:
            if not last <= t <= horizon:
                errors.append(f"événement {kind} {subject} : t={t} hors ordre ou hors du tour")
            last = t
            if set(data) != EVENT_DATA[kind]:
                errors.append(f"événement {kind} {subject} : données {sorted(EVENT_DATA[kind])} attendues")
            elif kind == "agent" and data["state"] not in get_args(AgentState):
                errors.append(f"événement agent {subject} : état inconnu {data['state']}")
        if errors:
            raise ValueError("; ".join(errors[:10]))
        return self


class SimSpec(BaseModel):
    kind: Literal["simulation"] = "simulation"
    version: Literal[2] = 2
    seed: int
    meta: Meta
    params: GameParams
    products: list[Product] = Field(min_length=1, max_length=4)
    components: list[Component]
    suppliers: list[Supplier]
    offers: list[Offer]
    lines: list[Line]
    modules: list[Module] = Field(min_length=1)
    roles: list[Role]
    agents: list[Agent] = Field(min_length=1)
    stations: list[Station]
    world: World
    notions: list[Notion]
    events: list[Event]
    economy: Economy
    targets: Targets
    departments: list[Department] = Field(default_factory=list)
    factory: Factory | None = None
    panels: list[Panel] = Field(default_factory=list)
    provenance: dict[str, Provenance] = Field(
        default_factory=dict, description="clé « famille.paramètre », ex. machine.mtbf_h"
    )

    @model_validator(mode="after")
    def _references(self) -> "SimSpec":
        ids = {
            "products": {p.id for p in self.products},
            "components": {c.id for c in self.components},
            "suppliers": {s.id for s in self.suppliers},
            "lines": {line.id for line in self.lines},
            "roles": {r.id for r in self.roles},
            "modules": {m.id for m in self.modules},
            "notions": {n.id for n in self.notions},
            "departments": {d.id for d in self.departments},
        }
        pack = load_pack(self.params.pack)
        errors = [] if self.meta.pack == self.params.pack else ["meta.pack et params.pack diffèrent"]
        used_modules = [m.id for m in self.modules] + [r.module_id for r in self.roles]
        used_modules += [a.module_id for a in self.agents if a.module_id] + [
            m for s in self.stations for m in s.modules
        ]
        used_modules += [m for e in self.events for m in e.modules]
        errors += [
            f"module inconnu du pack {self.params.pack} : {m}"
            for m in sorted(set(used_modules) - pack["modules"].keys())
        ]
        used_kinds = {s.kind for s in self.stations} | {k for m in self.modules for k in m.stations}
        errors += [
            f"poste inconnu du pack {self.params.pack} : {k}"
            for k in sorted(used_kinds - pack_station_kinds(self.params.pack, pack))
        ]
        errors += [f"produit {p.id} : composant ou ligne inconnus" for p in self.products
                  if p.component_id not in ids["components"] or p.line_id not in ids["lines"]]  # fmt: skip
        errors += [f"offre {o.id} : fournisseur ou composant inconnus" for o in self.offers
                   if o.supplier_id not in ids["suppliers"] or o.component_id not in ids["components"]]  # fmt: skip
        errors += [
            f"composant {c.id} sans offre" for c in self.components if c.id not in {o.component_id for o in self.offers}
        ]
        errors += [
            f"ligne {line.id} : produit inconnu" for line in self.lines if line.product_id not in ids["products"]
        ]
        errors += [f"module {m.id} : rôle inconnu" for m in self.modules if m.role_id not in ids["roles"]]
        errors += [
            f"agent {a.id} : module inactif" for a in self.agents if a.module_id and a.module_id not in ids["modules"]
        ]
        errors += [f"notion inconnue : {n}" for m in self.modules for n in m.notions if n not in ids["notions"]]
        prefixes = {"stock": "products", "component": "components", "line": "lines"}
        known_refs = {f"{kind}:{i}" for kind, key in prefixes.items() for i in ids[key]}
        known_refs |= {"dock_in", "dock_out", "kpi", "quality"}
        if self.factory:
            errors += self._factory_errors(ids)
            machines = {m.id for m in self.factory.machines}
            known_refs |= {f"{kind}:{i}" for kind in ("machine", "buffer") for i in machines}
            known_refs |= {f"mp:{i}" for i in ids["components"]} | {f"dept:{i}" for i in ids["departments"]}
            known_refs |= {"pf", "dock", "scrap", "quarantine"}
        errors += [
            f"objet {o.asset} : référence inconnue {o.ref}"
            for o in self.world.objects
            if o.ref and o.ref not in known_refs
        ]
        if len(ids["departments"]) != len(self.departments):
            errors.append("identifiants de département en double")
        errors += [
            f"{what} {x.id} : département inconnu {x.department_id}"
            for what, items in (("agent", self.agents), ("poste", self.stations))
            for x in items
            if x.department_id and x.department_id not in ids["departments"]
        ]
        posted = {s.kind for s in self.stations}
        if len({p.id for p in self.panels}) != len(self.panels):
            errors.append("identifiants de panneau en double")
        for panel in self.panels:
            if panel.source.split(".")[0] not in PUBLIC_ROOTS:
                errors.append(f"panneau {panel.id} : source inconnue {panel.source}")
            errors += [
                f"panneau {panel.id} : cible inconnue {c.target}"
                for c in panel.columns
                if c.target and c.target.split(".")[0] not in PUBLIC_ROOTS
            ]
            errors += [f"panneau {panel.id} : aucun poste de type {k}" for k in panel.station_kinds if k not in posted]
        if errors:
            raise ValueError("; ".join(errors[:10]))
        return self

    def _factory_errors(self, ids: dict[str, set[str]]) -> list[str]:
        factory = self.factory
        assert factory is not None
        errors = [] if self.world.template == "usine" else ["usine : world.template doit valoir « usine »"]
        day = factory.clock.minutes_per_day
        for name, (start, end) in (
            ("créneau d'enlèvement du client", factory.customer.pickup_window_min),
            ("créneau de livraison du fournisseur", factory.logistics.delivery_window_min),
        ):
            if not 0 <= start < end <= day:
                errors.append(f"{name} : 0 <= début < fin <= {day} minutes attendu")
        if factory.product_id not in ids["products"]:
            errors.append(f"usine : produit inconnu {factory.product_id}")
        errors += [
            f"ligne {line.id} : produit {line.product_id} différent de celui de l'usine ({factory.product_id})"
            for line in self.lines
            if line.product_id != factory.product_id
        ]
        errors += [
            f"nomenclature : composant inconnu {b.component_id}"
            for b in factory.bom
            if b.component_id not in ids["components"]
        ]
        machine_ids = [m.id for m in factory.machines]
        if len(set(machine_ids)) != len(machine_ids):
            errors.append("identifiants de machine en double")
        ranks: dict[str, list[int]] = {}
        for m in factory.machines:
            if m.line_id not in ids["lines"]:
                errors.append(f"machine {m.id} : ligne inconnue {m.line_id}")
            elif m.id != f"{m.line_id}-m{m.rank}":
                errors.append(f"machine {m.id} : identifiant incohérent avec la ligne {m.line_id} et le rang {m.rank}")
            ranks.setdefault(m.line_id, []).append(m.rank)
        errors += [
            f"ligne {line} : rangs {sorted(r)} non contigus à partir de 1"
            for line, r in ranks.items()
            if sorted(r) != list(range(1, len(r) + 1))
        ]
        errors += [f"ligne {line} sans machine" for line in sorted(ids["lines"] - ranks.keys())]
        for member in factory.crew:
            if member.department_id not in ids["departments"]:
                errors.append(f"figurant {member.id} : département inconnu {member.department_id}")
            if member.machine_id and member.machine_id not in machine_ids:
                errors.append(f"figurant {member.id} : machine inconnue {member.machine_id}")
        return errors


def _resolve_citations(notions: dict[str, Any], domain: str) -> None:
    """Citation de chaque notion qui désigne une fiche (`source:`), lue dans son en-tête « > Source : »."""
    for notion in notions.values():
        if "citation" not in notion and "source" in notion:
            path = REPO_ROOT / "knowledge" / domain / f"{notion['source']}.md"
            match = SOURCE_LINE.search(path.read_text(encoding="utf-8"))
            if match is None:
                raise ValueError(f"{path.name} : ligne « > Source : » absente")
            notion["citation"] = match.group(1).strip()


@lru_cache
def load_sim_catalog() -> dict[str, Any]:
    """ai/simulation.yaml (pack « atelier »), avec la citation de chaque notion lue dans sa fiche du corpus."""
    catalog = yaml.safe_load((get_settings().gmix_ai_dir / "simulation.yaml").read_text(encoding="utf-8"))
    _resolve_citations(catalog["notions"], "supply-chain")
    return catalog


@lru_cache
def load_pack(pack_id: str) -> dict[str, Any]:
    """Pack de domaine : `atelier` = ai/simulation.yaml, tout autre id = ai/packs/<id>.yaml. Ne pas modifier le
    résultat (partagé). Une notion sans `source:` ni `citation:` reste sans citation (à sourcer) : une spec qui
    la reprend est refusée par `Notion.citation`."""
    if pack_id == "atelier":
        return load_sim_catalog()
    path = get_settings().gmix_ai_dir / "packs" / f"{pack_id}.yaml"
    if not re.fullmatch(CODE_PATTERN, pack_id) or not path.is_file():
        raise ValueError(f"pack inconnu : {pack_id}")
    pack = yaml.safe_load(path.read_text(encoding="utf-8"))
    _check_pack(pack_id, pack)
    _resolve_citations(pack.get("notions", {}), pack.get("domain", "supply-chain"))
    return pack


def _check_pack(pack_id: str, pack: dict[str, Any]) -> None:
    """Formats que la spec suppose : limites `[min, max, défaut]`, postes `{kind, label}` uniques (annexe 0007)."""
    for key, bounds in pack.get("limits", {}).items():
        valid = isinstance(bounds, list) and len(bounds) == 3 and all(type(b) is int for b in bounds)
        if not valid or not bounds[0] <= bounds[2] <= bounds[1]:
            raise ValueError(
                f"pack {pack_id} : limits.{key} doit être [min, max, défaut], entiers, min <= défaut <= max"
            )
    stations = [s for d in pack.get("departments", []) for s in d.get("stations", [])]
    for station in stations:
        if set(station) != {"kind", "label"} or not re.fullmatch(CODE_PATTERN, str(station["kind"])):
            raise ValueError(f"pack {pack_id} : un poste est {{kind, label}} avec un kind en minuscules : {station}")
    names = [s["kind"] for s in stations]
    if len(set(names)) != len(names) or "machine" in names:
        raise ValueError(f"pack {pack_id} : type de poste en double ou réservé (« machine » est créé par machine)")


def pack_station_kinds(pack_id: str, pack: dict[str, Any]) -> frozenset[str]:
    """Types de poste acceptés : ceux des modules et des départements du pack, plus `machine` pour une usine (liste
    figée pour l'atelier)."""
    if pack_id == "atelier":
        return ATELIER_STATION_KINDS
    kinds = {k for m in pack["modules"].values() for k in m.get("stations", [])}
    kinds |= {s["kind"] for d in pack.get("departments", []) for s in d.get("stations", [])}
    return frozenset(kinds | ({"machine"} if pack.get("engine") == "factory" else set()))
