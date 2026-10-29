# Client Godot 4.7

Éditeur : `.\scripts\godot.ps1` · vérification headless : `.\scripts\godot.ps1 -Check` ·
liaison avec le backend : `.\scripts\smoke.ps1` (compte jetable) · jeu : `.\scripts\godot.ps1 -Run` ·
contrôles du client : `.\scripts\godot.ps1 -Tour [-Snapshot]` et `.\scripts\godot.ps1 -Flow [-NoLlm]`
(voir « Contrôles du client »).

## Parcours

Connexion (adresse du serveur, identifiant, mot de passe ; mot de passe provisoire à changer) -> accueil selon
le rôle -> salle du lobby -> monde 3D. Joueur : rejoindre avec le code, choisir son rôle, explorer l'atelier
(vue Sims par défaut), parler aux PNJ (E ou clic), décider aux postes (E ou clic), suivre les KPI (Tab : tableau
de bord), lire le débrief. Formateur : générer un business game par paramètres ou importer une spec JSON, le relire
(partie de référence en pilote automatique, modules, agents, aléas, notions et sources), l'exporter ou le
remplacer par un fichier JSON, créer le lobby, donner le code, lancer, simuler les semaines, agir sur tous les
modules, débrief ; créer les comptes joueurs.

## Arborescence

