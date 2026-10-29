class_name GmixNpc
extends Node3D
## Agent PNJ du business game (spec.agents) : patrouille dans les allées de sa zone, s'arrête et se tourne vers le
## joueur qui lui parle. Ses informations de la semaine (état public, `briefings`) le font réagir : « ! » au-dessus
## de la tête quand l'une est urgente, réplique en bulle quand un joueur approche. Le dialogue passe par l'API.
## Usine (`on_navmesh`) : l'agent et les figurants (opérateurs, chauffeurs) marchent sur le maillage de navigation
## cuit par le monde, et leur état (disponible, occupé, en déplacement, en pause, absent) vient de l'état public.

const SPEED := 1.3
const PAUSE_S := 2.5
const GREET_DISTANCE := 5.0
const BUBBLE_S := 8.0
const WAYPOINT := 0.15  # m : un point du chemin est atteint à cette distance
const ARRIVED := 0.1

## Entrée `agents` de la spec : {id, name, job, personality, tasks, character, zone, route, notions…} ; pour un
## figurant, {id, name: "", job, character, route: [position de départ], crew: true}.
var data: Dictionary = {}
var model_scene: PackedScene
var player: Node3D  # joueur local : l'agent l'interpelle quand il approche
var busy := false  # en dialogue : ne bouge plus
## Usine : le déplacement suit le maillage de navigation ; `nav_ready` passe à vrai quand le monde l'a cuit (avant, l'agent attend).
var on_navmesh := false
var nav_ready := false
var activity := ""  # AgentState de l'état public (vide : atelier, patrouille d'origine)

var _model: Node3D
var _route: Array[Vector3] = []
var _target := 0
var _pause := 0.0
var _marker: Label3D
var _bubble: Label3D
var _caption: Label3D  # nom et état (usine) ; point coloré seul pour un figurant
var _bubble_left := 0.0
var _line := ""
var _said := ""
var _post: Variant = null  # Vector3 : où l'agent travaille quand il est occupé
var _look: Variant = null  # Vector3 : ce qu'il regarde une fois arrivé
var _path := PackedVector3Array()
var _path_index := 0
var _path_goal := Vector3(INF, 0.0, INF)


func _ready() -> void:
	for point: Array in data.get("route", []):
		_route.append(Vector3(point[0], 0, point[1]))
	if model_scene != null:
		_model = model_scene.instantiate() as Node3D
		add_child(_model)
	_caption = _label("●" if is_crew() else data.get("name", "?"), 48 if is_crew() else 40, 2.2, 14.0)  # le métier s'affiche dans l'invite, à portée de voix
	_caption.modulate = Color(1.0, 0.95, 0.8)
	_marker = _label("!", 110, 2.75, 40.0)
	_marker.modulate = Color(1.0, 0.72, 0.3)
	_marker.visible = false
	_bubble = _label("", 30, 3.3, 12.0)
	_bubble.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_bubble.width = 480
	_bubble.visible = false
	var body := StaticBody3D.new()
	body.collision_layer = GmixPlayer.NPC_LAYER  # le clic de la vue Sims le trouve ; hors du maillage de navigation
	var shape := CollisionShape3D.new()
	var cylinder := CylinderShape3D.new()
	cylinder.radius = 0.35
	cylinder.height = 1.8
	shape.shape = cylinder
	shape.position.y = 0.9
	body.add_child(shape)
	add_child(body)
	_show_state()


func _process(delta: float) -> void:
	if _bubble_left > 0.0:
		_bubble_left -= delta
		_bubble.visible = _bubble_left > 0.0
	if player != null and not _line.is_empty() and _line != _said:
		if player.global_position.distance_to(global_position) < GREET_DISTANCE:
			_said = _line
			say(_line)
	if busy or activity == "absent":
		_animate("idle")
		return
	match activity:
		"occupe", "pause":
			_work(delta)
		"deplacement":
			_patrol(delta, 0.0)
		_:
			_patrol(delta, PAUSE_S)


func is_crew() -> bool:
	return data.get("crew", false)


## Informations de la semaine : {facts, urgent, line}. Une nouvelle réplique sera dite au prochain passage.
func set_briefing(briefing: Dictionary) -> void:
	_marker.visible = briefing.get("urgent", false)
	var line: Variant = briefing.get("line")
	_line = line if line is String else ""


