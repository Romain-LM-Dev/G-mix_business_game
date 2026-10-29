"""Business game simulé (docs/decisions/0006 et 0007) : paramètres de génération, spec produite par
gmix.game.generation et packs de domaine (ai/simulation.yaml = pack « atelier », ai/packs/<id>.yaml). Les modèles
valident aussi une spec importée ou modifiée à la main : toute référence croisée (offre, ligne, agent, poste,
machine, département) doit exister et les modules, secteurs et postes sont vérifiés contre le pack.
ADR 0008 : la spec porte aussi la conception par l'IA (design, tools, tutorial, réglages, plan d'aléas). Elle ne
contient que des choix dans les listes du pack ; ici sont refusés tout chiffre ou lien dans un texte conçu, toute
référence inconnue et toute interface au-delà des limites de lisibilité `UI_LIMITS`."""

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
    "camion_arrive", "camion_part",
]  # fmt: skip
Side = Literal["nord", "sud", "est", "ouest"]
# Rôles des objets d'un bloc (ADR 0009) ; `Role` désigne déjà les rôles des joueurs
ElementRole = Literal["stockage", "machine", "tampon", "poste", "affichage", "engin", "decor", "porte", "batiment"]
EDITABLE_ROLES = frozenset({"decor", "affichage"})  # ajout et retrait de l'éditeur de grille, sans `ref`
PATTERNS = ("edge", "rows", "line", "single")  # motifs de bloc du pack
RULE_KINDS = ("adjacent", "flow", "separated", "aisle_min", "facing", "near")  # types de placement_rules
STAFF_KINDS = frozenset({"demarrer", "avancer", "rejeu", "memoire", "debrief"})
MENU_SELECTOR = r"^(station:[a-z_]{2,30}|agent:[a-z0-9_]{2,30}|agent:\*|site:[a-z_]{2,30})$"
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

# Conception par l'IA (ADR 0008, annexe 0008 §1)
Audience = Literal["lycee", "bac_plus_2", "licence", "master", "formation_continue"]
Bloom = Literal["identifier", "expliquer", "calculer", "appliquer", "comparer", "arbitrer", "evaluer"]
Section = Literal["concept", "cast", "journey"]  # scénario et objectifs ; personnages ; interface et débrief
SectionMode = Literal["ia", "repli", "edition"]
FIXABLE = frozenset(
    {"theme", "modules", "extra_agents", "agent_tone", "difficulty", "weeks", "events", "products", "options",
     "company_name"}
)  # fmt: skip  # champs de GameParams que le formateur peut imposer
# textes conçus : ni chiffre ni lien (les chiffres viennent du moteur). \d ne voit pas ², ½, Ⅻ, ① : isnumeric() les voit
_FORBIDDEN_IN_TEXT = re.compile(r"\d|https?://")
TEXT_CHARS = (
    "A-Za-zÀ-ÖØ-öø-ÿŒœ ,.;:!?'’«»()–-"  # liste blanche des schémas de texte donnés au modèle (annexe 0008 §3.1)
)


def forbidden_in_text(text: str) -> bool:
    return bool(_FORBIDDEN_IN_TEXT.search(text)) or any(c.isnumeric() for c in text)


# Indicateurs du débrief par moteur (ids de engine.debrief()["kpis"]) ; défini ici : pas d'import circulaire
INDICATORS = {
    "weekly": ("otif", "trs", "stockouts", "cash"),
    "factory": ("otif", "trs", "stockouts", "cash", "good_share"),
}
RATIONALE_KEYS = frozenset({"modules", "difficulty", "tunings", "events", "agents", "panels", "tutorial", "debrief"})
UI_LIMITS = {  # lisibilité garantie (godot.ps1 -Tour à 4 tailles de fenêtre)
    "bandeau_panels": 2, "bandeau_columns": 6,  # colonnes : total des panneaux du bandeau
    "dashboard_panels": 6, "station_panels": 2,  # station : par type de poste
    "table_columns": 7, "kpis_columns": 6, "chart_series": 3,
    "supervision_panels": 6, "menu_items": 6,  # menu : entrées par cible et par public
    "tools": 6, "tutorial_steps": 5,  # outils : par public
    "panel_title": 40, "column_label": 24, "state_label": 20, "tool_label": 16,
}  # fmt: skip


class PlannedEvent(BaseModel):
    """Aléa imposé une semaine donnée (annoncé une semaine à l'avance par le moteur)."""

    week: int = Field(ge=2, le=12)
    event_id: str


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
    tunings: dict[str, Difficulty] = Field(
        default_factory=dict, description="clé de pack['tunables'] -> profil de difficulté qui fournit sa valeur"
    )
    event_plan: list[PlannedEvent] = Field(default_factory=list, max_length=3)
    network: dict[str, str] = Field(
        default_factory=dict, description="site du pack -> classe de distance permise ; absent : défaut du pack"
    )

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
        tunables = pack.get("tunables", {})
        errors += [f"réglage inconnu du pack {self.pack} : {k}" for k in self.tunings if k not in tunables]
        sites = pack.get("network", {}).get("sites", {})
        for site_id, distance in self.network.items():
            if site_id not in sites:
                errors.append(f"réseau : site inconnu du pack {self.pack} : {site_id}")
            elif distance not in sites[site_id]["distances"]:
                errors.append(f"réseau : classe {distance} non permise pour le site {site_id}")
        weeks = [e.week for e in self.event_plan]
        if len(set(weeks)) != len(weeks):
            errors.append("plan d'aléas : une semaine ne porte qu'un aléa")
        for planned in self.event_plan:
            event = pack.get("events", {}).get(planned.event_id)
            if planned.week > self.weeks:
                errors.append(f"plan d'aléas : semaine {planned.week} après la dernière ({self.weeks})")
            if event is None:
                errors.append(f"plan d'aléas : aléa inconnu du pack {self.pack} : {planned.event_id}")
            elif not set(event["modules"]) & set(self.modules):
                errors.append(f"plan d'aléas : {planned.event_id} ne touche aucun module joué")
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
    backstory: str | None = Field(default=None, max_length=160, description="fiche ; jamais dans npc.dialogue")


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
    # ADR 0009 (éditeur de grille) : identité stable et place dans la grille locale du bloc
    id: str | None = Field(default=None, description="<département>.<rôle>.<n> ; ajout : <département>.ajout.<rang>")
    department_id: str | None = None
    role: ElementRole | None = None
    cell: tuple[int, int] | None = Field(default=None, description="coin de l'emprise, grille locale du bloc")
    cells: tuple[int, int] | None = Field(default=None, description="emprise en cellules après rotation")


