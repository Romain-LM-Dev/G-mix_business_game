class_name GmixWorld
extends Node3D
## Monde 3D d'une partie, construit depuis spec.world (gmix.game.generation) : hall repris du jeu de référence
## G-mix Business_game (makeGround, three.js), objets du catalogue, postes d'interaction, agents qui patrouillent.
## L'état public (Session) anime le décor : remplissage des rayonnages, voyants des lignes, palettes aux quais,
## écran des indicateurs, alertes des agents. Aucune règle de jeu ici : actions et dialogues passent par l'API.
## Repère : 1 unité = 1 m ; hall centré sur l'origine de la taille `spec.world.size` (32 x 24 m pour l'atelier, ouvert
## vers +Z ; usine : 48 x 30 m fermé, ouvert seulement à la porte de quai) ; l'avant des assets est +Z.
## Gabarit `usine` (`spec.world.template`, ADR 0007) : zones et étiquettes des départements (`spec.departments`), machines
## et tables d'attente animées par `state.factory`, figurants (`spec.factory.crew`), agents et figurants qui marchent sur le
## maillage de navigation. Le gabarit atelier garde son comportement d'origine.
## Deux vues, au choix du joueur (action `toggle_view`) : vue Sims par défaut (GmixSimsView : caméra 3/4, clic pour marcher
## sur un maillage de navigation cuit à l'exécution depuis les collisions du plan généré, menu contextuel sur un agent ou
## un poste, toit enlevé et murs abaissés côté caméra) ou troisième personne (GmixPlayer).

enum View { SIMS, THIRD_PERSON }

## Le maillage de navigation est prêt : le clic pour marcher fonctionne.
signal navigation_ready

const CATALOG := "res://assets/catalog.json"
const MAIN := "res://scenes/main/main.tscn"
const PLAYER_MODEL := "char_worker_m"
const AVATAR_MODELS := ["char_manager_f", "char_manager_m", "char_office_f", "char_worker_f", "char_driver_m"]
const TREES := ["nat_tree", "nat_tree_oak", "nat_tree_pine", "nat_bush"]
const HALL := Vector2(32, 24)  # taille du hall quand la spec n'en donne pas
const ATELIER_SITE := Rect2(-35, -27, 70, 58)  # sol et limites du site de l'atelier ; l'usine calcule le sien depuis la spec
const SITE_MARGIN := 10.0  # m de sol autour des objets et des départements de l'usine
const NEUTRAL := Color(0.62, 0.67, 0.74)  # volume d'un asset dont la scène n'existe pas encore
const CREW_FRONT := 1.7  # m : un opérateur se tient devant sa machine (face +Z)
const TALK_DISTANCE := 2.6
const STATION_DISTANCE := 2.2
const AGENT_STOP := 1.7  # m : on s'arrête à cette distance d'un agent pour lui parler
const STATION_STOP := 0.35  # m : on va jusqu'au point de poste de la spec
const ARRIVED_SLACK := 0.6  # m : déjà assez près pour que l'ordre s'exécute sans marcher
const STATION_LINK := 2.6  # m : l'objet du décor le plus proche d'un poste (menu, survol) s'il n'a pas la même référence
const FULL_RACK_WEEKS := 3.0  # semaines de consommation qui remplissent un rayonnage
const FORKLIFT_SPEED := 2.0
const WORLD_LAYER := 1  # collisions du décor : seules elles forment le maillage de navigation
const NAV_RADIUS := 0.5  # multiple de la taille de cellule (0,25) : sinon arrondi au-dessus avec un avertissement
const WALL_LOWERED := 0.12  # échelle d'un mur côté caméra
const WALL_SPEED := 4.0
const LABEL_DISTANCE := 14.0  # m : à cette distance de la caméra Sims, une étiquette garde la taille qu'elle a en vue 3D
const LABEL_PX := Vector2(15.0, 26.0)  # taille d'une lettre en vue Sims (px de la fenêtre de référence)
const REFERENCE_HEIGHT := 720.0
const DECLUTTER_S := 0.2  # période du tri des étiquettes qui se recouvrent (vue Sims)
const DENIED_PAUSE_MS := 1500

var _catalog: Dictionary = {}
var _factory := false  # gabarit usine (spec.world.template)
var _hall := HALL
var _site := ATELIER_SITE
var _keep_clear: Array[Rect2] = []  # usine : ni arbre ni buisson sur le hall, les départements et les objets
var _warned: Dictionary = {}  # assets sans scène déjà signalés
var _agents: Array[GmixNpc] = []  # un par agent de spec.agents (jamais les figurants)
var _crew: Array[GmixNpc] = []  # usine : figurants de spec.factory.crew (opérateurs, chauffeurs)
var _station_nodes: Dictionary = {}  # id de poste -> objet du décor qui le représente
var _first_refresh := true
var _refs: Dictionary = {}  # "stock:p1", "component:c1", "line:l1", "dock_in", "dock_out", "kpi", usine : "machine:l1-m1", "buffer:l1-m1", "dept:stock_mp", "mp:c1", "pf"… -> objet
var _placed: Array[Dictionary] = []  # objets de spec.world.objects : {node, asset, ref, label}
var _player: GmixPlayer
var _hud: GmixHud
var _sims: GmixSimsView
var _view := View.SIMS
var _focus: Variant = null  # GmixNpc ou poste (Dictionary de spec.stations)
var _remote: Dictionary = {}  # peer_id -> GmixRemoteAvatar
var _forklift: Node3D
var _forklift_route: Array[Vector3] = []
var _forklift_target := 0
var _forklift_pause := 0.0
var _roof: Node3D  # charpente, luminaires et poteaux : cachés en vue Sims
var _walls: Array[Dictionary] = []  # murs abaissés quand la caméra Sims est de leur côté extérieur : {node, normal, center}
var _nav_ready := false
var _order: Dictionary = {}  # ordre en cours après un clic : {agent, talk} ou {station, node, use}
var _marker: MeshInstance3D  # repère de la destination du clic
var _hand := false
var _denied_at := -DENIED_PAUSE_MS
var _declutter_left := 0.0


