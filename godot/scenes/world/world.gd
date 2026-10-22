extends Node3D
## Monde 3D d'une partie, construit depuis le gabarit de carte (ai/world_templates.yaml, reçu avec le lobby) et la
## spec : zones, assets du catalogue, PNJ. Décisions et KPI passent par l'API : aucune règle de jeu n'est ici.
## Repère : 1 unité = 1 m ; une zone regarde la route (+Z local) ; l'avant des assets est +Z.

const CATALOG := "res://assets/catalog.json"
const MAIN := "res://scenes/main/main.tscn"
const PLAYER_MODEL := "char_worker_m"
const NPC_MODELS := ["char_manager_f", "char_manager_m", "char_office_f", "char_worker_f", "char_driver_m"]
const TREES := ["nat_tree", "nat_tree_oak", "nat_tree_pine", "nat_bush"]
const TALK_DISTANCE := 3.0
const SCREEN_DISTANCE := 4.5
const PROP_GAP := 1.5

var _catalog: Dictionary = {}
var _npcs: Array[GmixNpc] = []
var _screens: Array[Node3D] = []
var _player: GmixPlayer
var _hud: GmixHud
var _focus: Node3D
var _remote: Dictionary = {}  # peer_id -> GmixRemoteAvatar


func _ready() -> void:
	if Session.lobby.is_empty():
		get_tree().change_scene_to_file.call_deferred(MAIN)
		return
	var catalog: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for entry: Dictionary in catalog["assets"]:
		_catalog[entry["id"]] = entry
	var raw_template: Variant = Session.lobby.get("world_template")
	var template: Dictionary = raw_template if raw_template is Dictionary else {}  # gabarit inconnu : sol seul
	var spec := Session.spec()
	_build_environment(template)
	_build_roads(template)
	var slots := {}
	for slot: Dictionary in template.get("zones", []):
		slots[slot["id"]] = slot
	for zone: Dictionary in spec["world"]["zones"]:
		if slots.has(zone["id"]):
			_build_zone(zone, slots[zone["id"]], spec)
	_player = GmixPlayer.new()
	_player.model_scene = _scene(PLAYER_MODEL)
	var spawn: Array = template.get("spawn", [0, 0, 2])
	_player.position = Vector3(spawn[0], spawn[1], spawn[2])
	var first: Dictionary = slots.get(spec["world"]["zones"][0]["id"], {}) if not spec["world"]["zones"].is_empty() else {}
	if not first.is_empty():  # arrivée sur la route, face au siège (première zone : écran des KPI)
		_player.position.x = float(first["position"][0])
	add_child(_player)
	if not first.is_empty():
		_player.face_point(Vector3(first["position"][0], 0, first["position"][1]))
	_hud = GmixHud.new()
	add_child(_hud)
	_hud.modal_changed.connect(_on_modal_changed)
	_hud.leave_requested.connect(_leave)
	Session.lobby_changed.connect(_refresh_screens)
	_refresh_screens()
	_on_modal_changed(false)
	Presence.peers_changed.connect(_on_peers)
	Presence.status_changed.connect(_on_presence_status)
	Presence.join(str(Session.lobby["id"]), _player)


func _process(_delta: float) -> void:
	if _player == null:
		return
	_focus = null
	var best := TALK_DISTANCE
	for npc in _npcs:
		var distance := npc.global_position.distance_to(_player.global_position)
		if distance < best:
			best = distance
			_focus = npc
	if _focus == null:
		for screen in _screens:
			if screen.global_position.distance_to(_player.global_position) < SCREEN_DISTANCE:
				_focus = screen
	if _focus is GmixNpc:
		_hud.set_prompt("E : parler à %s" % (_focus as GmixNpc).data.get("name", ""))
	elif _focus != null:
		_hud.set_prompt("E : consulter les indicateurs")
	else:
		_hud.set_prompt("")


func _input(event: InputEvent) -> void:
	# Tab avant l'interface : sinon il sert à passer d'un bouton à l'autre.
	if event is InputEventKey and event.pressed and not event.echo and (event as InputEventKey).keycode == KEY_TAB:
		if not get_viewport().gui_get_focus_owner() is LineEdit:
			_hud.toggle_decisions()
			get_viewport().set_input_as_handled()


