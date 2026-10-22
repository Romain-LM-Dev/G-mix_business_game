# G-mix Open World

Générateur de business games en mini open world 3D. Un formateur choisit un domaine d'expertise
(ai/domains.yaml) et décrit son besoin ; des agents IA locaux (Ollama) génèrent un scénario pédagogique
cohérent (objectifs, KPI, décisions chiffrées, PNJ experts, carte) assemblé à partir d'assets 3D prédéfinis ;
les joueurs le jouent dans Godot. Rôles : joueur, formateur (crée et gère ses lobbies), admin (accès total).
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
- `start.cmd` / `.\scripts\start.ps1 [-Lan] [-NoGame]` : tout lancer (Docker, infra, Ollama, API, worker, jeu), premier admin
- `stop.cmd` / `.\scripts\stop.ps1 [-KeepInfra]` : tout arrêter (jeu, serveurs de partie, API, workers, conteneurs ; volumes gardés)
- `.\scripts\check-env.ps1` : diagnostic du poste, liste ce qui bloque
- `.\scripts\infra.ps1 up|down|status|logs|tools` : conteneurs + bootstrap (topics, buckets, migrations, domaines)
- `.\scripts\api.ps1 [-Lan]` : API avec rechargement (http://127.0.0.1:8000/docs) ; `-Lan` = ouverte au réseau de la salle
- `.\scripts\ingest.ps1 -Domain <slug>` : ingestion RAG des sources déclarées (SOURCES.md) + mesure de couverture
- `.\scripts\worker.ps1 <nom>` : worker Kafka (`generation` : business games par l'IA ; `system_ping` : diagnostic)
- `.\scripts\test.ps1 [-Fast] [-Integration]` : ruff + pytest + vérification du projet Godot
- `.\scripts\smoke.ps1` : test de bout en bout Godot <-> API <-> Kafka <-> worker <-> Ollama <-> RAG (compte admin jetable)
- `.\scripts\godot.ps1 [-Check|-Smoke|-Run] [-Api http://IP:8000]` : éditeur, vérification, liaison, jeu (autre serveur)
- `backend\.venv\Scripts\python -m gmix.tools.create_user --username <id> --role admin|trainer|player` : compte en CLI
- `.\scripts\models.ps1 [-IncludeOptional]` : modèles Ollama du catalogue
- `.\scripts\assets.ps1 [-Downloads <dossier>] [-Gallery <dossier>] [-SyncDb]` : chaîne des assets 3D (ai/assets.yaml)

## Agents (.claude/agents) : à qui déléguer
| Besoin | Agent | Modèle |
|---|---|---|
| Choix transverse, contrat, ADR, découpage | architecte | opus |
| Justesse métier, mécaniques, KPI, objectifs pédagogiques | game-designer | opus |
| Scènes, UI, menus, monde 3D (godot/) | godot-dev | sonnet |
| Endpoints, rôles, base, migrations | backend-api | sonnet |
| Topics, événements, workers, orchestration | pipeline-kafka | sonnet |
| Ingestion, embeddings, recherche, corpus | rag-knowledge | sonnet |
| Catalogue de tâches IA, prompts, budgets, tev1, PNJ | ia-runtime | sonnet |
| Catalogue et import d'assets 3D | assets-3d | haiku |
| Docker, scripts, environnement | devops | haiku |
| Relecture de diff, tests | qa-reviewer | sonnet |

Économie : ne pas lancer d'agent pour ce qui se règle en lisant deux fichiers. Donner à l'agent un périmètre
précis (fichiers, critère de fin) ; il rend un compte rendu court. Mécanique -> haiku, code -> sonnet,
conception et exactitude métier -> opus.

## Règles transverses
- IA : le code appelle une tâche de ai/models.yaml, jamais un modèle. Sorties JSON validées par schéma puis par
  `gmix.game.coherence`. `num_ctx` est fixé par modèle (le faire varier recharge le modèle).
- Kafka : commandes, événements et traitements IA asynchrones. Le temps réel 3D passe par le réseau Godot
  (serveur de partie par lobby, `gmix.game.servers` + autoload Presence). Règles de partie : `gmix.game.engine`
  (fonctions pures) appelé par l'API sous verrou de ligne.
- Code et identifiants en anglais ; contenus, interface et documentation en français.
- Windows + PowerShell 5.1 ; chemins entre guillemets (espace dans « Projet IE ») ; scripts .ps1 en UTF-8 avec BOM.
- Matériel : RTX 3060 Laptop 6 Go VRAM, 16 Go RAM. Un seul modèle d'environ 5 Go tient en VRAM.
- Ne jamais supprimer les volumes Docker (`down -v`, `infra.ps1 reset`) sans accord explicite.
- Avant de rendre la main : `.\scripts\test.ps1` (ou `-Fast` si Godot n'est pas touché).

## Documentation
docs/architecture.md · docs/ai-runtime.md · docs/kafka.md · docs/roles.md · docs/game-design.md ·
docs/decisions/ (ADR) · docs/blocages.md (points bloquants et décisions en attente) · godot/README.md
