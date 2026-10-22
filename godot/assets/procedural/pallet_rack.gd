@tool
extends GmixAsset
## Rayonnage à palettes : travées de 2,7 m (3 palettes Europe présentées côté 800 mm), niveaux de 1,6 m,
## profondeur 1,1 m (les palettes de 1,2 m débordent de 5 cm de chaque côté, comme en vrai).
## `fill_level` (0 à 1) remplit les emplacements du bas vers le haut : le stock se voit dans le monde.
## Variantes : niveau_remplissage, travees, niveaux.

const BAY_WIDTH := 2.7
const DEPTH := 1.1
const LEVEL_HEIGHT := 1.6
const PALLET_SCENE := "res://assets/industrial/prop_pallet/prop_pallet.tscn"

@export_range(1, 8) var bays := 2:
	set(value):
		bays = value
		_rebuild()
@export_range(1, 5) var levels := 3:
	set(value):
		levels = value
		_rebuild()
@export_range(0.0, 1.0, 0.05) var fill_level := 0.6:
	set(value):
		fill_level = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func capacity() -> int:
	return bays * levels * 3


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var upright := Mesher.material(Color(0.17, 0.33, 0.66))
	var beam := Mesher.material(Color(0.96, 0.52, 0.12))
	var total_width := bays * BAY_WIDTH
	var height := levels * LEVEL_HEIGHT + 0.3
	for i in range(bays + 1):
		var x := -total_width / 2.0 + i * BAY_WIDTH
		for z in [-DEPTH / 2.0, DEPTH / 2.0]:
			Mesher.box(self, Vector3(0.08, height, 0.08), Vector3(x, height / 2.0, z), upright)
		for k in range(levels + 1):  # entretoises du cadre
			Mesher.box(self, Vector3(0.04, 0.04, DEPTH), Vector3(x, 0.3 + k * LEVEL_HEIGHT * 0.95, 0), upright)
	var slots: Array[Vector3] = []
	for level in range(levels):
		var beam_y := 0.12 + level * LEVEL_HEIGHT
		for bay in range(bays):
			var center_x := -total_width / 2.0 + (bay + 0.5) * BAY_WIDTH
			for z in [-DEPTH / 2.0, DEPTH / 2.0]:
				Mesher.box(self, Vector3(BAY_WIDTH - 0.08, 0.1, 0.06), Vector3(center_x, beam_y, z), beam)
			for slot in range(3):
				slots.append(Vector3(center_x + (slot - 1) * 0.86, beam_y + 0.05, 0))
	var pallet_scene := load(PALLET_SCENE) as PackedScene
	if pallet_scene == null:
		return
	for i in range(roundi(fill_level * slots.size())):
		var pallet := pallet_scene.instantiate() as Node3D
		pallet.rotation.y = PI / 2.0  # côté 800 mm en façade, 1 200 mm en profondeur
		pallet.position = slots[i]
		Mesher.adopt(self, pallet)
