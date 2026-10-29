extends Node
## Parcours scripté de bout en bout (headless) : génération par paramètres -> lobby -> partie -> agents -> semaines
## -> débrief, en pilotant les vrais écrans (main.gd, home_screen, lobby_screen, world + HUD) comme le ferait un
## utilisateur : cases à cocher, listes, boutons, boîtes de dialogue. Chaque étape vérifie l'interface ET l'API.
##   Godot_console.exe --headless --path godot res://scenes/tools/flow_test/flow_test.tscn -- --api=http://127.0.0.1:8000
##       [--only=A,B,V] [--no-llm : saute les dialogues avec les agents (A.8), donc tout appel à Ollama]
## Jetons de comptes jetables dans l'environnement : GMIX_FLOW_TRAINER_TOKEN, GMIX_FLOW_PLAYER_TOKEN,
## GMIX_FLOW_PLAYER2_TOKEN (scripts\godot.ps1 -Flow les crée et les supprime). Code de sortie 0 si tout passe.
## La présence ENet (autoload Presence) n'est pas l'objet : elle est remplacée par une doublure inerte.

const MAIN := "res://scenes/main/main.tscn"
const WORLD := "res://scenes/world/world.tscn"
const HOME_SCRIPT := "res://scenes/main/home_screen.gd"
const LOBBY_SCRIPT := "res://scenes/lobby/lobby_screen.gd"
const WAIT_S := 20.0  # attente par défaut d'une condition (réseau local, Kafka)
const WS_WAIT_S := 45.0  # relais Kafka -> WebSocket
const TALK_WAIT_S := 120.0  # réponse d'un agent : le modèle de dialogue peut devoir se charger
const COMPANY := "Maison [QA] [b]Test[/b]"  # crochets volontaires : le texte de l'API doit être échappé
const STAND_IN := "prop_scene_absente_test"  # id d'asset qu'aucun catalogue ne contient (monde d'exemple)
const MESSAGE := "Bonjour, peux-tu me résumer la situation de la semaine ?"
## Paramètres du parcours formateur : tous différents des valeurs par défaut du formulaire (sauf les produits, dont la
## valeur par défaut est aussi la plus courante) ; transport et finance décochés pour couvrir les postes sans module.
const MAIN_PARAMS := {
	"theme": "agroalimentaire",
	"modules": ["approvisionnement", "production", "maintenance", "qualite", "commercial"],
	"agents": ["client", "fournisseur", "direction"],
	"tone": "exigeant",
	"difficulty": "expert",
	"events": "frequents",
	"weeks": 5,
	"products": 3,
	"company": COMPANY,
	"players": [2, 6],
}

## Parcours `--pack=usine` (ADR 0007) : pack usine choisi dans le formulaire, ses options (nombre de lignes) non par défaut ;
## jusqu'à l'entrée dans le monde (rejeu, postes et semaines : mission suivante, avec la génération du pack côté serveur).
const USINE_PARAMS := {
	"pack": "usine",
	"theme": "automobile",
	"modules": ["pilotage", "production", "maintenance"],
	"agents": [],
	"tone": "exigeant",
	"difficulty": "expert",
	"events": "frequents",
	"weeks": 5,
	"products": 1,
	"options": {"lines": 3},
	"company": COMPANY,
	"players": [2, 6],
}

## Intercepte les erreurs du moteur et des scripts (SCRIPT ERROR, ERROR:) pour les attribuer à l'étape en cours.
class ErrorCatcher:
	extends Logger

	var _mutex := Mutex.new()
	var _entries: Array[String] = []

	func _log_error(
		function: String, file: String, line: int, code: String, rationale: String,
		_editor_notify: bool, error_type: int, _backtraces: Array[ScriptBacktrace]
	) -> void:
		if error_type == ERROR_TYPE_WARNING:
			return
		_mutex.lock()
		_entries.append("%s:%d (%s) %s %s" % [file, line, function, code, rationale])
		_mutex.unlock()

	func take() -> Array[String]:
		_mutex.lock()
		var out := _entries.duplicate()
		_entries.clear()
		_mutex.unlock()
		return out


var _only: PackedStringArray = []
var _pack := "atelier"  # --pack=usine : parcours du pack usine
var _catcher := ErrorCatcher.new()
var _checks := 0
var _failures: Array[String] = []
var _step := ""
var _done := false
var _ws_states := 0  # messages lobby.state reçus par le WebSocket
var _ws_members := 0
var _trainer := ""
var _player := ""
var _player2 := ""
var _accepted := 0  # actions acceptées par l'API dans le lobby du parcours formateur (journal complet du débrief)


func _ready() -> void:
	if get_tree().current_scene == self:
		# Lancé comme scène principale : le jeu change de scène (main.gd, monde) et détruirait ce nœud.
		# Une seconde instance, sous la racine, pilote le jeu pendant ce temps.
		var runner: Node = (get_script() as GDScript).new()
		runner.name = "FlowRunner"
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


# --- déroulement ----------------------------------------------------------------------------------------------


func _run() -> void:
	var args := _arguments()
	_only = str(args.get("only", "A,B,V")).split(",")
	_pack = str(args.get("pack", "atelier"))
	OS.add_logger(_catcher)
	get_window().size = Vector2i(1280, 720)  # sans fenêtre, la taille serait 64 x 64 : la zone visible et les rayons du curseur divergeraient
	_stub_presence()
	Realtime.message_received.connect(_on_ws_message)
	var watchdog := get_tree().create_timer(float(args.get("timeout", "1500")))
	watchdog.timeout.connect(func() -> void: _finish("délai global dépassé pendant : " + _step))
	print("FLOW api=%s parcours=%s pack=%s" % [AppConfig.api_base_url, ",".join(_only), _pack])
	if args.has("fixture"):  # monde construit depuis les fichiers d'exemple (scenes/tools/fixtures), sans API
		await _fixture_world(str(args["fixture"]))
		_finish("")
		return

	_begin("0", "Prérequis : API joignable, jetons des comptes jetables")
	var health: Dictionary = await Api.get_json("/health")
	_check(health["ok"], "GET /health répond", str(health["error"]))
	_trainer = OS.get_environment("GMIX_FLOW_TRAINER_TOKEN")
	_player = OS.get_environment("GMIX_FLOW_PLAYER_TOKEN")
	_player2 = OS.get_environment("GMIX_FLOW_PLAYER2_TOKEN")
	_check(not _trainer.is_empty(), "jeton formateur fourni")
	_check(not _player.is_empty() and not _player2.is_empty() or not ("B" in _only), "jetons joueurs fournis")
	if _failures.is_empty() and "A" in _only:
		await _trainer_journey()
	_finish("")


func _finish(reason: String) -> void:
	if _done:
		return
	_done = true
	_end_step()
	if not reason.is_empty():
		_failures.append(reason)
	print("FLOW %s : %d vérification(s), %d échec(s)" % ["OK" if _failures.is_empty() else "KO", _checks, _failures.size()])
	for failure in _failures:
		print("FLOW ECHEC %s" % failure)
	get_tree().quit(0 if _failures.is_empty() else 1)


# --- monde d'exemple (sans API) ----------------------------------------------------------------------------------


## `--fixture=usine` : construit le monde depuis scenes/tools/fixtures/<pack>_spec.json et <pack>_state.json (annexe de l'ADR
## 0007) et contrôle le monde, les figurants et la marche des agents sur le maillage de navigation. Aucun appel réseau.
func _fixture_world(pack: String) -> void:
	_begin("F.1", "Monde %s construit depuis les fichiers d'exemple (sans API)" % pack)
	var loaded := {}
	for kind in ["spec", "state"]:
		var path := "res://scenes/tools/fixtures/%s_%s.json" % [pack, kind]
		var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if not _check(data is Dictionary, "fichier d'exemple lisible : %s" % path):
			return
		loaded[kind] = data
	# Un asset inconnu du catalogue Godot (scène pas encore fabriquée) : le monde doit afficher un volume neutre.
	(loaded["spec"]["world"]["objects"] as Array).append({"asset": STAND_IN, "position": [-6.0, -12.5], "rotation": 0, "label": "Étagère à bacs : scène absente", "ref": null})
	Session.open({"id": "fixture-%s" % pack, "name": "Exemple", "status": "running", "join_code": "EXEMPLE", "is_manager": true, "my_role": null, "members": [], "spec": loaded["spec"], "state": loaded["state"]})
	var world := (load(WORLD) as PackedScene).instantiate() as GmixWorld
	get_tree().root.add_child(world)
	await _frames(3)
	var stand_in: Variant = (world.get("_placed") as Array).filter(func(entry: Dictionary) -> bool: return entry["asset"] == STAND_IN)
	if _check(not (stand_in as Array).is_empty(), "asset sans scène : l'objet est quand même posé (volume neutre)"):
		var volume := ((stand_in as Array)[0]["node"] as Node3D).find_children("*", "MeshInstance3D", true, false)
		_check(not volume.is_empty() and (volume[0] as MeshInstance3D).mesh is BoxMesh, "asset sans scène : un volume plein à la place")
	_check(await _until(func() -> bool: return world.is_navigation_ready(), 60.0) != null, "le maillage de navigation est cuit")
	await _check_world(world)
	var checked := 0
	for npc: GmixNpc in (world.get("_agents") as Array) + (world.get("_crew") as Array):
		if npc.activity == "deplacement":  # marche entre les points de sa route : il bouge et reste sur le maillage
			var start := npc.position
			await get_tree().create_timer(4.0).timeout
			_check(npc.position.distance_to(start) > 1.0, "%s en déplacement : il marche (%.1f m en 4 s)" % [npc.data["id"], npc.position.distance_to(start)])
			var map := world.get_world_3d().navigation_map
			var snapped := NavigationServer3D.map_get_closest_point(map, npc.position)
			_check(Vector2(snapped.x - npc.position.x, snapped.z - npc.position.z).length() < 0.4, "%s : sur le maillage de navigation (%.2f m d'écart)" % [npc.data["id"], Vector2(snapped.x - npc.position.x, snapped.z - npc.position.z).length()])
			checked += 1
	_check(checked > 0, "au moins un agent en déplacement dans l'état d'exemple")
	var absent: Array = (world.get("_agents") as Array).filter(func(npc: GmixNpc) -> bool: return npc.activity == "absent")
	for npc: GmixNpc in absent:
		_check(not (npc.get_child(0) as Node3D).visible, "%s absent : son modèle est masqué" % npc.data["id"])
	world.queue_free()


# --- parcours A : formateur ----------------------------------------------------------------------------------


