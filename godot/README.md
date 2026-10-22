# Client Godot 4.7

Éditeur : `.\scripts\godot.ps1` · vérification headless : `.\scripts\godot.ps1 -Check` ·
liaison avec le backend : `.\scripts\smoke.ps1` (compte jetable) · jeu : `.\scripts\godot.ps1 -Run`.

## Parcours

Connexion (adresse du serveur, identifiant, mot de passe ; mot de passe provisoire à changer) -> accueil selon
le rôle -> salle du lobby -> monde 3D. Joueur : rejoindre avec le code, choisir son rôle, explorer, parler aux
PNJ (E), décider (Tab), suivre les KPI, lire le débrief. Formateur : générer ou importer un business game, le
relire (avertissements, réparations, sources), l'exporter ou le remplacer par un fichier JSON, créer le lobby,
donner le code, lancer, passer les phases, décider pour une équipe, débrief ; créer les comptes joueurs.

## Arborescence

| Dossier | Contenu |
|---|---|
| `autoload/` | AppConfig (serveur), EventBus (signaux), Api (HTTP + jeton), Realtime (WebSocket authentifié, reconnexion), Session (lobby ouvert, dialogues), Presence (multijoueur ENet, serveur et client) |
| `config/client.cfg` | adresses par défaut, surchargées par `user://client.cfg` (le serveur choisi à la connexion y est gardé) |
| `scenes/main/` | scène principale : coquille, connexion, accueil joueur / formateur / admin |
| `scenes/lobby/` | salle du lobby : rôle, participants, pilotage de la partie |
| `scenes/world/` | monde 3D construit depuis le gabarit de carte et la spec : joueur, PNJ, autres joueurs, HUD |
| `scenes/common/` | Ui (constructeurs d'interface), GameText (KPI, phase, débrief, spec en BBCode) |
| `scenes/boot/` | écran de diagnostic (`-- --smoke` en headless) |
| `assets/<catégorie>/<id>/<id>.tscn` | 59 assets du catalogue ai/assets.yaml (52 importés, 7 procéduraux) |
| `assets/_sources/<pack>/` | modèles GLB d'origine, textures et licence de chaque pack (CC0) |
| `assets/procedural/` | assets fabriqués en code : palette, rack, stock au sol, chariot, écran KPI, assemblages |
| `assets/catalog.json`, `assets/CREDITS.md` | générés depuis ai/assets.yaml (`.\scripts\assets.ps1`) |
| `scenes/tools/asset_gallery/` | galerie de tous les assets par catégorie (captures : `.\scripts\assets.ps1 -Gallery <dossier>`) |
| `tools/` | outillage : check_project.gd (`-Check`), build_asset_scenes.gd (construction des scènes d'assets) |
| `tests/` | tests GDScript (cadre à choisir : GUT ou gdUnit4) |

## Conventions

- GDScript statiquement typé ; fichiers et variables en snake_case, classes en PascalCase,
  signaux au passé (`lobby_joined`).
- Une scène est autonome : elle n'appelle que les autoloads et ses enfants ; entre scènes, des signaux.
- Les données de jeu viennent de la spec JSON fournie par l'API (ai/schemas/business_game.schema.json),
  jamais en dur.
- Input Map par touches physiques : `move_forward/back/left/right` (WASD en QWERTY = ZQSD en AZERTY),
  `jump`, `sprint`, `interact`, `toggle_menu`.
- Rendu Forward+, cible 60 FPS ; la VRAM (6 Go) est partagée avec Ollama.
- Fichiers `.uid` versionnés (Godot 4.4 et plus).
- Assets : 1 unité = 1 m, origine au sol au centre, avant vers +Z. Racine `GmixAsset` (assets/asset.gd) :
  les variantes du catalogue sont des propriétés (`sign_text`, `fill_level`, `fork_height`, `animation`…).
  Personnages : animations idle, walk, sprint, sit, drive, pick-up, emote-yes (assets/character.gd).
- Export : ajouter `*.cfg` aux fichiers non-ressources exportés (config/client.cfg).
- Interfaces construites en code (pas de .tscn d'interface) ; tout texte venant de l'API ou de l'IA passe par
  `GameText.esc()` avant un RichTextLabel.
- Serveur de partie : même projet lancé par l'API en headless (`-- --server --lobby=… --port=…`, secret dans
  GMIX_JWT_SECRET) ; sonde : `-- --presence-probe --host=… --port=… --ticket=…`.
