extends Node
## Aperçu du monde 3D d'un lobby sans passer par les menus : contrôle visuel du hall, des objets, des postes,
## des agents, de la vue Sims et de la présence. Jeton de connexion dans la variable d'environnement GMIX_TOKEN.
##   Godot.exe --path godot res://scenes/tools/world_preview/world_preview.tscn [--resolution 1920x1080] --
##       --api=http://127.0.0.1:8000 --lobby=<id> [--snapshot=C:/dossier]
## Sans API : `--fixture=usine` (ou `--pack=usine` sans `--lobby`) charge le monde usine depuis les fichiers d'exemple
## scenes/tools/fixtures/ (spec et état public tirés de l'annexe de l'ADR 0007), sans réseau ni jeton.
## Avec --snapshot (fenêtre et GPU requis, pas la version console), puis fermeture :
##   vue Sims au départ (sims.png), survol d'un agent (sims_survol.png), menu contextuel de l'agent (sims_menu.png),
##   menu contextuel d'un poste (sims_poste.png), clic pour marcher (sims_marche.png), caméra tournée et zoomée
##   (sims_rotation.png), vue à la troisième personne (troisieme_personne.png), puis vues d'ensemble du décor
##   (atelier : overview, atelier, quais ; usine : usine_*.png) et la fréquence d'images mesurée en vue Sims
##   (ligne « FPS » de la console : moyenne sur 5 s et pire image).

const WORLD := preload("res://scenes/world/world.tscn")
const FIXTURES := "res://scenes/tools/fixtures/%s_%s.json"
const VIEWS := {
	"overview.png": [Vector3(0, 30, 27), Vector3(0, 0, -1)],
	"atelier.png": [Vector3(-7, 5.5, 7), Vector3(1, 1, -4)],
	"quais.png": [Vector3(6, 6, 20), Vector3(6, 1, 6)],
}
const FACTORY_VIEWS := {
	"usine_ensemble.png": [Vector3(0, 52, 44), Vector3(0, 0, 4)],
	"usine_lignes.png": [Vector3(-2, 9, 13), Vector3(0, 0, -3)],
	"usine_stock_reception.png": [Vector3(-19, 9, 16), Vector3(-17, 0, 2)],
	"usine_qualite_emballage.png": [Vector3(21, 9, 14), Vector3(19, 0, -3)],
	"usine_quai.png": [Vector3(0, 8, 29), Vector3(0, 1, 10)],
	"usine_pilotage_maintenance.png": [Vector3(-2, 9, -3), Vector3(-1, 0, -13)],
	"usine_fournisseur.png": [Vector3(-30, 11, 14), Vector3(-36, 0, 30)],
}


func _ready() -> void:
	var args := {}
	for arg in OS.get_cmdline_user_args():
		var pair := arg.trim_prefix("--").split("=", true, 1)
		args[pair[0]] = pair[1] if pair.size() > 1 else ""
	var fixture := str(args.get("fixture", "usine" if args.get("pack", "") == "usine" and not args.has("lobby") else ""))
	if not fixture.is_empty():
		if not _open_fixture(fixture):
			get_tree().quit(1)
			return
	else:
		Api.token = OS.get_environment("GMIX_TOKEN")
		var res: Dictionary = await Api.get_json("/api/v1/lobbies/%s" % args.get("lobby", ""))
		if not res["ok"]:
			printerr("Lobby inaccessible : %s" % res["error"])
			get_tree().quit(1)
			return
		Session.open(res["data"])
	var directory: String = args.get("snapshot", "")
	if not directory.is_empty():
		var asked := get_window().size  # --resolution : la zone visible ; sans bordure, la fenêtre n'en ajoute pas
		get_window().borderless = true
		get_window().position = Vector2i.ZERO
		get_window().size = asked
		await get_tree().process_frame
	var world := WORLD.instantiate() as GmixWorld
	add_child(world)
	if not fixture.is_empty():  # la présence passe par l'API : sans elle, pas d'annonce d'échec dans les captures
		for connection in Presence.status_changed.get_connections():
			Presence.status_changed.disconnect(connection["callable"])
	if directory.is_empty():
		return
	DirAccess.make_dir_recursive_absolute(directory)
	print("FENETRE %s zone visible %s" % [get_window().size, get_viewport().get_visible_rect().size])
	get_tree().create_timer(300.0).timeout.connect(func() -> void: get_tree().quit(1))  # jamais de fenêtre qui reste ouverte
	while not world.is_navigation_ready():
		await get_tree().process_frame
	await _sims_tour(world, directory)
	for i in 5:
		await get_tree().process_frame  # le retour à la vue Sims (touche simulée) rend sa caméra courante à l'image suivante
	var camera := Camera3D.new()
	add_child(camera)
	camera.make_current()
	camera.far = 250.0
	var views: Dictionary = FACTORY_VIEWS if GmixFactoryState.is_factory(Session.spec()) else VIEWS
	for file: String in views:
		camera.position = views[file][0]
		camera.look_at(views[file][1])
		await _capture(directory.path_join(file))
	get_tree().quit(0)