class Site(BaseModel):
    """Site de la carte (ADR 0009) : l'usine, un fournisseur, un client. Sortie du placeur."""

    id: Code
    kind: Code
    label: str
    external: bool
    area: Rect
    gate: Point  # raccordement au lien
    supplier_id: str | None = None  # site fournisseur : fournisseur des offres
    distance_class: str | None = None
    km: float | None = Field(default=None, description="distance déclarée par le pack, pas la longueur 3D")
    travel_h: float | None = None
    transit_days: int | None = None


class Link(BaseModel):
    id: str
    type: Code  # link_types du pack : route, convoyeur, couloir, rail…
    from_site: str
    to_site: str
    points: list[Point] = Field(min_length=2)  # polyligne à angles droits
    vehicle: str | None = None  # id d'asset (veh_box_truck)


class World(BaseModel):
    template: Literal["atelier", "usine"] = "atelier"
    size: Point = (32, 24)  # hall du site principal
    spawn: Point
    objects: list[WorldObject]
    forklift_route: list[Point] = Field(default_factory=list)
    sites: list[Site] = Field(default_factory=list)  # site principal (external=False) en premier
    links: list[Link] = Field(default_factory=list)
    bounds: Rect | None = None  # tout le monde


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
    ui_theme: Code = "gmix"  # jeu de jetons godot/themes/<id>.json ; inconnu -> gmix côté client


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


class BlockGrid(BaseModel):
    """Grille locale d'un bloc (sortie du placeur, jamais éditée)."""

    origin: Point  # coin du bloc (m)
    cell_m: float = Field(gt=0)
    cols: int = Field(ge=1)
    rows: int = Field(ge=1)
    reserved: list[tuple[int, int]] = Field(
        default_factory=list, description="bande d'allée et cellule devant un poste"
    )
    palette: dict[str, tuple[int, int]] = Field(
        default_factory=dict, description="asset de décor ajoutable -> emprise en cellules"
    )


class Department(BaseModel):
    id: Code
    label: str
    external: bool = False
    area: Rect
    block: Code | None = None  # type de bloc du pack
    site_id: str | None = None  # zone externe : site qui la porte (son area est celle du site)
    grid: BlockGrid | None = None

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
    label: str = Field(max_length=UI_LIMITS["column_label"])
    format: Literal["text", "int", "dec1", "pct", "money", "minutes", "state"] = "text"
    labels: dict[str, str] = Field(default_factory=dict, description="format state : code -> libellé affiché")
    target: str | None = Field(default=None, description="chemin de la cible, ex. targets.otif")
    better: Literal["higher", "lower"] = Field(default="higher", description="sens de la pastille (ruptures : lower)")
    warn: float | None = Field(default=None, description="seuil « attention » entre la cible et l'alerte")

    @model_validator(mode="after")
    def _labels(self) -> "PanelColumn":
        too_long = [v for v in self.labels.values() if len(v) > UI_LIMITS["state_label"]]
        if too_long:
            raise ValueError(f"colonne {self.key} : libellé d'état de {UI_LIMITS['state_label']} caractères au plus")
        return self


class Panel(BaseModel):
    id: Code
    type: Literal["kpis", "table", "gauge", "chart", "flow"]
    title: str = Field(max_length=UI_LIMITS["panel_title"])
    placement: Literal["bandeau", "tableau_de_bord", "poste", "supervision"]  # supervision : écran du formateur
    audience: Literal["joueur", "formateur", "tous"] = "joueur"
    station_kinds: list[StationKind] = Field(default_factory=list, description="placement « poste »")
    source: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)*$", description="racine dans PUBLIC_ROOTS")
    match: str | None = Field(default=None, description="poste : garder les éléments dont item[match] == station.ref")
    columns: list[PanelColumn] = Field(default_factory=list)
    min: float | None = None  # gauge
    max: float | None = None

    @model_validator(mode="after")
    def _gauge(self) -> "Panel":
        if self.type == "gauge" and (self.min is None or self.max is None or self.min >= self.max):
            raise ValueError(f"panneau {self.id} : une jauge a un min et un max, avec min < max")
        if self.placement == "supervision" and self.audience == "joueur":
            raise ValueError(f"panneau {self.id} : la supervision est celle du formateur (audience formateur ou tous)")
        return self