func _trainer_journey() -> void:
	_begin("A.1", "Formateur : connexion, écran d'accueil, formulaire de génération")
	if not await _sign_in(_trainer):
		return
	var home := await _wait_screen(HOME_SCRIPT)
	if not _check(home != null, "l'écran d'accueil s'affiche après la connexion"):
		return
	if not await _check_home_form(home):
		return

	_begin("A.1b", "Choix du pack de jeu dans le formulaire (GET /games/options, packs[])")
	await _check_pack_choice(home)

	var params: Dictionary = USINE_PARAMS if _pack == "usine" else MAIN_PARAMS
	_begin("A.2", "Génération par paramètres non par défaut (pack %s)" % _pack)
	var game := await _generate(home, params)
	if game.is_empty():
		return

	_begin("A.3", "Relecture du business game (« Relire »)")
	await _read_game(home, game, params)
	await _import_and_replace(home, game)

	_begin("A.4", "Création du lobby depuis la liste")
	var lobby := await _create_lobby_from_list(home, game)
	if lobby == null:
		return

	_begin("A.5", "Salle du lobby : formateur, lancement de la partie")
	if not await _lobby_waiting_then_start(lobby, game):
		return

	_begin("A.6", "Monde 3D : construction depuis la spec")
	var world := await _enter_world(lobby)
	if world == null:
		return
	await _check_world(world)
	if _pack == "usine":
		print("  fin du parcours usine : vue Sims, postes, semaines et rejeu sont l'objet de la mission suivante")
		return

	_begin("A.6b", "Vue Sims par défaut : clic pour marcher, menu contextuel, caméra, bascule de vue")
	await _check_sims_view(world as GmixWorld)

	_begin("A.7", "Postes : panneaux et formulaires d'action avec leurs valeurs par défaut")
	await _visit_stations(world, true)

	_begin("A.8", "Dialogues avec chaque agent, puis mémoire au second dialogue")
	if _arguments().has("no-llm"):
		print("  ignoré (--no-llm) : aucun appel au modèle de langue")
	else:
		await _talk_to_agents(world, -1)

	_begin("A.9", "Touche d'interaction, tableau de bord, menu, débrief du formateur")
	await _interact_and_panels(world)

	_begin("A.10", "Une semaine simulée ailleurs arrive par le WebSocket")
	await _remote_advance_seen_by_hud(world)

	_begin("A.11", "Retour à la salle du lobby par le menu")
	var back := await _leave_world()
	if back == null:
		return

	_begin("A.12", "Semaines simulées depuis la salle du lobby jusqu'à la fin, débrief")
	await _play_to_the_end(back)

	_begin("A.13", "Retour à l'accueil : le lobby terminé figure dans la liste")
	await _back_home_lists_lobby()


# --- accueil et génération -------------------------------------------------------------------------------------


func _check_home_form(home: Control) -> bool:
	var loaded: Variant = await _until(
		func() -> Variant:
			var options: Variant = home.get("_options")
			return options if options is Dictionary and not (options as Dictionary).is_empty() else null
	)
	if not _check(loaded != null, "les options de génération sont chargées (GET /games/options)"):
		return false
	var options: Dictionary = loaded
	var raw := await _raw(_trainer, HTTPClient.METHOD_GET, "/api/v1/games/options")
	_check(raw["data"] == options, "les options affichées sont celles de l'API")
	for key in ["themes", "modules", "extra_agents", "tones", "difficulties", "events"]:
		_check(not (options[key] as Array).is_empty(), "options : « %s » non vide" % key)
	var themes := home.get("_theme_select") as OptionButton
	_check(themes.item_count == (options["themes"] as Array).size(), "liste des secteurs : %d choix" % themes.item_count)
	_check((home.get("_module_checks") as Array).size() == (options["modules"] as Array).size(), "une case par module")
	_check((home.get("_agent_checks") as Array).size() == (options["extra_agents"] as Array).size(), "une case par agent en plus")
	for pair: Array in (home.get("_module_checks") as Array) + (home.get("_agent_checks") as Array):
		_check((pair[1] as CheckBox).button_pressed, "case « %s » cochée au départ" % (pair[1] as CheckBox).text)
	var ranges: Dictionary = options["ranges"]
	var weeks := home.get("_weeks") as SpinBox
	var products := home.get("_products") as SpinBox
	_check(weeks.min_value == ranges["weeks"][0] and weeks.max_value == ranges["weeks"][1], "semaines : bornes de l'API")
	_check(int(weeks.value) == int(ranges["weeks"][2]), "semaines : valeur par défaut de l'API")
	_check(products.min_value == ranges["products"][0] and products.max_value == ranges["products"][1], "produits : bornes de l'API")
	var sector: Dictionary = (options["themes"] as Array)[themes.selected]
	var info := (home.get("_theme_info") as Label).text
	_check(info.contains(str(sector["description"])) and info.contains(str(sector["products"][0])), "description du secteur et ses produits")
	var status := home.get("_status") as Label
	_check(status.text.is_empty(), "aucun message d'erreur à l'ouverture", status.text)
	_check(await _until(func() -> bool: return Realtime.is_open()) != null, "le WebSocket s'ouvre après la connexion")

	var games := home.get("_games") as VBoxContainer
	var listed: Variant = await _until(func() -> bool: return not _children(games).is_empty())  # la liste arrive après les options
	_check(listed != null, "la liste des business games est affichée (même vide)")
	return true


## Choix du pack : format de `packs[]`, limites au format de `ranges`, un formulaire par pack avec ses options ; revient à l'atelier.
func _check_pack_choice(home: Control) -> void:
	var options: Dictionary = home.get("_options")
	var packs: Array = options.get("packs", [])
	if not _check(not packs.is_empty(), "options : « packs » non vide"):
		return
	_check(packs[0]["id"] == "atelier" and packs[0]["limits"] == options["ranges"], "le pack atelier vient en premier avec les limites de « ranges »")
	for pack: Dictionary in packs:
		var missing: Array[String] = []
		for key in ["id", "label", "description", "domain", "engine", "params", "themes", "modules", "extra_agents", "tones", "difficulties", "events", "limits"]:
			if not pack.has(key):
				missing.append(key)
		_check(missing.is_empty(), "pack %s : toutes les clés présentes" % pack["id"], ", ".join(missing))
		for key in ["weeks", "products"]:
			var bounds: Array = pack["limits"].get(key, [])
			_check(bounds.size() == 3 and bounds[0] <= bounds[2] and bounds[2] <= bounds[1], "pack %s : limites « %s » = [min, max, défaut]" % [pack["id"], key], str(bounds))
	if packs.size() < 2:
		return
	var select := home.get("_pack_select") as OptionButton
	_check(select != null and select.item_count == packs.size(), "liste « Type de jeu » : un choix par pack")
	for index in range(1, packs.size()):
		var pack: Dictionary = packs[index]
		await _select_pack(home, str(pack["id"]))
		var weeks := home.get("_weeks") as SpinBox
		var bounds: Array = pack["limits"]["weeks"]
		_check(weeks.min_value == bounds[0] and weeks.max_value == bounds[1] and int(weeks.value) == int(bounds[2]), "pack %s : semaines aux bornes du pack" % pack["id"])
		_check((home.get("_theme_select") as OptionButton).item_count == (pack["themes"] as Array).size(), "pack %s : ses secteurs" % pack["id"])
		_check((home.get("_module_checks") as Array).size() == (pack["modules"] as Array).size(), "pack %s : ses modules" % pack["id"])
		var controls: Dictionary = home.get("_option_controls")
		for option: Dictionary in pack["params"]:
			var shown := controls.has(option["id"])
			_check(shown, "pack %s : option « %s » dans le formulaire" % [pack["id"], option["label"]])
			if shown and option["type"] == "int":
				var spin := controls[option["id"]] as SpinBox
				_check(spin.min_value == option["min"] and spin.max_value == option["max"] and int(spin.value) == int(option["default"]), "option « %s » : bornes et valeur par défaut du pack" % option["id"])
		_check(controls.size() == (pack["params"] as Array).size(), "pack %s : aucune option en trop" % pack["id"])
	await _select_pack(home, "atelier")
	_check((home.get("_option_controls") as Dictionary).is_empty(), "retour à l'atelier : plus d'option de pack")


## Sélectionne un pack dans la liste « Type de jeu » (le formulaire se reconstruit à l'image suivante).
func _select_pack(home: Control, pack_id: String) -> void:
	var packs: Array = (home.get("_options") as Dictionary).get("packs", [])
	var index := _index_of(packs, pack_id)
	if packs.size() > 1 and int(home.get("_pack_index")) != index:
		_pick(home.get("_pack_select") as OptionButton, index)
		await _frames(3)


## Remplit le formulaire (cases, listes, nombres, nom) puis clique « Générer » ; renvoie le détail API du jeu créé.
func _generate(home: Control, params: Dictionary) -> Dictionary:
	await _select_pack(home, str(params.get("pack", "atelier")))
	_fill_form(home, params)
	var options: Dictionary = home.call("_current_pack")  # les choix du pack sélectionné (le pack atelier : les clés d'origine)
	var sector: Dictionary = (options["themes"] as Array)[_index_of(options["themes"], params["theme"])]
	var info := (home.get("_theme_info") as Label).text
	_check(info.contains(str(sector["description"])), "le choix du secteur met à jour sa description")
	var status := home.get("_status") as Label
	var button := home.get("_generate_button") as Button
	status.text = ""
	if not _click(button, "bouton « Générer »"):
		return {}
	_check(button.disabled, "le bouton est désactivé pendant la génération")
	var done: Variant = await _until(func() -> bool: return not button.disabled and not status.text.is_empty(), 60.0)
	if not _check(done != null, "la génération se termine"):
		return {}
	if not _check(status.text.begins_with("Business game prêt"), "message de succès", status.text):
		return {}
	var company: String = params.get("company", "")
	var title := "%s · %s" % [company, sector["label"]]
	var detail := await _find_game(_trainer, title)
	if not _check(not detail.is_empty(), "le jeu est dans GET /games", title):
		return {}
	title = str(detail["title"])
	var autopilot: Dictionary = detail["review"]["autopilot"]
	_check(status.text.contains("OTIF moyen %s %%" % GameText.number(autopilot["otif_mean"])), "le message affiche la partie de référence de l'API")
	_check(status.text.contains(GameText.money(autopilot["final_cash"])), "le message affiche la trésorerie finale de référence")
	var row: Variant = await _until(func() -> Variant: return _game_row(home, title))
	_check(row != null, "le jeu apparaît dans la liste", title)
	if row != null:
		var label := (row as Node).get_child(0) as Label
		_check(label.text.ends_with("[prêt]"), "état « prêt » affiché", label.text)
		_check(_button(row as Node, "Créer un lobby") != null, "bouton « Créer un lobby » sur un jeu prêt")
	_check_generated(detail, params)
	return detail


