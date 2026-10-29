@tool
extends GmixAsset
## Étagère métallique à bacs bleus (1,2 x 0,5 x 1,9 m) pour les pièces de rechange et consommables de la
## maintenance : 4 niveaux de bacs ouverts sur la face +Z. Collision : un bloc.

const W := 1.2
const D := 0.5
const H := 1.9


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var batch := Mesher.Batch.new()
	for x in [-W / 2.0 + 0.025, W / 2.0 - 0.025]:
		for z in [-D / 2.0 + 0.025, D / 2.0 - 0.025]:
			batch.box(Vector3(0.05, H, 0.05), Vector3(x, H / 2.0, z), Palette.STEEL_DARK)  # montants
	var levels := [0.1, 0.55, 1.0, 1.45]
	for y in levels:
		batch.box(Vector3(W, 0.03, D), Vector3(0, y, 0), Palette.STEEL)  # tablette
		for i in 3:
			var x := -0.38 + i * 0.38
			batch.box(Vector3(0.34, 0.26, 0.4), Vector3(x, y + 0.145, 0.02), Palette.BLUE)  # bac
			batch.box(Vector3(0.3, 0.02, 0.02), Vector3(x, y + 0.2, 0.225), Palette.LABEL_TEXT)  # étiquette
	batch.box(Vector3(W, 0.03, D), Vector3(0, H - 0.015, 0), Palette.STEEL)  # plateau haut
	batch.box(Vector3(W, 1.7, 0.02), Vector3(0, 0.95, -D / 2.0 + 0.01), Palette.STEEL_LIGHT)  # fond
	batch.build(self)
	Mesher.collider(self, [[Vector3(W, H, D), Vector3(0, H / 2.0, 0)]])
