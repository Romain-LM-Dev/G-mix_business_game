class_name GmixNpc
extends Node3D
## PNJ expert de la spec : personnage du catalogue, nom et métier au-dessus de la tête. Le dialogue passe par
## l'API (player.intent puis npc.dialogue) ; ici, seulement l'apparence et l'orientation vers le joueur.

## Entrée `npcs` de la spec : {id, name, job, personality, expertise, dialogue_goals, zone}.
var data: Dictionary = {}
var model_scene: PackedScene


func _ready() -> void:
	if model_scene != null:
		add_child(model_scene.instantiate())
	var label := Label3D.new()
	label.text = "%s\n%s" % [data.get("name", "?"), data.get("job", "")]
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 48
	label.pixel_size = 0.009
	label.outline_size = 10
	label.position.y = 2.3
	add_child(label)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var cylinder := CylinderShape3D.new()
	cylinder.radius = 0.4
	cylinder.height = 1.8
	shape.shape = cylinder
	shape.position.y = 0.9
	body.add_child(shape)
	add_child(body)


## Se tourne vers un point (le joueur qui lui parle) ; l'avant des assets est +Z.
func face(point: Vector3) -> void:
	var target := Vector3(point.x, global_position.y, point.z)
	if target.distance_to(global_position) > 0.1:
		look_at(target, Vector3.UP, true)
