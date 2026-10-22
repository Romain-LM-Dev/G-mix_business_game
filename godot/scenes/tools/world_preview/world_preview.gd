extends Node
## Aperçu du monde 3D d'un lobby sans passer par les menus : contrôle visuel du gabarit, des assets, des PNJ
## et de la présence. Jeton de connexion dans la variable d'environnement GMIX_TOKEN.
##   Godot.exe --path godot res://scenes/tools/world_preview/world_preview.tscn --
##       --api=http://127.0.0.1:8000 --lobby=<id> [--snapshot=C:/dossier]
## Avec --snapshot : vue du joueur (player.png), vue d'ensemble (overview.png), première zone (zone.png), fermeture.

const WORLD := preload("res://scenes/world/world.tscn")


func _ready() -> void:
	var args := {}
	for arg in OS.get_cmdline_user_args():
		var pair := arg.trim_prefix("--").split("=", true, 1)
		args[pair[0]] = pair[1] if pair.size() > 1 else ""
	Api.token = OS.get_environment("GMIX_TOKEN")
	var res: Dictionary = await Api.get_json("/api/v1/lobbies/%s" % args.get("lobby", ""))
	if not res["ok"]:
		printerr("Lobby inaccessible : %s" % res["error"])
		get_tree().quit(1)
		return
	Session.open(res["data"])
	add_child(WORLD.instantiate())
	var directory: String = args.get("snapshot", "")
	if directory.is_empty():
		return
	DirAccess.make_dir_recursive_absolute(directory)
	await _capture(directory.path_join("player.png"))
	var camera := Camera3D.new()
	camera.position = Vector3(0, 110, 100)
	add_child(camera)
	camera.look_at(Vector3.ZERO)
	camera.current = true
	await _capture(directory.path_join("overview.png"))
	var zone_id: String = Session.spec()["world"]["zones"][0]["id"]
	for slot: Dictionary in Session.lobby["world_template"]["zones"]:
		if slot["id"] == zone_id:  # devant la première zone : bâtiment, objets, PNJ
			var center := Vector3(slot["position"][0], 0, slot["position"][1])
			var front := Vector3(0, 0, 1).rotated(Vector3.UP, deg_to_rad(float(slot.get("facing", 0))))
			camera.position = center + front * 26.0 + Vector3(0, 8, 0)
			camera.look_at(center + Vector3(0, 2, 0))
	await _capture(directory.path_join("zone.png"))
	get_tree().quit(0)


func _capture(path: String) -> void:
	for i in 60:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(path)
	print("capture : %s" % path)