func _check_generated(detail: Dictionary, params: Dictionary) -> void:
	var spec: Dictionary = detail["spec"]
	var applied: Dictionary = spec["params"]
	_check(detail["status"] == "ready", "statut API « ready »")
	_check(applied["theme"] == params["theme"], "secteur envoyé : %s" % params["theme"])
	var modules: Array = params["modules"]
	var sent_modules: Array = applied["modules"]
	sent_modules.sort()
	var wanted: Array = modules.duplicate()
	wanted.sort()
	_check(sent_modules == wanted, "modules envoyés : %s" % ", ".join(wanted))
	var agents: Array = params["agents"]
	var sent_agents: Array = applied["extra_agents"]
	sent_agents.sort()
	var wanted_agents: Array = agents.duplicate()
	wanted_agents.sort()
	_check(sent_agents == wanted_agents, "agents en plus envoyés : %s" % ", ".join(wanted_agents))
	_check(applied["agent_tone"] == params["tone"], "caractère des agents : %s" % params["tone"])
	_check(applied["difficulty"] == params["difficulty"], "difficulté : %s" % params["difficulty"])
	_check(applied["events"] == params["events"], "aléas : %s" % params["events"])
	_check(int(applied["weeks"]) == int(params["weeks"]) and int(spec["meta"]["weeks"]) == int(params["weeks"]), "durée : %d semaines" % params["weeks"])
	_check(int(applied["products"]) == int(params["products"]) and (spec["products"] as Array).size() == int(params["products"]), "%d produits" % params["products"])
	_check((spec["modules"] as Array).size() == modules.size(), "%d modules dans la spec" % modules.size())
	if params.has("pack"):
		_check(applied["pack"] == params["pack"] and spec["meta"]["pack"] == params["pack"], "pack envoyé : %s" % params["pack"])
		for key: String in params.get("options", {}):
			_check(applied["options"].get(key) == params["options"][key], "option du pack « %s » : %s" % [key, params["options"][key]])
	if params.get("pack", "atelier") == "usine":  # un agent parlant par département (10) + les agents en plus, plus des figurants
		_check((spec["agents"] as Array).size() == 10 + agents.size(), "%d agents dans la spec (10 départements + en plus)" % (10 + agents.size()))
		_check((spec["factory"]["crew"] as Array).size() > 0 and spec["world"]["template"] == "usine", "spec usine : figurants et gabarit du monde")
		_check(int(spec["params"]["options"]["lines"]) == (spec["lines"] as Array).size(), "une ligne de la spec par ligne demandée")
	else:
		_check((spec["agents"] as Array).size() == modules.size() + agents.size(), "%d agents dans la spec (modules + en plus)" % (modules.size() + agents.size()))
	_check((spec["roles"] as Array).size() == modules.size(), "un rôle par module")
	_check(int(spec["meta"]["players"]["min"]) == int(params["players"][0]) and int(spec["meta"]["players"]["max"]) == int(params["players"][1]), "joueurs : %d à %d" % params["players"])
	var company: String = params.get("company", "")
	if not company.is_empty():
		_check(spec["meta"]["company"] == company, "nom de l'entreprise conservé tel quel")
	_check(detail["review"]["autopilot"] is Dictionary and not (detail["review"]["autopilot"] as Dictionary).is_empty(), "partie de référence en pilote automatique")


func _read_game(home: Control, game: Dictionary, params: Dictionary) -> void:
	var row: Variant = _game_row(home, str(game["title"]))
	if not _check(row != null, "ligne du jeu dans la liste"):
		return
	if not _click(_button(row as Node, "Relire"), "bouton « Relire »"):
		return
	var dialog: Variant = await _until(func() -> Variant: return _dialog(home))
	if not _check(dialog != null, "la fenêtre de relecture s'ouvre"):
		return
	var window := dialog as AcceptDialog
	_check(window.title == str(game["title"]), "titre de la fenêtre = titre du jeu")
	var text := _parsed(window)
	var spec: Dictionary = game["spec"]
	_check(not text.is_empty(), "le texte de relecture n'est pas vide")
	_check(text.contains(str(params.get("company", spec["meta"]["company"]))), "le nom de l'entreprise s'affiche tel quel, crochets compris")
	_check(text.contains("Partie de référence (pilote automatique)"), "partie de référence")
	_check(text.contains(str(spec["meta"]["pitch"]).left(40)), "contexte du jeu")
	for module: Dictionary in spec["modules"]:
		_check(text.contains(str(module["title"])), "module « %s » relu" % module["title"])
	for agent: Dictionary in spec["agents"]:
		_check(text.contains(str(agent["name"])) and text.contains(str(agent["personality"]["label"])), "agent « %s » relu" % agent["name"])
	for product: Dictionary in spec["products"]:
		_check(text.contains(str(product["name"])), "produit « %s » relu" % product["name"])
	for section in ["Objectifs", "Modules et rôles", "Agents", "Aléas possibles", "Notions et sources"]:
		_check(text.contains(section), "section « %s »" % section)
	var leak := _bbcode_leak(text, str(spec["meta"]["company"]))
	_check(leak.is_empty(), "aucune balise BBCode visible dans la relecture", leak)
	_check(_button(window, "Exporter la spec") != null and _button(window, "Remplacer par un fichier") != null, "actions d'export et de remplacement proposées")
	_close_dialog(window)
	await _frames(2)
	_check(_dialog(home) == null, "la fenêtre se ferme")


## Importer une spec exportée, puis la remplacer (mêmes appels que les boutons, sans boîte de fichier native).
func _import_and_replace(home: Control, game: Dictionary) -> void:
	var path := "user://flow_test_spec.json"
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(game["spec"], "  "))
	file.close()
	var status := home.get("_status") as Label
	status.text = ""
	await home.call("_send_spec", path, "/api/v1/games/import", false)
	_check(status.text.begins_with("Spec enregistrée"), "import d'une spec JSON", status.text)
	status.text = ""
	await home.call("_send_spec", path, "/api/v1/games/%s/spec" % game["id"], true)
	_check(status.text.begins_with("Spec enregistrée"), "remplacement de la spec d'un jeu existant", status.text)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	await _frames()
	var twins := 0
	for row in _children(home.get("_games") as Node):
		var label := row.get_child(0) as Label if row.get_child_count() > 0 else null
		if label != null and label.text.begins_with(str(game["title"]) + "  ["):
			twins += 1
	_check(twins == 2, "la liste montre le jeu et son import (%d lignes)" % twins)
	status.text = ""
	await home.call("_send_spec", "user://absent.json", "/api/v1/games/import", false)
	_check(not status.text.is_empty(), "un fichier illisible est signalé", status.text)


func _create_lobby_from_list(home: Control, game: Dictionary) -> Control:
	var row: Variant = _game_row(home, str(game["title"]))
	if not _check(row != null, "ligne du jeu dans la liste"):
		return null
	if not _click(_button(row as Node, "Créer un lobby"), "bouton « Créer un lobby »"):
		return null
	var dialog: Variant = await _until(func() -> Variant: return _dialog(home))
	if not _check(dialog != null, "la fenêtre « Nom du lobby » s'ouvre"):
		return null
	var window := dialog as ConfirmationDialog
	var edit := window.find_children("*", "LineEdit", true, false)[0] as LineEdit
	_check(edit.text.begins_with(str(game["title"])), "nom proposé : titre du jeu + date", edit.text)
	_check(edit.text.ends_with(Time.get_date_string_from_system()), "nom proposé : date du jour")
	edit.text = "QA flux %d" % (Time.get_ticks_msec() % 100000)
	var lobby_name := edit.text
	window.get_ok_button().pressed.emit()
	var screen := await _wait_screen(LOBBY_SCRIPT)
	if not _check(screen != null, "la salle du lobby s'affiche"):
		return null
	var view := Session.lobby
	_check(view.get("name") == lobby_name, "lobby créé avec le nom saisi", str(view.get("name")))
	_check(str(view.get("join_code", "")).length() == 6, "code d'accès à 6 caractères", str(view.get("join_code")))
	_check(view.get("is_manager") == true, "le formateur pilote son lobby")
	var server := await _raw(_trainer, HTTPClient.METHOD_GET, "/api/v1/lobbies/%s" % view["id"])
	_check(server["ok"] and server["data"]["spec"]["meta"]["title"] == game["title"], "le lobby porte la spec du jeu (GET /lobbies/{id})")
	return screen


func _lobby_waiting_then_start(lobby: Control, game: Dictionary) -> bool:
	var view := Session.lobby
	var spec := Session.spec()
	_check((lobby.get("_title") as Label).text.contains(str(view["name"])) and (lobby.get("_title") as Label).text.contains(str(game["title"])), "titre : lobby et business game")
	_check((lobby.get("_pitch") as Label).text == spec["meta"]["pitch"], "présentation du jeu")
	var code := lobby.get("_code") as Label
	_check(code.visible and code.text == "Code d'accès : %s" % view["join_code"], "code d'accès affiché au formateur", code.text)
	var week_text := _parsed(lobby.get("_week") as Node)
	_check(week_text.contains("En attente du lancement") and week_text.contains(str(spec["meta"]["company"])), "état : en attente du lancement", week_text)
	_check(_parsed(lobby.get("_kpis") as Node).contains("Trésorerie"), "indicateurs affichés")
	_check((lobby.get("_start_button") as Button).visible, "bouton « Lancer la partie » visible")
	_check(not (lobby.get("_advance_button") as Button).visible, "« Simuler la semaine » masqué avant le lancement")
	_check((lobby.get("_debrief_button") as Button).visible, "débrief ouvert au formateur")
	_check((lobby.get("_enter_button") as Button).text == "Observer l'atelier 3D", "le formateur observe l'atelier")
	_check(not (lobby.get("_role_box") as Control).visible, "pas de choix de rôle pour le formateur")
	_check(_texts(lobby.get("_members") as Node).any(func(t: String) -> bool: return t.contains("Personne pour l'instant")), "aucun participant au départ")

	var before := _ws_states
	_check(_click(lobby.get("_start_button") as Button, "bouton « Lancer la partie »"), "lancement demandé")
	var running: Variant = await _until(func() -> bool: return Session.state().get("status") == "running")
	if not _check(running != null, "la partie passe en cours"):
		return false
	var announced: Variant = await _until(func() -> bool: return (lobby.get("_status") as Label).text.begins_with("Partie lancée"))  # le WebSocket peut devancer la réponse HTTP
	_check(announced != null, "message de lancement", (lobby.get("_status") as Label).text)
	_check(not (lobby.get("_start_button") as Button).visible and (lobby.get("_advance_button") as Button).visible, "boutons : lancer masqué, simuler visible")
	_check((lobby.get("_advance_button") as Button).text == "Simuler la semaine 1", "libellé « Simuler la semaine 1 »", (lobby.get("_advance_button") as Button).text)
	_check(_parsed(lobby.get("_week") as Node).contains("Semaine 1 / %d" % int(spec["meta"]["weeks"])), "état : semaine 1 en cours")
	_check(await _until(func() -> bool: return _ws_states > before, WS_WAIT_S) != null, "le WebSocket relaie l'état (lobby.state)")
	var server := await _raw(_trainer, HTTPClient.METHOD_GET, "/api/v1/lobbies/%s" % view["id"])
	_check(server["data"]["state"]["status"] == "running" and server["data"]["status"] == "running", "API : lobby en cours")
	return true


# --- monde 3D --------------------------------------------------------------------------------------------------


func _enter_world(lobby: Control) -> Node:
	var old_id := get_tree().current_scene.get_instance_id()
	if not _click(lobby.get("_enter_button") as Button, "bouton « Observer l'atelier 3D »"):
		return null
	var world: Variant = await _until(
		func() -> Variant:
			var scene := get_tree().current_scene
			return scene if scene != null and scene.get_instance_id() != old_id and scene.scene_file_path == WORLD else null,
		60.0
	)
	await _frames(3)
	_check(world != null, "la scène du monde est chargée")
	return world as Node


func _hud_of(world: Node) -> GmixHud:
	return world.get("_hud") as GmixHud