def panel_errors(panels: list[Panel]) -> list[str]:
    """Limites de lisibilité `UI_LIMITS` d'un ensemble de panneaux (spec, ou catalogue d'un pack)."""
    lim, errors = UI_LIMITS, []
    bandeau = [p for p in panels if p.placement == "bandeau"]
    if len(bandeau) > lim["bandeau_panels"]:
        errors.append(f"bandeau : {lim['bandeau_panels']} panneaux au plus ({len(bandeau)})")
    if sum(len(p.columns) for p in bandeau) > lim["bandeau_columns"]:
        errors.append(f"bandeau : {lim['bandeau_columns']} colonnes au plus en tout")
    dashboard = [p for p in panels if p.placement == "tableau_de_bord"]
    if len(dashboard) > lim["dashboard_panels"]:
        errors.append(f"tableau de bord : {lim['dashboard_panels']} panneaux au plus ({len(dashboard)})")
    supervision = [p for p in panels if p.placement == "supervision"]
    if len(supervision) > lim["supervision_panels"]:
        errors.append(f"supervision : {lim['supervision_panels']} panneaux au plus ({len(supervision)})")
    for kind in sorted({k for p in panels if p.placement == "poste" for k in p.station_kinds}):
        count = sum(1 for p in panels if p.placement == "poste" and kind in p.station_kinds)
        if count > lim["station_panels"]:
            errors.append(f"poste {kind} : {lim['station_panels']} panneaux au plus ({count})")
    for p in panels:
        limit = {"table": "table_columns", "kpis": "kpis_columns", "chart": "chart_series"}.get(p.type)
        if limit and len(p.columns) > lim[limit]:
            errors.append(f"panneau {p.id} : {lim[limit]} colonnes au plus ({len(p.columns)})")
    return errors


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
    **dict.fromkeys(("camion_arrive", "camion_part"), {"site_id"}),  # sujet : commande d'achat ou client-<jour>
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


class Tool(BaseModel):
    """Barre d'actions du HUD ; la touche est le rang dans spec.tools + 1."""

    id: Code
    label: str = Field(min_length=2, max_length=UI_LIMITS["tool_label"])
    audience: Literal["joueur", "formateur"] = "joueur"
    kind: Literal[
        "action", "tableau_de_bord", "camera", "aide",  # aide : rouvre le didacticiel ; action : joueur seul
        "parler", "fiche",  # menu contextuel : parler à l'agent visé ; fiches de notions du poste, de l'agent, du site
        "demarrer", "avancer", "rejeu", "memoire", "debrief",  # formateur seul : routes Staff existantes
    ]  # fmt: skip
    action_id: str | None = None  # obligatoire si kind == "action" : action d'un module de la spec
    menu: list[Annotated[str, Field(pattern=MENU_SELECTOR)]] = Field(
        default_factory=list, description="sélecteurs de cible : station:<kind>, agent:<id>, agent:*, site:<kind>"
    )
    bar: bool = Field(default=True, description="False : seulement dans les menus (hors UI_LIMITS['tools'])")

    @model_validator(mode="after")
    def _action(self) -> "Tool":
        if self.kind == "action" and not self.action_id:
            raise ValueError(f"outil {self.id} : un outil « action » désigne une action de module (action_id)")
        if self.kind == "action" and self.audience != "joueur":
            raise ValueError(f"outil {self.id} : une action de module est réservée au joueur")
        if self.kind in STAFF_KINDS and self.audience != "formateur":
            raise ValueError(f"outil {self.id} : « {self.kind} » est réservé au formateur")
        if self.kind == "parler" and any(not m.startswith("agent:") for m in self.menu):
            raise ValueError(f"outil {self.id} : « parler » ne vise qu'un agent (agent:<id> ou agent:*)")
        return self


class TutorialStep(BaseModel):
    id: Code
    title: str = Field(min_length=2, max_length=40)
    text: str = Field(min_length=10, max_length=160)
    anchor: str = Field(pattern=r"^(panel|tool|station|agent|dept):[a-z0-9_-]+$")
    # panel:<Panel.id>, tool:<Tool.id>, station:<Station.kind>, agent:<Agent.id>, dept:<Department.id>


class DesignObjective(BaseModel):
    id: Code
    verb: Bloom
    text: str = Field(min_length=10, max_length=140)  # complément du verbe : « le goulot de chaque ligne »
    notion_ids: list[str] = Field(min_length=1, max_length=3)
    indicator: str  # dans INDICATORS (moteur de la spec)
    module_ids: list[ModuleId] = Field(min_length=1, max_length=3)


class DebriefQuestion(BaseModel):
    id: Code
    text: str = Field(min_length=15, max_length=200)
    objective_id: str
    notion_id: str  # une notion de l'objectif


class CastAgent(BaseModel):
    """Sortie de la section cast, et édition d'un personnage."""

    agent_id: str
    name: str = Field(min_length=2, max_length=30)
    personality: str  # id de pack["personalities"], du ton retenu
    backstory: str = Field(min_length=20, max_length=160)


class DesignOrigin(BaseModel):
    sections: dict[Section, SectionMode]
    model: str | None = None  # nom Ollama réellement servi (repli compris)
    prompts: dict[str, int] = Field(default_factory=dict)  # tâche -> version du prompt
    seed: int
    brief_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")  # brief normalisé (strip, espaces réduits)
    pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")  # octets du fichier du pack
    duration_ms: int = Field(ge=0)
    tokens: dict[str, int] = Field(default_factory=dict)  # prompt, completion (somme des appels)
    repairs: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    edits: int = 0


