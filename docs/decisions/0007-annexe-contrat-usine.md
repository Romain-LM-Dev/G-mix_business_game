# 0007, annexe : contrat du pack « usine » et plan d'exécution

Référence pour les briefs de délégation (ADR 0007). Les noms de champs Python sont en anglais ; les codes de
contenu (états, modules, postes) restent en français comme aujourd'hui. Toute divergence d'implémentation avec ce
contrat se signale à l'architecte avant d'être codée. ADR acceptée le 2026-10-28 : les changements de
l'acceptation sont marqués « (28/10) ». (29/10) Arbitrages après la transcription de spec.py par moteur-jeu :
marqués « (29/10) », corrections de code à faire listées au §7, étape 2.

## 1. Spec : ajouts à `backend/gmix/game/spec.py` (tous facultatifs ou élargissements)

Une spec v2 existante (pack `atelier`) doit rester valide sans modification. `version` reste 2.

```python
from typing import Annotated
Code = Annotated[str, Field(pattern=r"^[a-z_]{2,30}$")]
ModuleId = Code              # était un Literal : vérifié contre le pack dans GameParams et SimSpec
StationKind = Code           # idem
ExtraAgentId = Code          # (29/10) était un Literal : vérifié contre les clés de pack["extra_agents"]
MachineState = Literal["arret", "marche", "pause", "reglage", "panne", "attente_matiere", "sortie_pleine"]
AgentState = Literal["disponible", "occupe", "deplacement", "pause", "absent"]
ProductState = Literal["en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie"]
ValueStatus = Literal["source", "calibre", "exemple"]
Rect = tuple[float, float, float, float]   # x_min, z_min, x_max, z_max (m, repère du monde Godot)
PUBLIC_ROOTS = {"status", "week", "weeks", "cash", "overdraft", "kpis", "targets", "history", "stocks",
                "components", "lines", "pending", "settings", "event", "last", "log", "briefings", "factory"}
# (29/10) = toutes les clés de premier niveau de engine.public_state : un panneau peut lire chacune (journal des
#   décisions, découvert, faits des agents). Un test garde l'égalité : clés de public_state d'une spec atelier
#   + {"factory"} == PUBLIC_ROOTS == clés de public_state d'une spec usine.

# Champs ajoutés aux modèles existants
GameParams.pack: Code = "atelier"
GameParams.options: dict[str, int | str] = {}      # options du pack (format ActionField), validées contre le pack
GameParams.products: int = Field(default=3, ge=1, le=4)   # bornes du pack vérifiées par le validateur
#   _check : theme, modules, extra_agents, products et options vérifiés contre load_pack(pack)
ActionField.source: Literal["offers", "lines", "products", "machines"] | None
Meta.domain: str = "supply-chain"       # slug de ai/domains.yaml (RAG des agents, menu)
Meta.pack: Code = "atelier"
Agent.kind: Literal["module", "client", "fournisseur", "direction", "departement"]
Agent.department_id: str | None = None
Agent.facts: str | None = None          # clé de engine._FACTS ; None = règle actuelle (module_id ou kind)
Station.department_id: str | None = None
World.template: Literal["atelier", "usine"] = "atelier"

class Provenance(BaseModel):
    status: ValueStatus
    citation: str | None = None          # obligatoire si status == "source"
    note: str | None = None              # obligatoire sinon : d'où vient la valeur, pourquoi ce choix

class Department(BaseModel):
    id: Code
    label: str
    external: bool = False
    area: Rect

class Machine(BaseModel):
    id: str = Field(pattern=r"^l\d-m\d$")   # « l1-m3 » (cahier : L1-M3)
    line_id: str
    rank: int = Field(ge=1, le=8)
    name: str                            # « M3 · Soudage »
    operation: str
    cycle_min: float = Field(gt=0, le=240)
    run_min: float = Field(gt=0)         # marche avant une pause planifiée
    stop_min: float = Field(ge=0)        # durée de la pause planifiée
    mtbf_h: float = Field(gt=0)          # moyenne de la loi des pannes, en heures de marche
    weibull_shape: float = Field(default=2.0, ge=1.0, le=5.0)
    mttr_h: float = Field(gt=0)
    setup_min: float = Field(ge=0)       # à chaque changement de lot
    tool_life: int | None = Field(default=None, gt=0)   # produits avant changement d'outil
    tool_change_min: float = Field(default=0, ge=0)
    defect_rate: float = Field(ge=0, le=0.5)
    buffer: int = Field(ge=1, le=500)    # capacité de la table d'attente en sortie
    transfer_min: float = Field(ge=0)
    operators: int = Field(default=1, ge=0, le=4)
    asset: str

class BomItem(BaseModel):
    component_id: str
    per_unit: float = Field(gt=0)

class CrewMember(BaseModel):             # figurant : état animé, aucun dialogue
    id: str
    job: Code                            # operateur, chauffeur_fournisseur, chauffeur_client
    department_id: str
    machine_id: str | None = None
    character: str

class Clock(BaseModel):
    days_per_turn: int = Field(default=5, ge=1, le=5)
    minutes_per_day: int = Field(default=480, ge=60, le=1440)
    day_start_h: int = Field(default=8, ge=0, le=23)
    frame_min: float = Field(default=5, gt=0, le=60)
    breaks: list[tuple[int, int]] = []   # (28/10) pauses du personnel : (début en min depuis day_start_h, durée en
    #   min), dans la journée, sans chevauchement ; arrêtent toutes les machines (sauf relève au goulot) et les
    #   postes ; s'ajoutent aux arrêts propres à chaque machine (run_min / stop_min, stop_min = 0 : aucun)

class Logistics(BaseModel):
    units_per_pallet_mp: int = Field(gt=0)
    unload_min_per_pallet: float = Field(ge=0)
    inspect_min_per_pallet: float = Field(ge=0)
    supplier_nonconform_rate: float = Field(ge=0, le=0.5)
    delivery_window_min: tuple[int, int] = (0, 120)     # depuis le début de journée (cahier : 8 h - 10 h)
    mp_capacity_pallets: int = Field(gt=0)
    kit_min: float = Field(ge=0)                        # préparation et livraison d'un kit d'OF
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
    orders_per_day: int = Field(default=1, ge=1, le=10)            # (29/10) commandes passées par jour ouvré, à l'ouverture
    pickup_window_min: tuple[int, int] = (360, 450)                # (29/10) camion du client, en min depuis day_start_h
# (29/10) _factory_errors : 0 <= début < fin <= clock.minutes_per_day pour pickup_window_min et delivery_window_min.
# (29/10) En usine, Offer.lead_time est en jours ouvrés (1 à 8) et Offer.min_order en palettes ; atelier inchangé
#   (semaines, unités). Une commande d'achat = un camion.

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
    product_id: str                      # toutes les lignes font ce produit (cahier) ; Product.line_id = l1
    lot_size: int = Field(gt=0, le=1000)
    pf_min: int = Field(ge=0)            # sous ce stock PF, le pilote automatique relance un OF
    bom: list[BomItem] = Field(min_length=1)
    machines: list[Machine] = Field(min_length=1)
    crew: list[CrewMember] = Field(default_factory=list)
    clock: Clock = Clock()
    logistics: Logistics
    customer: Customer
    resources: Resources = Resources()
    costs: FactoryCosts
    protect_buffer: int = Field(default=30, ge=1, le=500)   # (29/10) table devant le goulot en mode tampon_avant

PanelType = Literal["kpis", "table", "gauge", "chart", "flow"]

class PanelColumn(BaseModel):
    key: str                             # clé d'un élément (table), d'un indicateur (kpis) ou de history (chart)
    label: str
    format: Literal["text", "int", "dec1", "pct", "money", "minutes", "state"] = "text"
    labels: dict[str, str] = Field(default_factory=dict)   # format state : code -> libellé affiché
    target: str | None = None            # chemin de la cible (ex. « targets.otif »)

class Panel(BaseModel):
    id: Code
    type: PanelType
    title: str
    placement: Literal["bandeau", "tableau_de_bord", "poste"]
    station_kinds: list[StationKind] = Field(default_factory=list)   # placement « poste »
    source: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)*$")           # racine dans PUBLIC_ROOTS
    match: str | None = None             # poste : ne garder que les éléments dont item[match] == station.ref
    columns: list[PanelColumn] = Field(default_factory=list)
    min: float | None = None             # gauge
    max: float | None = None

SimSpec.departments: list[Department] = []
SimSpec.factory: Factory | None = None
SimSpec.panels: list[Panel] = []
SimSpec.provenance: dict[str, Provenance] = {}   # clé « famille.paramètre », ex. « machine.mtbf_h »
```

