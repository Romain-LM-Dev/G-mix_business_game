class_name GmixPlayer
extends CharacterBody3D
## Joueur à la troisième personne. Touches physiques : ZQSD sur un clavier AZERTY (WASD en QWERTY), Maj pour
## courir, Espace pour sauter ; caméra à la souris quand elle est capturée (le monde la capture et la libère).

const WALK_SPEED := 4.5
const RUN_SPEED := 8.0
const JUMP_SPEED := 4.5
const MOUSE_SENSITIVITY := 0.004

## Modèle du catalogue (personnage animé) ; à renseigner avant l'ajout à la scène.
var model_scene: PackedScene
var controls_enabled := true

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")
var _pivot := Node3D.new()
var _arm := SpringArm3D.new()
var _model: Node3D
var _animation := ""


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
	var camera := Camera3D.new()
	camera.fov = 70.0
	camera.current = true
	_arm.add_child(camera)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion := event as InputEventMouseMotion
		_pivot.rotation.y -= motion.relative.x * MOUSE_SENSITIVITY
		_arm.rotation.x = clampf(_arm.rotation.x - motion.relative.y * MOUSE_SENSITIVITY, -1.2, 0.35)


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta
	var input := Vector2.ZERO
	if controls_enabled:
		input = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := (_pivot.global_basis * Vector3(input.x, 0, input.y))
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
	if controls_enabled and Input.is_action_just_pressed("jump") and is_on_floor():
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


## Orientation et animation diffusées aux autres joueurs (Presence).
func model_yaw() -> float:
	return _model.rotation.y if _model != null else 0.0


func animation_name() -> String:
	return _animation


func _animate(animation: String) -> void:
	if animation != _animation and _model != null:
		_animation = animation
		_model.set("animation", animation)
