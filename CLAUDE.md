# G-mix Open World

Générateur de business games en mini open world 3D. Un formateur choisit des paramètres (secteur, modules,
agents, difficulté, durée, aléas) ; `gmix.game.generation` assemble sans modèle une simulation hebdomadaire de
chaîne logistique (ai/simulation.yaml, ADR 0006), jouée dans un atelier Godot fait d'assets prédéfinis, avec
des agents PNJ (Ollama) qui disent les faits calculés par le moteur et se souviennent des échanges.
Rôles : joueur, formateur (crée et gère ses lobbies), admin (accès total).
Exigence n° 1 : les connaissances transmises doivent être vraies et sourcées.

Décisions : domaine prioritaire **supply chain** ; comptes locaux créés dans l'application (ADR 0004) ;
parties en réseau local ET à distance (ADR 0005). Points ouverts : docs/blocages.md.

## Stack et ports
| Brique | Techno | Où | Port hôte |
|---|---|---|---|
| Client | Godot 4.7.2 (GDScript) | `godot/` (natif) | - |
| API | FastAPI, Python 3.14 | `backend/gmix/api` | 8000 |
| Bus d'événements | Kafka 4.3.1 KRaft | Docker | 9092 |
| Base + RAG | PostgreSQL 18 + pgvector 0.8.7 | Docker | 5433 (5432 = PostgreSQL local) |
| Stockage objet | RustFS 1.0.1 (API S3) | Docker | 9000, console 9001 |
| IA | Ollama 0.40.x | natif, GPU | 11434 |

## Commandes (PowerShell, depuis la racine)
- `start.cmd` / `.\scripts\start.ps1 [-Lan] [-NoGame]` : tout lancer (Docker, infra, Ollama, API, jeu), premier admin
- `stop.cmd` / `.\scripts\stop.ps1 [-KeepInfra]` : tout arrêter (jeu, serveurs de partie, API, workers, conteneurs ; volumes gardés)
- `.\scripts\check-env.ps1` : diagnostic du poste, liste ce qui bloque
- `.\scripts\infra.ps1 up|down|status|logs|tools` : conteneurs + bootstrap (topics, buckets, migrations, domaines)
- `.\scripts\api.ps1 [-Lan]` : API avec rechargement (http://127.0.0.1:8000/docs) ; `-Lan` = ouverte au réseau de la salle
- `.\scripts\ingest.ps1 -Domain <slug>` : ingestion RAG des sources déclarées (SOURCES.md) + mesure de couverture
- `.\scripts\worker.ps1 <nom>` : worker Kafka (`system_ping` : diagnostic)
- `.\scripts\test.ps1 [-Fast] [-Integration]` : ruff + pytest + vérification du projet Godot
- `.\scripts\smoke.ps1` : test de bout en bout Godot <-> API <-> Kafka <-> worker <-> Ollama <-> RAG (compte admin jetable)
- `.\scripts\godot.ps1 [-Check|-Smoke|-Run] [-Api http://IP:8000]` : éditeur, vérification, liaison, jeu (autre serveur)
- `.\scripts\godot.ps1 -Tour [-Snapshot]` : contrôle de l'interface à 4 tailles de fenêtre ; `-Snapshot` : PNG dans `%TEMP%\gmix_imgs\ui_tour` (Godot à fenêtre)
- `.\scripts\godot.ps1 -Flow [-NoLlm]` : parcours scripté du client (formateur, bout en bout) ; comptes jetables nettoyés en base
- `backend\.venv\Scripts\python -m gmix.tools.create_user --username <id> --role admin|trainer|player` : compte en CLI
- `.\scripts\models.ps1 [-IncludeOptional]` : modèles Ollama du catalogue
- `.\scripts\assets.ps1 [-Downloads <dossier>] [-Gallery <dossier>] [-SyncDb]` : chaîne des assets 3D (ai/assets.yaml)
- `.\scripts\team.ps1 -Report|-Run <agentId>|-Json|-CheckOwners` : mesures de l'équipe d'agents (docs/equipe/README.md)

## Agents (.claude/agents) : équipe et organisation
La session principale tourne en `orchestrateur` (réglage `agent` de .claude/settings.json) : il découpe, délègue,
contrôle et rend un bilan, sans outil d'édition ni shell. Pour travailler sans lui, créer
.claude/settings.local.json (personnel, hors git) avec `{"agent": ""}`.

| Agent | Modèle | Possède | À lui pour |
|---|---|---|---|
| orchestrateur | session | rien : il délègue | découper, déléguer, contrôler, rendre compte |
| architecte | opus | docs/decisions/, contrats (messaging/topics.py, game/spec.py) | choix transverse, ADR, plan d'exécution |
| game-designer | opus | ai/simulation.yaml, ai/domains.yaml, ai/packs/ | justesse métier, chiffres, sources, agents PNJ, débrief |
| moteur-jeu | sonnet | backend/gmix/game/ et ses tests | moteur de simulation, génération, mémoire des agents |
| backend-api | sonnet | backend/gmix/api, db, alembic | endpoints, rôles, base, migrations |
| godot-dev | sonnet | godot/ hors godot/assets/ | atelier 3D, HUD, menus, réseau client |
| ia-runtime | sonnet | ai/models.yaml, prompts, evals (jeux, outils eval_*), backend/gmix/llm | tâches IA, prompts des agents PNJ, tev1, budgets, mesure des dialogues |
| rag-knowledge | sonnet | backend/gmix/rag, knowledge/ | ingestion, recherche, corpus |
| pipeline-kafka | sonnet | backend/gmix/messaging, workers | topics, événements, workers |
| assets-3d | sonnet | ai/assets.yaml, godot/assets/ | catalogue, import et fabrication d'assets 3D |
| devops | haiku | docker-compose.yml, infra/, scripts/, gmix.tools.ui_accounts | Docker, scripts, lancement, environnement, contrôles Godot (-Tour, -Flow) |
| qa-reviewer | sonnet | tests manquants | relecture de diff, tests, vérifications |
| documentaliste | sonnet | docs/ hors ADR, README, CLAUDE.md, .claude/ (agents, réglages) | docs à jour, références périmées, compétences et nouveaux agents |
| coach-equipe | opus | docs/equipe/ (rétros) | mesurer et améliorer l'équipe (propositions appliquées après accord de l'utilisateur) |

