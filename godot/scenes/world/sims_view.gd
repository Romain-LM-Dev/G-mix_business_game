class_name GmixSimsView
extends Node3D
## Vue façon Les Sims : caméra 3/4 vue de haut, suivant le joueur ou libre, avec rotation et zoom ; survol surligné ;
## clic sur le sol (marcher) ou sur un objet ou un agent (menu). Tout Node3D qui porte la métadonnée META est une cible
## sélectionnable : le monde en fait des agents et des objets de poste (cette classe ne connaît aucune règle de jeu).
## Commandes (Input Map) : move_* déplacent la caméra (elle devient libre), camera_follow la rattache au joueur,
## camera_rotate_* et camera_drag (clic droit ou milieu + glisser) la font tourner, camera_zoom_* (molette) la rapprochent,
## world_click (clic gauche) donne un ordre.

signal follow_changed(follow: bool)
signal ground_clicked(point: Vector3)
## `target` : la valeur de la métadonnée de l'objet cliqué ; `screen` : position du curseur (menu contextuel).
signal object_clicked(target: Dictionary, screen: Vector2)
## À chaque image : la cible sous le curseur ({} si aucune, ou curseur sur l'interface) et la position du curseur.
signal hovered(target: Dictionary, screen: Vector2)

const META := &"sims_target"
const PICK_LAYER := 8  # boîtes de sélection que le monde ajoute aux objets de poste (aucune collision physique)
const PICK_MASK := 1 | GmixPlayer.NPC_LAYER | PICK_LAYER
const RAY_LENGTH := 300.0
const WORLD_LAYER := 1  # décor plein : un agent qu'il cache n'est pas sélectionnable
const NUDGE := 0.6  # m : un clic sur la paroi d'un obstacle vise le sol devant elle, côté caméra
const FOV := 38.0  # degrés (jeu de référence) : perspective resserrée, effet diorama
const YAW_DEFAULT := 28.0  # degrés ; 0 = la caméra est au sud (+Z) et regarde vers le nord
const PITCH_DEFAULT := 52.0  # degrés sous l'horizon
const PITCH_MIN := 30.0
const PITCH_MAX := 80.0
const DISTANCE_DEFAULT := 30.0  # m : à FOV 38, ~19 m de haut et ~34 m de large au point suivi, soit le hall de 32 m
const DISTANCE_MIN := 8.0
const DISTANCE_MAX := 62.0  # le hall et sa pelouse tiennent à l'écran (FOV 38 : 62 m équivalent à 51 m en FOV 45)
const ZOOM_STEP := 0.9
const PAN_SPEED := 0.9  # m/s par mètre de distance
const ROTATE_SPEED := 1.6  # rad/s aux touches
const DRAG_YAW := 0.006  # rad par pixel
const DRAG_PITCH := 0.25  # degrés par pixel
const FOLLOW_SMOOTH := 7.0
const EASE := 10.0

var camera := Camera3D.new()
var follow_target: Node3D
var follow := true
var bounds := Rect2(-34.0, -26.0, 68.0, 56.0)  # plan XZ : où va la caméra libre
var input_enabled := true  # faux sous un panneau modal : ni caméra ni clic
var exclude: Array[RID] = []  # corps ignorés par la sélection (le joueur, les murs abaissés) : le monde les tient à jour

var _focus := Vector3.ZERO
var _yaw := deg_to_rad(YAW_DEFAULT)
var _yaw_goal := deg_to_rad(YAW_DEFAULT)
var _pitch := PITCH_DEFAULT
var _pitch_goal := PITCH_DEFAULT
var _distance := DISTANCE_DEFAULT
var _distance_goal := DISTANCE_DEFAULT
var _pointer := Vector2(-1.0, -1.0)
var _hover_node: Node3D
var _highlight := _make_highlight()


func _ready() -> void:
	camera.fov = FOV
	camera.near = 0.5
	camera.far = 250.0
	camera.position = Vector3(0, 0, _distance)
	add_child(camera)
	set_active(false)


## Active la vue : caméra courante, recadrée sur le joueur.
func set_active(on: bool) -> void:
	set_process(on)
	set_process_input(on)
	set_process_unhandled_input(on)
	if on:
		_pointer = get_viewport().get_mouse_position()
		snap()
		camera.make_current()
	else:
		_set_hover(null)


## Recadre tout de suite sur le joueur (sans glissement) et reprend le zoom et l'angle choisis.
func snap() -> void:
	if follow_target != null:
		_focus = follow_target.global_position
	_yaw = _yaw_goal
	_pitch = _pitch_goal
	_distance = _distance_goal
	_apply()


## Angle de la caméra autour du joueur (radians ; 0 = elle est au sud et regarde vers -Z).
func yaw() -> float:
	return _yaw_goal


func set_follow(on: bool) -> void:
	if follow != on:
		follow = on
		follow_changed.emit(on)


func _input(event: InputEvent) -> void:
	if event is InputEventMouse:
		_pointer = (event as InputEventMouse).position