func _unhandled_input(event: InputEvent) -> void:
	if _hud == null:
		return
	if event.is_action_pressed("toggle_menu"):
		_hud.toggle_menu()
	elif event.is_action_pressed("interact") and _focus != null and not _hud.is_modal():
		if _focus is GmixNpc:
			var npc := _focus as GmixNpc
			npc.face(_player.global_position)
			_hud.open_dialogue(npc.data)
		else:
			_hud.open_kpis()
	elif event is InputEventMouseButton and event.pressed and not _hud.is_modal():
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _on_modal_changed(open: bool) -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if open else Input.MOUSE_MODE_CAPTURED
	_player.controls_enabled = not open


func _leave() -> void:
	Presence.leave()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_tree().change_scene_to_file(MAIN)


## Autres joueurs du lobby (serveur de partie) : créés, déplacés, retirés selon chaque instantané.
func _on_peers(states: Dictionary) -> void:
	var me := multiplayer.get_unique_id() if not states.is_empty() else 0
	var spec := Session.spec()
	for peer_id: int in states:
		if peer_id == me:
			continue
		var avatar: GmixRemoteAvatar = _remote.get(peer_id)
		if avatar == null:
			avatar = GmixRemoteAvatar.new()
			avatar.model_scene = _scene(NPC_MODELS[absi(peer_id) % NPC_MODELS.size()])
			add_child(avatar)
			_remote[peer_id] = avatar
		var state: Dictionary = states[peer_id]
		avatar.apply(state, GameText.role_title(spec, state.get("role")))
	for peer_id: int in _remote.keys():
		if not states.has(peer_id):
			(_remote[peer_id] as Node).queue_free()
			_remote.erase(peer_id)


func _on_presence_status(text: String) -> void:
	_hud.notice(text, Ui.MUTED)


func _refresh_screens() -> void:
	var rows := GameText.kpi_rows(Session.spec(), Session.state())
	for screen in _screens:
		screen.call("show_kpis", rows)


# --- construction ------------------------------------------------------------------------------------------


func _build_environment(template: Dictionary) -> void:
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 35, 0)
	sun.shadow_enabled = true
	add_child(sun)

	var ground_size: Array = template.get("ground", [220, 120])
	var width := float(ground_size[0])
	var depth := float(ground_size[1])
	var grass := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(width + 200, depth + 200)
	grass.mesh = plane
	grass.material_override = Mesher.material(Color(0.42, 0.56, 0.36))
	grass.position.y = -0.02
	add_child(grass)
	var floor_body := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	floor_shape.shape = WorldBoundaryShape3D.new()
	floor_body.add_child(floor_shape)
	add_child(floor_body)
	for side: Array in [[Vector3(0, 5, -depth / 2), Vector3(width, 10, 1)], [Vector3(0, 5, depth / 2), Vector3(width, 10, 1)], [Vector3(-width / 2, 5, 0), Vector3(1, 10, depth)], [Vector3(width / 2, 5, 0), Vector3(1, 10, depth)]]:
		var wall := StaticBody3D.new()  # bords invisibles de la carte
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = side[1]
		shape.shape = box
		wall.position = side[0]
		wall.add_child(shape)
		add_child(wall)
	var rng := RandomNumberGenerator.new()
	rng.seed = 42  # même décor pour tous les joueurs
	for i in 60:
		var angle := rng.randf() * TAU
		var spot := Vector3(cos(angle) * (width / 2 + rng.randf_range(4, 30)), 0, sin(angle) * (depth / 2 + rng.randf_range(4, 30)))
		var tree := _instance(TREES[rng.randi() % TREES.size()])
		if tree != null:
			tree.position = spot
			tree.rotation.y = rng.randf() * TAU
			add_child(tree)