Carte de propriété lisible par machine : `.claude/ownership.json` (motifs de fichiers par agent, lus par
`.\scripts\team.ps1`), à tenir cohérente avec ce tableau (`.\scripts\team.ps1 -CheckOwners`).

Règles d'organisation :
- Un dossier = un propriétaire ; deux agents ne modifient jamais le même fichier en même temps (parallèle
  seulement sur des fichiers disjoints). Chacun écrit les tests de son propre code.
- Brief de délégation (un agent ne voit pas la conversation) : objectif, contexte (docs, fichiers, décisions),
  périmètre, critère de fin, compte rendu attendu.
- Compte rendu : fait · fichiers · vérifié (commande -> résultat réel) · reste et risques. Jamais « terminé »
  sans résultat de commande ; une vérification non lancée ou en échec est écrite telle quelle.
- Fin de chantier : `qa-reviewer` (`.\scripts\test.ps1`, avec `-Integration` si API, Kafka, Ollama ou Godot sont
  touchés), puis `documentaliste` si un comportement, un contrat ou une commande a changé.
- Mécanique -> haiku, code -> sonnet, conception et exactitude métier -> opus.
- Tâche sans compétence correspondante : ajouter d'abord la compétence à l'agent concerné, ou créer l'agent si le
  domaine n'est pas couvert (brief à `documentaliste`, qui l'inscrit au tableau) ; jamais `general-purpose` (interdit).

## Règles transverses
- IA : le code appelle une tâche de ai/models.yaml, jamais un modèle. Les agents ne disent que les faits
  calculés par le moteur (`briefings`). `num_ctx` est fixé par modèle (le faire varier recharge le modèle).
- Spec de business game : validée par `gmix.game.spec.SimSpec` puis jouée en pilote automatique ; toute
  action de ai/simulation.yaml a son handler dans `gmix.game.engine` (testé).
- Kafka : commandes, événements et traitements IA asynchrones. Le temps réel 3D passe par le réseau Godot
  (serveur de partie par lobby, `gmix.game.servers` + autoload Presence). Règles de partie : `gmix.game.engine`
  (fonctions pures) appelé par l'API sous verrou de ligne.
- Code et identifiants en anglais ; contenus, interface et documentation en français.
- Windows + PowerShell 5.1 ; chemins entre guillemets (espace dans « Projet IE ») ; scripts .ps1 en UTF-8 avec BOM.
- Matériel : RTX 3060 Laptop 6 Go VRAM, 16 Go RAM. Un seul modèle d'environ 5 Go tient en VRAM.
- Ne jamais supprimer les volumes Docker (`down -v`, `infra.ps1 reset`) sans accord explicite.
- Avant de rendre la main : `.\scripts\test.ps1` (ou `-Fast` si Godot n'est pas touché).

## Documentation
docs/prompt-projet.md : vision, attendus majeurs et prompt de session, à lire en premier
docs/architecture.md · docs/ai-runtime.md · docs/kafka.md · docs/roles.md · docs/game-design.md ·
docs/decisions/ (ADR) · docs/blocages.md (points bloquants et décisions en attente) · docs/equipe/ (évaluation de
l'équipe) · godot/README.md · ai/evals/README.md (évaluations des agents IA)
docs/references/usine-3d/ (inspiration « usine 3D » fournie par l'utilisateur : exemples non sourcés, lire le README)