class Design(BaseModel):
    """spec.design : présent seulement si le concept vient de l'IA (ADR 0008)."""

    version: Literal[1] = 1
    brief: str = Field(min_length=20, max_length=2000)
    audience: Audience
    fixed: dict[str, Any] = Field(default_factory=dict)  # contraintes du formateur (clés de FIXABLE)
    context: str = Field(min_length=20, max_length=700)
    objectives: list[DesignObjective] = Field(min_length=2, max_length=4)
    debrief: list[DebriefQuestion] = Field(default_factory=list, max_length=6)  # vide si journey est en repli
    unmet: list[str] = Field(default_factory=list, max_length=3)  # chacune <= 120 caractères
    rationale: dict[str, str] = Field(default_factory=dict)  # clés RATIONALE_KEYS, <= 160 caractères
    playability: dict[str, Any] = Field(default_factory=dict)  # sortie de design.playability
    origin: DesignOrigin

    @model_validator(mode="after")
    def _shape(self) -> "Design":
        errors = [f"contrainte non imposable : {k}" for k in sorted(set(self.fixed) - FIXABLE)]
        errors += [f"justification inconnue : {k}" for k in sorted(set(self.rationale) - RATIONALE_KEYS)]
        errors += [f"justification {k} : 160 caractères au plus" for k, v in self.rationale.items() if len(v) > 160]
        errors += [f"non couvert : 120 caractères au plus ({u[:20]}…)" for u in self.unmet if len(u) > 120]
        if errors:
            raise ValueError("; ".join(errors[:10]))
        return self


class DesignRequest(BaseModel):
    """Corps de POST /games/designs."""

    pack: Code
    brief: str = Field(min_length=20, max_length=2000)
    audience: Audience = "licence"
    fixed: dict[str, Any] = Field(default_factory=dict)
    players_min: int = Field(default=2, ge=1, le=60)
    players_max: int = Field(default=6, ge=1, le=60)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _check(self) -> "DesignRequest":
        unknown = sorted(set(self.fixed) - FIXABLE)
        if unknown:
            raise ValueError(f"contrainte non imposable : {', '.join(unknown)}")
        players = {"players_min": self.players_min, "players_max": self.players_max}
        GameParams(**(default_params(self.pack) | self.fixed | players))  # ValueError si le pack ou une valeur refuse
        return self


class DesignEdit(BaseModel):
    """Corps de PUT /games/{id}/design ; un champ absent reste inchangé."""

    title: str | None = Field(default=None, min_length=10, max_length=80)
    pitch: str | None = Field(default=None, min_length=40, max_length=500)
    context: str | None = Field(default=None, min_length=20, max_length=700)
    objectives: list[DesignObjective] | None = None
    debrief: list[DebriefQuestion] | None = None
    agents: list[CastAgent] | None = None
    panels: list[str] | None = None  # ids du catalogue du pack, dans l'ordre d'affichage
    tools: list[str] | None = None  # idem
    tutorial: list[TutorialStep] | None = None
    tunings: dict[str, Difficulty] | None = None
    event_plan: list[PlannedEvent] | None = None
    ui_theme: Code | None = None


def default_params(pack_id: str) -> dict[str, Any]:
    """GameParams d'un pack sans aucun choix : premier secteur, tous les modules (7 au plus), aucun agent en plus,
    ton « mixte » (sinon le premier), « equilibre », défauts de `limits`, aléas « rares », défaut de chaque option."""
    pack = load_pack(pack_id)
    tones = list(pack.get("agent_tones", ["mixte"]))
    options: dict[str, int | str] = {}
    for raw in pack.get("params", []):
        field = ActionField.model_validate(raw)
        if field.type == "int":
            options[field.id] = field.default if field.default is not None else field.min or 0
        else:
            options[field.id] = (field.options or [Option(id="", label="")])[0].id
    return {
        "pack": pack_id,
        "theme": next(iter(pack["themes"])),
        "modules": list(pack["modules"])[:7],
        "extra_agents": [],
        "agent_tone": "mixte" if "mixte" in tones else tones[0],
        "difficulty": "equilibre",
        "weeks": pack.get("limits", {}).get("weeks", ATELIER_LIMITS["weeks"])[2],
        "products": pack.get("limits", {}).get("products", ATELIER_LIMITS["products"])[2],
        "events": "rares",
        "options": options,
    }