func _check_world(world: Node) -> void:
	var spec := Session.spec()
	var hud := _hud_of(world)
	_check(hud != null, "le HUD est construit")
	var agents := world.get("_agents") as Array
	_check(agents.size() == (spec["agents"] as Array).size(), "un PNJ par agent de la spec (%d)" % agents.size())
	var refs := world.get("_refs") as Dictionary
	var factory := GmixFactoryState.is_factory(spec)
	var wanted: Array[String] = ["dock_in", "dock_out", "kpi"]
	if factory:  # usine : une machine et une table par machine, une zone par département, le quai et les stocks
		wanted = ["kpi", "dock", "pf"]
		for machine: Dictionary in spec["factory"]["machines"]:
			wanted.append("machine:" + str(machine["id"]))
			wanted.append("buffer:" + str(machine["id"]))
		for department: Dictionary in spec["departments"]:
			wanted.append("dept:" + str(department["id"]))
		for component: Dictionary in spec["components"]:
			wanted.append("mp:" + str(component["id"]))
	else:
		for product: Dictionary in spec["products"]:
			wanted.append("stock:" + str(product["id"]))
		for component: Dictionary in spec["components"]:
			wanted.append("component:" + str(component["id"]))
		for line: Dictionary in spec["lines"]:
			wanted.append("line:" + str(line["id"]))
	for ref in wanted:
		_check(refs.has(ref), "objet animé « %s » présent dans le monde" % ref)
	if factory:
		_check_factory_world(world as GmixWorld)
	var missing: Array[String] = []
	for item: Dictionary in spec["world"]["objects"]:
		if item["asset"] != STAND_IN and world.call("_scene", item["asset"]) == null:
			missing.append(str(item["asset"]))
	for agent: Dictionary in spec["agents"]:
		if world.call("_scene", agent["character"]) == null:
			missing.append(str(agent["character"]))
	_check(missing.is_empty(), "tous les assets de la spec existent au catalogue Godot", ", ".join(missing))
	var player := world.get("_player") as GmixPlayer
	_check(player != null and is_equal_approx(player.position.x, spec["world"]["spawn"][0]) and is_equal_approx(player.position.z, spec["world"]["spawn"][1]), "le joueur apparaît au point de départ de la spec")
	var week := _parsed(hud.get("_week") as Node)
	_check(week.contains("Semaine %d / %d" % [int(Session.state().get("week", 1)), int(spec["meta"]["weeks"])]) and week.contains(str(spec["meta"]["company"])), "HUD : semaine et entreprise", week)
	_check(_parsed(hud.get("_kpis") as Node).contains("OTIF"), "HUD : indicateurs")
	_check((hud.get("_role") as Label).text.contains("pilotez"), "HUD : message du formateur", (hud.get("_role") as Label).text)
	var screen: Variant = refs.get("kpi")
	if screen != null:
		_check(str((screen as Node).get("title")) == "Semaine %d / %d" % [int(Session.state().get("week", 1)), int(spec["meta"]["weeks"])], "écran des indicateurs synchronisé")
	if factory:
		return
	for line: Dictionary in Session.state()["lines"]:
		var node: Variant = refs.get("line:" + str(line["id"]))
		if node != null:
			_check(str((node as Node).get("state")) == str(line["status"]), "voyant de la ligne %s = %s" % [line["id"], line["status"]])


## Monde usine : hall de la taille de la spec, une zone par département, voyants des machines et tables d'attente de
## l'état public, un figurant par membre de `crew`, agents et figurants à l'état de `state.factory.agents`.
func _check_factory_world(world: GmixWorld) -> void:
	var spec := Session.spec()
	var state := Session.state()
	var hall: Vector2 = world.get("_hall")
	_check(is_equal_approx(hall.x, spec["world"]["size"][0]) and is_equal_approx(hall.y, spec["world"]["size"][1]), "hall de la taille de spec.world.size (%s)" % hall)
	var refs := world.get("_refs") as Dictionary
	for department: Dictionary in spec["departments"]:
		var zone: Node = refs.get("dept:" + str(department["id"]))
		if zone != null:
			var area: Array = department["area"]
			var size: Vector2 = zone.get("size")
			_check(is_equal_approx(size.x, float(area[2]) - float(area[0])) and is_equal_approx(size.y, float(area[3]) - float(area[1])), "zone « %s » : taille de son area" % department["label"])
			_check(str(zone.get("title")) == str(department["label"]), "zone « %s » : étiquette" % department["label"])
	for machine: Dictionary in state["factory"]["machines"]:
		var node: Node = refs.get("machine:" + str(machine["id"]))
		if node != null:
			_check(str(node.get("state")) == str(machine["state"]), "machine %s : voyant = %s" % [machine["id"], machine["state"]])
		var table: Node = refs.get("buffer:" + str(machine["id"]))
		if table != null:
			_check(int(table.get("capacity")) == int(machine["buffer_max"]), "table de %s : capacité %d" % [machine["id"], int(machine["buffer_max"])])
	var crew := world.get("_crew") as Array
	_check(crew.size() == (spec["factory"]["crew"] as Array).size(), "un figurant par membre de spec.factory.crew (%d)" % crew.size())
	for npc: GmixNpc in (world.get("_agents") as Array) + crew:
		var entry := GmixFactoryState.agent(state, str(npc.data["id"]))
		if not entry.is_empty():
			_check(npc.activity == str(entry["state"]), "%s : état « %s »" % [npc.data["id"], entry["state"]])


## Ouvre chaque poste de la spec ; avec `forms`, valide chaque formulaire d'action avec ses valeurs par défaut.
func _visit_stations(world: Node, forms: bool) -> void:
	var hud := _hud_of(world)
	var spec := Session.spec()
	var visited := 0
	for station: Dictionary in spec["stations"]:
		await _visit_station(hud, station, forms)
		visited += 1
	_check(visited == (spec["stations"] as Array).size(), "%d postes visités" % visited)
	hud.close_panels()


func _visit_station(hud: GmixHud, station: Dictionary, forms: bool) -> void:
	var spec := Session.spec()
	var id := str(station["id"])
	hud.open_station(station)
	await _frames(2)
	var panel := (hud.get("_panels") as Dictionary)["station"] as Control
	if not _check(panel.visible and hud.is_modal(), "poste %s : panneau ouvert" % id):
		return
	_check((hud.get("_station_title") as Label).text == station["label"], "poste %s : titre « %s »" % [id, station["label"]])
	var info := _parsed(hud.get("_station_info") as Node)
	_check(not info.is_empty(), "poste %s : informations affichées" % id)
	var leak := _bbcode_leak(info, "")
	_check(leak.is_empty(), "poste %s : aucune balise visible" % id, leak)
	_check_station_numbers(station, info)
	var actions := hud.get("_station_actions") as VBoxContainer
	var module_ids: Array = station["modules"]
	if module_ids.is_empty():
		var message := _texts(actions)
		var expects: bool = station["kind"] != "ecran_kpi" and station["kind"] != "rack_produit"
		_check(message.any(func(t: String) -> bool: return t.contains("géré automatiquement")) == expects, "poste %s : sans module -> %s" % [id, "géré automatiquement" if expects else "rien à décider"])
		_check(_buttons(actions, "Valider").is_empty(), "poste %s : aucun formulaire" % id)
		return
	var todo: Array = []  # [module_id, action_id] dans l'ordre d'affichage
	for module: Dictionary in spec["modules"]:
		if module["id"] in module_ids:
			for action: Dictionary in module["actions"]:
				todo.append([module["id"], action["id"]])
	var buttons := _buttons(actions, "Valider")
	_check(buttons.size() == todo.size(), "poste %s : %d formulaire(s) d'action" % [id, todo.size()], str(buttons.size()))
	if not forms:
		return
	for i in todo.size():
		buttons = _buttons(actions, "Valider")
		if not _check(i < buttons.size(), "poste %s : formulaire %s/%s" % [id, todo[i][0], todo[i][1]]):
			return
		await _submit_form(hud, buttons[i], todo[i][0], todo[i][1])
		await _frames(2)  # le panneau se reconstruit avec le nouvel état


## Clique « Valider » et vérifie la réponse affichée (notification) et le journal du lobby.
func _submit_form(hud: GmixHud, button: Button, module_id: String, action_id: String) -> void:
	var label := "%s/%s" % [module_id, action_id]
	var known := _children(hud.get("_notices") as Node)
	var log_before := (Session.state().get("log", []) as Array).size()
	if not _click(button, "bouton « Valider » (%s)" % label):
		return
	var notice: Variant = await _until(func() -> Variant: return _new_child(hud.get("_notices") as Node, known))
	if not _check(notice != null, "action %s : une notification répond" % label):
		return
	var text := _notice_text(notice as Node)
	var accepted := _notice_color(notice as Node) == Ui.OK
	if not _check(accepted, "action %s acceptée avec ses valeurs par défaut" % label, text):
		return
	_accepted += 1
	var log: Array = Session.state()["log"]
	var last: Dictionary = log.back()
	_check(last["module"] == module_id and last["action"] == action_id and last["summary"] == text, "action %s : le journal du lobby se met à jour" % label, str(last))
	_check(log.size() == mini(15, log_before + 1), "action %s : le journal s'allonge (%d -> %d, plafonné à 15)" % [label, log_before, log.size()])
	_check(last["name"] == Api.user["display_name"], "action %s : signée par le joueur" % label)


func _check_station_numbers(station: Dictionary, info: String) -> void:
	var state := Session.state()
	var ref: Variant = station.get("ref")
	match station["kind"]:
		"rack_produit":
			for stock: Dictionary in state["stocks"]:
				if stock["id"] == ref:
					_check(info.contains(GameText.number(stock["quantity"])), "poste %s : stock %s affiché" % [station["id"], GameText.number(stock["quantity"])])
		"rack_composant":
			for part: Dictionary in state["components"]:
				if part["id"] == ref:
					_check(info.contains(GameText.number(part["quantity"])) and info.contains(GameText.number(part["reorder_point"])), "poste %s : stock et point de commande" % station["id"])
		"ligne":
			for line: Dictionary in state["lines"]:
				if line["id"] == ref:
					_check(info.contains("TRS") and info.contains(GameText.number(line["trs"])), "poste %s : TRS de la ligne" % station["id"])
		"bureau":
			_check(info.contains(GameText.money(state["cash"])), "poste %s : trésorerie affichée" % station["id"])
		"ecran_kpi":
			_check(info.contains("OTIF") and info.contains("Aucune semaine jouée") == (state["history"] as Array).is_empty(), "poste %s : indicateurs et historique" % station["id"])


func _talk_to_agents(world: Node, limit: int) -> void:
	var hud := _hud_of(world)
	var agents: Array = Session.spec()["agents"]
	var count := agents.size() if limit < 0 else mini(limit, agents.size())
	for i in count:
		await _talk_to(hud, agents[i])
	hud.close_panels()


