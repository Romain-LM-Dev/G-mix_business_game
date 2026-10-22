class_name GmixRemoteAvatar
extends Node3D
## Autre joueur du lobby, piloté par les instantanés du serveur de partie (10 par seconde) : position lissée,
## orientation, animation, nom au-dessus de la tête.

const SMOOTHING := 12.0

var model_scene: PackedScene
var _model: Node3D
var _label := Label3D.new()
var _target := Vector3.ZERO
var _yaw := 0.0
var _animation := ""


func _ready() -> void:
	if model_scene != null:
		_model = model_scene.instantiate() as Node3D
		add_child(_model)
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.font_size = 36
	_label.pixel_size = 0.006
	_label.outline_size = 10
	_label.modulate = Color(0.75, 0.88, 1.0)
	_label.position.y = 2.2
	add_child(_label)


func apply(state: Dictionary, role_title: String) -> void:
	_label.text = "%s\n%s" % [state.get("name", "?"), role_title]
	var first := _target == Vector3.ZERO
	_target = state.get("position", Vector3.ZERO)
	if first:
		position = _target
	_yaw = float(state.get("yaw", 0.0))
	var animation := str(state.get("animation", "idle"))
	if animation != _animation and _model != null:
		_animation = animation
		_model.set("animation", animation)


func _process(delta: float) -> void:
	position = position.lerp(_target, minf(1.0, SMOOTHING * delta))
	if _model != null:
		_model.rotation.y = lerp_angle(_model.rotation.y, _yaw, minf(1.0, SMOOTHING * delta))
