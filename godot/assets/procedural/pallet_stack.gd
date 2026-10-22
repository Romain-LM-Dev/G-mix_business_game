@tool
extends GmixAsset
## Stock au sol : palettes Europe chargées, posées sur 2 rangées de 3 puis gerbées sur 2 niveaux
## (12 palettes au maximum). Variante : nombre_palettes.

const PALLET_SCENE := "res://assets/industrial/prop_pallet/prop_pallet.tscn"
const SPACING := Vector2(1.25, 0.85)
const STACK_HEIGHT := 1.18  # palette (0,144) + charge (1,0) + film

@export_range(0, 12) var pallet_count := 6:
	set(value):
		pallet_count = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var pallet_scene := load(PALLET_SCENE) as PackedScene
	if pallet_scene == null:
		return
	for i in range(pallet_count):
		var layer := i / 6
		var column := (i % 6) % 3
		var row := (i % 6) / 3
		var pallet := pallet_scene.instantiate() as Node3D
		pallet.position = Vector3((column - 1) * SPACING.x, layer * STACK_HEIGHT, (row - 0.5) * SPACING.y)
		Mesher.adopt(self, pallet)