func _talk_to(hud: GmixHud, agent: Dictionary) -> void:
	var id := str(agent["id"])
	var name_ := str(agent["name"])
	await hud.open_dialogue(agent)
	var panel := (hud.get("_panels") as Dictionary)["dialogue"] as Control
	if not _check(panel.visible and hud.is_modal(), "%s : dialogue ouvert" % name_):
		return
	var title := (hud.get("_dialogue_title") as Label).text
	_check(title.contains(name_) and title.contains(str(agent["job"])) and title.contains(str(agent["personality"]["label"])), "%s : nom, métier et caractère" % name_, title)
	_check((hud.get("_dialogue_tasks") as Label).text.contains(str(agent["tasks"][0])), "%s : ses tâches" % name_)
	var opening := _parsed(hud.get("_dialogue_log") as Node)
	var briefing: Dictionary = Session.state()["briefings"].get(id, {})
	var said: Variant = briefing.get("line")
	if said == null and not (briefing.get("facts", []) as Array).is_empty():
		said = briefing["facts"][0]
	_check(opening.contains(name_) and (said == null or opening.contains(str(said))), "%s : première réplique tirée de ses informations de la semaine" % name_, opening)
	var memory_before := (hud.get("_exchanges") as Array).size()

	var input := hud.get("_dialogue_input") as LineEdit
	input.text = MESSAGE
	input.text_submitted.emit(MESSAGE)
	_check(not input.editable, "%s : saisie bloquée pendant la réponse" % name_)
	var answered: Variant = await _until(func() -> bool: return input.editable, TALK_WAIT_S)
	if not _check(answered != null, "%s : une réponse arrive (modèle de dialogue)" % name_):
		return
	var exchanges := hud.get("_exchanges") as Array
	if not _check(exchanges.size() == memory_before + 1, "%s : l'échange s'ajoute au fil" % name_, "%d échanges, notices : %s" % [exchanges.size(), _notice_texts(hud)]):
		return
	var last: Dictionary = exchanges.back()
	var reply := str(last["reply"]).strip_edges()
	_check(not reply.is_empty(), "%s : réponse non vide" % name_, reply)
	_check(last["message"] == MESSAGE and int(last["week"]) == int(Session.state()["week"]), "%s : échange daté de la semaine en cours" % name_)
	var log := _parsed(hud.get("_dialogue_log") as Node)
	_check(log.contains(MESSAGE) and log.contains(reply), "%s : question et réponse visibles" % name_)
	_check(_bbcode_leak(log, "").is_empty(), "%s : aucune balise visible dans le dialogue" % name_, _bbcode_leak(log, ""))
	_check(input.text.is_empty(), "%s : champ vidé après envoi" % name_)

	hud.close_panels()
	await _frames()
	await hud.open_dialogue(agent)  # l'agent se souvient : le fil revient depuis l'API
	var back := hud.get("_exchanges") as Array
	_check(back.size() >= 1 and str(back.back()["message"]) == MESSAGE and str(back.back()["reply"]).strip_edges() == reply, "%s : l'historique revient à la réouverture (mémoire)" % name_)
	_check(_parsed(hud.get("_dialogue_log") as Node).contains(reply), "%s : la réponse mémorisée est affichée" % name_)
	var memory := await _raw(_api_token(), HTTPClient.METHOD_GET, "/api/v1/lobbies/%s/npcs/%s/memory" % [Session.lobby["id"], id])
	_check(memory["ok"] and (memory["data"] as Array).size() >= 1 and memory["data"].back()["message"] == MESSAGE, "%s : l'API garde l'échange (GET /npcs/%s/memory)" % [name_, id])
	hud.close_panels()


## E près d'un PNJ puis d'un poste (focus et invite du monde), Tab (tableau de bord), Échap (menu), débrief du menu.
func _interact_and_panels(world: Node) -> void:
	var hud := _hud_of(world)
	var player := world.get("_player") as GmixPlayer
	var agents := world.get("_agents") as Array
	if not agents.is_empty():
		var npc := agents[0] as GmixNpc
		player.global_position = npc.global_position + Vector3(0, 0, 1.2)
		await _frames(3)
		var prompt := (hud.get("_prompt") as Label).text
		_check(prompt.begins_with("E : parler à %s" % npc.data["name"]), "invite près d'un agent", prompt)
		await _press_action("interact")
		await _frames(2)
		_check(hud.is_modal() and (hud.get("_dialogue_title") as Label).text.contains(str(npc.data["name"])), "E ouvre le dialogue de l'agent")
		hud.close_panels()
	var free_station := _station_far_from_agents(world)
	if not free_station.is_empty():
		var at: Array = free_station["position"]
		player.global_position = Vector3(at[0], 0.1, at[1])
		await _frames(3)
		var prompt := (hud.get("_prompt") as Label).text
		_check(prompt == "E : %s" % free_station["label"], "invite près d'un poste", prompt)
		await _press_action("interact")
		await _frames(2)
		_check(hud.is_modal() and (hud.get("_station_title") as Label).text == free_station["label"], "E ouvre le poste")
		hud.close_panels()
	player.global_position = Vector3(-60, 0.1, -60)  # loin de tout
	await _frames(3)
	_check((hud.get("_prompt") as Label).text.is_empty(), "plus d'invite loin des postes et des agents")

	var state := Session.state()
	await _press_key(KEY_TAB)
	await _frames(2)
	var dashboard := (hud.get("_panels") as Dictionary)["dashboard"] as Control
	_check(dashboard.visible, "Tab ouvre le tableau de bord")
	var text := _parsed(hud.get("_dashboard") as Node)
	for section in ["Produits finis", "Composants", "Lignes", "Commandes en cours", "Dernières actions"]:
		_check(text.contains(section), "tableau de bord : « %s »" % section)
	for stock: Dictionary in state["stocks"]:
		_check(text.contains(str(stock["name"])), "tableau de bord : %s" % stock["name"])
	_check(text.contains("Aucune semaine jouée") == (state["history"] as Array).is_empty(), "tableau de bord : historique des semaines")
	_check(_bbcode_leak(text, str(Session.spec()["meta"]["company"])).is_empty(), "tableau de bord : aucune balise visible", _bbcode_leak(text, str(Session.spec()["meta"]["company"])))
	await _press_key(KEY_TAB)
	await _frames(2)
	_check(not dashboard.visible and not hud.is_modal(), "Tab referme le tableau de bord")

	await _press_action("toggle_menu")
	await _frames(2)
	var menu := (hud.get("_panels") as Dictionary)["menu"] as Control
	_check(menu.visible, "Échap ouvre le menu")
	_check(_buttons(menu, "Reprendre").size() == 1 and _buttons(menu, "Tableau de bord").size() == 1, "menu : Reprendre et Tableau de bord")
	_click(_button(menu, "Tableau de bord"), "menu > Tableau de bord")
	await _frames(2)
	_check(dashboard.visible, "menu > Tableau de bord ouvre le tableau")
	await _press_action("toggle_menu")
	await _frames(2)
	_check(not hud.is_modal(), "Échap referme le panneau")
	await _press_action("toggle_menu")
	await _frames(2)
	var debrief_button := _button(menu, "Débrief")
	_check(debrief_button != null, "menu : « Débrief » pour le formateur")
	if _click(debrief_button, "menu > Débrief"):
		var debrief := (hud.get("_panels") as Dictionary)["debrief"] as Control
		var shown: Variant = await _until(func() -> bool: return debrief.visible)
		_check(shown != null, "le débrief s'ouvre")
		var report := _parsed(hud.get("_debrief_text") as Node)
		for section in ["Objectifs", "À retenir", "Décisions de l'équipe", "Notions et sources"]:
			_check(report.contains(section), "débrief : « %s »" % section)
		_check(_bbcode_leak(report, str(Session.spec()["meta"]["company"])).is_empty(), "débrief : aucune balise visible", _bbcode_leak(report, ""))
	_click(_button(hud.get("_panels")["debrief"] as Node, "Fermer"), "débrief > Fermer")
	await _frames(2)
	_check(not hud.is_modal(), "Fermer referme le débrief")


## Ce que fait l'API pendant que le formateur est dans l'atelier (autre poste, autre onglet) : le HUD reçoit
## l'événement par le WebSocket, affiche l'annonce et l'atelier suit l'état public.
func _remote_advance_seen_by_hud(world: Node) -> void:
	var hud := _hud_of(world)
	var known := _children(hud.get("_notices") as Node)
	var before := _ws_states
	var week := int(Session.state()["week"])
	var res := await _raw(_trainer, HTTPClient.METHOD_POST, "%s/advance" % _lobby_url())
	if not _check(res["ok"], "POST /advance depuis un autre poste", str(res["error"])):
		return
	var seen: Variant = await _until(func() -> bool: return _ws_states > before and int(Session.state()["week"]) == week + 1, WS_WAIT_S)
	_check(seen != null, "l'état public change par le WebSocket (semaine %d)" % (week + 1))
	var notice: Variant = await _until(func() -> Variant: return _notice_with(hud, "Semaine %d simulée" % week, known), WAIT_S)
	_check(notice != null, "annonce « Semaine %d simulée » dans le HUD" % week, str(_notice_texts(hud)))
	if notice != null:
		_check(_notice_text(notice as Node).contains("OTIF") and _notice_text(notice as Node).contains("trésorerie"), "l'annonce reprend les indicateurs de la semaine")
	var weeks := int(Session.spec()["meta"]["weeks"])
	var refs := world.get("_refs") as Dictionary
	if refs.get("kpi") != null:
		_check(str((refs["kpi"] as Node).get("title")) == "Semaine %d / %d" % [week + 1, weeks], "l'écran de l'atelier passe à la semaine %d" % (week + 1))
	_check(_parsed(hud.get("_week") as Node).contains("Semaine %d / %d" % [week + 1, weeks]), "le HUD passe à la semaine %d" % (week + 1))
	_check(not Session.state()["last"] is Dictionary or (Session.state()["last"] as Dictionary)["week"] == week, "le rapport de la semaine %d est dans l'état" % week)


func _leave_world() -> Control:
	var world := get_tree().current_scene
	var hud := _hud_of(world)
	hud.close_panels()
	hud.toggle_menu()
	await _frames(2)
	var menu := (hud.get("_panels") as Dictionary)["menu"] as Control
	var back_button := _button(menu, "Retour à la salle du lobby")
	if not _check(back_button != null, "menu : « Retour à la salle du lobby »"):
		return null
	_click(back_button, "menu > Retour à la salle du lobby")
	var screen := await _wait_screen(LOBBY_SCRIPT)
	_check(screen != null, "retour à la salle du lobby ouvert")
	_check(Session.lobby.has("id"), "le lobby reste ouvert dans la session")
	return screen