class LayoutEdit(BaseModel):
    """Retouche du formateur, en cellules de la grille locale d'un bloc (ADR 0009, point 8). Le contrôle de
    placement relève de layout.check_placement."""

    op: Literal["move", "remove", "add"]
    object_id: str | None = None  # move, remove
    department_id: str | None = None  # add
    asset: str | None = None  # add : clé de grid.palette
    cell: tuple[int, int] | None = None  # move, add
    rot: Literal[0, 90, 180, 270] = 0  # remove : 0

    @model_validator(mode="after")
    def _fields(self) -> "LayoutEdit":
        needed = {"move": {"object_id", "cell"}, "remove": {"object_id"}, "add": {"department_id", "asset", "cell"}}
        given = {k for k in ("object_id", "department_id", "asset", "cell") if getattr(self, k) is not None}
        if self.op == "remove" and self.rot:
            given.add("rot")
        if given != needed[self.op]:
            raise ValueError(f"retouche {self.op} : champs {sorted(needed[self.op])} exigés, aucun autre")
        if self.cell is not None and min(self.cell) < 0:
            raise ValueError(f"retouche {self.op} : cellule négative")
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
    tools: list[Tool] = Field(default_factory=list)
    tutorial: list[TutorialStep] = Field(default_factory=list)
    design: Design | None = None
    layout_edits: list[LayoutEdit] = Field(default_factory=list, max_length=200)

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
        errors += self._world_errors() + self._layout_errors()
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
        errors += panel_errors(self.panels) + self._ui_errors(ids) + self._text_errors()
        if self.design:
            errors += self._design_errors(pack, ids)
        if errors:
            raise ValueError("; ".join(errors[:10]))
        return self

    def _ui_errors(self, ids: dict[str, set[str]]) -> list[str]:
        """Barre d'actions et didacticiel : limites de lisibilité, actions des modules joués, ancres existantes."""
        errors = []
        for audience in ("joueur", "formateur"):
            bar = [t for t in self.tools if t.audience == audience and t.bar]
            if len(bar) > UI_LIMITS["tools"]:
                what = "outils" if audience == "joueur" else f"outils {audience}"
                errors.append(f"{what} : {UI_LIMITS['tools']} au plus ({len(bar)})")
        if len({t.id for t in self.tools}) != len(self.tools):
            errors.append("identifiants d'outil en double")
        errors += self._menu_errors()
        actions = {a.id for m in self.modules for a in m.actions}
        errors += [
            f"outil {t.id} : action {t.action_id} absente des modules joués"
            for t in self.tools
            if t.kind == "action" and t.action_id not in actions
        ]
        if len(self.tutorial) > UI_LIMITS["tutorial_steps"]:
            errors.append(f"didacticiel : {UI_LIMITS['tutorial_steps']} étapes au plus ({len(self.tutorial)})")
        anchors = {
            "panel": {p.id for p in self.panels}, "tool": {t.id for t in self.tools},
            "station": {s.kind for s in self.stations}, "agent": {a.id for a in self.agents},
            "dept": ids["departments"],
        }  # fmt: skip
        for step in self.tutorial:
            kind, _, target = step.anchor.partition(":")
            if target not in anchors[kind]:
                errors.append(f"didacticiel {step.id} : ancre inconnue {step.anchor}")
        return errors

    def _menu_errors(self) -> list[str]:
        """Menus contextuels (ADR 0009, point 9) : cibles connues, action du bon poste, 6 entrées au plus par cible."""
        known = {
            "station": {s.kind for s in self.stations}, "agent": {a.id for a in self.agents} | {"*"},
            "site": {s.kind for s in self.world.sites},
        }  # fmt: skip
        owner = {a.id: m for m in self.modules for a in m.actions}
        errors, count = [], {}
        for tool in self.tools:
            for selector in tool.menu:
                kind, _, target = selector.partition(":")
                if target not in known[kind]:
                    errors.append(f"outil {tool.id} : menu, cible inconnue {selector}")
                    continue
                count[(tool.audience, selector)] = count.get((tool.audience, selector), 0) + 1
                module = owner.get(tool.action_id or "")
                if tool.kind == "action" and kind == "station" and module and target not in module.stations:
                    errors.append(
                        f"outil {tool.id} : l'action {tool.action_id} n'appartient à aucun module du poste {target}"
                    )
        limit = UI_LIMITS["menu_items"]
        errors += [
            f"menu {sel} ({aud}) : {limit} entrées au plus ({n})" for (aud, sel), n in count.items() if n > limit
        ]
        return errors

    def _world_errors(self) -> list[str]:
        """Sites et liens (ADR 0009) ; départements : site existant ; ids d'objet uniques."""
        world, errors = self.world, []
        site_ids = {s.id for s in world.sites}
        errors += [
            f"département {d.id} : site inconnu {d.site_id}"
            for d in self.departments
            if d.site_id and d.site_id not in site_ids
        ]
        object_ids = [o.id for o in world.objects if o.id]
        if len(set(object_ids)) != len(object_ids):
            errors.append("identifiants d'objet en double")
        if not world.sites:
            return errors
        if len(site_ids) != len(world.sites):
            errors.append("identifiants de site en double")
        if [s.external for s in world.sites].count(False) != 1 or world.sites[0].external:
            errors.append("sites : un seul site principal (external faux), en premier")
        bounds = world.bounds
        if bounds is None:
            errors.append("sites : world.bounds est absent")
        for i, a in enumerate(world.sites):
            if bounds and not (bounds[0] <= a.area[0] and bounds[1] <= a.area[1] and a.area[2] <= bounds[2]
                               and a.area[3] <= bounds[3]):  # fmt: skip
                errors.append(f"site {a.id} : hors de world.bounds")
            errors += [
                f"sites {a.id} et {b.id} : aires qui se chevauchent"
                for b in world.sites[i + 1 :]
                if a.area[0] < b.area[2] and b.area[0] < a.area[2] and a.area[1] < b.area[3] and b.area[1] < a.area[3]
            ]
        for link in world.links:
            if link.from_site not in site_ids or link.to_site not in site_ids:
                errors.append(f"lien {link.id} : site inconnu")
            if any(p[0] != q[0] and p[1] != q[1] for p, q in zip(link.points, link.points[1:], strict=False)):
                errors.append(f"lien {link.id} : segment ni horizontal ni vertical")
        suppliers = {s.supplier_id for s in world.sites if s.supplier_id}
        errors += [f"site fournisseur inconnu {x}" for x in sorted(suppliers - {s.id for s in self.suppliers})]
        errors += [f"fournisseur {x} sans site" for x in sorted({o.supplier_id for o in self.offers} - suppliers)]
        return errors

    def _layout_errors(self) -> list[str]:
        """layout_edits : champs selon l'opération (modèle) ; ici seulement des ids d'objet ou de département connus,
        et retrait réservé aux rôles `decor` et `affichage` sans `ref`."""
        objects = {o.id: o for o in self.world.objects if o.id}
        departments = {d.id for d in self.departments}
        errors = []
        for rank, edit in enumerate(self.layout_edits, start=1):
            if edit.op == "add":
                if edit.department_id not in departments:
                    errors.append(f"retouche {rank} : département inconnu {edit.department_id}")
                continue
            target = objects.get(edit.object_id or "")
            added = (edit.object_id or "").rpartition(
                ".ajout."
            )  # objet ajouté par une retouche : « <dép>.ajout.<rang> »
            if target is None and not (added[1] and added[0] in departments and added[2].isdigit()):
                errors.append(f"retouche {rank} : objet inconnu {edit.object_id}")
            elif edit.op == "remove" and target and (target.role not in EDITABLE_ROLES or target.ref):
                errors.append(f"retouche {rank} : l'objet {edit.object_id} est simulé, il ne se retire pas")
        return errors

    def _text_errors(self) -> list[str]:
        """Aucun chiffre ni lien dans un texte conçu : les nombres viennent du moteur, les sources du pack."""
        texts = [(f"fiche de {a.id}", a.backstory) for a in self.agents if a.backstory]
        texts += [(f"didacticiel {s.id}", f"{s.title} {s.text}") for s in self.tutorial]
        if self.design:
            d = self.design
            texts += [("contexte", d.context)] + [(f"objectif {o.id}", o.text) for o in d.objectives]
            texts += [(f"question {q.id}", q.text) for q in d.debrief] + [("non couvert", u) for u in d.unmet]
            texts += [(f"justification {k}", v) for k, v in d.rationale.items()]
        return [f"{where} : ni chiffre ni lien dans un texte conçu" for where, text in texts
                if forbidden_in_text(text)]  # fmt: skip

    def _design_errors(self, pack: dict[str, Any], ids: dict[str, set[str]]) -> list[str]:
        """Cohérence de spec.design avec les modules, notions et indicateurs de la spec et du pack."""
        design = self.design
        assert design is not None
        pack_notions = pack.get("notions", {})
        indicators = set(INDICATORS["factory" if self.factory else "weekly"])
        errors = []
        objective_ids = [o.id for o in design.objectives]
        if len(set(objective_ids)) != len(objective_ids):
            errors.append("identifiants d'objectif en double")
        question_ids = [q.id for q in design.debrief]
        if len(set(question_ids)) != len(question_ids):
            errors.append("identifiants de question en double")
        for o in design.objectives:
            errors += [f"objectif {o.id} : module inactif {m}" for m in o.module_ids if m not in ids["modules"]]
            own = {n for m in self.modules if m.id in o.module_ids for n in m.notions}
            own |= {n for a in self.agents if a.module_id in o.module_ids for n in a.notions}
            for n in o.notion_ids:
                if n not in ids["notions"] | pack_notions.keys():
                    errors.append(f"objectif {o.id} : notion inconnue {n}")
                elif n not in own:
                    errors.append(f"objectif {o.id} : la notion {n} n'appartient à aucun de ses modules")
            if o.indicator not in indicators:
                errors.append(f"objectif {o.id} : indicateur inconnu {o.indicator}")
                continue
            declared = [pack_notions[n]["indicators"] for n in o.notion_ids if "indicators" in pack_notions.get(n, {})]
            if declared and o.indicator not in {i for allowed in declared for i in allowed}:
                errors.append(f"objectif {o.id} : l'indicateur {o.indicator} n'illustre aucune de ses notions")
        by_id = {o.id: o for o in design.objectives}
        for q in design.debrief:
            objective = by_id.get(q.objective_id)
            if objective is None:
                errors.append(f"question {q.id} : objectif inconnu {q.objective_id}")
            elif q.notion_id not in objective.notion_ids:
                errors.append(f"question {q.id} : la notion {q.notion_id} n'est pas celle de l'objectif {objective.id}")
        if design.origin.sections.get("journey") != "repli":
            asked = {q.objective_id for q in design.debrief}
            errors += [f"objectif {o.id} sans question de débrief" for o in design.objectives if o.id not in asked]
        return errors

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
    _check_pack("atelier", catalog)
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
    try:
        _check_design_keys(pack_id, pack)
        _check_world_keys(pack_id, pack)
    except ValueError as exc:  # ValidationError de Tool ou TutorialStep : message préfixé par le pack
        if str(exc).startswith(f"pack {pack_id}"):
            raise
        raise ValueError(f"pack {pack_id} : {exc}") from exc