func _unhandled_input(event: InputEvent) -> void:
	if not input_enabled:
		return
	if event is InputEventMouseMotion and Input.is_action_pressed("camera_drag"):
		var motion := event as InputEventMouseMotion
		_yaw_goal -= motion.relative.x * DRAG_YAW
		_pitch_goal = clampf(_pitch_goal + motion.relative.y * DRAG_PITCH, PITCH_MIN, PITCH_MAX)
	elif event.is_action_pressed("camera_zoom_in", true):
		_distance_goal = clampf(_distance_goal * ZOOM_STEP, DISTANCE_MIN, DISTANCE_MAX)
	elif event.is_action_pressed("camera_zoom_out", true):
		_distance_goal = clampf(_distance_goal / ZOOM_STEP, DISTANCE_MIN, DISTANCE_MAX)
	elif event.is_action_pressed("camera_follow"):
		set_follow(not follow)
	elif event.is_action_pressed("world_click") and event is InputEventMouseButton:
		_click((event as InputEventMouseButton).position)


func _process(delta: float) -> void:
	if input_enabled:
		var pan := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		if pan != Vector2.ZERO:
			set_follow(false)
			_focus += Basis(Vector3.UP, _yaw) * Vector3(pan.x, 0, pan.y) * PAN_SPEED * _distance * delta
		_yaw_goal += Input.get_axis("camera_rotate_left", "camera_rotate_right") * ROTATE_SPEED * delta
	if follow and follow_target != null:
		_focus = _focus.lerp(follow_target.global_position, 1.0 - exp(-FOLLOW_SMOOTH * delta))
	_focus.x = clampf(_focus.x, bounds.position.x, bounds.end.x)
	_focus.z = clampf(_focus.z, bounds.position.y, bounds.end.y)
	var blend := 1.0 - exp(-EASE * delta)
	_yaw = lerpf(_yaw, _yaw_goal, blend)
	_pitch = lerpf(_pitch, _pitch_goal, blend)
	_distance = lerpf(_distance, _distance_goal, blend)
	_apply()
	_update_hover()


func _apply() -> void:
	global_position = _focus
	rotation = Vector3(-deg_to_rad(_pitch), _yaw, 0.0)
	camera.position = Vector3(0, 0, _distance)


# --- sélection -------------------------------------------------------------------------------------------------


## Ce que le rayon du curseur rencontre : {point} (sol, ou sol devant l'obstacle touché), plus {node, target} si c'est une
## cible. Un agent est choisi dès qu'il est visible, même contre la boîte de sélection d'un poste voisin.
func pick(screen: Vector2) -> Dictionary:
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	var end := origin + direction * RAY_LENGTH
	var hit := _cast(origin, end, GmixPlayer.NPC_LAYER)
	if hit.is_empty() or not _cast(origin, hit["position"], WORLD_LAYER).is_empty():
		hit = _cast(origin, end, PICK_MASK)
	if hit.is_empty():
		var ground: Variant = Plane(Vector3.UP, 0.0).intersects_ray(origin, direction)
		return {"point": ground} if ground is Vector3 else {}
	var node := hit["collider"] as Node
	while node != null:
		if node.has_meta(META):
			return {"point": hit["position"], "node": node, "target": node.get_meta(META)}
		node = node.get_parent()
	var point: Vector3 = hit["position"]
	var normal: Vector3 = hit["normal"]
	if absf(normal.y) < 0.7:
		point += Vector3(normal.x, 0.0, normal.z).normalized() * NUDGE
	return {"point": point}


func _cast(from: Vector3, to: Vector3, mask: int) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(from, to, mask, exclude)
	return get_world_3d().direct_space_state.intersect_ray(query)


func _click(screen: Vector2) -> void:
	var hit := pick(screen)
	if hit.has("target"):
		object_clicked.emit(hit["target"], screen)
	elif hit.has("point"):
		ground_clicked.emit(hit["point"])


func _update_hover() -> void:
	var over_interface := get_viewport().gui_get_hovered_control() != null
	if not input_enabled or over_interface or Input.is_action_pressed("camera_drag"):
		_set_hover(null)
		hovered.emit({}, _pointer)
		return
	var hit := pick(_pointer)
	_set_hover(hit.get("node"))
	hovered.emit(hit.get("target", {}), _pointer)


## Surligne un objet : une surcouche translucide sur tous ses maillages (aucun matériau d'asset n'est modifié).
func _set_hover(node: Node3D) -> void:
	if node == _hover_node:
		return
	_overlay(_hover_node, null)
	_hover_node = node
	_overlay(node, _highlight)


func _overlay(node: Node3D, material: Material) -> void:
	if node == null or not is_instance_valid(node):
		return
	for mesh: Node in node.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).material_overlay = material


static func _make_highlight() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	material.albedo_color = Color(UiTokens.LIME, 0.55)
	material.grow = true
	material.grow_amount = 0.02
	return material