| Dossier | Contenu |
|---|---|
| `autoload/` | AppConfig (serveur), EventBus (signaux), Api (HTTP + jeton), Realtime (WebSocket authentifié, reconnexion), Session (lobby ouvert tenu à jour par le WebSocket ; pose le thème commun sur la fenêtre), Presence (multijoueur ENet, serveur et client) |
| `config/client.cfg` | adresses par défaut, surchargées par `user://client.cfg` (le serveur choisi à la connexion y est gardé) |
| `scenes/main/` | scène principale : coquille, connexion, accueil joueur / formateur / admin |
| `scenes/lobby/` | salle du lobby : rôle, participants, pilotage de la partie |
| `scenes/world/` | monde 3D construit depuis `spec.world` (plan généré par `gmix.game.generation`) : `world.gd` (`GmixWorld`), `sims_view.gd` (`GmixSimsView`), `player.gd`, `npc.gd`, `remote_avatar.gd`, `hud.gd` |
| `scenes/common/` | Ui (thème et constructeurs d'interface), GameText (KPI, phase, débrief, spec en BBCode) |
| `scenes/boot/` | écran de diagnostic (`-- --smoke` en headless) |
| `scenes/tools/` | outils de contrôle : `ui_tour`, `flow_test`, `world_preview`, `asset_gallery` (voir plus bas) |
| `assets/<catégorie>/<id>/<id>.tscn` | 61 assets du catalogue ai/assets.yaml (52 importés, 9 procéduraux), au 2026-10-28 |
| `assets/_sources/<pack>/` | modèles GLB d'origine, textures et licence de chaque pack (CC0) |
| `assets/procedural/` | assets fabriqués en code : palette, rayonnage, stock au sol, chariot, écran KPI, ligne de production, bureau de chantier, assemblages |
| `assets/catalog.json`, `assets/CREDITS.md` | générés depuis ai/assets.yaml (`.\scripts\assets.ps1`) |
| `tools/` | outillage : check_project.gd (`-Check` : charge tous les scripts et scènes, vérifie la fenêtre de référence), build_asset_scenes.gd (construction des scènes d'assets) |
| `tests/` | vide (`.gitkeep`) : pas de cadre de tests unitaires GDScript ; les contrôles scriptés sont dans `scenes/tools/` |

## Conventions

- GDScript statiquement typé ; fichiers et variables en snake_case, classes en PascalCase,
  signaux au passé (`lobby_joined`).
- Une scène est autonome : elle n'appelle que les autoloads et ses enfants ; entre scènes, des signaux.
- Les données de jeu viennent de la spec et de l'état public fournis par l'API (modèle
  backend/gmix/game/spec.py), jamais en dur ; le client ne calcule aucune règle.
- Input Map par touches physiques (table « Commandes ») : `move_forward/back/left/right` (WASD en QWERTY = ZQSD
  en AZERTY), jamais de keycode en dur.
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

## Interface

- Fenêtre de référence 1280x720 (project.godot : taille de base, étirement `canvas_items`, aspect `expand`) : la
  zone visible fait toujours au moins 1280x720. `-Check` échoue si ces réglages changent.
- Thème commun `Ui.make_theme()`, posé sur la fenêtre par l'autoload Session. Constructeurs de `scenes/common/ui.gd` :
  `Ui.label` (police jamais sous 15 px, corps 18 px), `Ui.select` (liste dont la largeur ne dépend pas du plus long
  choix), `Ui.flow` (rangée de boutons qui passe à la ligne), `Ui.confirm`, `Ui.show_text` (fenêtre de lecture qui
  défile), `Ui.ask_text`, et `button`, `field`, `rich`, `scroll_list`, `screen_margin`.
- Règles : tout contenu long dans un ScrollContainer, textes à retour automatique, aucune largeur fixe supérieure à
  la zone visible, fenêtres modales dimensionnées sur le viewport.
- **Piège du thème** : il ne traverse ni un simple `Node` ni une `CanvasLayer`. Un outil d'interface doit être un
  `Control` (ui_tour l'est) ; le HUD, une `CanvasLayer`, pose le thème explicitement sur sa racine.

## Monde 3D : deux vues

Vue Sims par défaut, troisième personne avec `toggle_view`. `GmixWorld` (`world.gd`) expose aux outils de contrôle
`view()`, `is_navigation_ready()`, `sims_view()` et `screen_point()`.

| Action (Input Map) | Touche ou bouton | Effet |
|---|---|---|
| `move_forward/back/left/right` | W, S, A, D physiques (ZQSD en AZERTY) | vue Sims : déplace la caméra et la rend libre ; troisième personne : déplace le joueur |
| `jump` | Espace | saute (troisième personne seulement) |
| `sprint` | Maj | court, y compris pendant une marche ordonnée par un clic |
| `interact` | E | parle à l'agent ou ouvre le poste le plus proche, dans les deux vues |
| `toggle_menu` | Échap | menu (ferme d'abord le menu contextuel) |
| `toggle_view` | V | bascule vue Sims et troisième personne |
| `camera_follow` | C | rattache la caméra Sims au joueur |
| `camera_rotate_left/right` | flèche gauche, flèche droite | tourne la caméra Sims |
| `camera_zoom_in` | molette vers l'avant, flèche haut, Page haut | rapproche la caméra Sims |
| `camera_zoom_out` | molette vers l'arrière, flèche bas, Page bas | éloigne la caméra Sims |
| `world_click` | clic gauche | vue Sims : marcher (sol) ou menu contextuel (agent, poste) |
| `camera_drag` | clic droit ou clic milieu + glisser | tourne et incline la caméra Sims |
| (hors Input Map) | Tab | tableau de bord (`KEY_TAB` codé dans `world.gd`) |

- Vue Sims : caméra 3/4 suivie ou libre, survol surligné avec info-bulle, menu contextuel (« Parler à… »,
  « S'approcher », « Utiliser le poste », « S'y rendre »), toit retiré et murs côté caméra abaissés.
- Troisième personne : la souris est capturée tant qu'aucun panneau n'est ouvert.
- Navigation : maillage cuit à l'exécution (tâche de fond) depuis les collisions du plan généré, couches 1 (décor)
  et 16. Une destination à plus de 2,5 m du maillage est refusée avec une annonce. Maillage vide : retour à la
  troisième personne avec une annonce.
- Collisions : couche 1 décor, 4 agents (bloquent le joueur en troisième personne, pas en vue Sims), 8 boîtes de
  sélection des postes (sans effet physique), 16 emprises de secours. Un asset sans aucune collision reçoit une
  boîte à son emprise sur la couche 16 (bloque le joueur, compte dans le maillage, jamais la sélection au curseur ;
  ignoré sous 0,3 m de haut). Cinq assets sont concernés : `prop_kpi_screen`, `prop_desk_computer`,
  `prop_meeting_table`, `prop_pallet`, `prop_pallet_stack` (collision propre à fournir : assets-3d).
- Les agents patrouillent en ligne droite entre les points de leur route, sans maillage de navigation.

## Contrôles du client

Pas de GPU ni de fenêtre requis, sauf `-Snapshot`. Pour `-Tour` et `-Flow`, `scripts/godot.ps1` démarre l'API locale si
elle ne répond pas (et l'arrête ensuite), crée des comptes jetables (`uitour_…`, `flowtest_…`) avec
`gmix.tools.ui_accounts`, passe leurs jetons à Godot par variables d'environnement, puis supprime comptes, lobbies et
parties en base, même en cas d'échec. Le code de sortie est celui de Godot (0 = OK). Pas de `-Api` (écriture dans la
base locale), `-Tour` et `-Flow` ne se combinent pas.

| Outil | Lancement | Contrôle |
|---|---|---|
| `ui_tour` | `.\scripts\godot.ps1 -Tour [-Snapshot]` | lisibilité des écrans avant-jeu (connexion, diagnostic, accueils, salle du lobby, fenêtres) et des panneaux du HUD à 4 tailles de fenêtre (1280x720, 1366x768, 1920x1080, 1024x600) : dépassements, polices sous 15 px, textes tronqués, erreurs de script. `-Snapshot` (version à fenêtre, GPU requis, avec `-Tour` seulement) écrit les PNG dans `%TEMP%\gmix_imgs\ui_tour`. Crée deux business games et douze lobbies, supprimés ensuite. Aucun appel à Ollama. |
| `flow_test` | `.\scripts\godot.ps1 -Flow [-NoLlm]` | parcours A, formateur de bout en bout (génération, relecture, import, lobby, lancement, monde, vue Sims, postes, dialogues avec chaque agent et mémoire, semaines, débrief). `-NoLlm` (`--no-llm`) saute les dialogues, donc tout appel à Ollama. La présence ENet est remplacée par une doublure inerte. **Seul le parcours A existe** : B (joueurs) et V sont annoncés (`--only=A,B,V`) mais non écrits. |
| `world_preview` | exécutable Godot à fenêtre, `res://scenes/tools/world_preview/world_preview.tscn -- --api=… --lobby=<id> --snapshot=<dossier>` (jeton dans `GMIX_TOKEN`) | captures de l'atelier, de la vue Sims, de la troisième personne et fréquence d'images |
| `asset_gallery` | `.\scripts\assets.ps1 -Gallery <dossier>` | galerie de tous les assets par catégorie |

Si le nettoyage échoue, le script affiche les identifiants à nettoyer :
`backend\.venv\Scripts\python -m gmix.tools.ui_accounts cleanup <ids>`.

Limites connues (clic réel, clavier AZERTY réel, pavé tactile non éprouvés ; outils non suivis par git) :
docs/blocages.md.