func _play_to_the_end(lobby: Control) -> void:
	var spec := Session.spec()
	var weeks := int(spec["meta"]["weeks"])
	var advance := lobby.get("_advance_button") as Button
	while Session.state()["status"] == "running":
		var state := Session.state()
		var week := int(state["week"])
		var history := (state["history"] as Array).size()
		var expected := "Simuler la dernière semaine" if week >= weeks else "Simuler la semaine %d" % week
		_check(advance.visible and advance.text == expected, "bouton « %s »" % expected, advance.text)
		if not _click(advance, "bouton « %s »" % expected):
			return
		var dialog: Variant = await _until(func() -> Variant: return _dialog(lobby))
		if not _check(dialog != null, "semaine %d : confirmation demandée" % week):
			return
		_check((dialog as AcceptDialog).title == expected, "la confirmation porte le titre du bouton")
		(dialog as ConfirmationDialog).get_ok_button().pressed.emit()
		var played: Variant = await _until(func() -> bool: return (Session.state()["history"] as Array).size() == history + 1, 60.0)
		if not _check(played != null, "semaine %d simulée" % week):
			return
		var after := Session.state()
		var last: Dictionary = after["last"]
		_check(last["week"] == week and last["kpis"] is Dictionary and last["totals"] is Dictionary, "semaine %d : rapport de simulation" % week)
		await _frames(2)
		if after["status"] == "running":
			_check(int(after["week"]) == week + 1, "semaine %d -> %d" % [week, week + 1])
			_check(_parsed(lobby.get("_week") as Node).contains("Semaine %d / %d" % [week + 1, weeks]), "la salle affiche la semaine %d" % (week + 1))
			_check(_parsed(lobby.get("_kpis") as Node).contains(GameText.number(last["kpis"]["otif"])), "indicateurs de la salle mis à jour (OTIF)")
	var ended := Session.state()
	_check(ended["status"] == "finished" and (ended["history"] as Array).size() == weeks, "partie terminée après %d semaines" % weeks)
	await _frames(2)
	_check(not advance.visible and not (lobby.get("_enter_button") as Button).visible, "plus de simulation ni d'atelier une fois terminé")
	_check(not (lobby.get("_code") as Label).visible, "le code d'accès disparaît")
	_check(_parsed(lobby.get("_week") as Node).contains("Partie terminée"), "état : partie terminée")
	_check(Session.lobby["status"] == "closed", "lobby fermé côté client")
	var server := await _raw(_trainer, HTTPClient.METHOD_GET, "/api/v1/lobbies/%s" % Session.lobby["id"])
	_check(server["data"]["status"] == "closed" and server["data"]["state"]["status"] == "finished", "API : lobby terminé")

	var debrief := lobby.get("_debrief_button") as Button
	if not _click(debrief, "bouton « Débrief »"):
		return
	var window: Variant = await _until(func() -> Variant: return _dialog(lobby))
	if not _check(window != null, "la fenêtre du débrief s'ouvre"):
		return
	var text := _parsed(window as Node)
	for section in ["Objectifs", "À retenir", "Semaines jouées", "Notions et sources", "Décisions de l'équipe"]:
		_check(text.contains(section), "débrief : « %s »" % section)
	for week in range(1, weeks + 1):
		_check(text.contains("S%d : OTIF" % week), "débrief : ligne de la semaine %d" % week)
	_check(text.contains("atteint"), "débrief : objectifs atteints ou non")
	_check(_bbcode_leak(text, "").is_empty(), "débrief : aucune balise visible", _bbcode_leak(text, ""))
	var report := await _raw(_trainer, HTTPClient.METHOD_GET, "%s/debrief" % _lobby_url())
	_check(report["ok"] and int(report["data"]["weeks_played"]) == weeks, "API : débrief de %d semaines" % weeks)
	_check((report["data"]["log"] as Array).size() == _accepted, "le journal du débrief garde les %d actions acceptées" % _accepted, str((report["data"]["log"] as Array).size()))
	_close_dialog(window as AcceptDialog)


func _back_home_lists_lobby() -> void:
	var lobby := get_tree().current_scene.get("_screen") as Control
	var name_ := str(Session.lobby["name"])
	_click(_button(lobby, "Retour à l'accueil"), "bouton « Retour à l'accueil »")
	var home := await _wait_screen(HOME_SCRIPT)
	if not _check(home != null, "l'accueil revient"):
		return
	_check(Session.lobby.is_empty(), "la session du lobby est fermée à l'accueil")
	var tabs := home.find_children("*", "TabContainer", true, false)[0] as TabContainer
	tabs.current_tab = 1
	var row: Variant = await _until(
		func() -> Variant:
			for child in _children(home.get("_lobbies") as Node):
				var label := child.get_child(0) as Label if child.get_child_count() > 0 else null
				if label != null and label.text.begins_with(name_):
					return child
			return null
	)
	if not _check(row != null, "le lobby figure dans la liste « Lobbies »", name_):
		return
	var text := ((row as Node).get_child(0) as Label).text
	_check(text.contains("terminé"), "état « terminé » affiché", text)
	_check(not text.contains("code ["), "plus de code d'accès une fois terminé", text)
	tabs.current_tab = 0


# --- formulaire de génération --------------------------------------------------------------------------------


func _fill_form(home: Control, params: Dictionary) -> void:
	var options: Dictionary = home.call("_current_pack")
	var controls: Dictionary = home.get("_option_controls")
	for key: String in params.get("options", {}):
		_check(controls.has(key), "option du pack « %s » dans le formulaire" % key)
		if controls.has(key):
			(controls[key] as SpinBox).value = params["options"][key]
	_pick(home.get("_theme_select") as OptionButton, _index_of(options["themes"], params["theme"]))
	for pair: Array in (home.get("_module_checks") as Array):
		(pair[1] as CheckBox).button_pressed = pair[0] in params["modules"]
	for pair: Array in (home.get("_agent_checks") as Array):
		(pair[1] as CheckBox).button_pressed = pair[0] in params["agents"]
	_pick(home.get("_tone_select") as OptionButton, _index_of(options["tones"], params["tone"]))
	_pick(home.get("_difficulty_select") as OptionButton, _index_of(options["difficulties"], params["difficulty"]))
	_pick(home.get("_events_select") as OptionButton, _index_of(options["events"], params["events"]))
	(home.get("_weeks") as SpinBox).value = params["weeks"]
	(home.get("_products") as SpinBox).value = params["products"]
	(home.get("_company") as LineEdit).text = params.get("company", "")
	(home.get("_players_min") as SpinBox).value = params["players"][0]
	(home.get("_players_max") as SpinBox).value = params["players"][1]


func _pick(select: OptionButton, index: int) -> void:
	select.select(index)
	select.item_selected.emit(index)


func _index_of(items: Array, id: String) -> int:
	for i in items.size():
		if items[i]["id"] == id:
			return i
	return 0


func _game_row(home: Control, title: String) -> Variant:
	for row in _children(home.get("_games") as Node):
		var label := row.get_child(0) as Label if row.get_child_count() > 0 else null
		if label != null and label.text.begins_with(title + "  ["):
			return row
	return null


# --- vue Sims ----------------------------------------------------------------------------------------------------


## Vue Sims jouée comme un utilisateur : clics gauches synthétiques poussés dans la fenêtre (survol, sol, agent, poste),
## touches de caméra, bascule de vue. Les positions d'écran viennent de la caméra Sims ; les ordres, le maillage de
## navigation et l'ouverture des panneaux sont ceux du vrai monde.
func _check_sims_view(world: GmixWorld) -> void:
	var hud := _hud_of(world)
	var player := world.get("_player") as GmixPlayer
	var sims := world.sims_view()
	var spec := Session.spec()
	_check(world.view() == GmixWorld.View.SIMS, "la vue Sims est la vue par défaut")
	_check(sims.camera.current and not player.is_third_person(), "caméra Sims courante, joueur déplacé par le clic")
	_check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "curseur visible en vue Sims")
	var indicator := (hud.get("_view_label") as Label).text
	_check(indicator.begins_with("Vue Sims") and indicator.contains("suivie"), "HUD : vue et mode de caméra indiqués", indicator)
	_check((hud.get("_help") as Label).text.contains("Clic : marcher"), "HUD : aide des touches de la vue Sims")
	var ready: Variant = await _until(func() -> bool: return world.is_navigation_ready(), 30.0)
	if not _check(ready != null, "le maillage de navigation est cuit à l'exécution"):
		return
	_check(not (world.get("_roof") as Node3D).visible, "toit enlevé en vue Sims")

	# Tous les postes se rejoignent à pied depuis le point de départ : le plan généré ne bouche aucun passage.
	var map := world.get_world_3d().navigation_map
	var unreachable: Array[String] = []
	for station: Dictionary in spec["stations"]:
		var at := Vector3(station["position"][0], 0, station["position"][1])
		var goal := NavigationServer3D.map_get_closest_point(map, at)
		var path := NavigationServer3D.map_get_path(map, player.global_position, goal, true)
		if Vector2(goal.x - at.x, goal.z - at.z).length() > GmixPlayer.MAX_SNAP or path.size() < 2 or path[path.size() - 1].distance_to(goal) > 0.6:
			unreachable.append(str(station["id"]))
	_check(unreachable.is_empty(), "les %d postes sont accessibles à pied" % (spec["stations"] as Array).size(), ", ".join(unreachable))
	_check(not player.walk_to(Vector3(120, 0, 120)), "une destination hors du site est refusée")

	await _sims_walk(world, player)
	await _sims_agent(world, player, hud)
	await _sims_station(world, player, hud)
	await _sims_camera(world, player, hud)
	await _sims_toggle(world, player, hud)


func _sims_walk(world: GmixWorld, player: GmixPlayer) -> void:
	var sims := world.sims_view()
	var start := player.global_position
	var target := Vector3.ZERO
	for offset: Vector3 in [Vector3(3, 0, -2), Vector3(-3, 0, -2), Vector3(0, 0, -4), Vector3(4, 0, 0)]:
		var spot := _navigable(world, start + offset)
		if Vector2(spot.x - start.x - offset.x, spot.z - start.z - offset.z).length() < 0.05:
			target = spot
			break
	if not _check(target != Vector3.ZERO, "un point libre du sol près du joueur pour le clic"):
		return
	var screen := world.screen_point(target)
	var hit := sims.pick(screen)
	var flat := Vector2(hit["point"].x - target.x, hit["point"].z - target.z).length()  # le maillage flotte à 0,3 m du sol
	_check(not hit.has("target") and flat < 0.5, "le rayon du curseur retrouve le point du sol (%.2f m d'écart)" % flat, str(hit))
	_mouse(screen, true)
	_check(player.is_walking(), "un clic sur le sol lance la marche")
	_check((world.get("_marker") as Node3D).visible, "repère de destination affiché")
	var arrived: Variant = await _until(func() -> bool: return not player.is_walking(), 25.0)
	_check(arrived != null, "la marche se termine")
	var left := Vector2(player.global_position.x - target.x, player.global_position.z - target.z).length()
	_check(left < 0.8, "le joueur arrive à destination (%.2f m du but)" % left)
	_check(not (world.get("_marker") as Node3D).visible, "repère effacé à l'arrivée")
	await _frames(3)
	_check(player.animation_name() == "idle", "animation au repos à l'arrivée", player.animation_name())
	_check(not _hud_of(world).is_modal(), "aucun panneau ouvert par un simple clic au sol")


