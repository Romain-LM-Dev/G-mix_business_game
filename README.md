# G-mix Open World

Générateur de business games en mini open world 3D : un formateur choisit un domaine d'expertise, décrit son
besoin, et des agents IA locaux génèrent un scénario pédagogique cohérent, joué en multijoueur dans Godot.

## Démarrage (Windows, PowerShell)

Prérequis : Docker Desktop démarré, Python 3.14, Godot 4.7.2, Ollama.

```powershell
.\scripts\setup.ps1          # .env (secret JWT aléatoire), venv Python, dépendances, images Docker
.\scripts\infra.ps1 up       # Kafka, PostgreSQL+pgvector, RustFS + topics, buckets, migrations, domaines
.\scripts\models.ps1         # modèles Ollama du catalogue (ai/models.yaml)
.\scripts\check-env.ps1      # diagnostic : ce qui bloque
.\scripts\smoke.ps1          # test de bout en bout (lance l'API et le worker si besoin)
backend\.venv\Scripts\python -m gmix.tools.create_user --username admin --role admin   # premier compte
```

**Lancement rapide** : double-clic sur `start.cmd` (ou `.\scripts\start.ps1 [-Lan]`) : Docker, infrastructure,
Ollama, API, worker de génération et jeu ; au premier lancement, crée le compte `admin` et affiche son mot de
passe provisoire. Arrêt : `stop.cmd` (ou `.\scripts\stop.ps1 -KeepInfra` pour garder les conteneurs).

Séance à la main : `.\scripts\api.ps1` (ou `-Lan` en salle), `.\scripts\worker.ps1 generation` (génération des
business games par l'IA, 6 à 9 min chacune sur une RTX 3060 6 Go), puis `.\scripts\godot.ps1 -Run`.
L'admin crée les formateurs dans l'onglet Comptes ; un formateur génère ou importe un business game
(exemple : ai/examples/tresorerie_sous_tension.json), crée le lobby et donne le code aux joueurs.

Développement : `.\scripts\api.ps1` (http://127.0.0.1:8000/docs), `.\scripts\worker.ps1 system_ping`,
`.\scripts\godot.ps1` (éditeur), `.\scripts\test.ps1` (lint, tests, vérification Godot),
`.\scripts\ingest.ps1 -Domain supply-chain` (corpus RAG du domaine prioritaire),
`.\scripts\assets.ps1 -Gallery <dossier>` (assets 3D : construction des scènes et captures de contrôle).

Jeu en salle (réseau local) : sur la machine hôte `.\scripts\api.ps1 -Lan` (affiche l'adresse à utiliser),
sur chaque poste joueur `.\scripts\godot.ps1 -Run`, adresse `http://<IP-hôte>:8000` à l'écran de connexion.
La présence des autres joueurs passe par un serveur Godot par lobby, lancé par l'API sur les ports UDP
GAME_SERVER_PORTS (7000-7049) : à autoriser dans le pare-feu de l'hôte. Mode à distance : voir
docs/decisions/0005-jeu-local-et-distance.md.

Consoles : stockage S3 http://localhost:9001 · Kafka http://localhost:8085 (`.\scripts\infra.ps1 tools`).

## Organisation

| Dossier | Contenu |
|---|---|
| `godot/` | client 3D (voir godot/README.md) |
| `backend/gmix/` | API, messagerie Kafka, workers, couche IA, RAG, contrôles de cohérence |
| `ai/` | catalogue de modèles et de tâches, domaines, schémas, prompts, assets, évaluations |
| `knowledge/` | corpus de documents sourcés pour le RAG |
| `infra/`, `docker-compose.yml` | infrastructure locale |
| `docs/` | architecture, IA, Kafka, rôles, game design, décisions, blocages |
| `.claude/agents/` | agents Claude Code spécialisés (voir CLAUDE.md) |