Contrôles ajoutés à `SimSpec._references` (messages en français, 10 au plus comme aujourd'hui) :
- `factory` présent : `product_id`, `bom[].component_id`, `machines[].line_id` connus ; ids de machine uniques ;
  rangs contigus de 1 à k sur chaque ligne ; `crew[].department_id` et `machine_id` connus ; `world.template == "usine"`.
- `agents[].department_id`, `stations[].department_id` dans `departments` ; ids de départements uniques.
- Panneau : racine de `source` dans `PUBLIC_ROOTS` ; `station_kinds` présents dans `stations[].kind`.
- Provenance : `citation` si `source`, `note` sinon.
- Références du monde : en plus des actuelles, si `factory` : `machine:<id>`, `buffer:<id>`, `mp:<component_id>`,
  `dept:<id>`, `pf`, `dock`, `scrap`, `quarantine`.
- (29/10) Erreurs de validation en plus : racine de `PanelColumn.target` hors `PUBLIC_ROOTS` (même règle que
  `source`) ; deux panneaux de même `id` ; si `factory` : une ligne dont `product_id` diffère de
  `factory.product_id` (toutes les lignes font le même produit). Ne sont PAS des erreurs : lignes de longueurs
  différentes, panneau sans colonne.
- (29/10) Contrôles ajoutés par moteur-jeu, acceptés : `Machine.id == f"{line_id}-m{rank}"` (donc ids de ligne
  `l1` à `l9` en usine) ; au moins une machine par ligne ; `Department.area` avec x_min < x_max et z_min < z_max ;
  `meta.pack == params.pack` ; types de poste vérifiés contre le pack (`pack_station_kinds`).

`load_pack(pack_id) -> dict` (même module) : `atelier` -> `load_sim_catalog()` (ai/simulation.yaml) ; autre id ->
`ai/packs/<id>.yaml`, notions résolues comme aujourd'hui (`source:` -> ligne « > Source : » de la fiche,
sinon `citation:`), `lru_cache`.
(29/10) Un seul format de limites : `limits: {weeks: [min, max, défaut], products: [min, max, défaut]}`, trois
entiers, le même que `ranges` de `GET /games/options` déjà lu par Godot. Atelier : `{weeks: [4, 12, 8],
products: [2, 4, 3]}`. Une liste qui n'a pas trois entiers avec min <= défaut <= max est refusée au chargement.

## 2. État public : `engine.public_state(spec, state)["factory"]` (présent si `spec.factory`)

C'est le contrat entre moteur-jeu (producteur) et godot-dev (panneaux, décor). Les clés existantes (`kpis`,
`targets`, `history`, `stocks`, `components`, `lines`, `pending`, `last`, `briefings`…) restent, remplies au sens
du modèle usine (`lines[].capacity` = débit théorique du goulot x temps du tour ; `trs` = TRS mesuré).

| Clé | Contenu |
|---|---|
| `day` | jours simulés depuis le début (int) |
| `machines[]` | `id, line_id, rank, name, state` (MachineState, fin du dernier tour), `bottleneck` (bool), `rate_h` (60 / cycle), `availability` (% mesuré), `produced, defects, failures, downtime_min` (dernier tour), `buffer, buffer_max`, `age_h`, `tool_left` (int ou null) |
| `lines[]` | `id, name, bottleneck_id, theoretical_h` (goulot), `expected_h` ((28/10) formule du cahier corrigée : 60 / cycle du goulot x part du temps hors pauses x MTBF / (MTBF + trajet + MTTR) du goulot x rendement cumulé de la ligne ; le cahier ignore les pannes et ne prend que les défauts du goulot), `real_h` (mesuré), `production_rate` (% bons / prévus), `wip`, `of_id` (OF en cours ou null) |
| `stocks` | `mp[]` : `component_id, name, quantity, pallets, capacity_pallets, reorder_point, pending` ; `pf` : `quantity, pallets, capacity_pallets, min` ; `quarantine` (int) |
| `orders` | `production[]` : `id, line_id, quantity, done, status` (attente, en_cours, termine) ; `customer[]` : `id, quantity, due_day, shipped, status` (ouverte, livree, en_retard), commandes ouvertes et 10 dernières closes |
| `agents` | `{<id agent ou figurant>: {state: AgentState, at: id de poste, de machine ou de département, ou null}}` |
| `products` | `{<ProductState>: int}` |
| `flow` | `nodes[]` : `id, label, kind` (departement, machine, tampon), `state` (ou null), `count` ; `edges[]` : `from, to, count` (unités passées au dernier tour) |
| `formulas[]` | `id` (notion, ou `notion.facteur`), `expected, measured, unit` : valeurs calculées par le moteur pour le débrief et les panneaux ; (28/10) TRS décomposé : `capacite_et_trs` puis `capacite_et_trs.disponibilite`, `.performance`, `.qualite` |