func _ready() -> void:
	if Session.lobby.is_empty():
		get_tree().change_scene_to_file.call_deferred(MAIN)
		return
	var catalog: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for entry: Dictionary in catalog["assets"]:
		_catalog[entry["id"]] = entry
	var world: Dictionary = Session.spec().get("world", {})
	_factory = GmixFactoryState.is_factory(Session.spec())
	var size: Array = world.get("size", [HALL.x, HALL.y])
	_hall = Vector2(float(size[0]), float(size[1]))
	_site = _compute_site(world)
	_build_environment()
	_build_hall()
	for item: Dictionary in world.get("objects", []):
		_place(item)
	_zones_without_object()
	_link_stations()
	_bake_navigation()  # avant le joueur et les agents : seuls les obstacles fixes comptent
	_player = GmixPlayer.new()
	_player.model_scene = _scene(PLAYER_MODEL)
	var spawn: Array = world.get("spawn", [0, 6])
	_player.position = Vector3(spawn[0], 0, spawn[1])
	add_child(_player)
	_player.face_point(Vector3(0, 0, -10))  # face aux lignes
	_player.walk_finished.connect(_on_walk_finished)
	for agent: Dictionary in Session.spec().get("agents", []):
		_add_agent(agent)
	if _factory:
		for member: Dictionary in Session.spec()["factory"]["crew"]:
			_add_crew(member)
	for point: Array in world.get("forklift_route", []):
		_forklift_route.append(Vector3(point[0], 0, point[1]))
	if _forklift_route.size() >= 2:
		_forklift = _instance("veh_forklift")
		if _forklift != null:
			_forklift.position = _forklift_route[0]
			add_child(_forklift)
	_marker = _make_marker()
	_sims = GmixSimsView.new()
	_sims.follow_target = _player
	_sims.exclude = [_player.get_rid()]
	_sims.bounds = _site.grow(-1.0)
	add_child(_sims)
	_sims.ground_clicked.connect(_on_ground_clicked)
	_sims.object_clicked.connect(_on_object_clicked)
	_sims.hovered.connect(_on_hovered)
	_sims.follow_changed.connect(func(follow: bool) -> void: _hud.set_view(_view == View.SIMS, follow))
	_hud = GmixHud.new()
	add_child(_hud)
	_hud.modal_changed.connect(_on_modal_changed)
	_hud.leave_requested.connect(_leave)
	Session.lobby_changed.connect(_refresh)
	_refresh()
	_set_view(View.SIMS)
	_on_modal_changed(false)
	Presence.peers_changed.connect(_on_peers)
	Presence.status_changed.connect(_on_presence_status)
	Presence.join(str(Session.lobby["id"]), _player)


func _process(delta: float) -> void:
	if _player == null:
		return
	_drive_forklift(delta)
	_update_focus()
	if _view == View.SIMS:
		_update_cutaway(delta)
		_declutter_left -= delta
		if _declutter_left <= 0.0:
			_declutter_left = DECLUTTER_S
			_declutter_labels()
		var pulse := 1.0 + 0.12 * sin(Time.get_ticks_msec() / 150.0)
		_marker.scale = Vector3(pulse, 0.15 * pulse, pulse)


## Ce que la touche d'interaction viserait : l'agent le plus proche à portée de voix, sinon le poste le plus proche.
func _update_focus() -> void:
	_focus = null
	var best := TALK_DISTANCE
	for agent in _agents:
		var distance := _flat_distance(agent.global_position, _player.global_position)
		if distance < best:
			best = distance
			_focus = agent
	if _focus == null:
		best = STATION_DISTANCE
		for station: Dictionary in Session.spec().get("stations", []):
			var distance := _flat_distance(_station_point(station), _player.global_position)
			if distance < best:
				best = distance
				_focus = station
	if _focus is GmixNpc:
		var agent := _focus as GmixNpc
		_hud.set_prompt("E : parler à %s (%s)" % [agent.data["name"], str(agent.data["job"]).to_lower()])
	elif _focus is Dictionary:
		_hud.set_prompt("E : %s" % _focus["label"])
	else:
		_hud.set_prompt("")


func _input(event: InputEvent) -> void:
	# Tab avant l'interface : sinon il sert à passer d'un bouton à l'autre.
	if event is InputEventKey and event.pressed and not event.echo and (event as InputEventKey).keycode == KEY_TAB:
		if not get_viewport().gui_get_focus_owner() is LineEdit:
			_hud.toggle_dashboard()
			get_viewport().set_input_as_handled()


func _unhandled_input(event: InputEvent) -> void:
	if _hud == null:
		return
	if event.is_action_pressed("toggle_menu"):
		if not _hud.close_context_menu():
			_hud.toggle_menu()
	elif event.is_action_pressed("toggle_view") and not _hud.is_modal():
		_set_view(View.THIRD_PERSON if _view == View.SIMS else View.SIMS)
	elif event.is_action_pressed("interact") and _focus != null and not _hud.is_modal():
		_stop_order()
		_interact(_focus)
	elif _view == View.THIRD_PERSON and event is InputEventMouseButton and event.pressed and not _hud.is_modal():
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _on_modal_changed(open: bool) -> void:
	if open:
		_stop_order()
	_apply_mouse_mode()
	_player.controls_enabled = not open
	_sims.input_enabled = not open
	if not open:
		for agent in _agents:
			agent.busy = false


func _leave() -> void:
	Presence.leave()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Input.set_default_cursor_shape(Input.CURSOR_ARROW)
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
			avatar.model_scene = _scene(AVATAR_MODELS[absi(peer_id) % AVATAR_MODELS.size()])
			add_child(avatar)
			_remote[peer_id] = avatar
			_style_labels(_view == View.SIMS, avatar)
		var state: Dictionary = states[peer_id]
		avatar.apply(state, GameText.role_title(spec, state.get("role")))
	for peer_id: int in _remote.keys():
		if not states.has(peer_id):
			(_remote[peer_id] as Node).queue_free()
			_remote.erase(peer_id)


func _on_presence_status(text: String) -> void:
	_hud.notice(text, Ui.MUTED)


## L'état public se voit dans l'atelier : stocks, lignes, quais, écran, alertes des agents.
func _refresh() -> void:
	var state := Session.state()
	var week := int(state.get("week", 1))
	if _factory:
		_refresh_factory(state)
	else:
		for stock: Dictionary in state.get("stocks", []):
			var weeks := float(stock["quantity"]) / maxf(1.0, float(stock["forecast"]))
			_set_visual("stock:" + str(stock["id"]), "fill_level", snappedf(clampf(weeks / FULL_RACK_WEEKS, 0.0, 1.0), 0.05))
		for part: Dictionary in state.get("components", []):
			var weeks := float(part["quantity"]) / maxf(1.0, float(part["usage"]))
			_set_visual("component:" + str(part["id"]), "fill_level", snappedf(clampf(weeks / FULL_RACK_WEEKS, 0.0, 1.0), 0.05))
		for line: Dictionary in state.get("lines", []):
			_set_visual("line:" + str(line["id"]), "state", line["status"])
		var pending: Array = state.get("pending", [])
		var arriving := pending.filter(func(order: Dictionary) -> bool: return int(order["arrival_week"]) <= week)
		_set_visual("dock_in", "pallet_count", mini(12, arriving.size() * 2))
		var last: Variant = state.get("last")
		var served := int(last["totals"]["served"]) if last is Dictionary else 300
		_set_visual("dock_out", "pallet_count", clampi(roundi(served / 150.0), 1, 12))
	var screen: Node = _refs.get("kpi")
	if screen != null:
		screen.set("title", "Semaine %d / %d" % [week, int(state.get("weeks", 1))])
		screen.call("show_kpis", GameText.kpi_rows(state))
	var briefings: Dictionary = state.get("briefings", {})
	for agent in _agents:
		agent.set_briefing(briefings.get(agent.data["id"], {}))
	if _view == View.SIMS and _sims != null:
		_style_labels(true, self)  # un rayonnage reconstruit recrée son enseigne


