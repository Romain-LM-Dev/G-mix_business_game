# G-mix Open World : prompt maître

Texte de référence qui recadre toute session sur les attentes majeures du projet. Il ne répète pas les ADR : il
renvoie à eux (« ADR 0008 annexe §3 »). Il ne contient aucun état volatil (état courant : docs/equipe/reprise.md).
Les ADR 0008 et 0009 sont acceptés (29/10, décisions par défaut à confirmer par l'utilisateur) : leurs modules (`gmix.game.design`,
`gmix.game.layout`, `gmix.tools.eval_design`) et leurs options (`godot.ps1 -Flow -Design`) sont décidés ; vérifier
leur existence (Glob) avant de s'en servir.

## 1. Mission et vision

G-mix génère des **business games 3D dans la même direction artistique que Les Sims**. Un LLM local génère ces jeux
de façon intelligente, mais il conçoit : le moteur calcule.

| Étape | Ce que fait l'utilisateur ou le système |
|---|---|
| Domaine | Le formateur choisit un domaine parmi une sélection proposée, qui dépend des assets disponibles |
| Paramètres | Il choisit un ensemble de modules et de paramètres (ou écrit un brief libre) |
| Monde | Le LLM génère le monde, fait de différents quadrillages qui permettent de placer les assets |
| Placement | Il est cohérent et fondé sur les expertises métier du domaine choisi |
| Interfaces | Les interfaces joueur et formateur changent et sont modulaires : elles offrent les outils adaptés au domaine |

Exemple de référence : en supply chain, les fournisseurs sont externalisés et reliés par des routes et des transports.
Rôles : joueur, formateur (crée et gère ses lobbies), admin (accès total). Exigence n° 1 : les connaissances
transmises sont vraies et sourcées.

Décisions de l'utilisateur (2026-10-29) :

| Décision | Contenu |
|---|---|
| Caméra | La caméra Sims actuelle est validée. Il manque le côté Sims des menus contextuels et un mode construction sur grille |
| DA | Assets procéduraux, DA sauge/turquoise du jeu de référence (déjà reprise : `godot/scenes/common/ui_tokens.gd`, `godot/assets/procedural/palette.gd`) |
| Domaine v1 | Supply chain seule, avec toutes les briques génériques : un nouveau domaine = un pack `ai/packs/<id>.yaml` + des assets, pas du code |
| Édition | Le formateur modifie le monde généré avant publication avec un éditeur de grille (mode construction), et peut aussi régénérer ou ajuster les paramètres. Spécification : ADR 0009 |
| Local | Plus jamais de LLM externe (ChatGPT, Gemini, etc.) : tout est local (Ollama) |

## 2. Les attendus majeurs

Si un chantier ne sert aucun de ces dix attendus, le remettre en question avant de l'écrire.

