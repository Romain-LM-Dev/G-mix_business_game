@tool
extends GmixAsset
## Armoire de sécurité jaune (1,1 x 0,6 x 1,9 m) à deux portes battantes pour produits inflammables, huiles et
## solvants, avec pictogramme et bac de rétention. Portes en façade (+Z). Collision : un bloc.

const W := 1.1
const D := 0.6
const H := 1.9


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var batch := Mesher.Batch.new()
	var yellow := Palette.MARK_YELLOW
	batch.box(Vector3(W, 0.12, D), Vector3(0, 0.06, 0), Palette.DARK)  # socle de rétention
	batch.box(Vector3(W, H - 0.12, D - 0.04), Vector3(0, 0.12 + (H - 0.12) / 2.0, -0.02), yellow)  # caisson
	for side in [-1.0, 1.0]:
		batch.box(Vector3(W / 2.0 - 0.03, H - 0.2, 0.03), Vector3(side * (W / 4.0), 1.0, D / 2.0 - 0.015), yellow.darkened(0.08))  # porte
		batch.box(Vector3(0.03, 0.3, 0.04), Vector3(side * 0.06, 1.0, D / 2.0 + 0.02), Palette.DARK)  # poignée
	batch.box(Vector3(0.3, 0.3, 0.012), Vector3(0, 1.5, D / 2.0 + 0.008), Palette.ALERT, Vector3(0, 0, 45))  # pictogramme : losange
	batch.box(Vector3(0.1, 0.1, 0.014), Vector3(0, 1.5, D / 2.0 + 0.012), Palette.LABEL_TEXT, Vector3(0, 0, 45))
	batch.box(Vector3(W, 0.04, D), Vector3(0, H - 0.02, 0), Palette.STEEL_DARK)  # dessus
	batch.build(self)
	Mesher.collider(self, [[Vector3(W, H, D), Vector3(0, H / 2.0, 0)]])