func _set_visual(ref: String, property: String, value: Variant) -> void:
	var node: Node = _refs.get(ref)
	if node != null and node.get(property) != value:  # un rayonnage se reconstruit à chaque changement
		node.set(property, value)


# --- usine : état public (`state.factory`, annexe §2) -> décor et agents ----------------------------------------------


## Machines (voyant et libellé d'état), tables d'attente, rayonnages, bac à rebut ; agents et figurants à leur état.
## Fin de tour seulement : la chronologie du tour (rejeu) viendra animer ces mêmes objets.
func _refresh_factory(state: Dictionary) -> void:
	var factory: Dictionary = state.get("factory", {})
	for machine: Dictionary in factory.get("machines", []):
		var id := str(machine["id"])
		_set_visual("machine:" + id, "state", str(machine["state"]))
		_set_visual("buffer:" + id, "capacity", maxi(1, int(machine.get("buffer_max", 1))))
		_set_visual("buffer:" + id, "fill_level", GmixFactoryState.buffer_fill(machine))
	for component_id in _refs_of("mp:"):
		var fill := GmixFactoryState.mp_fill(state, component_id)
		if fill >= 0.0:
			_set_visual("mp:" + component_id, "fill_level", fill)
	var pf := GmixFactoryState.pf_fill(state)
	if pf >= 0.0:
		_set_visual("pf", "fill_level", pf)
	_set_visual("scrap", "fill_level", GmixFactoryState.scrap_fill(state, Session.spec()))
	for npc in _agents + _crew:
		_apply_agent_state(npc, state)
	_first_refresh = false


## Identifiants qui suivent un préfixe dans les références du décor (« mp: » -> les composants dont un rayonnage existe).
func _refs_of(prefix: String) -> PackedStringArray:
	var ids := PackedStringArray()
	for ref: String in _refs:
		if ref.begins_with(prefix):
			ids.append(ref.substr(prefix.length()))
	return ids


func _apply_agent_state(npc: GmixNpc, state: Dictionary) -> void:
	var entry := GmixFactoryState.agent(state, str(npc.data["id"]))
	if entry.is_empty():
		return
	var at: Variant = entry.get("at")
	var spot: Variant = _spot_of(str(at)) if at != null else null
	var look: Variant = _look_of(str(at)) if at != null else null
	if spot is Vector3 and not npc.is_crew():
		spot = (spot as Vector3) + Vector3(0.9, 0.0, 0.0)  # à côté de l'objet : le point de poste est celui du joueur
	npc.apply_state(str(entry["state"]), spot, look, _first_refresh)


## Où travailler à `at` (id de machine, de poste ou de département) : devant la machine ou au point du poste, sinon au
## bas de la zone du département ; null si `at` n'est rien de tout cela.
func _spot_of(at: String) -> Variant:
	var machine: Node3D = _refs.get("machine:" + at)
	if machine != null:
		return machine.position + machine.basis * Vector3(0.0, 0.0, CREW_FRONT)
	for station: Dictionary in Session.spec().get("stations", []):
		if str(station["id"]) == at:
			return _station_point(station)
	for department: Dictionary in Session.spec().get("departments", []):
		if str(department["id"]) == at:
			var rect := GmixFactoryState.area_rect(department["area"])
			return Vector3(rect.get_center().x, 0.0, rect.end.y - 1.3)
	return null


func _look_of(at: String) -> Variant:
	var machine: Node3D = _refs.get("machine:" + at)
	if machine != null:
		return machine.position
	var node: Node3D = _station_nodes.get(at)
	return node.position if node != null else null


## Étendue du sol et des limites du site. Atelier : constantes d'origine. Usine : hall, départements (les extérieurs
## sont hors du hall), objets et point d'apparition, plus une marge ; calcule aussi ce qu'on ne plante pas.
func _compute_site(world: Dictionary) -> Rect2:
	if not _factory:
		return ATELIER_SITE
	var hall := Rect2(-_hall / 2.0, _hall)
	var site := hall
	_keep_clear.append(hall.grow(5.0))
	for department: Dictionary in Session.spec().get("departments", []):
		var area := GmixFactoryState.area_rect(department["area"])
		site = site.merge(area)
		_keep_clear.append(area.grow(4.0))
	for item: Dictionary in world.get("objects", []):
		var footprint := _footprint(str(item["asset"]))
		var reach := maxf(footprint.x, footprint.z) / 2.0
		var rect := Rect2(Vector2(item["position"][0], item["position"][1]) - Vector2(reach, reach), Vector2(reach, reach) * 2.0)
		site = site.merge(rect)
		_keep_clear.append(rect.grow(2.5))
	var spawn: Array = world.get("spawn", [0, 6])
	return site.expand(Vector2(float(spawn[0]), float(spawn[1]))).grow(SITE_MARGIN)


## Zone au sol d'un département : `prop_floor_zone` de la taille de sa zone, titre et couleur par département.
func _zone(department: Dictionary) -> void:
	var node := _instance("prop_floor_zone")
	if node == null:
		return
	var departments: Array = Session.spec().get("departments", [])
	var rect := GmixFactoryState.area_rect(department["area"])
	node.set("size", rect.size)
	node.set("color", GmixFactoryState.zone_color(departments.find(department), bool(department.get("external", false))))
	node.set("title", str(department["label"]))
	node.position = Vector3(rect.get_center().x, 0.0, rect.get_center().y)
	add_child(node)
	_refs["dept:" + str(department["id"])] = node


## Un département que la spec n'a pas posé dans `world.objects` (référence `dept:<id>`) reçoit quand même sa zone.
func _zones_without_object() -> void:
	for department: Dictionary in Session.spec().get("departments", []):
		if not _refs.has("dept:" + str(department["id"])):
			_zone(department)


## Figurant de spec.factory.crew : opérateur devant sa machine, chauffeur dans la zone de son département. Aucun dialogue.
func _add_crew(member: Dictionary) -> void:
	var spec := Session.spec()
	var spot := Vector3.ZERO
	var machine_id: Variant = member.get("machine_id")
	var detail := ""
	if machine_id != null and _spot_of(str(machine_id)) is Vector3:
		spot = _spot_of(str(machine_id))
		for machine: Dictionary in spec["factory"]["machines"]:
			if machine["id"] == machine_id:
				detail = str(machine["name"])
	else:
		for department: Dictionary in spec.get("departments", []):
			if department["id"] == member["department_id"]:
				var rect := GmixFactoryState.area_rect(department["area"])
				spot = Vector3(rect.get_center().x, 0.0, rect.position.y + 1.5)
				detail = str(department["label"])
	var npc := GmixNpc.new()
	npc.data = {
		"id": member["id"], "name": "", "job": GmixFactoryState.crew_title(str(member["job"])), "detail": detail,
		"character": member["character"], "route": [[spot.x, spot.z]], "crew": true,
	}
	npc.model_scene = _scene(str(member["character"]))
	npc.player = _player
	npc.on_navmesh = true
	npc.position = spot
	npc.set_meta(GmixSimsView.META, {"kind": "crew", "agent": npc})
	add_child(npc)
	_pick_box(npc, Vector3(1.0, 1.9, 1.0))
	_crew.append(npc)