| # | Attendu | Comment on le vérifie |
|---|---|---|
| 1 | **Domaines proposés selon les assets.** Un domaine est proposé si un pack est chargé, sourcé et couvert à 100 % ; sinon grisé avec la raison. Un nouveau domaine = données | ADR 0009 décision 7 ; critère 0009-9 (`pack_coverage("usine")["ratio"] == 1.0`, 422 pour un pack non proposé) |
| 2 | **L'IA conçoit** concept, cast et journey à partir du brief et des paramètres, en choisissant dans les catalogues du pack | ADR 0008 annexe §9 critères 3 et 5 ; `gmix.tools.eval_design --series C` atteint les seuils du §8 |
| 3 | **Un monde sur grilles**, posé par un placeur déterministe : carte, site, bloc | ADR 0009 décision 1 ; critères 0009-1, 0009-2 |
| 4 | **Placement fondé sur le métier** : règles d'implantation du domaine, chacune avec sa provenance | ADR 0009 décision 6 ; critère 0009-8 (`check_placement` ne trouve rien ; un plan qui viole une règle est refusé, 6 types) |
| 5 | **Réseau logistique** : fournisseurs externalisés, routes, camions rejoués, délais dérivés de la distance | ADR 0009 décisions 3 et 4 ; critères 0009-3, 0009-4, 0009-5 |
| 6 | **Jeu juste et jouable**, toujours : validation, essai en pilote automatique, deux réparations au plus, repli déterministe | ADR 0008 décision 2 ; annexe §9 critères 1, 2, 3 |
| 7 | **Le formateur garde la main** : aperçu 3D, éditeur de grille, régénération d'une section, réglage des paramètres, publication ; pas de lobby sur un brouillon | ADR 0009 décision 8 ; critères 0009-10 à 0009-12 ; ADR 0008 décision 2 et annexe §9 critère 4 |
| 8 | **Interfaces modulaires et lisibles** : panneaux et outils du domaine, menus contextuels Sims, 4 tailles de fenêtre | `.\scripts\godot.ps1 -Tour` ; ADR 0008 décision 5 ; ADR 0009 décision 9 ; critères 0009-6, 0009-12 et 0009-13 |
| 9 | **Partie rejouable et vraie** : événements discrets, mêmes paramètres = même spec, agents qui ne disent que les faits calculés, notions citées | ADR 0007 décisions 1, 2, 7 ; `.\scripts\test.ps1` ; annexe 0008 §8 (notions d'objectif avec citation : 100 %) |
| 10 | **Tout local et tenable sur le poste** (RTX 3060 6 Go) : un job de conception de 3 min en médiane, jamais plus de 10 | ADR 0008 décision 4 et annexe §8 ; `.\scripts\check-env.ps1` |

## 3. Chaîne de bout en bout

```
 domaine proposé (couverture d'assets, ADR 0009 d.7)
        |
        v
 modules + paramètres (GameParams) + brief libre (20 à 2000 caractères)
        |
        v
 conception par l'IA : concept -> cast -> journey      (3 appels, un job à la fois)
   choix dans les catalogues du pack ; aucun nombre, aucune coordonnée, aucun lien
        |
        v
 placeur déterministe (gmix.game.layout) : grille carte / site / bloc + réseau logistique
        |
        v
 validation : SimSpec -> check_design -> essai en pilote automatique
              (<= 2 réparations par le modèle, relax sans modèle, sinon repli déterministe)
        |
        v
 aperçu 3D + éditeur de grille du formateur (mode construction) ; régénérer / ajuster les paramètres
        |
        v
 publication (brouillon -> publié) -> lobby
        |
        v
 partie jouée : moteur à événements discrets (gmix.game.factory), chronologie rejouée en 3D
        |
        v
 débrief (indicateurs calculés, notions et sources, règles non sourcées listées)
```

Détail : ADR 0008 décisions 2 et 4, annexe §3 ; ADR 0009 décisions 1 à 6 ; ADR 0007 décisions 1 et 2.

## 4. Principes non négociables

| Principe | Conséquence concrète |
|---|---|
| **L'IA conçoit, le moteur calcule et seul juge** | `gmix.game.engine` et `gmix.game.factory` sont la vérité ; le rejeu 3D montre ce qui a été calculé (ADR 0007 d.2) |
| L'IA n'écrit ni chiffre, ni coordonnée, ni lien | Elle choisit dans des énumérations construites depuis le pack ; texte sans chiffre (ADR 0008 d.1, ADR 0009 d.2) |
| Connaissances vraies et sourcées | Provenance de chaque valeur : `source` (citation), `calibre` (note), `exemple` ; jamais de source inventée ; les valeurs et règles non sourcées sont affichées (ADR 0007 d.8, ADR 0009 d.6) |
| Les agents PNJ ne disent que les faits calculés | `briefings` du moteur ; `npc.dialogue` inchangé (ADR 0006, ADR 0008 d.1) |
| Un domaine est une donnée | Pack `ai/packs/<id>.yaml` + assets ; une nouvelle mécanique demande un modèle pur testé (ADR 0007 d.5) |
| Local d'abord | Ollama, aucun LLM externe ; le code appelle une tâche de `ai/models.yaml`, jamais un modèle |
| Interfaces lisibles | Police 15 px au moins, aucun débordement aux 4 tailles (`-Tour`), limites `UI_LIMITS` (ADR 0008 d.5) |
| Un seul modèle en VRAM | `num_ctx` fixé par modèle ; Kafka pour les traitements IA asynchrones, jamais pour le temps réel 3D |
| Tests d'abord | Une erreur de placement est une erreur du pack, vue par les tests, jamais à l'exécution (ADR 0009 d.1) |

**Ce qui a été perdu ou abandonné et ne doit pas revenir** :

| Abandonné | Pourquoi |
|---|---|
| Génération narrative LLM de 7 à 9 min (qwen2.5:7b, commit 5a5d288) | Occupait le GPU ; le modèle écrivait effets et montants : sens inversés, montants inventés (ADR 0006, ADR 0008 Contexte) |
| Scénarios libres non calibrés | Valeurs sans provenance, KPI mal choisis (ADR 0006 Contexte) |
| Un pack écrit par l'IA et jouable sans relecture | Contraire à l'exigence n° 1 (ADR 0008 « Rejeté ») |
| Génération synchrone dans l'API | Plusieurs minutes de requête HTTP, GPU disputé (ADR 0008 « Rejeté ») |
| Site ou bloc de pur décor que le moteur ne simule pas | La 3D ne montre que ce qui est calculé (ADR 0009 question 1, recommandation à confirmer) |
| Parcelles libres sans grille, terrain de taille fixe | Remplacés par les grilles (ADR 0009 « Ce qui est remplacé ») |
| Textes de 7 à 11 px du jeu de référence | 15 px au moins (ADR 0008 d.5) |
| LLM externe | Décision de l'utilisateur du 2026-10-29 |

Avertissements à ne jamais retirer sans preuve (docs/blocages.md) : le jeu de référence n'a pas de licence (accord
de son autrice avant toute diffusion) ; le calibrage des simulations est à faire relire par `game-designer` ; le
corpus est provisoire et les domaines sans corpus sont « non sourcés ».

