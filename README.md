# G-mix Open World

Générateur de business games en mini open world 3D : un formateur choisit des paramètres (secteur, modules,
agents, difficulté, durée, aléas) et obtient aussitôt une simulation de chaîne logistique cohérente, jouée en
multijoueur dans un atelier Godot avec des agents PNJ (IA locale) qui informent les joueurs et se souviennent
des échanges.

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
Ollama, API et jeu ; au premier lancement, crée le compte `admin` et affiche son mot de passe provisoire.
Arrêt : `stop.cmd` (ou `.\scripts\stop.ps1 -KeepInfra` pour garder les conteneurs).

Séance à la main : `.\scripts\api.ps1` (ou `-Lan` en salle), puis `.\scripts\godot.ps1 -Run`. L'admin crée
les formateurs dans l'onglet Comptes ; un formateur génère un business game par paramètres (ou importe une
spec), crée le lobby, donne le code aux joueurs, lance la partie et simule les semaines. Les joueurs agissent
aux postes de l'atelier (touche E) et parlent aux agents.

Développement : `.\scripts\api.ps1` (http://127.0.0.1:8000/docs), `.\scripts\worker.ps1 system_ping`,
`.\scripts\godot.ps1` (éditeur), `.\scripts\test.ps1` (lint, tests, vérification Godot),
`.\scripts\ingest.ps1 -Domain supply-chain` (corpus RAG du domaine prioritaire),
`.\scripts\assets.ps1 -Gallery <dossier>` (assets 3D : construction des scènes et captures de contrôle).

Contrôles du client Godot (API locale, comptes jetables `uitour_…` ou `flowtest_…` créés puis supprimés en base) :
`.\scripts\godot.ps1 -Tour [-Snapshot]` (lisibilité de l'interface à 4 tailles de fenêtre ; `-Snapshot` écrit des PNG
dans `%TEMP%\gmix_imgs\ui_tour`, version à fenêtre de Godot) et `.\scripts\godot.ps1 -Flow [-NoLlm]` (parcours
formateur de bout en bout ; `-NoLlm` sans Ollama). Si un nettoyage échoue :
`backend\.venv\Scripts\python -m gmix.tools.ui_accounts cleanup <ids>`.

Qualité des dialogues des agents : `backend\.venv\Scripts\python -m gmix.tools.eval_dialogue` depuis `backend\`
(Ollama et PostgreSQL démarrés), rapports dans `ai/evals/results/` (voir ai/evals/README.md).

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
| `backend/gmix/` | API, génération et moteur des simulations, agents PNJ, messagerie Kafka, couche IA, RAG |
| `ai/` | contenu des simulations, catalogue de modèles et de tâches, domaines, prompts, assets, évaluations |
| `knowledge/` | corpus de documents sourcés pour le RAG |
| `infra/`, `docker-compose.yml` | infrastructure locale |
| `docs/` | architecture, IA, Kafka, rôles, game design, décisions, blocages |
| `.claude/agents/` | agents Claude Code spécialisés (voir CLAUDE.md) |