func _drive_forklift(delta: float) -> void:
	if _forklift == null:
		return
	if _forklift_pause > 0.0:
		_forklift_pause -= delta
		return
	var offset := _forklift_route[_forklift_target] - _forklift.position
	if offset.length() < 0.1:
		_forklift_target = (_forklift_target + 1) % _forklift_route.size()
		_forklift_pause = 3.0
		return
	var step := offset.normalized() * minf(FORKLIFT_SPEED * delta, offset.length())
	_forklift.position += step
	_forklift.rotation.y = atan2(step.x, step.z)


static func _flat_distance(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x, a.z).distance_to(Vector2(b.x, b.z))


static func _station_point(station: Dictionary) -> Vector3:
	return Vector3(station["position"][0], 0, station["position"][1])


# --- API pour les outils de contrôle (flow_test, world_preview) -------------------------------------------------


func view() -> View:
	return _view


func is_navigation_ready() -> bool:
	return _nav_ready


func sims_view() -> GmixSimsView:
	return _sims


## Position à l'écran (pixels de la fenêtre de référence) d'un point du monde, vu par la caméra Sims.
func screen_point(point: Vector3) -> Vector2:
	return _sims.camera.unproject_position(point)


# --- vues ------------------------------------------------------------------------------------------------------


func _set_view(view_id: View) -> void:
	var sims := view_id == View.SIMS
	_view = view_id
	_stop_order()
	_hud.close_context_menu()
	_hud.show_hover("", Vector2.ZERO)
	if sims:
		_player.set_third_person(false)
		_sims.set_active(true)
	else:
		_sims.set_active(false)
		_player.set_camera_yaw(_sims.yaw())
		_player.set_third_person(true)
		for wall in _walls:
			(wall["node"] as Node3D).scale.y = 1.0
		_marker.visible = false
	_roof.visible = not sims
	_style_labels(sims, self)
	_set_hand(false)
	_hud.set_view(sims, _sims.follow)
	_apply_mouse_mode()


func _apply_mouse_mode() -> void:
	var captured := _view == View.THIRD_PERSON and not _hud.is_modal()
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if captured else Input.MOUSE_MODE_VISIBLE


func _set_hand(on: bool) -> void:
	if on != _hand:
		_hand = on
		Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND if on else Input.CURSOR_ARROW)


## Murs côté caméra abaissés : on voit l'intérieur sans que la caméra se heurte à un mur plein.
func _update_cutaway(delta: float) -> void:
	var camera_at := _sims.camera.global_position
	var transparent: Array[RID] = [_player.get_rid()]  # la sélection au curseur ignore le joueur et les murs abaissés
	for wall in _walls:
		var outside := (camera_at - (wall["center"] as Vector3)).dot(wall["normal"] as Vector3) > 0.0
		var node := wall["node"] as Node3D
		node.scale.y = move_toward(node.scale.y, WALL_LOWERED if outside else 1.0, WALL_SPEED * delta)
		if node.scale.y < 0.6:
			transparent.append(wall["body"])
	_sims.exclude = transparent


## Étiquettes : à distance de la caméra Sims elles seraient minuscules, donc taille constante à l'écran (`fixed_size`)
## et sans portée ; à la troisième personne, réglages d'origine (mémorisés au premier passage).
func _style_labels(sims: bool, root: Node) -> void:
	var tan_half := tan(deg_to_rad(_sims.camera.fov) / 2.0)
	for node: Node in root.find_children("*", "Label3D", true, false):
		var label := node as Label3D
		if label.billboard == BaseMaterial3D.BILLBOARD_DISABLED:
			continue  # texte collé sur un objet (écran des indicateurs) : il suit la perspective
		if not label.has_meta("third_pixel_size"):
			label.set_meta("third_pixel_size", label.pixel_size)
			label.set_meta("third_range", label.visibility_range_end)
		var base := float(label.get_meta("third_pixel_size"))
		if sims:
			var letter := clampf(float(label.font_size) * base / (LABEL_DISTANCE * 2.0 * tan_half) * REFERENCE_HEIGHT, LABEL_PX.x, LABEL_PX.y)
			label.fixed_size = true
			label.pixel_size = letter / REFERENCE_HEIGHT * 2.0 * tan_half / float(label.font_size)
			label.visibility_range_end = 0.0
			label.set_meta("sims_px", letter)
		else:
			label.modulate.a = 1.0
			label.outline_modulate.a = 1.0
			label.fixed_size = false
			label.pixel_size = base
			label.visibility_range_end = float(label.get_meta("third_range"))


## Priorité d'une étiquette quand elles se recouvrent : personnages (0), objets (1), point d'état d'un figurant (2 : il ne
## doit pas cacher le nom d'une machine qu'il a juste devant lui).
func _label_rank(label: Label3D) -> int:
	var owner_node := label.get_parent()
	if owner_node is GmixNpc and (owner_node as GmixNpc).is_crew():
		return 2
	return 0 if owner_node is GmixNpc or owner_node is GmixRemoteAvatar else 1


## Étiquettes qui se recouvrent à l'écran (vue Sims) : on garde d'abord celles des personnages, puis les plus proches de la
## caméra, et on efface les autres (transparence : leur visibilité appartient à leur propriétaire, un « ! » ou une bulle).
func _declutter_labels() -> void:
	var labels: Array[Label3D] = []
	for node: Node in find_children("*", "Label3D", true, false):
		var label := node as Label3D
		if label.is_visible_in_tree() and label.has_meta("sims_px"):
			labels.append(label)
	var camera := _sims.camera
	var camera_at := camera.global_position
	labels.sort_custom(
		func(a: Label3D, b: Label3D) -> bool:
			var rank_a := _label_rank(a)
			var rank_b := _label_rank(b)
			if rank_a != rank_b:
				return rank_a < rank_b
			return a.global_position.distance_squared_to(camera_at) < b.global_position.distance_squared_to(camera_at)
	)
	var kept: Array[Rect2] = []
	for label in labels:
		var shown := not camera.is_position_behind(label.global_position)
		var rect := Rect2()
		if shown:
			var letter := float(label.get_meta("sims_px"))  # la boîte englobante d'une étiquette face caméra est un cube : seule sa largeur sert
			var width := label.get_aabb().size.x / label.pixel_size * letter / float(label.font_size)
			var extent := Vector2(width, letter * 1.5 * (label.text.count("\n") + 1))
			rect = Rect2(camera.unproject_position(label.global_position) - extent / 2.0, extent)
			for other in kept:
				if other.intersects(rect):
					shown = false
					break
		if shown:
			kept.append(rect)
		label.modulate.a = 1.0 if shown else 0.0
		label.outline_modulate.a = label.modulate.a