## 5. Le monde

| Notion | Définition | Renvoi |
|---|---|---|
| Grille de carte | Un site = une cellule de `map.cell_m` ; classe de distance = anneau, camp = côté. Le kilométrage est affiché, pas mis à l'échelle | ADR 0009 d.1 |
| Grille de site | Les blocs sont des rectangles alignés sur `grid.site_cell_m` (0,5 m) ; plan en U conservé | ADR 0009 d.1 |
| Grille locale de bloc | Cellule, allée, bande libre ; motifs `edge`, `rows`, `line`, `single` ; contenu par rôles (`stockage`, `machine`, `poste`…) | ADR 0009 d.1 et Contrat |
| Sites et liens | Le principal, les fournisseurs, les clients ; liens à angles droits qui finissent à `ref: dock` | ADR 0009 d.3, Contrat |
| Règles de placement | `placement_rules[]` du pack, types connus du code (`adjacent`, `flow`, `separated`, `aisle_min`, `facing`, `near`), chacune avec provenance | ADR 0009 d.6 |
| Couverture d'assets | Assets requis du pack, couverts s'ils sont `importe` dans `ai/assets.yaml` | ADR 0009 d.7 |
| Délais | Préparation + ⌈ km ÷ vitesse ÷ heures de conduite par jour ⌉, bornés de 1 à 8 jours | ADR 0009 d.3, critère 0009-3 |

Le placeur est pur et sans hasard : même spec, même type de monde (critère 0009-1). L'IA ne choisit que ce que le moteur
simule : en tranche 1, la classe de distance de chaque fournisseur. Éditeur de grille : spécifié dans l'ADR 0009
décision 8 (`layout_edits`, `apply_edits`, critère 0009-10), y renvoyer plutôt que recopier. Un plan modifié par le formateur repasse par `check_placement`.

## 6. Interfaces

| Sujet | Règle | Renvoi |
|---|---|---|
| Modularité | Le pack déclare un catalogue de panneaux (5 types) et d'outils (6 au plus) ; l'IA en choisit et ordonne une partie ; le formateur réordonne ou masque ; le joueur règle sa disposition | ADR 0008 d.5 ; ADR 0007 d.6 |
| Joueur et formateur | Deux publics, deux jeux d'outils (`audience`) ; écran de séance formateur modulaire (emplacement `supervision`) | ADR 0008 annexe §10.1 |
| Menus contextuels Sims | Clic sur un objet ou un agent, menu d'actions du domaine ; = `Tool.menu` du pack | ADR 0009 décision 9 ; critère 0009-13 ; docs/blocages.md (vue Sims) ; godot/README.md |
| Mode construction | Éditeur de grille du formateur, avant publication ; routes `PUT /api/v1/games/{id}/layout` et `/params` | ADR 0009 décision 8 ; critères 0009-11 et 0009-12 |
| DA | Sauge/turquoise ; jetons de thème `meta.ui_theme` ; assets procéduraux | `godot/scenes/common/ui_tokens.gd`, `godot/assets/procedural/palette.gd` |
| Lisibilité | Fenêtre de référence 1280x720, police 15 px au moins, aucun débordement aux 4 tailles | `.\scripts\godot.ps1 -Tour` |
| Le client ne calcule rien | Il met en forme la spec et interpole la chronologie | ADR 0009 Contrat (Godot) |

## 7. Savoir et agents PNJ