## Charge la spec et l'état d'exemple d'un pack dans une séance factice (aucun appel réseau).
func _open_fixture(pack: String) -> bool:
	var loaded := {}
	for kind in ["spec", "state"]:
		var path := FIXTURES % [pack, kind]
		if not FileAccess.file_exists(path):
			printerr("Fichier d'exemple absent : %s" % path)
			return false
		var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if not data is Dictionary:
			printerr("Fichier d'exemple illisible : %s" % path)
			return false
		loaded[kind] = data
	var spec: Dictionary = loaded["spec"]
	Session.open({
		"id": "fixture-%s" % pack, "name": "Exemple %s" % pack, "status": "running", "join_code": "EXEMPLE",
		"is_manager": true, "my_role": null, "members": [], "spec": spec, "state": loaded["state"],
		"game_title": spec["meta"]["title"],
	})
	return true


func _sims_tour(world: GmixWorld, directory: String) -> void:
	var hud := world.get("_hud") as GmixHud
	var agents := world.get("_agents") as Array
	await _capture(directory.path_join("sims.png"), 240)  # le temps de compiler les shaders
	await _measure_fps()
	var player := world.get("_player") as GmixPlayer
	var npc := agents[0] as GmixNpc
	for candidate: GmixNpc in agents:  # le plus proche du joueur : celui que la caméra suivie montre
		if candidate.global_position.distance_to(player.global_position) < npc.global_position.distance_to(player.global_position):
			npc = candidate
	npc.busy = true  # il ne bouge plus pendant les captures
	var at := world.screen_point(npc.global_position + Vector3(0, 0.9, 0))
	_mouse(at, false)
	await _capture(directory.path_join("sims_survol.png"), 20)
	_mouse(at, true)
	await _capture(directory.path_join("sims_menu.png"), 20)
	hud.close_context_menu()
	npc.busy = false
	var visible_rect := Rect2(Vector2(200, 160), Vector2(700, 380))  # hors bandeau et aide : un clic ne traverse pas l'interface
	for entry: Dictionary in world.get("_placed"):
		var node := entry["node"] as Node3D
		var spot := world.screen_point(node.global_position + Vector3(0, 0.8, 0))
		if node.has_meta(GmixSimsView.META) and visible_rect.has_point(spot):
			_mouse(spot, true)
			break
	await _capture(directory.path_join("sims_poste.png"), 20)
	hud.close_context_menu()
	var ahead := player.global_position + Vector3(2.0, 0.0, -4.0)
	_mouse(world.screen_point(ahead), true)
	await _capture(directory.path_join("sims_marche.png"), 25)
	Input.action_press("camera_rotate_right")
	for i in 90:
		await get_tree().process_frame
	Input.action_release("camera_rotate_right")
	for i in 6:
		_action("camera_zoom_out")
	await _capture(directory.path_join("sims_rotation.png"), 60)
	_action("toggle_view")
	await _capture(directory.path_join("troisieme_personne.png"), 60)
	await _measure_fps("troisième personne")
	_action("toggle_view")


## Fréquence d'images moyenne sur 5 s et pire image (ms), la caméra ne bougeant pas : la mesure du budget de 45 images/s.
func _measure_fps(view_name := "vue Sims") -> void:
	var started := Time.get_ticks_msec()
	var frames := 0
	var worst := 0.0
	var last := started
	while Time.get_ticks_msec() - started < 5000:
		await get_tree().process_frame
		var now := Time.get_ticks_msec()
		worst = maxf(worst, float(now - last))
		last = now
		frames += 1
	print("FPS %s : %.1f en moyenne sur 5 s, pire image %.0f ms, %d appels de rendu, %d objets" % [
		view_name,
		frames / ((last - started) / 1000.0),
		worst,
		Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
	])


## Déplace le curseur sur un point de l'écran ou clique dessus (coordonnées de la zone visible).
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


func _action(action: String) -> void:
	for pressed in [true, false]:
		var event := InputEventAction.new()
		event.action = action
		event.pressed = pressed
		Input.parse_input_event(event)


func _capture(path: String, frames := 60) -> void:
	for i in frames:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("capture : %s" % path)