# --- ordres : marcher, parler, utiliser un poste -----------------------------------------------------------------


func _on_ground_clicked(point: Vector3) -> void:
	if _hud.close_context_menu() or _hud.is_modal():
		return
	_stop_order()
	_walk(point, 0.3)


func _on_object_clicked(target: Dictionary, screen: Vector2) -> void:
	if _hud.is_modal():
		return
	var entries: Array = []
	var title := ""
	if target["kind"] == "agent" or target["kind"] == "crew":
		var agent := target["agent"] as GmixNpc
		title = _target_title(target)
		if target["kind"] == "agent":  # un figurant ne parle pas
			entries.append(["Parler à %s" % agent.data["name"], func() -> void: _go_to_agent(agent, true)])
		entries.append(["S'approcher", func() -> void: _go_to_agent(agent, false)])
	else:
		var stations: Array = target["stations"]
		var node := target["node"] as Node3D
		title = _target_title(target)
		for station: Dictionary in stations:
			var caption := "Utiliser le poste" if stations.size() == 1 else "Utiliser : %s" % station["label"]
			entries.append([caption, func() -> void: _go_to_station(station, node, true)])
		entries.append(["S'y rendre", func() -> void: _go_to_station(stations[0], node, false)])
	_hud.open_context_menu(title, entries, screen)


func _on_hovered(target: Dictionary, screen: Vector2) -> void:
	_set_hand(not target.is_empty())
	_hud.show_hover(_target_title(target), screen)


func _target_title(target: Dictionary) -> String:
	if target.is_empty():
		return ""
	if target["kind"] == "agent" or target["kind"] == "crew":
		var agent := target["agent"] as GmixNpc
		var parts: Array[String] = []
		if target["kind"] == "agent":
			parts.append("%s · %s" % [agent.data["name"], str(agent.data["job"]).to_lower()])
		else:
			parts.append(str(agent.data["job"]))
			if not str(agent.data.get("detail", "")).is_empty():
				parts.append(str(agent.data["detail"]))
		if not agent.state_text().is_empty():
			parts.append(agent.state_text())
		return " · ".join(parts)
	return " / ".join((target["stations"] as Array).map(func(station: Dictionary) -> String: return station["label"]))


## Marche jusqu'à un point du sol ; faux (et une annonce) s'il est trop loin du maillage de navigation ou sans chemin.
func _walk(point: Vector3, stop_distance: float) -> bool:
	if not _nav_ready or not _player.walk_to(point, stop_distance):
		if Time.get_ticks_msec() - _denied_at > DENIED_PAUSE_MS:
			_denied_at = Time.get_ticks_msec()
			_hud.notice("Destination inaccessible : choisissez un point libre du sol.", Ui.WARN)
		return false
	_marker.position = _player.walk_goal() + Vector3(0, 0.04, 0)
	_marker.visible = true
	return true


func _go_to_agent(agent: GmixNpc, talk: bool) -> void:
	_stop_order()
	if _flat_distance(agent.global_position, _player.global_position) <= AGENT_STOP + ARRIVED_SLACK:
		if talk:
			_interact(agent)
		return
	if _walk(agent.global_position, AGENT_STOP):
		agent.busy = true  # l'agent attend le joueur au lieu de continuer sa ronde
		_order = {"agent": agent, "talk": talk}


func _go_to_station(station: Dictionary, node: Node3D, use: bool) -> void:
	_stop_order()
	var point := _station_point(station)
	if _flat_distance(point, _player.global_position) <= STATION_STOP + ARRIVED_SLACK:
		if use:
			_open_station(station, node)
		return
	if _walk(point, STATION_STOP):
		_order = {"station": station, "node": node, "use": use}


func _open_station(station: Dictionary, node: Node3D) -> void:
	if node != null:
		_player.face_point(node.global_position)
	_interact(station)


func _interact(target: Variant) -> void:
	if target is GmixNpc:
		var agent := target as GmixNpc
		agent.busy = true
		agent.face(_player.global_position)
		_player.face_point(agent.global_position)
		_hud.open_dialogue(agent.data)
	elif target is Dictionary:
		_hud.open_station(target)


## Abandonne l'ordre en cours (nouveau clic, touche, panneau, changement de vue) et libère l'agent qui attendait.
func _stop_order() -> void:
	var order := _order
	_order = {}
	var agent: GmixNpc = order.get("agent")
	if agent != null:
		agent.busy = false
	if _player != null:
		_player.stop_walking()


func _on_walk_finished(reached: bool) -> void:
	_marker.visible = false
	var order := _order
	_order = {}
	if order.is_empty():
		return
	var agent: GmixNpc = order.get("agent")
	if agent != null and not (reached and order["talk"]):
		agent.busy = false
	if not reached:
		_hud.notice("Impossible d'aller plus loin : le passage est bloqué.", Ui.WARN)
	elif agent != null and order["talk"]:
		_interact(agent)
	elif order.has("station") and order["use"]:
		_open_station(order["station"], order["node"])


func _make_marker() -> MeshInstance3D:
	var mesh := TorusMesh.new()
	mesh.inner_radius = 0.28
	mesh.outer_radius = 0.5
	mesh.rings = 24
	mesh.ring_segments = 6
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Ui.ACCENT
	var marker := MeshInstance3D.new()
	marker.mesh = mesh
	marker.material_override = material
	marker.scale = Vector3(1, 0.15, 1)
	marker.visible = false
	marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(marker)
	return marker


# --- navigation ------------------------------------------------------------------------------------------------


## Cuit le maillage de navigation depuis les collisions du décor (sol, murs, rayonnages, machines, postes) : le plan est
## généré, donc rien n'est précuit. L'analyse se fait ici (fil principal), la cuisson en tâche de fond.
func _bake_navigation() -> void:
	var navmesh := NavigationMesh.new()
	navmesh.agent_radius = NAV_RADIUS
	navmesh.agent_height = 2.0
	navmesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	navmesh.geometry_collision_mask = WORLD_LAYER | GmixPlayer.BLOCK_LAYER
	var source := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(navmesh, source, self)
	NavigationServer3D.bake_from_source_geometry_data_async(navmesh, source, _on_navmesh_baked.bind(navmesh))


func _on_navmesh_baked(navmesh: NavigationMesh) -> void:
	_finish_navigation.call_deferred(navmesh)


func _finish_navigation(navmesh: NavigationMesh) -> void:
	if navmesh.get_polygon_count() == 0:
		push_warning("Maillage de navigation vide : le clic pour marcher est indisponible")
		_hud.notice("Navigation indisponible : passage à la vue à la troisième personne.", Ui.WARN)
		_set_view(View.THIRD_PERSON)
		return
	var region := NavigationRegion3D.new()
	region.navigation_mesh = navmesh
	add_child(region)
	await get_tree().physics_frame  # la carte de navigation se synchronise à l'image physique suivante
	await get_tree().physics_frame
	_nav_ready = true
	for npc in _agents + _crew:
		npc.nav_ready = true  # usine : agents et figurants peuvent marcher
	navigation_ready.emit()


