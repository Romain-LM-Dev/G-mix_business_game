# 0009 : monde généré sur grilles et réseau logistique

Date : 2026-10-29. Statut : proposé (questions en fin de document). Complète l'ADR 0007 (usine, quai, chronologie) et
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
5. **Généralité.** Les types de blocs, de liens et de sites, les motifs et les rôles ne parlent pas de supply chain.
   Un autre domaine s'exprime avec le même contrat (voir le tableau) ; sa mécanique demande les primitives de l'ADR 0008
   (point 3, B).

| Domaine | Sites et liens | Blocs (motif) |
|---|---|---|
| Hôpital | domicile et EHPAD (ambulance, route), pharmacie centrale (fournisseur, route) | urgences, chambres (`rows` de lits), bloc opératoire (`edge`), laboratoire, admission ; couloirs |
| Commerce | entrepôt régional (camion, route), fournisseurs | réserve (`rows`), surface de vente (`rows` de rayons), caisses (`line`) |
| Restaurant | grossiste et marché (camionnette, route) | cuisine (`line` de postes), salle (`edge`), chambre froide (`rows`), plonge |

## Contrat

Spec (`backend/gmix/game/spec.py`, champs facultatifs, une spec v2 existante reste valide) :

```python
Side = Literal["nord", "sud", "est", "ouest"]
Role = Literal["stockage", "machine", "tampon", "poste", "affichage", "engin", "decor", "porte", "batiment"]
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
```

Les contrôles (`_references`) ne s'appliquent que si `world.sites` n'est pas vide :
- les ids de site sont uniques, un seul site principal, en premier ;
- les aires des sites sont disjointes et toutes dans `bounds` ;
- `from_site` et `to_site` de chaque lien existent, et chaque segment est horizontal ou vertical ;
- chaque fournisseur des offres a un site, et le `supplier_id` de chaque site fournisseur est connu ;
- le `site_id` de chaque département existe.

Pack (game-designer), contrôlé par `_check_pack` :
- `grid: {site_cell_m: 0.5}` : les `area` internes sont des multiples de cette cellule.
- `block_types.<id>: {label, pattern: edge|rows|line|single, cell_m, front_aisle_cells, row_aisle_cells}`.
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

Placeur (`gmix.game.layout`, moteur-jeu) :

```python
def place_world(spec: dict, pack: dict) -> dict
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
- caméra Sims qui peut reculer jusqu'à `world.bounds`.

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

Budgets : `place_world` < 50 ms (compris dans `POST /games` < 1 s) ; 400 objets et 8 sites au plus ; 2 événements par
camion.

**Après** :
- tranche 2 : plusieurs types de liens et le mode de transport choisi par l'IA (vitesse et coût calibrés), le décor par
  emplacements (`categories`, `defaults`, `candidate_assets`), le réseau de l'atelier (délais en semaines) ;
- tranche 3 : des blocs et des gabarits de site facultatifs, choisis par l'IA quand un moteur s'en sert, et le second
  domaine.

## Questions à l'utilisateur

1. Faut-il interdire à l'IA les sites et blocs de pur décor (entrepôt distant, parking) que le moteur ne simule pas ?
   **Recommandation : oui.** La 3D ne montre que ce qui est calculé.
2. Un trajet de camion est-il rejoué en 30 minutes simulées, avec une étiquette pour un transit de plusieurs jours, ou
   pendant toute sa durée ? **Recommandation : 30 minutes.** Un camion qui roule plusieurs jours encombrerait la carte
   et coûterait en images par seconde.
3. Le réseau de l'atelier (fournisseurs externes, délais en semaines) en tranche 1 ou en tranche 2 ?
   **Recommandation : tranche 2.** La tranche 1 se démontre sur l'usine, qui a déjà un quai et une chronologie.
