# Pipeline Kafka

Kafka 4.3.1 en mode KRaft (sans ZooKeeper), un nœud. Hôte : `localhost:9092` ; conteneurs : `kafka:29092`.
Création automatique de topics désactivée : la liste fait foi dans `backend/gmix/messaging/topics.py` et
`python -m gmix.bootstrap` crée ceux qui manquent. Console : `.\scripts\infra.ps1 tools` puis http://localhost:8085.

## Topics

| Topic | Partitions | Rétention | Contenu |
|---|---|---|---|
| gmix.system.ping / gmix.system.pong | 1 | 1 h | diagnostic de bout en bout |
| gmix.generation.commands | 3 | 7 j | demandes de génération ou de régénération d'une section |
| gmix.generation.events | 3 | 7 j | progression et résultat (relayés au formateur par WebSocket) |
| gmix.game.events | 3 | 30 j | décisions des joueurs, aléas, évolution des KPI |
| gmix.npc.transcripts | 3 | 30 j | dialogues PNJ terminés (évaluation, débrief) |
| gmix.rag.commands / gmix.rag.events | 1 | 7 j | ingestion de documents |
| gmix.audit | 1 | 90 j | actions formateur et admin |
| gmix.dlq | 1 | 30 j | messages en échec avec l'erreur |

## Enveloppe (`gmix.messaging.envelope.Envelope`)

`id`, `type` (ex. `generation.stage_completed`), `version`, `occurred_at`, `source`, `correlation_id`
(toute la chaîne), `causation_id` (message déclencheur), `actor` {user_id, role}, `lobby_id`, `client_id`
(session WebSocket à notifier), `payload`. Une réponse se construit avec `event.reply(type, source, payload)`.
Côté client, le format reçu est `{type, payload, meta}`.

## Événements en service

| Type | Topic | Émetteur -> destinataire | Payload |
|---|---|---|---|
| `generation.requested` | generation.commands | API -> worker-generation | job_id, game_id ; `client_id` = id du formateur |
| `generation.progress` | generation.events | worker -> WebSocket du formateur | job_id, game_id, stage, progress (0-100) |
| `generation.completed` / `generation.failed` | generation.events | idem | title, warnings, repairs / error, refused |
| `lobby.state` | game.events | API -> WebSocket des membres du lobby | lobby_status, state (état public), action {type, by…} |
| `lobby.members` | game.events | idem | members [{user_id, display_name, game_role}] |
| `npc.exchange` | npc.transcripts | API (non relayé) | npc_id, message, reply, intent, sources |
| `account.created`, `game.spec_saved`, `lobby.created` | audit | API | ids et rôle de l'auteur |

Les décisions sont appliquées par l'API sous verrou de ligne (`gmix.game.engine`, fonctions pures) : la
réponse HTTP porte le nouvel état, `lobby.state` le diffuse aux autres membres. Kafka indisponible : l'action
est enregistrée quand même et les clients se resynchronisent par `GET /api/v1/lobbies/{id}`.
Le worker de génération traite un job à la fois (`max_poll_interval_ms` porté à 45 min) ; un message relivré
après un plantage relance le job, un job déjà terminé est ignoré.

## Conventions

- Clé de partition : `lobby_id`, sinon `correlation_id` (ordre garanti pour une partie ou une génération).
- Producteur idempotent, `acks=all`. Consommateurs : commit manuel après traitement (au moins une fois),
  handlers idempotents, erreur -> `gmix.dlq` puis commit (pas de blocage sur un message empoisonné).
- Groupes : un par type de worker (`worker-system`, `worker-generation`…). Le relais WebSocket de l'API
  consomme sans groupe : chaque instance reçoit tout et ne notifie que ses propres clients.
- Le temps réel 3D ne passe pas par Kafka (voir docs/decisions/0002-kafka-hors-temps-reel.md).