func _build_roads(template: Dictionary) -> void:
	var asphalt := Mesher.material(Color(0.22, 0.23, 0.25))
	var paint := Mesher.material(Color(0.92, 0.92, 0.85))
	for road: Dictionary in template.get("roads", []):
		var start := Vector3(road["from"][0], 0, road["from"][1])
		var end := Vector3(road["to"][0], 0, road["to"][1])
		var along_x := absf(end.x - start.x) >= absf(end.z - start.z)
		var length := start.distance_to(end)
		var middle := (start + end) / 2.0
		var size := Vector3(length, 0.05, 10) if along_x else Vector3(10, 0.05, length)
		Mesher.box(self, size, middle + Vector3(0, 0.025, 0), asphalt)
		var direction := (end - start).normalized()
		var steps := int(length / 6.0)
		for i in steps:
			var at := start + direction * (i * 6.0 + 3.0)
			var dash := Vector3(3, 0.02, 0.25) if along_x else Vector3(0.25, 0.02, 3)
			Mesher.box(self, dash, at + Vector3(0, 0.06, 0), paint)
			if i % 4 == 2:  # tous les 24 m, décalés pour dégager le point d'apparition (centre de la route)
				for offset in [-6.0, 6.0]:
					var lamp := _instance("prop_street_light")
					if lamp != null:
						var side := Vector3(0, 0, offset) if along_x else Vector3(offset, 0, 0)
						add_child(lamp)
						lamp.position = at + side
						lamp.look_at(at - side * 2.0, Vector3.UP, true)  # le bras éclaire la route


## Parcelle : bâtiment au fond, objets en rangée devant, PNJ devant l'entrée, panneau côté route.
func _build_zone(zone: Dictionary, slot: Dictionary, spec: Dictionary) -> void:
	var root := Node3D.new()
	root.name = zone["id"]
	root.position = Vector3(slot["position"][0], 0, slot["position"][1])
	root.rotation_degrees.y = float(slot.get("facing", 0))
	add_child(root)
	var width := float(slot["size"][0])
	var depth := float(slot["size"][1])
	Mesher.box(root, Vector3(width, 0.06, depth), Vector3(0, 0.03, 0), Mesher.material(Color(0.55, 0.56, 0.55)))
	var ids: Array = zone["asset_ids"]
	var front := -depth / 2.0 + 2.0
	if not ids.is_empty():
		var building := _instance(ids[0])
		if building != null:
			var building_depth := _footprint(ids[0]).z
			building.position = Vector3(0, 0, -depth / 2.0 + building_depth / 2.0 + 1.0)
			if _catalog[ids[0]].get("sign", false):
				building.set("sign_text", zone["name"])
			root.add_child(building)
			front = building.position.z + building_depth / 2.0

	var props := ids.slice(1)
	var row_z := lerpf(front, depth / 2.0, 0.55)
	var row_width := 0.0
	for id in props:
		row_width += _footprint(id).x + PROP_GAP
	var x := -minf(row_width, width - 4.0) / 2.0
	for id in props:
		var node := _instance(id)
		if node == null:
			continue
		var size := _footprint(id)
		if x + size.x > width / 2.0 - 1.0:  # rangée pleine : on repart plus près de la route
			x = -minf(row_width, width - 4.0) / 2.0
			row_z = minf(row_z + 5.0, depth / 2.0 - 2.0)
		node.position = Vector3(x + size.x / 2.0, 0, row_z)
		root.add_child(node)
		if id == "prop_kpi_screen":
			_screens.append(node)
		x += size.x + PROP_GAP

	var zone_npcs := []
	for npc: Dictionary in spec["npcs"]:
		if npc["zone"] == zone["id"]:
			zone_npcs.append(npc)
	for i in zone_npcs.size():
		var npc := GmixNpc.new()
		npc.data = zone_npcs[i]
		npc.model_scene = _scene(NPC_MODELS[absi(hash(npc.data["id"])) % NPC_MODELS.size()])
		npc.position = Vector3((i - (zone_npcs.size() - 1) / 2.0) * 4.5, 0, front + 2.5)  # noms lisibles côte à côte
		root.add_child(npc)
		_npcs.append(npc)

	var sign := Label3D.new()
	sign.text = zone["name"]
	sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sign.font_size = 72
	sign.pixel_size = 0.012
	sign.outline_size = 14
	sign.position = Vector3(0, 4.5, depth / 2.0 - 1.0)
	root.add_child(sign)


func _scene(id: String) -> PackedScene:
	if not _catalog.has(id):
		return null
	return load(_catalog[id]["scene"]) as PackedScene


func _instance(id: String) -> Node3D:
	var scene := _scene(id)
	if scene == null:
		push_warning("Asset absent du catalogue Godot : %s" % id)
		return null
	return scene.instantiate() as Node3D


func _footprint(id: String) -> Vector3:
	if not _catalog.has(id):
		return Vector3.ONE
	var footprint: Dictionary = _catalog[id]["footprint"]
	return Vector3(float(footprint["w"]), float(footprint["h"]), float(footprint["d"]))