(29/10) Précisions pour moteur-jeu et godot-dev :
- Ids : agent d'un département = `agent_<department_id>` (ex. `agent_maintenance`) ; figurants = `op_<machine_id>`
  (ex. `op_l1-m3`), `chauffeur_fournisseur`, `chauffeur_client`.
- Les opérateurs n'ont pas d'événement `agent` : leur état découle de celui de leur machine, par cette table fixe
  (utilisée aussi par `factory.agents`) : `marche`, `reglage`, `panne` -> `occupe` ; `pause` -> `pause` ;
  `arret`, `attente_matiere`, `sortie_pleine` -> `disponible`.
- `products` : mêmes définitions que les compteurs de la chronologie (§3), à la fin du tour.
- (29/10, pack v0) `kpis` en usine garde `otif, trs, cash` et ajoute `good_share` : part de bons mesurée au
  contrôle au dernier tour, en % (0 à 100), `null` avant le premier tour. `kpis.stockouts` y compte les
  jours-ligne arrêtés faute de MP au dernier tour ; le débrief l'intitule ainsi (pas « références en rupture »).
- (29/10, pack v0) Plusieurs panneaux peuvent partager un placement (deux au bandeau) : Godot les affiche dans
  l'ordre du pack.
- Chemins des panneaux : `table` et `chart` exigent une liste au bout du chemin ; `kpis` et `gauge` lisent des
  nombres ou des textes (`source` + `column.key`). Godot affiche « donnée absente » sinon. `briefings` est un
  dictionnaire par agent : lisible, mais aucun panneau ne le lit en tranche 1 (le dialogue l'affiche déjà).

`state.last` (rapport du tour) garde les clés lues par `advance`, `debrief` et `autopilot_check` (`week, kpis,
totals{demand, served, lost, returns}, delayed, event, costs, revenue`) ; OTIF calculé commande par commande
(livrée complète au plus tard le jour promis). Budget : état public < 64 Ko JSON (3 lignes x 4 machines, 12 tours).

## 3. Chronologie d'un tour (`Timeline`, rendue par l'API, rejouée par Godot)

```python
EventKind = Literal["of_lance", "kit_livre", "lot_termine", "panne", "reparation_debut", "reparation_fin",
                    "preventif", "reglage", "changement_outil", "livraison_mp", "non_conforme", "rebut", "palette",
                    "commande_client", "expedition", "agent"]
class Timeline(BaseModel):
    week: int
    days: int
    minutes_per_day: int
    day_start_h: int
    frame_min: float
    states: list[MachineState]     # ordre des codes : l'index est la valeur des instantanés
    machines: list[str]            # ordre des colonnes machine
    counters: list[str]            # "mp" puis les ProductState
    frames: list[tuple[float, list[int], list[int], list[int]]]   # t, états, tables d'attente, compteurs
    events: list[tuple[float, EventKind, str, dict[str, Any]]]    # t, type, sujet (id), données
```

- `t` en minutes simulées depuis le début du tour ; jour = `t // minutes_per_day` ; heure affichée =
  `day_start_h` + reste. Un instantané toutes les `frame_min` minutes, plus le dernier à la fin du tour.
- Événement `agent` : sujet = id d'agent ou de figurant ; données `{state, at, until}` (`until` : fin prévue,
  pour animer un déplacement). `panne` : `{duration_min}` ; `livraison_mp` et `expedition` : `{quantity}`.
- Le moteur place la chronologie dans `state["last"]["timeline"]` ; l'API la retire avant d'enregistrer l'état ;
  `public_state` ne la rend jamais (garde-fou des deux côtés). Budget : < 200 Ko JSON par tour.
- Validée par un test (modèle ci-dessus, dans spec.py ou le test) ; Godot ne calcule rien, il interpole.

(29/10) Forme exacte, à coder séparément par moteur-jeu (production), backend-api (stockage JSONB tel quel, sans
transformation) et godot-dev (rejeu) :
- `states` = toujours les 7 codes dans l'ordre du Literal `MachineState` (index 0 `arret` à 6 `sortie_pleine`).
- `machines` = ids de `spec.factory.machines`, triés par ligne puis par rang ; M = leur nombre.
- `counters` = toujours `["mp", "en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe",
  "stock_pf", "expedie"]` (C = 9). En unités de produit (de MP pour `mp`), jamais en palettes. `mp` : stock MP
  hors quarantaine et hors kits livrés ; `en_cours` : unités dans les machines et sur les tables, sauf la table de
  la dernière machine ; `a_controler` : table de la dernière machine et file du contrôle ; `conforme` : bonnes,
  en attente d'emballage ; `a_retoucher` : 0 en tranche 1 ; `emballe` : en colis ou en palette, pas encore à
  l'entrepôt ; `stock_pf` : à l'entrepôt PF ; `rebut` et `expedie` : cumuls depuis le début du tour.
- Instantané = `[t, états, tables, compteurs]` : `états` liste de M entiers de 0 à 6 (un par machine, ordre de
  `machines`) ; `tables` liste de M entiers (unités sur la table de sortie de chaque machine, de 0 à
  `Machine.buffer` ; celle de la dernière machine précède le contrôle) ; `compteurs` liste de C entiers.
  Valeurs à l'instant t, après tous les événements datés de t.
- `t` : minutes de travail depuis le début du tour, arrondies au centième ; la nuit n'existe pas (t = 480 :
  fin du jour 1 et début du jour 2, encours conservé). Instantanés à t = 0, f, 2f… et un dernier à
  T = days x minutes_per_day si T n'est pas un multiple de f ; t strictement croissant (481 instantanés par défaut).
- Événements triés par t croissant, ordre de production à t égal ; toutes les clés de données présentes, `null`
  seulement là où c'est indiqué :