def _check_design_keys(pack_id: str, pack: dict[str, Any]) -> None:
    """Clés de conception d'un pack (ADR 0008, annexe §1) : `tunables`, `notions.*.indicators`, `tools`, `tutorial`."""
    notions = pack.get("notions", {})
    for key, tunable in pack.get("tunables", {}).items():
        for profile in get_args(Difficulty):
            value = pack.get("difficulties", {}).get(profile, {}).get(key)
            if type(value) not in (int, float):
                raise ValueError(f"pack {pack_id} : tunables.{key} doit être numérique dans le profil {profile}")
        label = tunable.get("label")
        if not isinstance(label, str) or not 0 < len(label) <= UI_LIMITS["panel_title"]:
            raise ValueError(
                f"pack {pack_id} : tunables.{key}.label : texte de {UI_LIMITS['panel_title']} caractères au plus"
            )
        # shortcut: `value` n'est exigé nulle part tant que l'usine ne le déclare pas (arbitrage e : à exiger quand
        # game-designer l'aura livré) ; déclaré, il doit désigner une clé de `values`
        if "value" in tunable and tunable["value"] not in pack.get("values", {}):
            raise ValueError(f"pack {pack_id} : tunables.{key}.value : clé absente de values : {tunable['value']}")
        missing = [n for n in tunable.get("teaches", []) if n not in notions]
        if missing:
            raise ValueError(f"pack {pack_id} : tunables.{key}.teaches : notion inconnue {', '.join(missing)}")
    for notion_id, notion in notions.items():
        indicators = notion.get("indicators", [])
        if not isinstance(indicators, list) or not all(isinstance(i, str) for i in indicators):
            raise ValueError(f"pack {pack_id} : notions.{notion_id}.indicators doit être une liste d'identifiants")
        known = INDICATORS["factory" if pack.get("engine") == "factory" else "weekly"]
        if not set(indicators) <= set(known):
            raise ValueError(f"pack {pack_id} : notions.{notion_id}.indicators : inconnus du moteur : {indicators}")
    tools = [Tool.model_validate(t) for t in pack.get("tools", [])]
    actions = {a["id"] for m in pack["modules"].values() for a in m.get("actions", [])}
    action_tools = [t.action_id for t in tools if t.kind == "action"]
    if len({t.id for t in tools}) != len(tools) or len(set(action_tools)) != len(action_tools):
        raise ValueError(f"pack {pack_id} : tools : identifiant ou action en double")
    missing = [a for a in action_tools if a not in actions]
    if missing:
        raise ValueError(f"pack {pack_id} : tools : action absente des modules du pack : {', '.join(missing)}")
    tutorial = [TutorialStep.model_validate(s) for s in pack.get("tutorial", [])]
    if len(tutorial) > UI_LIMITS["tutorial_steps"]:
        raise ValueError(f"pack {pack_id} : tutorial : {UI_LIMITS['tutorial_steps']} étapes au plus")
    known = {
        "panel": {p["id"] for p in pack.get("panels", [])}, "tool": {t.id for t in tools},
        "station": pack_station_kinds(pack_id, pack), "dept": {d["id"] for d in pack.get("departments", [])},
    }  # fmt: skip  # pas d'ancre « agent: » : les agents n'existent qu'une fois la partie générée
    for step in tutorial:
        kind, _, target = step.anchor.partition(":")
        if target not in known.get(kind, ()):
            raise ValueError(f"pack {pack_id} : tutorial {step.id} : ancre inconnue du pack {step.anchor}")