| Sujet | Règle |
|---|---|
| Corpus | `knowledge/<domaine>/`, sources déclarées dans `SOURCES.md` ; ingestion et couverture : `.\scripts\ingest.ps1 -Domain supply-chain` |
| Notions | Chaque notion du pack porte une citation ; une notion hors du pack est interdite à l'IA (ADR 0008 d.1) |
| Agents | Un agent parlant par module ou département ; le moteur calcule ses faits ; le modèle les dit en une ou deux phrases avec le caractère de l'agent (docs/game-design.md) |
| Mémoire | Les six derniers échanges du lobby avec l'agent ; mémoire partagée entre joueurs, risque d'injection persistante accepté (ADR 0007 d.12) |
| Garde-fous | Pré-filtre lexical, tours douteux jamais mémorisés ; garde-fou des nombres de `npc.py` en attente de décision (docs/blocages.md) |
| Débrief | Indicateurs calculés, aléas survenus, notions et sources, valeurs et règles non sourcées |

## 8. Contraintes techniques et budgets

Matériel : RTX 3060 Laptop 6 Go de VRAM, 16 Go de RAM ; un seul modèle d'environ 5 Go tient en VRAM. Le 7b tourne à
21,5 tok/s et met 7 à 27 s à charger ; tev1:4b (4,6 Go) ne tient pas à côté du modèle de dialogue (ADR 0008 Contexte,
docs/blocages.md). Dialogue : qwen2.5:3b (`ai/models.yaml`).

| Budget | Valeur | Source |
|---|---|---|
| Job de conception | médiane 3 min, 90e centile 5 min, 10 min au plus, puis repli | ADR 0008 d.4 ; annexe §8 |
| Tokens par job | médiane <= 10 000, maximum <= 20 000 | ADR 0008 annexe §8 |
| Réparations par le modèle | 2 essais au plus par section | ADR 0008 d.2 |
| `POST /games` | < 1 s (pilote automatique compris, 3 lignes x 4 machines, 12 tours) | ADR 0007 Conséquences |
| `PUT /design` | < 1 s | ADR 0008 annexe §9 critère 4 |
| `place_world` | < 50 ms, 400 objets et 8 sites au plus, 2 événements par camion | ADR 0009 Budgets |
| `advance` | < 150 ms ; état public < 64 Ko ; chronologie < 200 Ko par tour | ADR 0007 Conséquences ; 0009-5 |
| Images par seconde | 45 ou plus en vue usine avec le modèle 3b chargé (ADR 0007) ; 45 ou plus en vue usine avec la carte `world_preview` (0009-6) | ADR 0007 Conséquences ; ADR 0009 |
| Lisibilité | police >= 15 px ; 4 tailles de fenêtre | ADR 0008 d.5 |

Ports, stack et commandes : CLAUDE.md. Contexte `num_ctx` : docs/ai-runtime.md.

## 9. Façon de travailler

| Sujet | Règle |
|---|---|
| Équipe | Propriétaires et tableau : CLAUDE.md. Un dossier = un propriétaire ; jamais `general-purpose` |
| Orchestrateur | Découpe, délègue avec un brief (objectif, contexte, périmètre, critère de fin, compte rendu attendu), contrôle, rend un bilan |
| Une mission = un livrable | Un agent, un résultat vérifiable ; pas de chantier fourre-tout |
| Lectures ciblées | Grep puis plages de lignes ; les annexes d'ADR ne se lisent pas en entier |
| Tests compacts | `.\scripts\test.ps1 -Fast` (sans Godot), `-Only <fichier ou expression -k>`, `-Integration` (API, Kafka, Ollama) ; `.\scripts\godot.ps1 -Check`, `-Tour`, `-Flow` |
| Comptes rendus courts | Fait · fichiers · vérifié (commande -> résultat réel) · reste et risques |
| Fin de chantier | `qa-reviewer`, puis `documentaliste` si un comportement, un contrat ou une commande a changé |

**Effort adaptatif par tâche** (champ `effort` du frontmatter des agents ; l'orchestrateur peut le surcharger par
mission). Jamais « max » par défaut.

| Effort | Agents |
|---|---|
| low | devops, documentaliste, pipeline-kafka, rag-knowledge |
| medium | moteur-jeu, backend-api, godot-dev, ia-runtime, assets-3d, qa-reviewer, coach-equipe |
| high | architecte, game-designer : uniquement pour de la conception |

