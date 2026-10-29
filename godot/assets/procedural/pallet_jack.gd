@tool
extends GmixAsset
## Transpalette manuel : deux fourches de 1,15 m (avant vers +Z), carter de pompe jaune et timon incliné vers l'arrière.
## Variante : chargee (une palette Europe chargée posée sur les fourches).
## Emprise : 0,56 (X) x 1,55 (Z) x 1,2 m. Collision : un bloc (à retirer si le monde déplace l'engin).

const PALLET_SCENE := "res://assets/industrial/prop_pallet/prop_pallet.tscn"

@export var loaded := false:
	set(value):
		loaded = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var yellow := Color(0.97, 0.76, 0.12)
	var dark := Color(0.17, 0.18, 0.2)
	var steel := Color(0.5, 0.52, 0.56)
	var batch := Mesher.Batch.new()
	for x in [-0.2, 0.2]:
		batch.box(Vector3(0.16, 0.06, 1.15), Vector3(x, 0.06, 0.2), steel)  # fourche
		batch.box(Vector3(0.12, 0.05, 0.1), Vector3(x, 0.035, 0.7), dark)  # galet de nez
		batch.cylinder(0.075, 0.05, Vector3(x, 0.075, -0.6), dark, Vector3.AXIS_X, 10)  # roue directrice
	batch.box(Vector3(0.54, 0.2, 0.4), Vector3(0, 0.2, -0.57), yellow)  # carter de pompe
	batch.box(Vector3(0.1, 0.9, 0.05), Vector3(0, 0.75, -0.67), steel, Vector3(-10, 0, 0))  # timon
	batch.box(Vector3(0.32, 0.04, 0.05), Vector3(0, 1.19, -0.75), dark)  # poignée
	batch.box(Vector3(0.05, 0.12, 0.05), Vector3(0.1, 1.11, -0.75), yellow)  # levier de levage
	batch.build(self)
	if loaded:
		var scene := load(PALLET_SCENE) as PackedScene
		if scene != null:
			var pallet := scene.instantiate() as Node3D
			pallet.rotation.y = PI / 2.0  # grand côté (1,2 m) le long des fourches
			pallet.position = Vector3(0, 0.09, 0.2)
			pallet.set("load_height", 0.7)
			Mesher.adopt(self, pallet)
	Mesher.collider(self, [[Vector3(0.56, 1.2, 1.55), Vector3(0, 0.6, 0)]])
