# 0009 : monde généré sur grilles et réseau logistique

Date : 2026-10-29. Statut : accepté (29/10, décisions par défaut à confirmer : voir les questions en fin de document),
amendé le 29/10 par les points 8 et 9 (éditeur de grille du formateur, menus contextuels). Complète l'ADR 0007 (usine, quai, chronologie) et
l'ADR 0008 (conception par l'IA). Le contrat est dans ce document ; le plan s'ajoute à `0008-annexe-contrat-conception.md`
(§10).

## Contexte

Demande de l'utilisateur (29/10) : « les blocs, départements, etc. sont disposés sur des cadrillages différents qui
définissent le placement des assets […] l'IA doit générer le monde et le business game de manière logique selon le
domaine et les paramétrages ; en supply chain, les fournisseurs sont externalisés et reliés par des routes et des
transports ».

Aujourd'hui, le pack usine déclare des rectangles (`departments[].area`, en mètres), et la génération (étape 6 de 0007)
pose les éléments le long du bord intérieur de chaque zone. Le fournisseur et le client sont deux zones `external`
écrites à la main. Les trois fournisseurs des offres ne sont que des lignes de tableau. Les délais (`Offer.lead_time`)
viennent des profils, sans lien avec une distance.

L'ancien pipeline (5a5d288, `ai/world_templates.yaml`) avait des parcelles libres : centre, taille, `facing`,
`categories` et `defaults`, c'est-à-dire des assets sûrs en cas d'échec, avec des routes `from/to`. Il n'avait ni grille
ni règle de placement à l'intérieur d'une parcelle.

## Décision