| Type | Sujet | Données |
|---|---|---|
| `of_lance`, `kit_livre`, `lot_termine` | id d'OF | `line_id`, `quantity` (unités ; de MP pour `kit_livre`) |
| `panne` | id de machine | `duration_min` (réparation tirée, hors trajet et attente du technicien) |
| `reparation_debut`, `reparation_fin` | id de machine | `by` (id d'agent) |
| `preventif` | id de machine | `by`, `duration_min` |
| `reglage`, `changement_outil` | id de machine | `duration_min` |
| `livraison_mp`, `non_conforme` | id de commande d'achat | `component_id`, `quantity` (acceptée ; mise en quarantaine) |
| `rebut` | id de ligne d'origine | `quantity` |
| `palette` | `pf` | `quantity` (unités de la palette entrée à l'entrepôt) |
| `commande_client` | id de commande client | `quantity`, `due_day` (jour absolu, comme `factory.day`) |
| `expedition` | id de commande client | `quantity`, `on_time` (booléen) |
| `agent` | id d'agent ou de figurant (sauf opérateurs, §2) | `state` (AgentState), `at` (id de poste, machine ou département, ou null), `until` (t de fin prévue, ou null) |

Exemple (une ligne ; une vraie chronologie a 481 instantanés). À t = 125 (jour 1, 10 h 05), M3 est en panne
depuis 118,5 : M2 s'est arrêtée table pleine (10 / 10) avec sa pièce finie dedans, M4 attend la matière, le
technicien répare depuis 121,5. `en_cours` = 4 + 10 + 0 sur les tables + 3 pièces dans M1, M2 et M3 = 17.

```json
{
  "week": 3, "days": 5, "minutes_per_day": 480, "day_start_h": 8, "frame_min": 5,
  "states": ["arret", "marche", "pause", "reglage", "panne", "attente_matiere", "sortie_pleine"],
  "machines": ["l1-m1", "l1-m2", "l1-m3", "l1-m4"],
  "counters": ["mp", "en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie"],
  "frames": [
    [125.0, [1, 6, 4, 5], [4, 10, 0, 2], [1840, 17, 2, 5, 0, 3, 6, 240, 0]]
  ],
  "events": [
    [118.5, "panne", "l1-m3", {"duration_min": 60.0}],
    [118.5, "agent", "agent_maintenance", {"state": "deplacement", "at": "l1-m3", "until": 121.5}],
    [121.5, "reparation_debut", "l1-m3", {"by": "agent_maintenance"}]
  ]
}
```

## 4. API, base, Kafka

- `GET /api/v1/lobbies/{lobby_id}/weeks/{week}/timeline` -> 200 `Timeline` ; 404 si le lobby n'est pas visible
  (même règle que `GET /lobbies/{id}` : membres, formateur du lobby, admin) ou si le tour n'est pas simulé ;
  410 pour une partie d'avant l'ADR 0006. Compression gzip permise (Godot l'accepte).
- Table `lobby_timelines` : `lobby_id` (FK lobbies, ON DELETE CASCADE), `week` (smallint), `timeline` (JSONB),
  `created_at` ; clé primaire (`lobby_id`, `week`). Écrite par `POST /lobbies/{id}/advance` dans la même
  transaction que l'état.
- `GET /api/v1/games/options` : clés actuelles inchangées (pack `atelier`) + `packs[]` : `id, label, description,
  domain, engine, params[]` (format ActionField), `themes[]`, `modules[]`, `limits` (semaines, produits ;
  (29/10) même format que `ranges` : `[min, max, défaut]`).
  `POST /games` accepte `pack` et `options` ; `BusinessGame.domain_slug` = `meta.domain` (fin de la constante
  `DOMAIN` dans games.py) ; `gmix.game.npc` cherche dans le corpus de `spec.meta.domain`.
- Kafka : aucun topic, aucun worker, aucun type d'événement nouveau (`topics.py` inchangé). Le client sait qu'une
  chronologie existe quand `spec.factory` est présent et que `state.last.week` change.

## 5. Pack `ai/packs/usine.yaml` (propriétaire game-designer)

Clés de premier niveau : `version, id, domain, engine, label, description, inspiration, world{template, size,
spawn}, clock, limits{weeks, products}, params[], difficulties, targets, values, machine_types, themes,
departments[], crew[], modules, extra_agents, personalities, agent_tones, events, events_levels, notions, panels[]`
(les quatre de caractère et d'aléas au format de ai/simulation.yaml).

- `params` : `[{id: lines, label: Lignes de production, type: int, min: 1, max: 3, default: 2}]`.
- `values` : `<famille.paramètre>: {value, unit, status, citation | source | note}`. Familles : `fournisseur.*`,
  `reception.*`, `stock_mp.*`, `machine.*`, `qualite.*`, `emballage.*`, `entrepot_pf.*`, `client.*`,
  `maintenance.*`, `pilotage.*`. Copiées dans `spec.provenance` ; les nombres vont dans les champs typés.
- `machine_types` : archétypes (`asset` et paramètres de `Machine`) ; la tranche 1 reprend les 4 machines de
  l'exemple du cahier (§5.2) en `exemple`. Les difficultés jouent sur des facteurs (MTBF, défauts, stocks de
  départ, charge = demande / débit réel, fiabilité fournisseur), en `calibre`.
- `themes.<id>.products[]` : `name, price, cost, operations [[libellé, machine_type]…], mp{name, cost, per_unit,
  units_per_pallet, suppliers[[nom, ville]…]}`. La demande est calculée depuis le débit réel des lignes et la
  charge de la difficulté (le contraire de l'atelier).
- (28/10) Corrections du cahier à appliquer dès la v0 (décision 11 de l'ADR, audit du game-designer) :
  - **Postes hors lignes dimensionnés** : le goulot reste dans les lignes (M3). Au nombre maximal de lignes, contrôle
    et emballage >= 1,2 x débit théorique de l'usine (somme des 60 / cycle du goulot : 60 / h avec l'exemple, donc
    >= 72 / h). Contrôle = 60 / `qc_min_per_unit` ; emballage = 60 x `units_per_case` x `cases_per_pallet` /
    (`cases_per_pallet` x `pack_min_per_case` + `wrap_min_per_pallet`). Le cahier donne 21 / h (17 min par palette
    de 6) : corriger par le format du colis (plusieurs produits par colis) et les temps, en `calibre` avec le
    calcul en note (un second poste demanderait un champ : hors tranche 1). Réception, kits, chariot et quai :
    vérifiés à la mesure (critère 3).
  - **Disponibilité avec les pannes** (le cahier ne compte que les pauses) et TRS décomposé : formule de
    `expected_h` (§2).
  - **Rendement cumulé** : part de bons = produit des (1 - `defect_rate`) des machines de la ligne.
  - **Lot de 24** (4 palettes de 6 au format du cahier) au lieu de 20 : un lot fait des palettes entières (garder
    un multiple de la palette si le colis change). `lot_size` compte les unités lancées ; la palettisation
    continue d'un lot à l'autre.
  - **Charge** : demande = 0,80 à 0,90 x débit réel attendu (`expected_h`) selon la difficulté, en `calibre` ; note :
    au-delà, l'attente croît très vite (wikipedia-en-kingman-s-formula).
  - **Seuil de blocage d'un lot** (tranche 2) : limite haute de la carte p, p + 3 x racine(p (1 - p) / n) (p :
    part de défauts attendue, n : unités contrôlées du lot ; wikipedia-en-p-chart), calculée par la génération dans
    `qc_block_threshold`, pas 0,15 fixe.
  - **Pauses** : 2 x 10 + 1 x 20 min par journée de 8 h dans `clock.breaks` (même total que les 4 x 10 du cahier),
    `stop_min` des machines à 0. Les 20 min : Code du travail, art. L3121-16 (hors corpus : `calibre` tant que la
    fiche manque).
- `departments[]` : `id, label, external, area, stations[{kind, label}], elements[{asset, label, ref?, count?}],
  agent{name, job, character, facts, tasks[], notions[], module?}`. La génération place les éléments d'une zone
  le long de son bord intérieur, le poste devant ; les lignes sont placées par le code dans la zone `production`.
  (29/10) `stations` : liste de `{kind, label}`, ces deux clés exactement (`kind` au format `Code`, `label` texte
  affiché). Un `kind` n'apparaît qu'une fois dans tout le pack et devient l'id du poste ; le poste prend le
  `department_id` de sa zone, sans `ref`. Le type `machine` est réservé : jamais déclaré dans un département, la
  génération crée un poste par machine (`id` = `machine_<id machine>`, `ref` = id de machine, département
  `production`) ; il figure dans `modules.<id>.stations` des modules qui y agissent.
- (29/10) `limits` : `{weeks: [4, 12, 6], products: [1, 1, 1]}` pour l'usine (format du §1).
- `crew[]` : `{job: operateur, per: machine, characters: [...]}`, `{job: chauffeur_fournisseur, department: fournisseur}`,
  `{job: chauffeur_client, department: client}`.
- `modules` : format actuel. Tranche 1 :

| Module | Rôle | Action (champs) | Pilote automatique |
|---|---|---|---|
| pilotage | Responsable de production | `lancer_of` (line : lines ; lots : int 1-40, (29/10) au lieu de 1-20) ; `commander_mp` (offer : offers ; pallets : int) | OF quand stock PF + encours < `pf_min` ; MP au point de commande (consommation pendant le délai + stock de sécurité) |
| production | Chef de ligne | `proteger_goulot` (line ; mode : aucune, releve_pauses, tampon_avant) | aucune |
| maintenance | Responsable maintenance | `preventif` (line ; cible : aucune, goulot, toutes) ; `priorite_reparation` (ordre : arrivee, goulot) | préventif sur le goulot, ordre d'arrivée |
| qualite (tranche 2) | Responsable qualité | `frequence_controle` (1 sur N) | 100 % |

(29/10) Voulu : un module absent de `modules` du pack est refusé (paramètres et spec). `qualite` n'entre dans le
pack qu'en tranche 2, avec son handler ; d'ici là, le contrôle tourne à 100 % sans module et sans rôle, et
l'agent contrôleur informe sans action (`module` absent de son entrée).

(29/10) Arbitrage des écarts du pack v0 (ai/packs/usine.yaml) :
1. **`world.dock` refusé.** Le quai devient une entrée de `departments` sans agent : `{id: quai, label: Quai
   partagé (réception et expédition), area: [-6, 8.5, 6, 15], stations: [], elements: [porte (ref dock),
   transpalette]}`. Donc `departments[].agent` est facultatif (zone partagée : ni agent parlant ni poste) ; le quai
   apparaît dans `factory.flow` et reçoit `dept:quai`. Pas de clé `door` : la génération pose l'élément
   `ref: dock` sur le mur avant, centré sur la zone, et Godot ouvre le mur à la position et à la largeur
   (emprise) de cet objet. La ressource partagée reste `Resources.docks`.
2. **`lancer_of` jusqu'à 40 lots accepté** (20 lots de 24 = 480 < environ 665 bons par ligne et par semaine).
3. **Jauge et bandeau acceptés** : `kpis.good_share` et deux panneaux au bandeau (§2). Lire `factory.stocks.pf`
   par un panneau `kpis` est conforme (nombres au bout de `source` + `key`).
4. **Clés client acceptées** : `client.commandes_par_jour` -> `Customer.orders_per_day`,
   `client.creneau_enlevement_min` -> `Customer.pickup_window_min` (§1). `machine.tampon_avant` ->
   `Factory.protect_buffer` (§1) ; `fournisseur.retard_jours` (1) reste une règle du moteur (livraison en retard
   le jour ouvré suivant).
5. **Effets `nonconform` et `mtbf` acceptés**, pour le modèle usine seulement : `nonconform` = points ajoutés au
   taux de palettes non conformes du tour (plafond 0,5) ; `mtbf` = facteur des MTBF du tour (âges conservés).
   Effets du modèle usine : `delay_risk, cost, demand, nonconform, mtbf` ; un test de moteur-jeu refuse tout effet
   d'un pack que son modèle ne traite pas. Correction game-designer (exigence n° 1) : `mtbf: 0.7` fait tomber les
   machines 1 / 0,7 = 43 % plus souvent, pas 30 % : écrire « environ 40 % » ou prendre `mtbf: 0.77` ; préciser
   « 10 points de plus » pour `lot_mp_non_conforme`.
6. **Charge sur les machines de référence refusée.** La demande se calcule sur le débit réel attendu des machines
   de la partie (facteurs de difficulté compris), pour que « usine chargée à 90 % » reste vrai. Avec la règle du
   pack v0, en expert : demande = 0,90 x 16,6 / h (attendu des machines de référence), alors que les machines de
   la partie (MTBF x 0,6, défauts x 1,5) n'attendent que 15,8 / h, soit une charge réelle de 95 % avant même les
   arrêts de l'amont et l'attente du technicien : proche de 1, où l'attente explose (Kingman). L'expert
   reste plus dur par J+1, ± 15 %, les stocks bas et les pannes plus fréquentes (plus de variabilité, plus
   d'attente). Si le pilote automatique ne peine pas assez (critère 7), game-designer relève `load` en expert
   (0,92 au plus) ; la génération vérifie charge réelle < 0,95 pour chaque difficulté et chaque nombre de lignes.

(29/10) Règles du moteur prévues par le pack (moteur-jeu les code telles quelles, game-designer les a fixées) :
- **Préventif** : une intervention par machine ciblée et par tour (`goulot` : le goulot de la ligne ; `toutes` :
  ses machines). Ordre : les goulots d'abord (lignes dans l'ordre), puis les autres machines (ligne, puis rang).
  Créneaux : les pauses de `clock.breaks` du tour, les plus longues d'abord, puis dans l'ordre des jours et des
  heures. Chaque intervention prend le premier créneau libre, commence au début de la pause et dure
  `preventive_min`. Ce qui dépasse la pause arrête la machine. Le technicien n'est qu'à une tâche à la fois :
  une panne en attente passe avant, et le préventif se décale au créneau libre suivant. Sans créneau libre dans
  le tour, l'intervention n'est pas faite (fait de l'agent maintenance). En fin d'intervention : âge remis à
  zéro, coût `preventive_per_intervention`, événement `preventif`. Un préventif sur le goulot pendant une pause
  l'emporte sur la relève.
- **Relève** (`releve_pauses`) : au plus `Resources.line_leads` lignes (1) l'ont à la fois. Une demande sur
  une autre ligne est refusée par le handler (`GameRuleError` : « Le chef de ligne relève déjà la ligne … »)
  tant qu'une ligne la garde ; repasser cette ligne en `aucune` ou `tampon_avant` libère la relève. Pendant les
  pauses, le goulot de la ligne relevée tourne, son opérateur est en pause et l'agent de production est
  `occupe` à cette machine. Coût : minutes de relève x `operator_per_h` / 60.
- **Clés `agent.facts`** à écrire dans `engine._FACTS`. Chaque fait sort des nombres du moteur, en une ou deux
  phrases ; « urgent » donne le « ! » et la réplique. `direction` existe déjà.

| Clé | Faits (urgent) |
|---|---|
| `usine_fournisseur` | commandes en cours : palettes, jour prévu, créneau ; retard annoncé (urgent) ; hausse de prix en cours ; réclamations reçues pour palettes non conformes |
| `usine_reception` | palettes reçues et mises en quarantaine au dernier tour (urgent si > 0) ; minutes d'attente d'un camion au quai ; prochaine livraison (jour, palettes) |
| `usine_stock_mp` | stock MP en palettes et places libres ; sous le point de commande, commandes en cours comprises (urgent) ; kits livrés et minutes de ligne arrêtée faute de matière (urgent si > 0) |
| `usine_production` | par ligne : bons par heure mesurés et attendus ; goulot et ses minutes perdues (panne, attente, sortie pleine, pause), urgent s'il en a perdu ; OF en cours |
| `usine_qualite` | contrôlés et rebutés au dernier tour ; part de bons mesurée et attendue (urgent si mesurée < attendue - 2 points) ; en attente de contrôle |
| `usine_emballage` | colis et palettes faits ; conformes en attente d'emballage (urgent au-delà de 2 palettes) |
| `usine_maintenance` | pannes et minutes d'arrêt, machine la plus touchée (urgent si goulot) ; disponibilité mesurée de chaque goulot ; pannes qui ont attendu le technicien (nombre, minutes) ; préventifs faits et non faits |
| `usine_pilotage` | commandes client ouvertes et en retard (urgent si retard) ; stock PF + encours sous `pf_min` (urgent) ; OTIF et TRS du dernier tour face aux objectifs |
| `usine_entrepot_pf` | stock PF en palettes et places libres (urgent si plein) ; commande prête ou non pour le prochain camion ; commandes parties en retard ou incomplètes (urgent si > 0) |
| `usine_client` | commande du jour (produits, jour promis) ; OTIF du dernier tour (urgent sous l'objectif) ; commandes reçues en retard |

- `notions` (formules comprises) : fiches ajoutées par rag-knowledge le 28/10 (étape 4, noms de
  knowledge/supply-chain/SOURCES.md), à vérifier et citer par game-designer :

| Notion | Énoncé à vérifier | Fiches (28/10) |
|---|---|---|
| `disponibilite` | fonctionnement / (fonctionnement + arrêts) ; avec pannes : MTBF / (MTBF + MTTR). Convention du jeu, à dire : MTBF = temps moyen de marche entre pannes, réparation exclue | wikipedia-en-availability, wikipedia-en-mean-time-between-failures, wikipedia-en-mean-time-to-repair, wikipedia-fr-temps-moyen-entre-pannes ; wikipedia-fr-disponibilite prend une autre convention (MTBF = MTTF + MTTR) |
| `pannes_par_usure` | taux de défaillance croissant (Weibull de forme > 1) : le préventif sert ; constant : il ne sert pas | pas de fiche Weibull ; partiel : wikipedia-en-mean-time-between-failures (taux constant en vie utile, courbe en baignoire), wikipedia-en-reliability-centered-maintenance, wikipedia-en-maintenance ; forme en `calibre` |
| `goulot` | le débit d'une ligne en série est celui de son poste le plus lent ; une heure perdue au goulot est perdue pour toute l'usine | wikipedia-en-theory-of-constraints, wikipedia-fr-theorie-des-contraintes (le goulet n'est pas toujours la contrainte) |
| `rendement_en_cascade` | part de bons en sortie = produit des (1 - taux de défaut) des machines (le cahier n'applique que celui du goulot) | wikipedia-en-rolled-throughput-yield (deux phrases, sans exemple chiffré) |
| `loi_de_little` | encours = débit x temps de traversée | wikipedia-en-little-s-law (formule absente du texte de wikipedia-fr-theorie-des-files-d-attente) |
| `capacite_et_trs` | TRS = disponibilité x performance x qualité | wikipedia-en-overall-equipment-effectiveness (NF E60-182 non lue : ne pas la citer) |
| `temps_de_lot` | premier produit + (n - 1) x cycle du goulot, sans attente | aucune fiche : `exemple`, non présentée comme notion |
| `point_de_commande`, `stock_de_securite`, `otif` | reprises de ai/simulation.yaml | corpus actuel |

- `panels[]` (tranche 1) : bandeau `kpis` (OTIF, TRS, stock PF, trésorerie avec cibles) ; tableau de bord :
  `flow` (`factory.flow`), `table` machines (`factory.machines`, colonne `state` libellée), `chart` (`history`,
  otif et trs), `table` OF (`factory.orders.production`) ; postes : `machine` -> `table` (`factory.machines`,
  `match: id`), `pilotage` -> `table` commandes client et MP, `maintenance` -> `table` pannes,
  `poste_qualite` -> `gauge` part de bons.

Plan en U, hall de 48 x 30 m (x de -24 à 24, z de -15 à 15, porte de quai au mur avant z = 15, x de -3 à 3).
Zones indicatives ; allées d'au moins 2,5 m pour le chariot, vérifiées par les tests de génération :

```
 z=-15 +-----------+---------------------+---------------------+-------------+
       | Stock MP  | Maintenance et PDR  | Pilotage (bureau)   | Contrôle    |
       | -24..-14  | -11..0 / -15..-11   | 2..11 / -15..-11    | qualité     |
       | -15..4    +---------------------+---------------------+ 14..24      |
       |           | Production -11..11 / -9..4                | -15..-4     |
       |           |  L1  M1 > M2 > M3 > M4   (z = -6)         +-------------+
       |           |  L2  M1 > M2 > M3 > M4   (z = -2)         | Emballage   |
       |           |  L3  M1 > M2 > M3 > M4   (z = 2)          | 14..24/-4..5|
       +-----------+-------+-------------------+---------------+-------------+
       | Réception         | Quai partagé      | Entrepôt PF                 |
       | -24..-6 / 4..15   | -6..6 / 8..15     | 6..24 / 6..15               |
 z=+15 +-------------[ porte de quai ]---------+-----------------------------+
        aire des camions ; usine du fournisseur à gauche (bld_factory_plant), client à droite
        (bld_distribution_center), route en z = 22 ; apparition du joueur en (0, 20)
```

Assets à fabriquer (assets-3d ; propriétés GDScript lues par world.gd entre parenthèses) :

| Id | Usage | Tranche |
|---|---|---|
| `prop_machine` | machine de ligne, base Kenney `machine.glb` + colonne d'état (`state` : MachineState, `title`) | 1 |
| `prop_buffer_table` | table d'attente (`fill_level` 0-1, `capacity`) | 1 |
| `prop_dock_door` | porte de quai sectionnelle avec feu (`state` : libre, occupe) | 1 |
| `prop_floor_zone` | marquage au sol d'une zone (`title`, `color`, `size`) : départements, dépose, quarantaine, conforme, à retoucher | 1 |
| `veh_pallet_jack` | transpalette | 1 |
| `prop_inspection_table` | table de contrôle avec instruments | 1 |
| `prop_scrap_bin` | bac à rebut (`fill_level`) | 1 |
| `prop_packing_table` | table d'emballage (cartons, ruban, balance) | 1 |
| `prop_pallet_wrapper` | filmeuse de palettes | 1 |
| `prop_workbench` | établi et servante d'outils | 1 |
| `prop_wall_board` | tableau de ligne ou des interventions (`title`, `lines`) | 1 |
| `prop_part_token` | pièce symbolique par état du produit (`product_state` : ProductState) | 2 |
| `prop_bin_shelf` | étagère à bacs (petites pièces, PDR) | 2 |
| `prop_safety_cabinet` | armoire de sécurité | 3 |

Réutilisés : `prop_pallet_rack` (stock MP, entrepôt PF), `prop_pallet`, `prop_pallet_stack`, `prop_conveyor`,
`veh_forklift`, `veh_box_truck`, `prop_desk_computer`, `prop_site_office`, `furn_*`, `prop_kpi_screen`,
`prop_andon_light`, `char_*`, `bld_factory_plant`, `bld_distribution_center`, `road_*`.

## 6. Tranches et critères de fin

**Tranche 1 (verticale)** : un produit, une MP, 1 à 3 lignes de 4 machines ; réception (déchargement, contrôle,
non-conformes en quarantaine), stock MP, kits, lignes, contrôle (conforme ou rebut), emballage, entrepôt PF,
commandes client datées, quai partagé ; pannes Weibull, MTTR, technicien unique, pauses, réglages ; décisions
`lancer_of`, `commander_mp`, `preventif`, `priorite_reparation`, `proteger_goulot` ; 10 agents parlants et les
figurants ; rejeu ; panneaux ; débrief formules (attendu / mesuré). Fin quand :
1. Même spec et mêmes décisions -> même état et même chronologie (empreinte identique).
2. Machines de l'exemple du cahier, sans panne ni pause, tables larges : lot de 20 en 67 ± 1 min (cas de test de
   la formule ; le pack prend 24) ; ligne à 20 ± 0,5 / h en régime établi ; avec pauses 110 / 10, ou (28/10)
   `breaks` 2 x 10 + 1 x 20 sur 480 min, débit attendu x 110 / 120 (= 440 / 480).
3. Débit mesuré d'une ligne <= débit du goulot ; table pleine -> amont `sortie_pleine` ; vide -> aval `attente_matiere`.
   (28/10) Pack usine à 3 lignes, MP et place PF suffisantes : le goulot de chaque ligne est une machine ; la
   génération vérifie contrôle et emballage >= 1,2 x débit théorique de l'usine (§5) ; file devant contrôle et
   emballage <= 2 palettes en fin de journée, chariot et quai occupés < 83 % ; sortie de l'emballage = somme des
   bons des lignes, à cette file près (débit de l'usine = somme des débits des lignes).
4. Un seul technicien : jamais deux réparations en même temps ; réparation = trajet + MTTR.
5. Sur 50 graines, le préventif réduit les pannes avec Weibull de forme 2 et ne change rien avec la forme 1.
6. Bilan matière par tour : MP consommée = nomenclature x unités lancées ; unités lancées = encours + bons + rebut.
7. Pilote automatique : objectifs atteints en « découverte », manqués en « expert » (comme aujourd'hui).
8. Budgets de l'ADR (génération < 1 s, `advance` < 150 ms, état < 64 Ko, chronologie < 200 Ko, 45 images/s).
9. Chaque action d'un pack a son handler ; chaque `agent.facts` existe ; chaque notion a sa citation ; chaque
   valeur a sa provenance ; tests de l'atelier inchangés et verts.
10. Godot : `-Check`, `-Tour` (panneaux usine aux 4 tailles), `-Flow` sur le pack usine (génération, lobby,
    tour simulé, rejeu x960 jusqu'au bout, débrief) ; `.\scripts\test.ps1 -Integration` vert.

**Tranche 2** : retouches, seuil de blocage d'un lot, absences et remplacement par le chef de ligne, chariot à
batterie, usure d'outil visible, jetons de produit, module qualité, aléas propres à l'usine.
**Tranche 3** : nomenclature à plusieurs articles, pièces de rechange avec délai, horloge commune du formateur,
armoire de sécurité. **Tranche 4** : pack `atelier` migré au format pack avec panneaux ; second domaine.

## 7. Plan d'exécution (tranche 1)

| # | Agent | Fichiers | Contrat | Fin | Après |
|---|---|---|---|---|---|
| 1 | documentaliste | .claude/ownership.json, CLAUDE.md (tableau) | `ai/packs/**` -> game-designer | `.\scripts\team.ps1 -CheckOwners` OK | - |
| 2 | moteur-jeu | backend/gmix/game/spec.py (délégué par l'architecte, qui n'a pas de shell), backend/tests/test_spec_contract.py | §1 | anciennes specs valides ; spec usine écrite à la main valide ; 6 cas refusés (ligne, rang, nomenclature, provenance, panneau, référence du monde) ; `test.ps1 -Fast` vert ; (28/10) `Clock.breaks` (si l'étape est close : ajouté à l'étape 6) | - |
| 3 | game-designer | ai/packs/usine.yaml (v0) | §5 | 10 départements, agents, modules, actions, valeurs avec provenance (cahier en `exemple`), notions marquées « à sourcer », panneaux ; chargé par `load_pack` | 2 pour le test, rédaction tout de suite |
| 4 | rag-knowledge | knowledge/supply-chain/ (fiches, SOURCES.md) | notions du §5 | **fait le 28/10** (18 fiches, SOURCES.md ; correspondance au §5, sans fiche Weibull ni temps de lot) | - |
| 5a | assets-3d | ai/assets.yaml | ids du §5 | entrées du catalogue (statut `a_sourcer` permis) : `test_assets` vert | - |
| 5b | assets-3d | godot/assets/, backend/gmix/tools/assets.py si besoin | propriétés du §5 | scènes construites, collision propre à chaque asset, galerie `assets.ps1 -Gallery` | 5a |
| 6 | moteur-jeu | backend/gmix/game/factory.py (nouveau), engine.py, generation.py, npc.py (domaine), backend/tests/test_factory.py, test_generation.py, test_engine.py | §1, 2, 3 | critères 1 à 9 de la tranche 1 | 2, 3 (v0), 5a |
| 7 | backend-api | backend/gmix/api/routes/lobbies.py, games.py, backend/gmix/db/models.py, backend/alembic/ (migration), backend/tests/test_game_flow.py | §4 | migration aller-retour ; route chronologie testée pour membre, autre joueur (404), autre formateur (404), admin, tour non simulé (404) ; `advance` range et retire la chronologie ; `lobby.state` sans chronologie ; options et `POST /games` du pack usine < 1 s | 2 ; parallèle à 6 avec une chronologie bouchon |
| 8 | godot-dev | godot/scenes/world/ (world.gd, hud.gd, npc.gd, nouveaux panels.gd et replay.gd), scenes/main/home_screen.gd (pack et options), scenes/common/game_text.gd, scenes/tools/ (tour, flow `--pack=usine`, world_preview) | §2, 3, 5 | hall depuis `spec.world.size`, zones et étiquettes des départements, décor piloté par les références, PNJ sur le maillage de navigation, rejeu (pause, x1, x60, x240, x960, événement suivant, jour), 5 types de panneaux, HUD atelier inchangé ; critère 10 ; 45 images/s mesurées (`world_preview`) | 2 ; parallèle à 6 et 7 avec des fichiers d'exemple tirés de l'annexe |
| 9 | game-designer | ai/packs/usine.yaml (v1) | §5 | notions sourcées (fiches de l'étape 4) ou retirées ; calibrage relu sur le pilote automatique de l'étape 6 ; en-tête qui liste les valeurs restées `exemple` | 4, 6 |
| 10 | ia-runtime | ai/evals/ (cas usine), ai/prompts/npc.dialogue.md si besoin | faits de `_FACTS` usine | au moins 30 cas (minutes, heures, OF, machine « M3 de la ligne 1 ») joués avec qwen2.5:3b ; taux de nombres inventés comparé à l'atelier ; rapport dans ai/evals/results/ | 6 |
| 11 | devops | scripts/godot.ps1 | option `-Pack` | `.\scripts\godot.ps1 -Flow -Pack usine` et `-Tour` lancent les contrôles du pack | 8 |
| 12 | documentaliste | docs/architecture.md, game-design.md, kafka.md, roles.md, ai-runtime.md, blocages.md, godot/README.md, docs/references/usine-3d/README.md | ADR 0007 | docs à jour (route chronologie, rejeu, packs, panneaux) ; README des références corrigé : les 60 / h de la section 8 sont théoriques (« sans pauses ni pannes »), les 53 / h de la 5.3 réels, pas d'incohérence ; la formule de débit réel du cahier ignore les pannes et le rendement en cascade ; (28/10) blocages.md : risque accepté de la mémoire partagée (ADR, point 12) et atténuations en place | 6 à 11 |
| 13 | qa-reviewer | tests manquants | tout | relecture du diff contre cette annexe ; `.\scripts\test.ps1 -Integration` vert ; `.\scripts\smoke.ps1` OK | 12 |

(29/10) Étape 2 rouverte, à finir avant la vague B (moteur-jeu, backend/gmix/game/spec.py et ses tests) :
1. `PUBLIC_ROOTS` (lignes 35 à 38) : ajouter `"overdraft"`, `"log"`, `"briefings"` ; test d'égalité avec les clés
   de `public_state` (§1).
2. `ATELIER_LIMITS` (ligne 40) -> `{"weeks": (4, 12, 8), "products": (2, 4, 3)}` ; `_bounds` (lignes 646 à 648)
   n'accepte plus que `[min, max, défaut]` (trois entiers, min <= défaut <= max), contrôlé dans `load_pack`.
3. Boucle des panneaux (lignes 561 à 564) : racine de `PanelColumn.target`, ids de panneau en double.
4. `_factory_errors` : ligne dont `product_id` diffère de `factory.product_id`.
5. Test de la chronologie : longueurs M et C de chaque instantané, `states` égal à l'ordre de `MachineState`,
   `counters` égal à la liste du §3, données d'événement complètes selon le tableau du §3.
(29/10, pack v0) Ajouts à spec.py, en plus des cinq corrections ci-dessus (moteur-jeu, même étape) :
6. `Customer.orders_per_day` (int, 1 par défaut, 1 à 10) et `Customer.pickup_window_min` ((360, 450) par défaut).
7. `Factory.protect_buffer` (int, 30 par défaut, 1 à 500).
8. `_factory_errors` : fenêtres `pickup_window_min` et `delivery_window_min` dans la journée (0 <= début < fin
   <= `minutes_per_day`).
9. Commentaires d'unité : en usine, `Offer.lead_time` en jours ouvrés et `Offer.min_order` en palettes.
Hors spec.py, pour l'étape 6 : `departments[].agent` facultatif dans la génération (quai) ; effets d'aléas par
modèle avec test ; `kpis.good_share` et le sens usine de `kpis.stockouts` ; règles du préventif et de la relève ;
les 10 clés `usine_*` (§5). game-designer (pack v0 -> v0.1) : quai en département sans agent, texte de
`vague_de_chaleur` et de `lot_mp_non_conforme`, note `client.charge` sur le débit de la partie (§5, 29/10).
Effets ailleurs : backend-api (étape 7) rend `packs[].limits` au format `[min, max, défaut]` ; godot-dev (étape 8)
lit les limites d'un pack comme `ranges` ; game-designer (étapes 3 et 9) suit les formats `limits` et `stations`
du §5 et ne met pas `qualite` dans le pack.

Vagues : **A** = 1, 2, 3, 4, 5a en parallèle (fichiers disjoints) ; **B** = 6, 7, 8 et 5b en parallèle ;
**C** = 9, 10, 11 en parallèle ; **D** = 12 puis 13. Seul moteur-jeu touche `backend/gmix/game/` ; seul
backend-api touche `api/` et `db/` ; godot-dev ne touche pas `godot/assets/`. pipeline-kafka n'intervient pas.