# --- construction ------------------------------------------------------------------------------------------


func _build_environment() -> void:
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
	sun.rotation_degrees = Vector3(-55, 30, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS  # 6 Go de VRAM partagés avec Ollama
	sun.directional_shadow_max_distance = 90.0
	add_child(sun)
	var grass := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(160, 140)
	grass.mesh = plane
	grass.material_override = Mesher.material(Color(0.61, 0.68, 0.56))
	grass.position.y = -0.03
	add_child(grass)
	var floor_body := StaticBody3D.new()
	var floor_shape := CollisionShape3D.new()
	floor_shape.shape = WorldBoundaryShape3D.new()
	floor_body.add_child(floor_shape)
	add_child(floor_body)
	var middle := _site.get_center()
	_solid(Vector3(_site.size.x, 0.2, _site.size.y), Vector3(middle.x, -0.1, middle.y))  # le sol que le maillage de navigation voit (un plan infini n'en est pas un)
	for side: Array in [
		[Vector3(middle.x, 5, _site.position.y - 1), Vector3(_site.size.x + 10, 10, 1)],
		[Vector3(middle.x, 5, _site.end.y + 1), Vector3(_site.size.x + 10, 10, 1)],
		[Vector3(_site.position.x - 1, 5, middle.y), Vector3(1, 10, _site.size.y + 2)],
		[Vector3(_site.end.x + 1, 5, middle.y), Vector3(1, 10, _site.size.y + 2)],
	]:
		_solid(side[1], side[0])  # bords invisibles du site
	var rng := RandomNumberGenerator.new()
	rng.seed = 42  # même décor pour tous les joueurs
	var planted := 0
	var garden := _site.grow(-1.0)
	while planted < 45:
		var spot := Vector3(rng.randf_range(garden.position.x, garden.end.x), 0, rng.randf_range(garden.position.y, garden.end.y))
		if _is_built(spot):  # ni dans le hall ni sur l'aire de livraison
			continue
		var tree := _instance(TREES[rng.randi() % TREES.size()])
		if tree != null:
			tree.position = spot
			tree.rotation.y = rng.randf() * TAU
			add_child(tree)
		planted += 1


## Emplacement bâti où l'on ne plante pas : atelier, le hall et l'aire de livraison ; usine, hall, départements et objets.
func _is_built(spot: Vector3) -> bool:
	if not _factory:
		return absf(spot.x) < 21 and spot.z < 24
	var point := Vector2(spot.x, spot.z)
	for rect in _keep_clear:
		if rect.has_point(point):
			return true
	return false


## Hall de stockage du jeu de référence : dalle et allées peintes, murs isolés au fond et sur les côtés, portiques
## en acier, contreventements de toiture, éclairage, aire de livraison devant les quais (façade ouverte).
## Charpente et luminaires sont dans `_roof` (cachés en vue Sims) ; les murs sont abaissables (`_wall`).
func _build_hall() -> void:
	if _factory:
		_build_factory_hall()
		return
	var paint := Mesher.material(Color(0.9, 0.85, 0.68))
	var steel := Mesher.material(Color(0.35, 0.4, 0.38))
	var panel := Mesher.material(Color(0.84, 0.83, 0.78))
	var curb := Mesher.material(Color(0.27, 0.4, 0.36))
	var half := _hall / 2.0
	_roof = Node3D.new()
	add_child(_roof)
	Mesher.box(self, Vector3(_hall.x, 0.04, _hall.y), Vector3(0, -0.02, 0), Mesher.material(Color(0.71, 0.72, 0.68)))
	Mesher.box(self, Vector3(_hall.x, 0.03, 8), Vector3(0, -0.025, half.y + 4), Mesher.material(Color(0.62, 0.66, 0.6)))
	for x in [-13.7, -8.5, -2.9, 2.7, 8.3, 13.8]:  # allées
		Mesher.box(self, Vector3(0.075, 0.01, 20), Vector3(x, 0.005, -1), paint)
	for x in range(-14, 15, 4):  # limite des quais
		Mesher.box(self, Vector3(1.5, 0.012, 0.12), Vector3(x, 0.006, half.y - 0.2), Mesher.material(Color(0.91, 0.8, 0.47)))
	Mesher.box(self, Vector3(_hall.x, 0.28, 0.28), Vector3(0, 0.14, -half.y), curb)
	for x in [-half.x, half.x]:
		Mesher.box(self, Vector3(0.28, 0.28, _hall.y), Vector3(x, 0.14, 0), curb)
	var back := _wall(Vector3(_hall.x, 5.7, 0.22), Vector3(0, 2.85, -half.y + 0.25), Vector3(0, 0, -1), panel)  # mur du fond
	for x in [-half.x + 0.1, half.x - 0.1]:
		_wall(Vector3(0.22, 5.7, _hall.y - 0.5), Vector3(x, 2.85, 0), Vector3(signf(x), 0, 0), panel)  # murs latéraux
	for y in range(5):  # joints des panneaux isolés
		Mesher.box(back, Vector3(_hall.x - 0.2, 0.025, 0.05), Vector3(0, 0.5 + y * 1.2, 0.13), Mesher.material(Color(0.72, 0.72, 0.67)))
	for x in [-15.5, -10.5, -5.5, -0.5, 4.5, 9.5, 15.5]:  # portiques
		for z in [-half.y + 0.1, half.y]:
			_solid(Vector3(0.24, 7.2, 0.24), Vector3(x, 3.6, z))
			Mesher.box(_roof, Vector3(0.24, 7.2, 0.24), Vector3(x, 3.6, z), steel)
		Mesher.box(_roof, Vector3(0.24, 0.24, _hall.y), Vector3(x, 7.1, 0), steel)
	Mesher.box(_roof, Vector3(_hall.x, 0.3, 0.3), Vector3(0, 7.1, half.y), steel)
	for x in [-13, -8, -3, 2, 7]:  # contreventements
		for z in [-9, -4, 1, 6]:
			for angle in [PI / 4, -PI / 4]:
				var brace := Mesher.box(_roof, Vector3(0.07, 0.07, 7.1), Vector3(x + 2.5, 6.86, z + 2.5), steel)
				brace.rotation.y = angle
	for x in [-11, -4, 3, 10]:  # luminaires : le tube est dans la charpente, la lumière reste allumée en vue Sims
		Mesher.box(_roof, Vector3(2.5, 0.12, 0.42), Vector3(x, 6.45, -0.5), Mesher.material(Color(0.95, 0.92, 0.82), Color(0.55, 0.53, 0.43)))
		var lamp := OmniLight3D.new()
		lamp.light_color = Color(1.0, 0.93, 0.81)
		lamp.light_energy = 1.4
		lamp.omni_range = 11.0
		lamp.position = Vector3(x, 6.2, -0.5)
		add_child(lamp)


## Hall de l'usine, de la taille de `spec.world.size` : dalle, plinthe, murs isolés fermés sur les quatre côtés avec une
## seule ouverture, celle des portes de quai (`prop_dock_door` posées au mur avant) ; sans porte, la façade reste ouverte
## comme celle de l'atelier. Mêmes matériaux et mêmes règles que l'atelier : charpente et luminaires dans `_roof` (cachés
## en vue Sims), murs abaissables côté caméra. Les zones peintes sont celles des départements (`_zone`).
func _build_factory_hall() -> void:
	var steel := Mesher.material(Color(0.35, 0.4, 0.38))
	var panel := Mesher.material(Color(0.84, 0.83, 0.78))
	var curb := Mesher.material(Color(0.27, 0.4, 0.36))
	var half := _hall / 2.0
	var opening := _dock_opening()
	_roof = Node3D.new()
	add_child(_roof)
	Mesher.box(self, Vector3(_hall.x, 0.04, _hall.y), Vector3(0, -0.02, 0), Mesher.material(Color(0.71, 0.72, 0.68)))
	Mesher.box(self, Vector3(_hall.x, 0.03, 8), Vector3(0, -0.025, half.y + 4), Mesher.material(Color(0.62, 0.66, 0.6)))  # aire des camions
	Mesher.box(self, Vector3(_hall.x, 0.28, 0.28), Vector3(0, 0.14, -half.y), curb)
	for x in [-half.x, half.x]:
		Mesher.box(self, Vector3(0.28, 0.28, _hall.y), Vector3(x, 0.14, 0), curb)
	var back := _wall(Vector3(_hall.x, 5.7, 0.22), Vector3(0, 2.85, -half.y + 0.25), Vector3(0, 0, -1), panel)
	for x in [-half.x + 0.1, half.x - 0.1]:
		_wall(Vector3(0.22, 5.7, _hall.y - 0.5), Vector3(x, 2.85, 0), Vector3(signf(x), 0, 0), panel)
	for y in range(5):  # joints des panneaux isolés
		Mesher.box(back, Vector3(_hall.x - 0.2, 0.025, 0.05), Vector3(0, 0.5 + y * 1.2, 0.13), Mesher.material(Color(0.72, 0.72, 0.67)))
	var front: Array[Vector2] = []  # morceaux du mur avant (x de début, x de fin) ; aucune porte : façade ouverte
	if opening != Vector2.ZERO:
		front = [Vector2(-half.x, opening.x), Vector2(opening.y, half.x)]
	for piece in front:
		if piece.y - piece.x > 0.5:
			_wall(Vector3(piece.y - piece.x, 5.7, 0.22), Vector3((piece.x + piece.y) / 2.0, 2.85, half.y - 0.25), Vector3(0, 0, 1), panel)
	var columns := maxi(2, roundi(_hall.x / 6.0))  # un portique tous les 6 m environ
	for i in columns + 1:
		var x := -half.x + 0.5 + i * (_hall.x - 1.0) / columns
		for z in [-half.y + 0.1, half.y]:
			if z > 0.0 and opening != Vector2.ZERO and x > opening.x - 0.4 and x < opening.y + 0.4:
				continue  # pas de poteau dans l'ouverture des portes
			_solid(Vector3(0.24, 7.2, 0.24), Vector3(x, 3.6, z))
			Mesher.box(_roof, Vector3(0.24, 7.2, 0.24), Vector3(x, 3.6, z), steel)
		Mesher.box(_roof, Vector3(0.24, 0.24, _hall.y), Vector3(x, 7.1, 0), steel)
	for z in [-half.y, half.y]:
		Mesher.box(_roof, Vector3(_hall.x, 0.3, 0.3), Vector3(0, 7.1, z), steel)
	for x in range(int(-half.x + 3), int(half.x - 5), 5):  # contreventements
		for z in range(int(-half.y + 3), int(half.y - 5), 5):
			for angle in [PI / 4, -PI / 4]:
				var brace := Mesher.box(_roof, Vector3(0.07, 0.07, 7.1), Vector3(x + 2.5, 6.86, z + 2.5), steel)
				brace.rotation.y = angle
	for x in range(int(-half.x + 6), int(half.x - 3), 12):  # luminaires : la lumière reste allumée en vue Sims
		for z in [-half.y / 2.0, half.y / 2.0]:
			Mesher.box(_roof, Vector3(2.5, 0.12, 0.42), Vector3(x, 6.45, z), Mesher.material(Color(0.95, 0.92, 0.82), Color(0.55, 0.53, 0.43)))
			var lamp := OmniLight3D.new()
			lamp.light_color = Color(1.0, 0.93, 0.81)
			lamp.light_energy = 1.4
			lamp.omni_range = 14.0
			lamp.position = Vector3(x, 6.2, z)
			add_child(lamp)


## Étendue en X des portes de quai (assets `prop_dock_door` près du mur avant), Vector2.ZERO s'il n'y en a pas.
func _dock_opening() -> Vector2:
	var span := Vector2(INF, -INF)
	for item: Dictionary in Session.spec().get("world", {}).get("objects", []):
		if item["asset"] == "prop_dock_door" and absf(float(item["position"][1]) - _hall.y / 2.0) < 2.0:
			var reach := _footprint("prop_dock_door").x / 2.0
			span = Vector2(minf(span.x, float(item["position"][0]) - reach), maxf(span.y, float(item["position"][0]) + reach))
	return span if span.x < span.y else Vector2.ZERO


## Collision pleine (couche du décor : elle compte dans le maillage de navigation), avec un volume visible si `mat`.
func _solid(size: Vector3, at: Vector3, mat: Material = null) -> StaticBody3D:
	if mat != null:
		Mesher.box(self, size, at, mat)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	body.position = at
	body.add_child(shape)
	add_child(body)
	return body


## Mur : collision pleine hauteur, volume visible dans un nœud posé au sol (on l'écrase en vue Sims quand la caméra est
## du côté `normal`, vers l'extérieur du hall).
func _wall(size: Vector3, at: Vector3, normal: Vector3, mat: Material) -> Node3D:
	var holder := Node3D.new()
	holder.position = Vector3(at.x, 0.0, at.z)
	add_child(holder)
	Mesher.box(holder, size, Vector3(0, at.y, 0), mat)
	_walls.append({"node": holder, "body": _solid(size, at).get_rid(), "normal": normal, "center": holder.position})
	return holder


## Objet de spec.world.objects ; `label` devient le titre, l'enseigne ou une étiquette flottante.
func _place(item: Dictionary) -> void:
	var zone_of: Variant = _department(str(item.get("ref", "")).trim_prefix("dept:")) if str(item.get("ref", "")).begins_with("dept:") else null
	if zone_of is Dictionary:  # zone d'un département : sa taille et son titre viennent de `spec.departments`
		_zone(zone_of)
		return
	var node := _instance(item["asset"])
	if node == null:
		return
	node.position = Vector3(item["position"][0], 0, item["position"][1])
	node.rotation_degrees.y = float(item.get("rotation", 0))
	if item["asset"] == "prop_floor_zone":
		node.position.y = 0.005  # marquage dans une zone de département : posé au-dessus pour ne pas scintiller
	add_child(node)
	var label: Variant = item.get("label")
	if label is String and not label.is_empty():
		if _factory:
			label = str(label).get_slice(":", 0).get_slice(",", 0).strip_edges()  # « Table : cartons, ruban » -> « Table »
		if "title" in node:  # ligne de production
			node.set("title", label)
		elif node.get_node_or_null("Sign") != null:
			node.set("sign_text", label)
		else:
			var caption := Label3D.new()
			caption.text = label
			caption.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			caption.font_size = 36
			caption.pixel_size = 0.007
			caption.outline_size = 10
			caption.position.y = _height(item["asset"]) + 0.4
			caption.visibility_range_end = 22.0
			node.add_child(caption)
	var ref: Variant = item.get("ref")
	if ref is String:
		_refs[ref] = node
	if node.find_children("*", "StaticBody3D", true, false).is_empty():
		_block(node, _footprint(item["asset"]))  # asset sans collision (écran, bureau, palettes) : une boîte à son emprise
	_placed.append({"node": node, "asset": item["asset"], "ref": ref if ref is String else "", "label": label if label is String else ""})


## Relie chaque poste de la spec à l'objet du décor qui le représente (même référence, sinon le plus proche à moins de
## STATION_LINK m de son emprise) : le clic et le survol de la vue Sims passent par cet objet. Un poste sans objet reçoit
## un repère au sol. Les cibles sont des métadonnées (GmixSimsView.META) sur le nœud de l'objet.
func _link_stations() -> void:
	for station: Dictionary in Session.spec().get("stations", []):
		var point := _station_point(station)
		var entry := _station_entry(station, point)
		var node: Node3D = entry["node"] if not entry.is_empty() else _station_marker(station, point)
		var target: Dictionary = node.get_meta(GmixSimsView.META, {})
		if target.is_empty():
			target = {"kind": "station", "stations": [], "node": node}
			node.set_meta(GmixSimsView.META, target)
			_pick_box(node, _footprint(entry.get("asset", "")) if not entry.is_empty() else Vector3(1.8, 2.0, 1.8))
		(target["stations"] as Array).append(station)
		_station_nodes[str(station["id"])] = node


func _station_entry(station: Dictionary, point: Vector3) -> Dictionary:
	var ref: Variant = station.get("ref")
	var best := {}
	var best_distance := STATION_LINK
	for entry in _placed:
		if entry["asset"] == "prop_floor_zone" or str(entry["ref"]).begins_with("buffer:"):
			continue  # marquage au sol et table d'attente : jamais le poste d'une machine (même identifiant)
		if ref != null and str(entry["ref"]).get_slice(":", 1) == str(ref):  # « stock:p1 » pour le poste de p1
			return entry
		if str(entry["ref"]).is_empty() and str(entry["label"]).is_empty():
			continue  # décor sans nom (camion, voyant) : jamais un poste
		var footprint := _footprint(entry["asset"])
		var local := (entry["node"] as Node3D).global_transform.affine_inverse() * point
		var distance := Vector2(maxf(absf(local.x) - footprint.x / 2.0, 0.0), maxf(absf(local.z) - footprint.z / 2.0, 0.0)).length()
		if distance < best_distance:
			best_distance = distance
			best = entry
	return best


## Repère au sol d'un poste sans objet : disque lumineux et zone de clic.
func _station_marker(station: Dictionary, point: Vector3) -> Node3D:
	var node := Node3D.new()
	node.position = point
	add_child(node)
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.9
	mesh.bottom_radius = 0.9
	mesh.height = 0.02
	var disc := MeshInstance3D.new()
	disc.mesh = mesh
	disc.material_override = Mesher.material(Color(0.3, 0.62, 1.0), Color(0.15, 0.3, 0.5))
	disc.position.y = 0.011
	node.add_child(disc)
	var label := Label3D.new()
	label.text = str(station["label"])
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 36
	label.pixel_size = 0.007
	label.outline_size = 10
	label.position.y = 1.2
	label.visibility_range_end = 22.0
	node.add_child(label)
	return node


## Collision pleine à l'emprise d'un asset qui n'en a pas : sans elle on le traverserait et le maillage de navigation
## passerait dessus. Écart à signaler à assets-3d : une collision propre à l'asset remplace celle-ci.
func _block(node: Node3D, size: Vector3) -> void:
	if size.y < 0.3:
		return  # à plat sur le sol : on l'enjambe
	var body := StaticBody3D.new()
	body.collision_layer = GmixPlayer.BLOCK_LAYER
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y / 2.0
	body.add_child(shape)
	node.add_child(body)


## Boîte de sélection d'un objet de poste : couche à part, sans effet sur le joueur ni sur le maillage de navigation.
func _pick_box(node: Node3D, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.collision_layer = GmixSimsView.PICK_LAYER
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position.y = size.y / 2.0
	body.add_child(shape)
	node.add_child(body)


## Emprise (largeur, hauteur, profondeur) d'un asset d'après le catalogue.
func _footprint(id: String) -> Vector3:
	if not _catalog.has(id):
		return Vector3(1.0, 2.0, 1.0)
	var footprint: Dictionary = _catalog[id]["footprint"]
	return Vector3(float(footprint["w"]), float(footprint["h"]), float(footprint["d"]))


func _add_agent(agent: Dictionary) -> void:
	var npc := GmixNpc.new()
	npc.data = agent
	npc.model_scene = _scene(agent["character"])
	npc.player = _player
	npc.on_navmesh = _factory
	var start: Array = agent["route"][0]
	npc.position = Vector3(start[0], 0, start[1])
	npc.set_meta(GmixSimsView.META, {"kind": "agent", "agent": npc})
	add_child(npc)
	_pick_box(npc, Vector3(1.0, 1.9, 1.0))
	_agents.append(npc)


func _scene(id: String) -> PackedScene:
	if not _catalog.has(id) or not ResourceLoader.exists(str(_catalog[id]["scene"])):
		return null
	return load(_catalog[id]["scene"]) as PackedScene


## Un asset du catalogue sans scène (pas encore fabriqué) ou absent du catalogue Godot : volume neutre à son emprise (ou
## 1 x 2 x 1 m si le catalogue ne le connaît pas), signalé une fois ; le monde se construit quand même.
func _instance(id: String) -> Node3D:
	var scene := _scene(id)
	if scene == null:
		if not _warned.has(id):
			_warned[id] = true
			push_warning("Asset sans scène : %s (volume neutre à l'emprise du catalogue)" % id)
		var size := _footprint(id)
		var holder := Node3D.new()
		Mesher.box(holder, size, Vector3(0, size.y / 2.0, 0), Mesher.material(NEUTRAL))
		return holder
	return scene.instantiate() as Node3D


func _department(id: String) -> Variant:
	for department: Dictionary in Session.spec().get("departments", []):
		if str(department["id"]) == id:
			return department
	return null


func _height(id: String) -> float:
	return float(_catalog[id]["footprint"]["h"]) if _catalog.has(id) else 2.0
