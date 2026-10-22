# Rôles et droits

| Action | Joueur | Formateur | Admin |
|---|:-:|:-:|:-:|
| Rejoindre un lobby avec un code, jouer, parler aux PNJ | oui | observer | oui |
| Voir ses propres résultats et son débrief | oui | - | oui |
| Créer, configurer, générer un business game et son lobby | - | ses lobbies | tous |
| Relire, modifier, régénérer une section d'une spec | - | ses specs | toutes |
| Lancer, mettre en pause, clore une partie ; voir les résultats de ses joueurs | - | ses lobbies | tous |
| Proposer des documents pour le corpus RAG | - | oui | oui |
| Valider le corpus, gérer domaines, assets et modèles IA | - | - | oui |
| Gérer les comptes et les rôles, consulter l'audit | - | - | oui |

Règles d'implémentation (agent backend-api) :
- Rôle porté par `users.role` (`player`, `trainer`, `admin`) et vérifié sur chaque endpoint par une
  dépendance FastAPI ; la propriété (« ses lobbies ») est vérifiée en base, pas déduite du client.
- Toute action formateur ou admin qui modifie des données publie un événement sur `gmix.audit`.
- Le client Godot masque les menus selon le rôle, mais seule l'API fait foi.

Comptes : identifiant + mot de passe gérés par l'application (docs/decisions/0004-comptes-locaux.md).
Le premier admin est créé en ligne de commande, l'admin crée les formateurs, chaque formateur crée les comptes
de ses joueurs. Pas d'inscription libre en v1.

## Implémentation (backend/gmix/api)

| Endpoints | Qui |
|---|---|
| `POST /api/v1/auth/login`, `GET /auth/me`, `POST /auth/password` | tout compte actif |
| `POST/GET /api/v1/users` | formateur (crée des joueurs, voit les siens), admin (tout) |
| `POST /api/v1/games`, `POST /games/import`, `GET /games`, `GET/PUT /games/{id}(/spec)` | formateur (ses business games), admin |
| `POST /api/v1/lobbies`, `/{id}/start`, `/{id}/advance` | formateur du lobby, admin |
| `POST /lobbies/join`, `PUT /{id}/role`, `POST /{id}/decisions`, `/{id}/npcs/{npc}/talk`, `/{id}/presence` | membres ; le formateur peut décider pour une équipe |
| `GET /api/v1/lobbies`, `/{id}`, `/{id}/debrief` | membres, formateur, admin ; débrief joueur en fin de partie seulement |
| `WebSocket /ws` (en-tête `Authorization: Bearer`), `POST /system/ping` | tout compte / formateur et admin |

- Un lobby d'un autre formateur répond 404 (pas d'énumération) ; un joueur ne reçoit jamais les effets des
  options ni le débrief avant la fin (`engine.player_spec`).
- Mots de passe scrypt, jeton d'accès de 8 h, 5 essais de connexion par identifiant et adresse en 5 min.
- Premier admin : `backend\.venv\Scripts\python -m gmix.tools.create_user --username admin --role admin`.