**Pile partagée** (plusieurs sessions peuvent tourner sur la même pile) :
- Avant de démarrer : `docker ps`, http://127.0.0.1:8000/docs, Ollama (http://127.0.0.1:11434). Ce qui répond est réutilisé.
- Jamais `stop.ps1` ni `docker compose down` ; jamais supprimer les volumes (`down -v`, `infra.ps1 reset`) sans accord explicite.
- Ne relancer que ce qui est arrêté ; ne pas tuer un processus qu'on n'a pas lancé.

## 10. Définition de fini

| Contrôle | Commande ou critère |
|---|---|
| Qualité de base | `.\scripts\test.ps1` (ou `-Fast` si Godot n'est pas touché) vert |
| API, Kafka, Ollama ou Godot touchés | `.\scripts\test.ps1 -Integration` vert |
| Bout en bout | `.\scripts\smoke.ps1` OK |
| Client | `.\scripts\godot.ps1 -Check`, `-Tour`, `-Flow` (et `-Flow -Design` quand il existe, avec et sans `-NoLlm`) |
| Conception par l'IA | Critères 1 à 7 de l'ADR 0008 annexe §9, dont les seuils du §8 sur la série C |
| Monde et réseau | Critères 0009-1 à 0009-13 (ADR 0009 « Tranches, critères et budgets ») |
| Équipe | `.\scripts\team.ps1 -CheckOwners` si une règle de propriété change |
| Documentation | Passe de `documentaliste` ; aucun chiffre sans commande ni compte rendu daté |

« Terminé » sans résultat de commande n'est pas terminé ; une vérification non lancée ou en échec s'écrit telle quelle.

## 11. Où en est-on

État courant : docs/equipe/reprise.md. Plan d'exécution : ADR 0008 annexe §10 et §10.1.

## 12. Prompt de session

À coller en tête d'une session Claude Code.

```
Tu travailles sur G-mix Open World : un générateur de business games 3D (direction artistique Les Sims) dont un
LLM local conçoit les jeux, sur un moteur déterministe. Avant toute action, lis docs/prompt-projet.md, CLAUDE.md et
docs/equipe/reprise.md. Tu es l'orchestrateur : tu découpes, tu délègues au propriétaire du dossier, tu contrôles.

Les 5 règles qui comptent le plus :
1. L'IA conçoit, le moteur calcule et seul juge. L'IA n'écrit ni chiffre, ni coordonnée, ni lien : elle choisit
   dans les catalogues du pack. Les agents PNJ ne disent que les faits calculés.
2. Tout est vrai et sourcé : provenance source|calibre|exemple, jamais de source inventée, aucun avertissement
   (docs/blocages.md) retiré sans preuve.
3. Un domaine est une donnée (pack + assets), pas du code ; le monde est posé sur grilles par un placeur
   déterministe selon les règles métier du domaine ; le formateur relit et édite avant de publier.
4. Tout est local (Ollama), aucun LLM externe ; budgets du poste (RTX 3060 6 Go) tenus.
5. Interfaces modulaires et lisibles aux 4 tailles (police 15 px au moins) ; pile partagée : jamais stop.ps1,
   jamais docker compose down, jamais supprimer les volumes.

Boucle de travail, pour chaque mission (une mission = un livrable) :
1. Comprendre : lectures ciblées (Grep puis plages de lignes), ADR concerné, état dans reprise.md.
2. Déléguer au propriétaire (tableau de CLAUDE.md) avec un brief : objectif, contexte, périmètre, critère de fin,
   compte rendu attendu. Pas de general-purpose. Fichiers disjoints seulement en parallèle.
3. Vérifier par commande, jamais de mémoire : test.ps1 -Fast|-Integration|-Only, godot.ps1 -Check|-Tour|-Flow,
   smoke.ps1. Un résultat non lancé ou en échec s'écrit tel quel.
4. Documenter : documentaliste si un comportement, un contrat ou une commande a changé ; qa-reviewer en fin de chantier.

Effort adaptatif : low pour devops, documentaliste, pipeline-kafka, rag-knowledge ; medium pour moteur-jeu,
backend-api, godot-dev, ia-runtime, assets-3d, qa-reviewer, coach-equipe ; high pour architecte et game-designer,
seulement en conception. Jamais « max » par défaut ; surcharge par mission si la tâche l'exige.

Comptes rendus courts : fait, fichiers, vérifié (commande -> résultat), reste et risques. Si une demande s'écarte de
ces attendus (génération narrative par LLM, scénarios non calibrés, domaine codé en dur), dis-le avant d'agir.
```
