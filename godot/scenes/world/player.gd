class_name GmixPlayer
extends CharacterBody3D
## Joueur, avec deux modes de déplacement. Troisième personne : ZQSD sur un clavier AZERTY (WASD en QWERTY), Maj pour
## courir, Espace pour sauter, caméra à la souris quand elle est capturée. Vue Sims : le joueur ne bouge que par
## `walk_to()` (clic pour marcher), sur le maillage de navigation du monde ; la caméra est alors celle de GmixSimsView.
## Le monde choisit le mode (`set_third_person`) ; Presence lit la position, `model_yaw()` et `animation_name()`.

## Fin d'une marche ordonnée par `walk_to()` : `reached` est faux si elle est interrompue, bloquée ou sans chemin.
signal walk_finished(reached: bool)

const WALK_SPEED := 4.5
const RUN_SPEED := 8.0
const JUMP_SPEED := 4.5
const MOUSE_SENSITIVITY := 0.004
const NPC_LAYER := 4  # couche physique des agents : bloquent le joueur à la troisième personne, pas en vue Sims
const BLOCK_LAYER := 16  # emprises ajoutées par le monde aux assets sans collision : bloquent le joueur, jamais la sélection au curseur
const MAX_SNAP := 2.5  # m : un clic plus loin que cela du maillage de navigation n'est pas une destination
const REACH_SLACK := 0.6  # m : marche finie à moins de `stop_distance` + cette marge du but = arrivée
const STUCK_S := 1.2  # s sans avancer avant d'abandonner la marche

## Modèle du catalogue (personnage animé) ; à renseigner avant l'ajout à la scène.
var model_scene: PackedScene
var controls_enabled := true

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _pivot := Node3D.new()
var _arm := SpringArm3D.new()
var _camera := Camera3D.new()
var _nav := NavigationAgent3D.new()
var _model: Node3D
var _animation := ""
var _third_person := true
var _walking := false
var _goal := Vector3.ZERO
var _stop_distance := 0.3
var _stuck := 0.0


func _ready() -> void:
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.35
	capsule.height = 1.8
	shape.shape = capsule
	shape.position.y = 0.9
	add_child(shape)
	if model_scene != null:
		_model = model_scene.instantiate() as Node3D
		add_child(_model)
	_pivot.position.y = 1.6
	add_child(_pivot)
	_arm.spring_length = 5.5
	_arm.margin = 0.2
	_arm.rotation.x = -0.35
	_arm.add_excluded_object(get_rid())
	_pivot.add_child(_arm)
	_camera.fov = 70.0
	_arm.add_child(_camera)
	_nav.avoidance_enabled = false
	_nav.path_desired_distance = 0.4
	add_child(_nav)
	set_third_person(_third_person)


## Troisième personne (clavier, souris, caméra du joueur) ou vue Sims (clic pour marcher, caméra extérieure).
func set_third_person(active: bool) -> void:
	_third_person = active
	stop_walking()
	collision_mask = 1 | BLOCK_LAYER | (NPC_LAYER if active else 0)
	_camera.current = active


func is_third_person() -> bool:
	return _third_person


func _unhandled_input(event: InputEvent) -> void:
	if _third_person and event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion := event as InputEventMouseMotion
		_pivot.rotation.y -= motion.relative.x * MOUSE_SENSITIVITY
		_arm.rotation.x = clampf(_arm.rotation.x - motion.relative.y * MOUSE_SENSITIVITY, -1.2, 0.35)


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta
	var input := Vector2.ZERO
	if controls_enabled and _third_person:
		input = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if _walking and input != Vector2.ZERO:
		stop_walking()  # une touche de déplacement reprend la main
	var direction := Vector3.ZERO
	if _walking:
		direction = _path_direction(delta)
	elif input != Vector2.ZERO:
		direction = _pivot.global_basis * Vector3(input.x, 0, input.y)
		direction.y = 0
		direction = direction.normalized()
	var running := controls_enabled and Input.is_action_pressed("sprint")
	var speed := RUN_SPEED if running else WALK_SPEED
	if direction != Vector3.ZERO:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
		if _model != null:
			_model.rotation.y = lerp_angle(_model.rotation.y, atan2(direction.x, direction.z), 10.0 * delta)
	else:
		velocity.x = move_toward(velocity.x, 0, speed)
		velocity.z = move_toward(velocity.z, 0, speed)
	if controls_enabled and _third_person and Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = JUMP_SPEED
	move_and_slide()
	if not is_on_floor():
		_animate("jump")
	elif direction != Vector3.ZERO:
		_animate("sprint" if running else "walk")
	else:
		_animate("idle")


## Tourne la caméra (et le personnage) vers un point du monde ; la caméra regarde vers -Z du pivot.
func face_point(point: Vector3) -> void:
	var direction := point - global_position
	_pivot.rotation.y = atan2(-direction.x, -direction.z)
	if _model != null:
		_model.rotation.y = atan2(direction.x, direction.z)


## Oriente la caméra de troisième personne (même sens que la vue Sims : 0 = elle regarde vers -Z).
func set_camera_yaw(yaw: float) -> void:
	_pivot.rotation.y = yaw


## Orientation et animation diffusées aux autres joueurs (Presence).
func model_yaw() -> float:
	return _model.rotation.y if _model != null else 0.0


func animation_name() -> String:
	return _animation


# --- marche sur le maillage de navigation ----------------------------------------------------------------------


## Marche jusqu'à `point` (ramené sur le maillage de navigation) et s'arrête à `stop_distance` mètres du but.
## Faux si le maillage n'est pas prêt, si le point en est trop éloigné ou s'il n'y a aucun chemin.
func walk_to(point: Vector3, stop_distance := 0.3) -> bool:
	var map := get_world_3d().navigation_map
	if NavigationServer3D.map_get_iteration_id(map) == 0:
		return false
	var goal := NavigationServer3D.map_get_closest_point(map, Vector3(point.x, 0.0, point.z))
	if Vector2(goal.x - point.x, goal.z - point.z).length() > MAX_SNAP:
		return false
	if NavigationServer3D.map_get_path(map, global_position, goal, true).size() < 2 and _flat_distance(goal) > stop_distance:
		return false
	stop_walking()
	_goal = goal
	_stop_distance = stop_distance
	_stuck = 0.0
	_nav.target_desired_distance = stop_distance
	_nav.target_position = goal
	_walking = true
	return true


func is_walking() -> bool:
	return _walking


## Destination en cours (repère du monde) : le monde y pose son repère de clic.
func walk_goal() -> Vector3:
	return _goal


func stop_walking(reached := false) -> void:
	if not _walking:
		return
	_walking = false
	walk_finished.emit(reached)


## Direction horizontale du prochain point du chemin ; termine la marche à l'arrivée ou si le joueur est bloqué.
func _path_direction(delta: float) -> Vector3:
	var remaining := _flat_distance(_goal)
	if remaining <= _stop_distance or _nav.is_navigation_finished():
		stop_walking(remaining <= _stop_distance + REACH_SLACK)
		return Vector3.ZERO
	_stuck = _stuck + delta if get_real_velocity().length() < 0.3 else 0.0
	if _stuck > STUCK_S:
		stop_walking()
		return Vector3.ZERO
	var direction := _nav.get_next_path_position() - global_position
	direction.y = 0
	return direction.normalized()


func _flat_distance(point: Vector3) -> float:
	return Vector2(global_position.x - point.x, global_position.z - point.z).length()


func _animate(animation: String) -> void:
	if animation != _animation and _model != null:
		_animation = animation
		_model.set("animation", animation)