## État public d'un agent de l'usine ({state, at} de `state.factory.agents`) : `spot` est le poste ou la machine où il
## travaille (Vector3 ou null) et `look` ce qu'il regarde ; `snap` : il y est tout de suite (entrée dans le monde), sinon il y marche.
func apply_state(code: String, spot: Variant, look: Variant, snap: bool) -> void:
	var wanted: Variant = spot if code == "occupe" else null
	if code == activity and wanted == _post and look == _look:
		return
	activity = code
	_post = wanted
	_look = look
	_path_goal = Vector3(INF, 0.0, INF)  # nouveau but : nouveau chemin
	if snap and _post is Vector3:
		position = Vector3((_post as Vector3).x, 0.0, (_post as Vector3).z)
		_face_look()
	if _model != null:
		_model.visible = code != "absent"
	_show_state()


## Texte lisible de l'état courant (info-bulle, dialogue) ; vide hors usine.
func state_text() -> String:
	return GmixFactoryState.state_text(activity) if not activity.is_empty() else ""


func say(text: String) -> void:
	_bubble.text = text
	_bubble.visible = true
	_bubble_left = BUBBLE_S


## Se tourne vers un point (le joueur qui lui parle).
func face(point: Vector3) -> void:
	var direction := point - global_position
	rotation.y = atan2(direction.x, direction.z)


## Nom et état sous forme de texte flottant : un figurant n'a qu'un point de la couleur de son état.
func _show_state() -> void:
	if _caption == null:
		return
	if activity.is_empty():
		return
	_caption.modulate = GmixFactoryState.state_color(activity)
	if not is_crew():
		_caption.text = "%s\n%s" % [data.get("name", "?"), GmixFactoryState.state_text(activity)]


## Texte au-dessus de la tête, masqué au-delà de `visible_up_to` mètres pour ne pas encombrer la vue.
func _label(text: String, font_size: int, height: float, visible_up_to: float) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = font_size
	label.pixel_size = 0.007
	label.outline_size = 12
	label.position.y = height
	label.visibility_range_end = visible_up_to
	add_child(label)
	return label


func _animate(animation: String) -> void:
	if _model != null and _model.get("animation") != animation:
		_model.set("animation", animation)


# --- déplacement ---------------------------------------------------------------------------------------------


## Ronde entre les points de la route, avec une pause à chaque point.
func _patrol(delta: float, pause: float) -> void:
	if _route.size() < 2:
		_animate("idle")
		return
	if _pause > 0.0:
		_pause -= delta
		_animate("idle")
		return
	if _go(_route[_target], delta):
		_target = (_target + 1) % _route.size()
		_pause = pause


## Au poste : il y marche s'il n'y est pas encore, puis y reste (immobile, tourné vers ce qu'il fait).
func _work(delta: float) -> void:
	if not _post is Vector3 or _go(_post as Vector3, delta):
		_face_look()
		_animate("idle")


func _face_look() -> void:
	if _look is Vector3:
		var direction := (_look as Vector3) - position
		if Vector2(direction.x, direction.z).length() > 0.05:
			rotation.y = atan2(direction.x, direction.z)


## Avance vers `goal` (en ligne droite dans l'atelier, sur le maillage de navigation dans l'usine) ; vrai à l'arrivée.
func _go(goal: Vector3, delta: float) -> bool:
	goal.y = 0.0
	var next := goal
	if on_navmesh:
		if not nav_ready:
			_animate("idle")
			return false
		if _path_goal.distance_to(goal) > 0.01:
			_plan(goal)
		while _path_index < _path.size() - 1 and _flat(_path[_path_index]) < WAYPOINT:
			_path_index += 1
		if _path.is_empty():
			return true  # aucun chemin : il reste où il est
		next = _path[_path_index]
		next.y = 0.0
	var offset := next - position
	offset.y = 0.0
	if offset.length() < ARRIVED:
		if next == goal or _path_index >= _path.size() - 1:
			_animate("idle")
			return true
		_path_index += 1
		return false
	var step := offset.normalized() * minf(SPEED * delta, offset.length())
	position += step
	rotation.y = atan2(step.x, step.z)  # l'avant des personnages est +Z
	_animate("walk")
	return false


func _plan(goal: Vector3) -> void:
	var map := get_world_3d().navigation_map
	_path_goal = goal
	_path_index = 0
	_path = NavigationServer3D.map_get_path(map, position, NavigationServer3D.map_get_closest_point(map, goal), true)
	if _path.size() > 1:
		_path_index = 1  # le premier point est la position de départ


func _flat(point: Vector3) -> float:
	return Vector2(position.x - point.x, position.z - point.z).length()
