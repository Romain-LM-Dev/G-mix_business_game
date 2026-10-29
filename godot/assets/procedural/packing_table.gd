@tool
extends GmixAsset
## Table d'emballage en inox (plan à 0,85 m) : carton monté ouvert, pile de cartons à plat, dévidoir de ruban
## adhésif et balance ; cartons à plat sur la tablette basse. L'emballeur se tient côté +Z.
## Emprise : 2,0 (X) x 0,9 (Z) x 1,2 m. Un seul maillage fusionné ; collision : un bloc.

const TOP := 0.85


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var steel := Palette.STEEL_PALE
	var frame := Palette.STEEL
	var kraft := Palette.CARDBOARD
	var kraft_dark := Palette.CARDBOARD_DARK
	var dark := Palette.DARK
	var batch := Mesher.Batch.new()
	batch.box(Vector3(2.0, 0.04, 0.9), Vector3(0, TOP - 0.02, 0), steel)  # plan de travail
	for x in [-0.94, 0.94]:
		for z in [-0.4, 0.4]:
			batch.box(Vector3(0.05, TOP - 0.04, 0.05), Vector3(x, (TOP - 0.04) / 2.0, z), frame)  # pieds
	batch.box(Vector3(1.9, 0.03, 0.8), Vector3(0, 0.25, 0), frame)  # tablette basse
	batch.box(Vector3(0.8, 0.14, 0.55), Vector3(-0.45, 0.335, 0), kraft)  # cartons à plat rangés dessous
	batch.box(Vector3(0.8, 0.04, 0.55), Vector3(-0.45, 0.42, 0), kraft_dark)
	batch.box(Vector3(0.5, 0.28, 0.38), Vector3(-0.55, TOP + 0.14, 0.0), kraft)  # carton monté
	batch.box(Vector3(0.42, 0.01, 0.3), Vector3(-0.55, TOP + 0.281, 0.0), kraft_dark)  # intérieur
	batch.box(Vector3(0.5, 0.02, 0.15), Vector3(-0.55, TOP + 0.34, 0.24), kraft, Vector3(-35, 0, 0))  # rabats
	batch.box(Vector3(0.5, 0.02, 0.15), Vector3(-0.55, TOP + 0.34, -0.24), kraft, Vector3(35, 0, 0))
	batch.box(Vector3(0.5, 0.1, 0.38), Vector3(0.1, TOP + 0.05, 0.05), kraft)  # pile de cartons à plat
	batch.box(Vector3(0.5, 0.04, 0.38), Vector3(0.12, TOP + 0.12, 0.04), kraft_dark, Vector3(0, 8, 0))
	batch.box(Vector3(0.14, 0.04, 0.22), Vector3(0.62, TOP + 0.02, 0.15), dark)  # dévidoir : socle
	batch.box(Vector3(0.1, 0.16, 0.03), Vector3(0.62, TOP + 0.1, 0.24), dark)  # flasque
	batch.cylinder(0.075, 0.1, Vector3(0.62, TOP + 0.13, 0.17), Palette.MARK_YELLOW, Vector3.AXIS_X, 10)  # rouleau de ruban
	batch.box(Vector3(0.32, 0.05, 0.3), Vector3(0.82, TOP + 0.025, -0.18), frame)  # balance : base
	batch.box(Vector3(0.28, 0.02, 0.26), Vector3(0.82, TOP + 0.06, -0.18), steel)  # plateau
	batch.box(Vector3(0.12, 0.06, 0.03), Vector3(0.82, TOP + 0.04, -0.03), Palette.OK)  # afficheur
	batch.build(self)
	Mesher.collider(self, [[Vector3(2.0, 0.85, 0.9), Vector3(0, 0.425, 0)]])