1. **Trois niveaux de grille, un placeur déterministe** (module pur `gmix.game.layout`, propriétaire moteur-jeu).
   - **Carte** : les sites (l'usine, les fournisseurs, les clients) occupent chacun une cellule de `map.cell_m`. La carte
     est schématique : la classe de distance d'un site donne son anneau, son camp (amont à l'ouest, aval à l'est) donne
     son côté. Le kilométrage réel est affiché, pas mis à l'échelle.
   - **Site** : les blocs internes (départements) sont des rectangles alignés sur la grille du site (`grid.site_cell_m`,
     0,5 m). Le plan en U validé dans 0007 est inchangé et se lit tel quel sur cette grille.
   - **Bloc** : chaque type de bloc a sa grille locale (cellule, côté de l'allée, bande libre) et un **motif** : `edge`
     (le long des murs, poste devant), `rows` (rangées de racks et allées), `line` (lignes de machines en série avec
     leurs tables d'attente) ou `single` (un bâtiment centré, tourné vers la route). Le pack décrit le contenu d'un
     bloc par des **rôles** : stockage, machine, tampon, poste, affichage, engin, décor, porte, bâtiment. Il donne des
     quantités, fixes (`count`) ou dérivées de la spec (`per` : une par ligne, une par machine, ou selon la capacité en
     places). Le placeur tire les emprises (`ai/assets.yaml`, `footprint`) en nombre de cellules et range tout.
   - Une erreur de placement est une erreur du pack, vérifiée par les tests sur toutes les options. Elle n'arrive
     jamais à l'exécution.
2. **L'IA ne produit ni coordonnée ni nombre, et ne choisit que ce que le moteur simule.** Le rejeu 3D reste la vérité
   calculée (ADR 0007, point 2) : un site ou un bloc que le moteur ignore enseignerait faux. En tranche 1, l'IA choisit
   dans le concept (ADR 0008) la **classe de distance** de chaque site fournisseur, parmi celles que le pack permet pour
   ce site (`GameParams.network`). Le choix des blocs facultatifs, du mode de transport et du gabarit de site viendra
   quand un moteur s'en servira (tranches 2 et 3).
3. **Réseau logistique.** Le pack déclare les classes de distance (km), les types de liens (vitesse, véhicule), les
   heures de conduite par jour et les sites (camp, liens, classes permises, délai de préparation), chaque nombre avec
   sa provenance (`values`, `reseau.*`). La génération calcule le délai d'une offre, puis le borne dans les limites du
   pack : préparation + ⌈ km ÷ vitesse ÷ heures de conduite par jour ⌉. Les classes par défaut redonnent les délais
   actuels (1, 3 et 5 jours), donc rien ne change sans conception. Chaque fournisseur des offres devient un **site
   externe** de la carte, relié à la porte de quai (`ref: dock`) par une route.
4. **Camions dans le rejeu.** Le moteur usine ajoute deux événements à la chronologie, `camion_arrive` et `camion_part`
   (données : `site_id`), pour chaque camion de fournisseur et de client. Godot fait rouler le camion sur la polyligne du
   lien pendant les 30 minutes simulées qui précèdent l'arrivée, et pendant les 30 qui suivent le départ. Un transit de
   plusieurs jours s'affiche en étiquette (« en route, arrivée jour 3 »). Rien ne passe par Kafka ni par le serveur de
   partie.
5. **Généralité.** Les types de blocs, de liens et de sites, les motifs, les rôles, les règles de placement, les
   actions des menus contextuels et l'éditeur de grille ne parlent pas de supply chain : ils sont des données de pack,
   lues par du code générique. (29/10, décision de l'utilisateur) La v1 ne propose que la supply chain. Aucun autre
   domaine n'est conçu ici : un domaine futur s'écrira avec les mêmes briques, et sa mécanique avec les primitives de
   l'ADR 0008 (point 3, B).

6. **Placement fondé sur le métier du domaine.** Le pack déclare des `placement_rules[]`, les règles d'implantation de
   son domaine. Chacune est d'un type que le code connaît, et chaque type est une fonction testée, jamais évaluée
   depuis le YAML. Chaque règle a sa provenance : `source` avec citation, `calibre` avec note, ou `exemple`.
   - Le placeur applique les règles qui orientent (`facing`, `aisle_min`) et vérifie les autres sur le plan du site.
   - Une règle violée fait échouer les tests du pack, jamais une partie.
   - L'aperçu et le débrief listent les règles non sourcées, comme ils listent les valeurs (ADR 0007, point 8).

   Règles de l'usine en tranche 1 :
   - **marche en avant** (`flow`) : réception -> stock MP -> production -> contrôle -> emballage -> entrepôt PF -> quai.
     Elle vient du cahier, donc `exemple` ;
   - **réception et entrepôt PF contigus au quai** (`adjacent`) : cahier, `exemple` ;
   - **quarantaine séparée du stock conforme** (`separated`) : NF EN ISO 9001 §8.7, non lue, donc `calibre` à sourcer ;
   - **allées de chariot d'au moins 2,5 m** (`aisle_min`) : `calibre`, en attendant la fiche INRS ;
   - **écran des indicateurs tourné vers l'allée de production** (`facing`) : `exemple`.
7. **Domaines proposés selon les assets.**
   - Les **assets requis** d'un pack sont ceux qu'il cite : éléments des départements, types de machine, bâtiments des
     sites, véhicules des liens, personnages des agents et des figurants. Les assets de décor facultatifs (tranche 2)
     n'en font pas partie.
   - Un asset requis est **couvert** s'il a le statut `importe` dans ai/assets.yaml, ce qui garantit sa scène Godot
     (vérifiée par `test_assets`). Les scènes procédurales (pack `gmix`), que l'utilisateur garde, comptent comme
     `importe`. La couverture d'un pack est le nombre d'assets requis couverts divisé par le nombre
     d'assets requis.
   - Un pack est **proposé** au formateur si `load_pack` le charge, si toutes ses notions ont une citation et si sa
     couverture vaut 100 %. Un domaine de ai/domains.yaml est proposé s'il a au moins un pack proposé.
   - Godot affiche un domaine non proposé en grisé, avec la raison : « aucun pack » ou « n assets manquants ».
   - `POST /games` et `POST /games/designs` refusent un pack non proposé (422), sauf pour l'admin, qui peut l'essayer.
8. **(29/10) Retouches du formateur : un éditeur de grille, comme le mode construction des Sims.** Avant de publier,
   le formateur (ou l'admin) peut retoucher le monde généré. Il peut aussi régénérer une section ou ajuster les
   paramètres.
   - **Modèle.** Les retouches forment une liste ordonnée, `spec.layout_edits`, de 200 éléments au plus. Chaque
     retouche s'exprime en cellules de la grille locale d'un bloc, jamais en mètres : le snap est garanti par
     construction. `layout.apply_edits` rejoue la liste après `place_world`, de façon pure et sans hasard, et la graine
     n'y entre pas. La même spec (paramètres, graine et retouches) donne donc le même monde.
   - **Ce que l'éditeur touche :**
     - déplacer ou tourner (par quart de tour) n'importe quel objet, à l'intérieur de son bloc ;
     - ajouter ou retirer un objet de rôle `decor` ou `affichage` sans `ref`. Un ajout se prend dans la palette du bloc
       (`block_types.<id>.decor`, assets `importe`).
   - **Ce qu'il ne touche pas :**
     - le nombre des objets simulés (stockage, machine, tampon, poste, porte, engin, bâtiment). Il se règle par les
       paramètres (capacité, lignes, machines), puis le placement est refait. Raison : la 3D ne montre que ce qui est
       calculé (point 2) ;
     - le déplacement d'un bloc entier (`move_block`), reporté en tranche 2. Les retouches étant locales au bloc, elles
       resteront valides ;
     - **la topologie du réseau** : sites, liens, positions sur la carte. Trois raisons :
       - les sites et les liens sont des données du moteur (fournisseurs des offres, délais) ; déplacer un site
         changerait un délai sans source ;
       - la carte est schématique (l'anneau donne la classe de distance), donc une position glissée n'a pas de sens
         métier ;
       - un site ajouté serait un site de décor, interdit (question 1).

       Les choix de topologie permis par le pack passent par l'ajustement des paramètres (`GameParams.network` : la
       classe de distance de chaque site), suivi d'une recompilation et d'un essai en pilote automatique.
   - **Validation.** Chaque enregistrement rejoue toute la liste, puis lance `check_placement`. La première retouche
     refusée renvoie son rang et une raison lisible (« retouche 3 : la cellule est dans l'allée du bloc Stock MP »), et
     rien n'est gardé. Les retouches d'objets ne changent aucun nombre du moteur : la recompilation et le pilote
     automatique sont relancés, et le test exige un verdict et un débrief identiques. Un ajustement des paramètres
     refait la génération avec la même graine, puis rejoue les retouches. Celles qui ne tiennent plus sont retirées et
     listées (`dropped`), comme les étapes de didacticiel orphelines (annexe 0008, §2 f). Tout enregistrement repasse le
     jeu en `draft`, et la publication refait les contrôles : rien de non valide ne se publie.
   - **Annuler et rétablir.** L'historique, c'est la liste. Godot garde une pile de rétablissement locale et envoie la
     liste entière à chaque pas (route idempotente). « Tout annuler » envoie une liste vide, ce qui rend le placement
     automatique.
9. **(29/10) Menus contextuels, comme dans les Sims.** Un clic sur un poste, un agent ou un site ouvre la liste de ses
   actions. Ces actions sont des outils du pack (`Tool.menu`, un sélecteur de cible), et aucun code n'est propre à un
   domaine. Le client ne connaît que des verbes génériques :
   - ouvrir le formulaire d'une action, pré-rempli avec l'id de la cible quand le formulaire a ce champ ;
   - parler à l'agent ;
   - afficher les fiches de notions ;
   - centrer la caméra ;
   - (formateur) les routes Staff existantes.

   Une action dont le rôle du joueur ne tient pas le module est grisée, avec sa raison, et l'API la refuse de toute
   façon. En mode construction, le menu propose les verbes fixes de l'éditeur : déplacer, tourner, retirer (grisé avec
   sa raison pour un objet simulé), annuler.

## Contrat

Spec (`backend/gmix/game/spec.py`, champs facultatifs, une spec v2 existante reste valide) :

```python
Side = Literal["nord", "sud", "est", "ouest"]
ElementRole = Literal["stockage", "machine", "tampon", "poste", "affichage", "engin", "decor", "porte", "batiment"]
#   (29/10) renommé : `Role` existe déjà dans spec.py (rôles des joueurs)
EDITABLE_ROLES = frozenset({"decor", "affichage"})          # ajout et retrait possibles, sans `ref` ; les autres : déplacer
GameParams.network: dict[str, str] = {}    # site du pack -> classe de distance permise ; absent : défaut du pack
#   _check : site dans pack["network"]["sites"], classe dans ses `distances`
class Site(BaseModel):                       # sortie du placeur
    id: Code
    kind: Code                               # fournisseur, client… (pack)
    label: str                               # « Aciers du Rhône (Lyon) »
    external: bool
    area: Rect
    gate: Point                              # raccordement au lien
    supplier_id: str | None = None           # site fournisseur : fournisseur des offres
    distance_class: str | None = None
    km: float | None = None                  # distance déclarée par le pack, pas la longueur 3D
    travel_h: float | None = None
    transit_days: int | None = None
class Link(BaseModel):
    id: str
    type: Code                               # pack link_types : route, convoyeur, couloir, rail…
    from_site: str
    to_site: str
    points: list[Point] = Field(min_length=2) # polyligne à angles droits ; la fin d'une route est l'aire du quai
    vehicle: str | None = None               # id d'asset (veh_box_truck)
World.sites: list[Site] = []                 # site principal (external=False) en premier
World.links: list[Link] = []
World.bounds: Rect | None = None             # tout le monde ; World.size reste le hall du site principal
Department.block: Code | None = None         # type de bloc du pack
Department.site_id: str | None = None        # zone externe : site qui la porte (son area est celle du site)
EventKind += "camion_arrive", "camion_part"  # EVENT_DATA : {"site_id"} ; sujet : id de commande d'achat ou client-<jour>

# (29/10) éditeur de grille (point 8)
WorldObject.id: str | None = None            # « <département>.<rôle>.<n> » ; ajout : « <département>.ajout.<rang> »
WorldObject.department_id: str | None = None
WorldObject.role: ElementRole | None = None
WorldObject.cell: tuple[int, int] | None = None   # coin de l'emprise, grille locale du bloc
WorldObject.cells: tuple[int, int] | None = None  # emprise en cellules après rotation (fantôme de Godot)
class BlockGrid(BaseModel):                  # sortie du placeur, jamais éditée
    origin: Point                            # coin du bloc (m)
    cell_m: float
    cols: int
    rows: int
    reserved: list[tuple[int, int]] = []     # bande d'allée et cellule devant chaque poste
    palette: dict[str, tuple[int, int]] = {} # asset de décor ajoutable -> emprise en cellules (assets `importe`)
Department.grid: BlockGrid | None = None
class LayoutEdit(BaseModel):
    op: Literal["move", "remove", "add"]
    object_id: str | None = None             # move, remove
    department_id: str | None = None         # add
    asset: str | None = None                 # add : clé de grid.palette
    cell: tuple[int, int] | None = None      # move, add
    rot: Literal[0, 90, 180, 270] = 0
    #   _check : champs requis selon op, et aucun autre
SimSpec.layout_edits: list[LayoutEdit] = Field(default_factory=list, max_length=200)

# (29/10) menus contextuels (point 9) : extension de Tool (annexe 0008, §1)
Tool.kind += "parler", "fiche"               # parler : agent visé ; fiche : notions du poste, de l'agent ou du site
Tool.menu: list[str] = []                    # sélecteurs : station:<kind>, agent:<id>, agent:*, site:<kind>
Tool.bar: bool = True                        # False : seulement dans les menus (hors UI_LIMITS["tools"])
UI_LIMITS["menu_items"] = 6                  # par cible et par public
```

Contrôles ajoutés (`_references`) :
- un sélecteur `menu` désigne un type de poste, un agent ou un type de site de la spec ;
- `parler` ne vise que `agent:` ;
- une action de menu sur `station:<kind>` appartient à un module de ce poste ;
- `UI_LIMITS["menu_items"]` est respecté ;
- les ids d'objet sont uniques ;
- `layout_edits` ne vise que des ids d'objet ou de département existants.

`generate` filtre les menus comme les outils, par modules joués (annexe 0008, §2 a).

Les contrôles (`_references`) ne s'appliquent que si `world.sites` n'est pas vide :
- les ids de site sont uniques, un seul site principal, en premier ;
- les aires des sites sont disjointes et toutes dans `bounds` ;
- `from_site` et `to_site` de chaque lien existent, et chaque segment est horizontal ou vertical ;
- chaque fournisseur des offres a un site, et le `supplier_id` de chaque site fournisseur est connu ;
- le `site_id` de chaque département existe.

Pack (game-designer), contrôlé par `_check_pack` :
- `grid: {site_cell_m: 0.5}` : les `area` internes sont des multiples de cette cellule.
- `block_types.<id>: {label, pattern: edge|rows|line|single, cell_m, front_aisle_cells, row_aisle_cells, decor: [assets]}`
  (`decor` est la palette de l'éditeur ; ces assets sont facultatifs et n'entrent pas dans la couverture).
- (29/10) `tools[]` gagnent `menu` et `bar` (point 9). Le catalogue du pack peut dépasser les limites, que `generate`
  applique après filtrage.
- `departments[]` : une zone interne gagne `block`, `front` (`Side` de l'allée principale), `capacity`
  (`mp_capacity_pallets` ou `pf_capacity_pallets`, pour `rows`), et ses `elements[]` gagnent `role`, puis `count` ou
  `per` (`line`, `machine` ou `places`, avec `places` = places par élément). Une zone externe déclare `site` au lieu
  d'`area`.
- `network` :
  - `map: {cell_m, road_offset_m}` ;
  - `distance_classes.<id>: {label, km, ring}` ;
  - `link_types.<id>: {label, speed_kmh, vehicle}` ;
  - `driving_h_per_day` ;
  - `sites.<id>: {kind, side: ouest|est, link, distances: [classes], default, prep_days, supplier_profile?, building}`.
- Provenance : `values` contient `reseau.distance.<classe>`, `reseau.vitesse.<type>`, `reseau.conduite_h_jour` et
  `reseau.preparation.<site>`. Les villes des thèmes restent compatibles avec les classes permises, sinon on les retire.
- `placement_rules[]` : `{id, kind, status, citation | note, ...paramètres}`. `kind` et ses paramètres :
  - `adjacent {a, b}` : deux blocs qui se touchent ou que seule une allée de 3 m au plus sépare ;
  - `flow {blocks}` : chaque bloc est `adjacent` au suivant ;
  - `separated {a, b, min_m}` : au moins `min_m` entre deux blocs ou deux `ref` ;
  - `aisle_min {min_m}` : toutes les allées et toutes les bandes d'allée ;
  - `facing {block, role, toward: front|dock|centre}` ;
  - `near {a, b, max_m}`.

Placeur (`gmix.game.layout`, moteur-jeu) :

```python
def place_world(spec: dict, pack: dict) -> dict
def check_placement(spec: dict, pack: dict) -> list[str]   # « règle <id> : … », une par règle violée
def required_assets(pack: dict) -> set[str]
def pack_coverage(pack_id: str) -> dict                    # {ratio, required, missing}, d'après ai/assets.yaml
def apply_edits(world: dict, edits: list[dict], pack: dict) -> tuple[dict, list[dict]]
#   (29/10) rejoue les retouches dans l'ordre ; rend (monde, rejets [{index, reason, message}]) ; recalcule la position
#   des postes et les routes des agents. reason : cible_inconnue, hors_bloc, allee, occupe, devant_poste, role_fixe,
#   asset_non_permis. Les appelants (generate, recompile, routes) enchaînent place_world, apply_edits et check_placement.
```

Pur, sans hasard. Il rend `world` (objets, sites, liens, `bounds`, `spawn`, `forklift_route`), la position des postes
et les routes des agents (cellules libres de la bande d'allée de leur bloc). Les règles :
- une cellule ne porte qu'un objet ;
- tout objet reste dans son bloc ;
- la bande d'allée reste libre, et chaque poste a une cellule libre devant lui ;
- les objets sont tournés de 0, 90, 180 ou 270° vers le côté `front`.

Pour un motif `rows`, le nombre de racks vaut ⌈ capacité ÷ places ⌉. Pour un motif `line`, il y a autant de machines et
de tables que dans `spec.factory.machines`. Le placeur remplace le placement « le long du bord intérieur » prévu à
l'étape 6 de 0007.

Godot (godot-dev) :
- bâtiment de chaque site, avec une étiquette : nom, classe, km, durée de route ;
- liens tracés le long de `points` (une route en tranche 1) ;
- camions du rejeu, comme au point 4 ;
- caméra Sims qui peut reculer jusqu'à `world.bounds` (l'utilisateur la garde telle quelle) ;
- (29/10) **menus contextuels** (point 9) : un clic sur un poste, un agent ou un site ouvre une liste ancrée. Elle
  contient les outils de son public dont `menu` désigne la cible, dans l'ordre de la spec, avec 6 entrées au plus.
  Elle se ferme avec Échap ou un clic à côté, et se parcourt au clavier ;
- (29/10) **mode construction** (formateur, écran de préparation, jeu en `draft` ou `ready`) :
  - la grille du bloc survolé est visible (traits à `cell_m`, cellules `reserved` hachurées), les autres blocs sont
    estompés ;
  - le fantôme est vert si son emprise est libre et rouge sinon, avec la raison écrite : la couleur n'est jamais seule ;
  - le snap se fait sur les cellules, R ou la molette tourne d'un quart de tour, les flèches déplacent d'une cellule,
    Entrée pose et Échap annule ;
  - une palette montre le décor du bloc (`grid.palette`) ;
  - le menu contextuel de l'objet propose les verbes du point 8 ;
  - Ctrl+Z et Ctrl+Y (et leurs boutons) annulent et rétablissent ; un compteur montre les retouches, et un bouton
    « Tout annuler » rend le placement automatique ;
  - « Paramètres » et « Régénérer » appellent leurs routes.

  Le fantôme n'est qu'indicatif : il lit l'occupation des cellules, sans aucune règle de jeu. Au dépôt, l'API tranche.
  Un refus remet l'objet en place et affiche la raison. L'écran respecte le plancher de 15 px et passe aux 4 tailles
  de `-Tour`.

Le client ne calcule rien : il met en forme les nombres de la spec et interpole ceux de la chronologie.

## Ce qui est remplacé, affiné ou conservé

- `world.size` est conservé (hall du site principal) ; `world.bounds` couvre le reste.
- `world.template` est conservé : il devient un id de pack en tranche 3, quand il y aura plusieurs gabarits de site.
- `departments[].area` est conservé, aligné sur la grille du site ; pour une zone externe, il est calculé par le placeur.
- `external` + `area` écrits à la main sont remplacés par `site` et `network.sites`. Le département `fournisseur` (son
  agent parlant) se rattache au site du fournisseur standard ; les deux autres sites n'ont pas d'agent.
- `ref: dock` est conservé : la route y aboutit. `forklift_route`, `Resources.docks` et le plan en U sont conservés.
- De `world_templates.yaml`, on garde `facing` (le côté `front`), les routes en segments (les `points`), `categories` et
  `defaults` : ce sont les assets de décor sûrs d'un bloc, pour le choix du décor par l'IA en tranche 2. On abandonne
  les parcelles libres sans grille et le terrain de taille fixe.

## Tranches, critères et budgets

**Tranche 1 (le plus petit sous-ensemble démontrable)** : le pack usine seul. Blocs internes sur grilles (motifs `edge`,
`rows`, `line`), trois sites fournisseurs et un site client en motif `single`, des routes, des camions rejoués, la classe
de distance choisie par l'IA et les délais tirés du graphe. L'atelier ne change pas. Fin quand :
1. Le placement est valide pour 1 à 3 lignes et pour chaque secteur : aucun chevauchement, tout objet dans son bloc,
   la bande d'allée libre, les postes accessibles, et le même monde pour la même spec (même empreinte).
2. Les racks MP et PF valent ⌈ capacité ÷ places ⌉ ; machines et tables suivent `factory.machines`.
3. Le délai suit la formule pour chaque profil et chaque classe permise, borné de 1 à 8 jours. Les classes par défaut
   redonnent 1, 3 et 5 jours, et les tests de l'usine restent verts sans modification.
4. Il y a un site par fournisseur des offres et pour le client, un lien par site externe ; les liens sont à angles
   droits, ne traversent pas le hall et finissent sur l'aire du quai.
5. Chaque camion a un `camion_arrive` avant son `camion_part` ; jamais plus de `Resources.docks` camions à quai ; la
   chronologie reste sous 200 Ko.
6. Godot : sites, routes et camions rejoués à x960 jusqu'à la fin du tour, 45 images/s ou plus en vue usine avec la
   carte (`world_preview`), `-Tour` inchangé.
7. ADR 0008 : un brief « fournisseurs lointains » met au moins un site en `national` ou `international` (cas d'éval), et
   la jouabilité est vérifiée après ce choix.
8. `check_placement` ne trouve rien sur l'usine, de 1 à 3 lignes. Un plan modifié qui viole une règle est refusé, et
   cela pour chacun des 6 types de règle.
9. `pack_coverage` liste les assets `a_sourcer` d'un pack. `GET /games/options` le marque non proposé ; `POST` répond
   422 à un formateur et 201 à l'admin. Le pack usine est couvert à 100 % à la fin de la tranche.
10. (29/10) `apply_edits` :
    - rejouer deux fois la même spec donne le même monde (même empreinte) ;
    - chaque raison de rejet est produite par un cas de test, avec son message ;
    - une retouche qui viole chacun des 6 types de règle est refusée par `check_placement` ;
    - sur 3 graines, 20 retouches d'objets laissent identiques le verdict du pilote automatique et les indicateurs du
      débrief ;
    - après un ajustement des paramètres qui retire une ligne, les retouches de cette ligne apparaissent dans `dropped`.
11. (29/10) API (`PUT /games/{id}/layout`, `PUT /games/{id}/params`, annexe 0008 §6) :
    - les droits : 200 pour le formateur propriétaire et pour l'admin, 403 pour un joueur, 404 pour un autre formateur ;
    - un refus renvoie 422 avec le rang et la raison, et la base n'a pas changé ;
    - 409 si le jeu est `generating` ou si un lobby non terminé l'utilise ;
    - la publication est refusée si `check_placement` n'est pas vide (spec injectée) ;
    - chaque route répond en moins d'1 s.
12. (29/10) Godot, mode construction :
    - `-Tour` passe aux 4 tailles avec la grille, le fantôme, la palette et le menu ;
    - le parcours `-Flow -Design` passe par ces étapes : déplacer un rack, retirer un décor, annuler, rétablir, un dépôt
      refusé avec sa raison affichée, puis la publication ;
    - 45 images/s ou plus avec la grille visible.
13. (29/10) Menus contextuels :
    - le pack usine déclare un menu pour chaque type de poste, pour les agents et pour les sites fournisseurs ;
    - `SimSpec` refuse un sélecteur inconnu, plus de 6 entrées et `parler` hors agent ;
    - dans `-Flow`, un clic sur un poste ouvre son menu, et l'action ouverte depuis un site fournisseur arrive
      pré-remplie avec ce fournisseur ;
    - l'API refuse toujours l'action d'un module que le rôle du joueur ne tient pas.

Budgets :
- `place_world` < 50 ms (compris dans `POST /games` < 1 s) ;
- `apply_edits` avec 200 retouches < 50 ms ;
- 400 objets et 8 sites au plus ;
- 2 événements par camion.

**Après** :
- tranche 2 : plusieurs types de liens et le mode de transport choisi par l'IA (vitesse et coût calibrés), le décor par
  emplacements (`categories`, `defaults`, `candidate_assets`), le réseau de l'atelier (délais en semaines) ;
- tranche 3 : des blocs et des gabarits de site facultatifs, choisis par l'IA quand un moteur s'en sert, et le second
  domaine.

## Questions à l'utilisateur

(29/10) L'utilisateur n'a pas objecté : les trois recommandations sont retenues **par défaut, à confirmer**. Ce sont
oui, 30 minutes et non (pack fermé sauf pour l'admin).

1. Faut-il interdire à l'IA les sites et blocs de pur décor (entrepôt distant, parking) que le moteur ne simule pas ?
   **Recommandation : oui.** La 3D ne montre que ce qui est calculé.
2. Un trajet de camion est-il rejoué en 30 minutes simulées, avec une étiquette pour un transit de plusieurs jours, ou
   pendant toute sa durée ? **Recommandation : 30 minutes.** Un camion qui roule plusieurs jours encombrerait la carte
   et coûterait en images par seconde.
3. Un pack dont il manque des assets reste-t-il jouable par le formateur, avec des boîtes de remplacement ?
   **Recommandation : non.** Il reste fermé (critère du point 7), sauf pour l'admin.

Décidé sans question : le réseau de l'atelier, avec ses délais en semaines, vient en tranche 2. La tranche 1 se
démontre sur l'usine, qui a déjà un quai et une chronologie.
