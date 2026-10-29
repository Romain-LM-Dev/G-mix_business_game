@tool
extends GmixAsset
## Assemblage d'assets du catalogue (ex. poste de travail = bureau + fauteuil + écran).
## `parts` : liste de [chemin de scène, position, rotation Y en degrés], positions en mètres.

@export var parts: Array = []:
	set(value):
		parts = value
		_rebuild()

## Collision de l'assemblage (taille d'une boîte posée au sol, centrée) ; nulle : celle des pièces seulement.
@export var solid_box := Vector3.ZERO:
	set(value):
		solid_box = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	for part: Array in parts:
		var scene := load(part[0]) as PackedScene
		if scene == null:
			push_warning("%s : pièce introuvable %s" % [asset_id, part[0]])
			continue
		var node := scene.instantiate() as Node3D
		node.position = part[1]
		node.rotation.y = deg_to_rad(part[2])
		Mesher.adopt(self, node)
	if solid_box != Vector3.ZERO:
		Mesher.collider(self, [[solid_box, Vector3(0, solid_box.y / 2.0, 0)]])