## Clic sur un agent : survol et info-bulle, menu contextuel, « Parler à… », marche jusqu'à portée, dialogue ouvert.
func _sims_agent(world: GmixWorld, player: GmixPlayer, hud: GmixHud) -> void:
	var agents := world.get("_agents") as Array
	if agents.is_empty():
		return
	var npc := agents[0] as GmixNpc
	var name_ := str(npc.data["name"])
	await _teleport_near(world, player, npc.global_position + Vector3(3, 0, 5))
	var screen := world.screen_point(npc.global_position + Vector3(0, 0.9, 0))
	_mouse(screen, false)
	await _frames(3)
	var tooltip := hud.get("_hover") as Control
	_check(tooltip.visible and _hover_text(hud).contains(name_), "survol : info-bulle de %s" % name_, _hover_text(hud))
	_mouse(screen, true)
	await _frames(3)
	var menu := hud.get("_context_menu") as Control
	if not _check(hud.is_context_menu_open() and menu != null, "clic sur %s : menu contextuel" % name_):
		return
	_check(_texts(menu).any(func(text: String) -> bool: return text.contains(name_)), "menu : titre au nom de l'agent")
	_check(_button(menu, "S'approcher") != null, "menu : « S'approcher »")
	await _escape_closes_menu(hud)
	_mouse(screen, true)  # le menu est refermé : un nouveau clic le rouvre
	await _frames(3)
	menu = hud.get("_context_menu") as Control
	var talk := _button(menu, "Parler à %s" % name_)
	if not _check(talk != null, "menu : « Parler à %s »" % name_):
		return
	var from := Vector2(player.global_position.x - npc.global_position.x, player.global_position.z - npc.global_position.z).length()
	_click(talk, "« Parler à %s »" % name_)
	_check(not hud.is_context_menu_open(), "le choix referme le menu")
	_check(player.is_walking() and npc.busy, "le joueur marche vers l'agent, qui l'attend (%.1f m)" % from)
	var opened: Variant = await _until(func() -> bool: return hud.is_modal(), 25.0)
	_check(opened != null, "le dialogue s'ouvre à l'arrivée")
	_check((hud.get("_dialogue_title") as Label).text.contains(name_), "dialogue avec %s" % name_, (hud.get("_dialogue_title") as Label).text)
	var close := Vector2(player.global_position.x - npc.global_position.x, player.global_position.z - npc.global_position.z).length()
	_check(close <= GmixWorld.TALK_DISTANCE, "le joueur est à portée de voix (%.1f m)" % close)
	_check(not player.is_walking(), "le joueur ne marche plus")
	hud.close_panels()
	await _frames(2)
	_check(not npc.busy, "l'agent reprend sa ronde à la fermeture")


## Clic sur l'objet d'un poste : menu, « Utiliser le poste », marche jusqu'au point du poste, panneau du poste ouvert.
func _sims_station(world: GmixWorld, player: GmixPlayer, hud: GmixHud) -> void:
	var station := _station_far_from_agents(world)
	if station.is_empty():
		return
	var node := _station_node(world, station)
	if not _check(node != null, "le poste « %s » a un objet sélectionnable" % station["label"]):
		return
	var at := Vector3(station["position"][0], 0, station["position"][1])
	await _teleport_near(world, player, node.global_position + Vector3(0, 0, 8))
	var screen := world.screen_point(node.global_position + Vector3(0, 0.8, 0))
	var hit := world.sims_view().pick(screen)
	_check(hit.get("node") == node, "le rayon du curseur touche l'objet du poste « %s »" % station["label"], str(hit))
	_mouse(screen, false)
	await _frames(3)
	_check((hud.get("_hover") as Control).visible and _hover_text(hud).contains(str(station["label"])), "survol : info-bulle du poste", "%s visible=%s menu=%s" % [_hover_text(hud), (hud.get("_hover") as Control).visible, hud.is_context_menu_open()])
	_check(_overlaid(node), "survol : l'objet est surligné")
	_mouse(screen, true)
	await _frames(3)
	var menu := hud.get("_context_menu") as Control
	if not _check(hud.is_context_menu_open() and menu != null, "clic sur le poste : menu contextuel"):
		return
	var use := _button(menu, "Utiliser le poste")
	if use == null:
		use = _button(menu, "Utiliser : %s" % station["label"])
	_check(_button(menu, "S'y rendre") != null, "menu : « S'y rendre »")
	if not _click(use, "« Utiliser le poste »"):
		return
	_check(player.is_walking(), "le joueur marche vers le poste")
	var opened: Variant = await _until(func() -> bool: return hud.is_modal(), 25.0)
	_check(opened != null, "le panneau du poste s'ouvre à l'arrivée")
	_check((hud.get("_station_title") as Label).text == station["label"], "panneau du poste « %s »" % station["label"], (hud.get("_station_title") as Label).text)
	var left := Vector2(player.global_position.x - at.x, player.global_position.z - at.z).length()
	_check(left <= GmixWorld.STATION_DISTANCE, "le joueur est au poste (%.2f m)" % left)
	hud.close_panels()
	await _frames(2)
	# Un clic ailleurs referme le menu sans donner d'ordre.
	screen = world.screen_point(node.global_position + Vector3(0, 0.8, 0))
	_mouse(screen, true)
	await _frames(3)
	var menu_box := (hud.get("_context_menu") as Control).get_global_rect() if hud.is_context_menu_open() else Rect2()
	var elsewhere := Vector2.ZERO
	for offset: Vector3 in [Vector3(2, 0, 2), Vector3(-2, 0, 2), Vector3(2, 0, -2), Vector3(-2, 0, -2), Vector3(0, 0, 4), Vector3(0, 0, -4)]:
		var spot := world.screen_point(_navigable(world, player.global_position + offset))
		if not menu_box.grow(8.0).has_point(spot) and not world.sims_view().pick(spot).has("target"):
			elsewhere = spot
			break
	if _check(hud.is_context_menu_open() and elsewhere != Vector2.ZERO, "menu rouvert et un point du sol libre hors du menu"):
		_mouse(elsewhere, true)
		await _frames(2)
		_check(not hud.is_context_menu_open() and not player.is_walking(), "un clic ailleurs referme le menu sans marcher")


## Rotation, zoom, caméra libre puis suivie, murs abaissés côté caméra.
func _sims_camera(world: GmixWorld, player: GmixPlayer, hud: GmixHud) -> void:
	var sims := world.sims_view()
	var yaw := sims.yaw()
	Input.action_press("camera_rotate_right")
	await _frames(20)
	Input.action_release("camera_rotate_right")
	_check(sims.yaw() > yaw + 0.1, "flèche droite : la caméra tourne (%.2f -> %.2f rad)" % [yaw, sims.yaw()])
	var distance := float(sims.get("_distance_goal"))
	await _press_action("camera_zoom_out")
	await _press_action("camera_zoom_out")
	_check(float(sims.get("_distance_goal")) > distance + 1.0, "molette arrière : la caméra s'éloigne")
	await _press_action("camera_zoom_in")
	_check(float(sims.get("_distance_goal")) < distance * 1.3, "molette avant : la caméra se rapproche")
	var focus := sims.global_position
	Input.action_press("move_forward")
	await _frames(15)
	Input.action_release("move_forward")
	_check(not sims.follow and sims.global_position.distance_to(focus) > 0.5, "ZQSD : la caméra devient libre et se déplace")
	_check((hud.get("_view_label") as Label).text.contains("libre"), "HUD : caméra libre indiquée", (hud.get("_view_label") as Label).text)
	await _press_action("camera_follow")
	await _frames(60)
	_check(sims.follow and (hud.get("_view_label") as Label).text.contains("suivie"), "touche de suivi : la caméra suit de nouveau le joueur")
	_check(sims.global_position.distance_to(player.global_position) < 1.0, "la caméra est revenue sur le joueur")
	# Caméra au nord du mur du fond : ce mur s'abaisse, il ne cache plus l'intérieur.
	var back := ((world.get("_walls") as Array)[0] as Dictionary)["node"] as Node3D
	sims.set_follow(false)
	sims.set("_focus", Vector3(0, 0, -10))
	sims.set("_yaw_goal", PI)
	sims.snap()
	await _frames(60)
	_check(back.scale.y < 0.5, "mur du fond abaissé quand la caméra est derrière (échelle %.2f)" % back.scale.y)
	sims.set("_yaw_goal", 0.0)
	sims.snap()
	await _frames(90)
	_check(back.scale.y > 0.95, "mur du fond relevé quand la caméra est devant (échelle %.2f)" % back.scale.y)
	sims.set("_yaw_goal", deg_to_rad(GmixSimsView.YAW_DEFAULT))
	sims.set_follow(true)
	sims.snap()


## Bascule vers la troisième personne (clavier, souris capturée, toit en place) et retour.
func _sims_toggle(world: GmixWorld, player: GmixPlayer, hud: GmixHud) -> void:
	var sims := world.sims_view()
	await _press_action("toggle_view")
	await _frames(3)
	_check(world.view() == GmixWorld.View.THIRD_PERSON and player.is_third_person(), "la touche de bascule passe à la troisième personne")
	_check(not sims.camera.current, "la caméra Sims n'est plus courante")
	_check((world.get("_roof") as Node3D).visible, "toit remis en place")
	if DisplayServer.get_name() != "headless":  # sans fenêtre, le mode de la souris reste « visible »
		_check(Input.mouse_mode == Input.MOUSE_MODE_CAPTURED, "souris capturée à la troisième personne")
	_check((hud.get("_view_label") as Label).text.contains("troisième personne"), "HUD : vue à la troisième personne indiquée", (hud.get("_view_label") as Label).text)
	_check((hud.get("_help") as Label).text.contains("Maj : courir"), "HUD : aide des touches de la troisième personne")
	var before := player.global_position
	Input.action_press("move_forward")
	await _frames(25)
	Input.action_release("move_forward")
	_check(player.global_position.distance_to(before) > 0.5, "ZQSD déplace le joueur à la troisième personne")
	await _press_action("toggle_view")
	await _frames(3)
	_check(world.view() == GmixWorld.View.SIMS and sims.camera.current and not player.is_third_person(), "retour à la vue Sims")
	_check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE and not (world.get("_roof") as Node3D).visible, "curseur visible, toit enlevé")


## Texte de l'info-bulle de survol sur une seule ligne (le HUD le coupe en lignes de 360 px au plus).
func _hover_text(hud: GmixHud) -> String:
	return (hud.get("_hover_label") as Label).text.replace("\n", " ")


## Ferme le menu contextuel par la touche Échap (action toggle_menu) sans ouvrir le menu du jeu.
func _escape_closes_menu(hud: GmixHud) -> void:
	await _press_action("toggle_menu")
	await _frames(2)
	_check(not hud.is_context_menu_open() and not hud.is_modal(), "Échap referme le menu contextuel sans ouvrir le menu du jeu")


## Point du maillage de navigation le plus proche (le sol libre : ni rayonnage ni machine).
func _navigable(world: GmixWorld, point: Vector3) -> Vector3:
	return NavigationServer3D.map_get_closest_point(world.get_world_3d().navigation_map, Vector3(point.x, 0.0, point.z))


## Déplace le joueur (et sa caméra) près d'un point : pour avoir l'objet visé au milieu de l'écran, hors du bandeau.
func _teleport_near(world: GmixWorld, player: GmixPlayer, point: Vector3) -> void:
	player.global_position = _navigable(world, point) + Vector3(0, 0.05, 0)
	world.sims_view().snap()
	await _frames(4)