def _positive(value: Any, *, zero: bool = False) -> bool:
    return type(value) in (int, float) and (value >= 0 if zero else value > 0)


def _check_world_keys(pack_id: str, pack: dict[str, Any]) -> None:
    """Clés de monde d'un pack (ADR 0009) : `grid`, `block_types`, `network`, `placement_rules`, `values` reseau.*,
    blocs et éléments des départements. Toutes facultatives (l'atelier n'en déclare aucune) ; déclarées, elles sont
    contrôlées en entier."""

    def fail(message: str) -> None:
        raise ValueError(f"pack {pack_id} : {message}")

    departments = pack.get("departments", [])
    grid = pack.get("grid")
    if grid is not None:
        cell = grid.get("site_cell_m") if isinstance(grid, dict) else None
        if not _positive(cell):
            fail("grid.site_cell_m doit être un nombre positif")
        for d in departments:
            for edge in () if d.get("external") else d.get("area", ()):
                if abs(edge / cell - round(edge / cell)) > 1e-6:
                    fail(f"departments.{d['id']}.area : multiple de grid.site_cell_m ({cell}) attendu")
    blocks = pack.get("block_types", {})
    for block_id, block in blocks.items():
        where = f"block_types.{block_id}"
        if not isinstance(block.get("label"), str) or block.get("pattern") not in PATTERNS:
            fail(f"{where} : label et pattern ({', '.join(PATTERNS)}) attendus")
        if not _positive(block.get("cell_m")):
            fail(f"{where}.cell_m doit être un nombre positif")
        for key in ("front_aisle_cells", "row_aisle_cells"):
            if type(block.get(key, 0)) is not int or block.get(key, 0) < 0:
                fail(f"{where}.{key} doit être un entier positif ou nul")
        decor = block.get("decor", [])
        if not isinstance(decor, list) or not all(isinstance(a, str) for a in decor):
            fail(f"{where}.decor doit être une liste d'assets")
    sides, roles = get_args(Side), get_args(ElementRole)
    for d in departments:
        if "block" in d and d["block"] not in blocks:
            fail(f"departments.{d['id']}.block : type de bloc inconnu {d['block']}")
        if "front" in d and d["front"] not in sides:
            fail(f"departments.{d['id']}.front : {', '.join(sides)} attendu")
        if "capacity" in d and d["capacity"] not in ("mp_capacity_pallets", "pf_capacity_pallets"):
            fail(f"departments.{d['id']}.capacity : mp_capacity_pallets ou pf_capacity_pallets attendu")
        for element in d.get("elements", []):
            where = f"departments.{d['id']} élément {element.get('asset')}"
            if "role" in element and element["role"] not in roles:
                fail(f"{where} : role inconnu {element['role']}")
            if "count" in element and "per" in element:
                fail(f"{where} : count ou per, pas les deux")
            if "count" in element and (type(element["count"]) is not int or element["count"] < 0):
                fail(f"{where} : count entier positif ou nul attendu")
            if "per" in element and element["per"] not in ("line", "machine", "places"):
                fail(f"{where} : per vaut line, machine ou places")
            if element.get("per") == "places" and not _positive(element.get("places")):
                fail(f"{where} : per places exige places (places par élément)")
    network = pack.get("network")
    if network is not None:
        classes, link_types, sites = (network.get(k, {}) for k in ("distance_classes", "link_types", "sites"))
        cell = network.get("map", {})
        if not _positive(cell.get("cell_m")) or not _positive(cell.get("road_offset_m"), zero=True):
            fail("network.map : cell_m positif et road_offset_m positif ou nul attendus")
        if not _positive(network.get("driving_h_per_day")):
            fail("network.driving_h_per_day doit être un nombre positif")
        if not classes or not link_types or not sites:
            fail("network : distance_classes, link_types et sites ne sont pas vides")
        for name, c in classes.items():
            if not isinstance(c.get("label"), str) or not _positive(c.get("km")) or type(c.get("ring")) is not int:
                fail(f"network.distance_classes.{name} : label, km positif et ring entier attendus")
        for name, t in link_types.items():
            if not isinstance(t.get("label"), str) or not _positive(t.get("speed_kmh")) or not t.get("vehicle"):
                fail(f"network.link_types.{name} : label, speed_kmh positif et vehicle attendus")
        for name, site in sites.items():
            where = f"network.sites.{name}"
            if not re.fullmatch(CODE_PATTERN, str(site.get("kind"))) or site.get("side") not in ("ouest", "est"):
                fail(f"{where} : kind (code) et side (ouest ou est) attendus")
            if site.get("link") not in link_types or not site.get("building"):
                fail(f"{where} : link du pack et building attendus")
            distances = site.get("distances")
            if not distances or not isinstance(distances, list) or not set(distances) <= classes.keys():
                fail(f"{where}.distances : classes de distance du pack attendues")
            if site.get("default") not in distances:
                fail(f"{where}.default : une des distances permises attendue")
            if type(site.get("prep_days")) is not int or site["prep_days"] < 0:
                fail(f"{where}.prep_days : entier positif ou nul attendu")
        if "values" in pack:  # chaque nombre du réseau a sa provenance
            wanted = [f"reseau.distance.{c}" for c in classes] + [f"reseau.vitesse.{t}" for t in link_types]
            wanted += ["reseau.conduite_h_jour", *(f"reseau.preparation.{s}" for s in sites)]
            absent = [k for k in wanted if k not in pack["values"]]
            if absent:
                fail(f"values : provenance absente : {', '.join(absent)}")
    rules = pack.get("placement_rules", [])
    if len({r.get("id") for r in rules}) != len(rules):
        fail("placement_rules : identifiant en double")
    known = {d["id"] for d in departments} | set(blocks)
    needs = {"adjacent": ("a", "b"), "flow": ("blocks",), "separated": ("a", "b", "min_m"), "aisle_min": ("min_m",),
             "facing": ("block", "role", "toward"), "near": ("a", "b", "max_m")}  # fmt: skip
    for rule in rules:
        where, kind = f"placement_rules.{rule.get('id')}", rule.get("kind")
        if kind not in RULE_KINDS:
            fail(f"{where} : kind vaut {', '.join(RULE_KINDS)}")
        if rule.get("status") not in get_args(ValueStatus):
            fail(f"{where} : status vaut source, calibre ou exemple")
        origin = "citation" if rule["status"] == "source" else "note"
        if not rule.get(origin):
            fail(f"{where} : {origin} manquante (provenance)")
        absent = [k for k in needs[kind] if k not in rule]
        if absent:
            fail(f"{where} : paramètres manquants {', '.join(absent)}")
        if any(not _positive(rule[k]) for k in ("min_m", "max_m") if k in rule):
            fail(f"{where} : min_m et max_m sont des nombres positifs")
        if kind == "flow" and (not isinstance(rule["blocks"], list) or len(rule["blocks"]) < 2):
            fail(f"{where} : flow veut au moins deux blocs")
        refs = rule["blocks"] if kind == "flow" else [rule[k] for k in ("a", "b", "block") if k in rule]
        unknown = [] if kind == "separated" else [r for r in refs if r not in known]  # separated accepte des `ref`
        if unknown:
            fail(f"{where} : bloc inconnu {', '.join(map(str, unknown))}")
        if kind == "facing" and (rule["role"] not in roles or rule["toward"] not in ("front", "dock", "centre")):
            fail(f"{where} : role du pack et toward front, dock ou centre attendus")


def pack_station_kinds(pack_id: str, pack: dict[str, Any]) -> frozenset[str]:
    """Types de poste acceptés : ceux des modules et des départements du pack, plus `machine` pour une usine (liste
    figée pour l'atelier)."""
    if pack_id == "atelier":
        return ATELIER_STATION_KINDS
    kinds = {k for m in pack["modules"].values() for k in m.get("stations", [])}
    kinds |= {s["kind"] for d in pack.get("departments", []) for s in d.get("stations", [])}
    return frozenset(kinds | ({"machine"} if pack.get("engine") == "factory" else set()))