## Objet du décor qui porte la cible du poste (métadonnée de la vue Sims).
func _station_node(world: GmixWorld, station: Dictionary) -> Node3D:
	for child in world.get_children():
		if child.has_meta(GmixSimsView.META):
			var target: Dictionary = child.get_meta(GmixSimsView.META)
			if target["kind"] == "station" and (target["stations"] as Array).any(func(entry: Dictionary) -> bool: return entry["id"] == station["id"]):
				return child as Node3D
	return null


func _overlaid(node: Node3D) -> bool:
	for mesh in node.find_children("*", "MeshInstance3D", true, false):
		if (mesh as MeshInstance3D).material_overlay != null:
			return true
	return false


## Curseur à un point de l'écran (zone visible), avec un clic gauche si `click` : événements poussés comme par la fenêtre.
func _mouse(at: Vector2, click: bool) -> void:
	var motion := InputEventMouseMotion.new()
	motion.position = at
	motion.global_position = at
	get_viewport().push_input(motion, true)
	if click:
		for pressed in [true, false]:
			var button := InputEventMouseButton.new()
			button.button_index = MOUSE_BUTTON_LEFT
			button.position = at
			button.global_position = at
			button.pressed = pressed
			get_viewport().push_input(button, true)


# --- API hors interface ------------------------------------------------------------------------------------


func _lobby_url() -> String:
	return "/api/v1/lobbies/%s" % Session.lobby["id"]


func _api_token() -> String:
	return Api.token


## Requête avec le jeton d'un autre compte (un second poste), sans toucher à la session du client.
func _raw(token: String, method: HTTPClient.Method, path: String, body: Variant = null, timeout_s := 60.0) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = timeout_s
	add_child(http)
	var headers := PackedStringArray(["Accept: application/json", "Authorization: Bearer " + token])
	var payload := ""
	if body != null:
		headers.append("Content-Type: application/json")
		payload = JSON.stringify(body)
	var err := http.request(AppConfig.api_base_url + path, headers, method, payload)
	if err != OK:
		http.queue_free()
		return {"ok": false, "status": 0, "data": null, "error": error_string(err)}
	var response: Array = await http.request_completed
	http.queue_free()
	var status: int = response[1]
	var text := (response[3] as PackedByteArray).get_string_from_utf8()
	var data: Variant = JSON.parse_string(text) if not text.is_empty() else null
	var detail := ""
	if data is Dictionary and (data as Dictionary).has("detail"):
		detail = str(data["detail"])
	return {"ok": response[0] == HTTPRequest.RESULT_SUCCESS and status < 400, "status": status, "data": data, "error": "HTTP %d %s" % [status, detail]}


func _find_game(token: String, title: String) -> Dictionary:
	var list := await _raw(token, HTTPClient.METHOD_GET, "/api/v1/games")
	if not list["ok"]:
		return {}
	for game: Dictionary in list["data"]:
		if game["title"] == title:
			return (await _raw(token, HTTPClient.METHOD_GET, "/api/v1/games/%s" % game["id"]))["data"]
	return {}


func _latest_game(token: String) -> Dictionary:
	var list := await _raw(token, HTTPClient.METHOD_GET, "/api/v1/games")
	if not list["ok"] or (list["data"] as Array).is_empty():
		return {}
	return (await _raw(token, HTTPClient.METHOD_GET, "/api/v1/games/%s" % list["data"][0]["id"]))["data"]


# --- recherche et lecture dans l'interface ---------------------------------------------------------------------


func _doomed(node: Node) -> bool:
	var current: Node = node
	while current != null:
		if current.is_queued_for_deletion():
			return true
		current = current.get_parent()
	return false


## Enfants directs encore vivants (Ui.clear() retire les anciens à la fin de l'image).
func _children(node: Node) -> Array[Node]:
	var out: Array[Node] = []
	for child in node.get_children():
		if not child.is_queued_for_deletion():
			out.append(child)
	return out


func _new_child(node: Node, known: Array[Node]) -> Variant:
	for child in _children(node):
		if not known.has(child):
			return child
	return null


func _buttons(root: Node, caption: String) -> Array[Button]:
	var out: Array[Button] = []
	for node in root.find_children("*", "Button", true, false):
		var button := node as Button
		if button.text == caption and button.is_visible_in_tree() and not _doomed(button):
			out.append(button)
	return out


func _button(root: Node, caption: String) -> Button:
	var found := _buttons(root, caption)
	return found[0] if not found.is_empty() else null


## Clic réel : un bouton absent ou désactivé n'est pas cliquable par un utilisateur.
func _click(button: Button, label: String) -> bool:
	if not _check(button != null and button.is_visible_in_tree() and not button.disabled, "%s est cliquable" % label):
		return false
	button.pressed.emit()
	return true


func _dialog(parent: Node) -> AcceptDialog:
	for child in _children(parent):
		if child is AcceptDialog and (child as AcceptDialog).visible:
			return child as AcceptDialog
	return null


func _close_dialog(dialog: AcceptDialog) -> void:
	dialog.get_ok_button().pressed.emit()


func _texts(root: Node) -> Array[String]:
	var out: Array[String] = []
	for node in root.find_children("*", "Label", true, false):
		if not _doomed(node):
			out.append((node as Label).text)
	return out


## Texte affiché (sans balises) de tous les RichTextLabel sous `root`, ou du nœud lui-même.
func _parsed(root: Node) -> String:
	if root is RichTextLabel:
		return (root as RichTextLabel).get_parsed_text()
	var out := PackedStringArray()
	for node in root.find_children("*", "RichTextLabel", true, false):
		out.append((node as RichTextLabel).get_parsed_text())
	return "\n".join(out)


## Première balise BBCode encore visible dans un texte affiché (hors `allowed`, texte qui en contient légitimement).
func _bbcode_leak(shown: String, allowed: String) -> String:
	var text := shown.replace(allowed, "") if not allowed.is_empty() else shown
	var found := RegEx.create_from_string("\\[/?(b|i|u|color|font_size|lb|rb|center|url)(=[^\\]]*)?\\]").search(text)
	return found.get_string() if found != null else ""


func _notice_text(panel: Node) -> String:
	return (panel.get_child(0) as Label).text


func _notice_color(panel: Node) -> Color:
	return (panel.get_child(0) as Label).get_theme_color("font_color")


func _notice_texts(hud: GmixHud) -> PackedStringArray:
	var out := PackedStringArray()
	for panel in _children(hud.get("_notices") as Node):
		out.append(_notice_text(panel))
	return out


func _notice_with(hud: GmixHud, fragment: String, known: Array[Node]) -> Variant:
	for panel in _children(hud.get("_notices") as Node):
		if not known.has(panel) and _notice_text(panel).contains(fragment):
			return panel
	return null


## Poste du monde sans agent à moins de 3 m : l'invite « E » y désigne alors le poste.
func _station_far_from_agents(world: Node) -> Dictionary:
	for station: Dictionary in Session.spec()["stations"]:
		var at: Array = station["position"]
		var free := true
		for npc in (world.get("_agents") as Array):
			var p := (npc as Node3D).global_position
			if Vector2(p.x, p.z).distance_to(Vector2(at[0], at[1])) < 3.0:
				free = false
		if free:
			return station
	return {}


# --- entrées simulées ------------------------------------------------------------------------------------------


func _press_action(action: String) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = true
	Input.parse_input_event(event)
	await get_tree().process_frame
	var release := InputEventAction.new()
	release.action = action
	release.pressed = false
	Input.parse_input_event(release)


func _press_key(keycode: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.physical_keycode = keycode
	event.pressed = true
	Input.parse_input_event(event)
	await get_tree().process_frame
	var release := InputEventKey.new()
	release.keycode = keycode
	release.physical_keycode = keycode
	release.pressed = false
	Input.parse_input_event(release)


# --- étapes, vérifications, erreurs moteur ---------------------------------------------------------------------


func _begin(id: String, title: String) -> void:
	_end_step()
	_step = "%s %s" % [id, title]
	print("STEP %s" % _step)


func _end_step() -> void:
	if _step.is_empty():
		return
	var errors := _catcher.take()
	_check(errors.is_empty(), "aucune erreur moteur ni script", "\n    ".join(errors))


func _check(condition: bool, label: String, detail := "") -> bool:
	_checks += 1
	if condition:
		print("  ok  %s" % label)
	else:
		var text := label if detail.is_empty() else "%s : %s" % [label, detail]
		_failures.append("%s > %s" % [_step, text])
		print("  KO  %s" % text)
	return condition


func _arguments() -> Dictionary:
	var result := {}
	for arg in OS.get_cmdline_user_args():
		var pair := arg.trim_prefix("--").split("=", true, 1)
		result[pair[0]] = pair[1] if pair.size() > 1 else ""
	return result


## Attend qu'une condition devienne vraie (image par image) ; renvoie sa valeur, ou null après le délai.
func _until(condition: Callable, timeout_s := WAIT_S) -> Variant:
	var deadline := Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() <= deadline:
		var value: Variant = condition.call()
		if value:
			return value
		await get_tree().process_frame
	return null


func _frames(count := 2) -> void:
	for i in count:
		await get_tree().process_frame


func _stub_presence() -> void:
	var stub := GDScript.new()
	stub.source_code = (
		"extends Node\nsignal peers_changed(states: Dictionary)\nsignal status_changed(text: String)\n"
		+ "func join(_lobby_id: String, _avatar: Node3D) -> void:\n\tpass\nfunc leave() -> void:\n\tpass\n"
	)
	stub.reload()
	Presence.set_script(stub)


func _on_ws_message(type: String, _payload: Dictionary) -> void:
	match type:
		"lobby.state":
			_ws_states += 1
		"lobby.members":
			_ws_members += 1


# --- session et navigation (comme main.gd) --------------------------------------------------------------------


## Connexion par jeton (déjà obtenu par le script) puis ouverture de l'application, comme après l'écran de connexion.
func _sign_in(token: String) -> bool:
	Session.close()
	Realtime.disconnect_from_server()
	Api.logout()
	Api.token = token
	var me: Dictionary = await Api.get_json("/api/v1/auth/me")
	if not _check(me["ok"], "GET /auth/me avec le jeton", str(me["error"])):
		return false
	Api.user = me["data"]
	print("  compte %s (%s)" % [Api.user["username"], Api.user["role"]])
	await _goto(MAIN)
	return true


func _goto(scene_path: String) -> void:
	var old := get_tree().current_scene
	var old_id := old.get_instance_id() if old != null else 0
	get_tree().change_scene_to_file(scene_path)
	await _until(
		func() -> bool:
			var current := get_tree().current_scene
			return current != null and current.get_instance_id() != old_id and current.scene_file_path == scene_path
	)
	await _frames()


## Écran affiché par main.gd (accueil, lobby…), identifié par son script.
func _wait_screen(script_path: String, timeout_s := WAIT_S) -> Control:
	var screen: Variant = await _until(
		func() -> Variant:
			var main := get_tree().current_scene
			var current: Variant = main.get("_screen") if main != null else null
			if current is Control and is_instance_valid(current) and not (current as Control).is_queued_for_deletion():
				var script := (current as Control).get_script() as Script
				if script != null and script.resource_path == script_path:
					return current
			return null,
		timeout_s
	)
	return screen as Control
