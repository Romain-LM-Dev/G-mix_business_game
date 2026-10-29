@tool
extends GmixAsset
## Table de contrôle qualité : plan de travail clair à 0,88 m, caisson à tiroirs, pied à coulisse, jauge à cadran,
## pièces à contrôler, bac turquoise, lampe articulée et petit écran. Le contrôleur se tient côté +Z.
## Emprise : 1,8 (X) x 0,9 (Z) x 1,4 m (lampe comprise). Un seul maillage fusionné ; collision : un bloc.

const TOP := 0.88


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var white := Palette.WALL_LIGHT
	var steel := Palette.STEEL_LIGHT
	var shiny := Palette.STEEL_PALE
	var dark := Palette.DARK
	var batch := Mesher.Batch.new()
	batch.box(Vector3(1.8, 0.04, 0.9), Vector3(0, TOP - 0.02, 0), white)  # plan de travail
	batch.box(Vector3(1.7, 0.06, 0.8), Vector3(0, TOP - 0.07, 0), steel)  # chant
	for x in [-0.84, 0.84]:
		for z in [-0.38, 0.38]:
			batch.box(Vector3(0.05, TOP - 0.04, 0.05), Vector3(x, (TOP - 0.04) / 2.0, z), steel)  # pieds
	batch.box(Vector3(1.0, 0.03, 0.78), Vector3(-0.35, 0.22, 0), steel)  # tablette basse
	batch.box(Vector3(0.5, 0.62, 0.78), Vector3(0.58, 0.53, 0), Palette.MACHINE_ACCENTS[0])  # caisson à tiroirs
	for y in [0.32, 0.53, 0.74]:
		batch.box(Vector3(0.22, 0.025, 0.02), Vector3(0.58, y, 0.4), shiny)  # poignées
	batch.box(Vector3(0.28, 0.01, 0.035), Vector3(-0.55, TOP + 0.005, 0.2), shiny)  # pied à coulisse : règle
	batch.box(Vector3(0.015, 0.012, 0.075), Vector3(-0.67, TOP + 0.006, 0.2), shiny)  # bec fixe
	batch.box(Vector3(0.03, 0.02, 0.06), Vector3(-0.58, TOP + 0.01, 0.2), dark)  # coulisseau
	batch.box(Vector3(0.14, 0.1, 0.12), Vector3(-0.2, TOP + 0.05, 0.05), dark)  # jauge à cadran
	batch.cylinder(0.04, 0.02, Vector3(-0.2, TOP + 0.06, 0.12), Palette.WALL_LIGHT, Vector3.AXIS_Z, 10)  # cadran
	for at in [Vector3(0.12, 0, 0.15), Vector3(0.2, 0, 0.0), Vector3(0.05, 0, -0.1)]:
		batch.box(Vector3(0.09, 0.05, 0.07), Vector3(at.x, TOP + 0.025, at.z), shiny, Vector3(0, at.x * 100.0, 0))  # pièces
	batch.box(Vector3(0.34, 0.12, 0.26), Vector3(0.38, TOP + 0.06, 0.12), Palette.TURQUOISE)  # bac turquoise
	batch.box(Vector3(0.28, 0.03, 0.2), Vector3(0.38, TOP + 0.125, 0.12), Palette.CARDBOARD)
	batch.cylinder(0.07, 0.03, Vector3(-0.72, TOP + 0.015, -0.3), dark, Vector3.AXIS_Y, 10)  # lampe : socle
	batch.box(Vector3(0.025, 0.26, 0.025), Vector3(-0.72, TOP + 0.16, -0.3), steel)  # bras vertical
	batch.box(Vector3(0.025, 0.3, 0.025), Vector3(-0.72, TOP + 0.35, -0.2), steel, Vector3(50, 0, 0))  # bras incliné vers l'avant
	batch.box(Vector3(0.34, 0.04, 0.12), Vector3(-0.72, TOP + 0.5, -0.08), white)  # tube lumineux
	batch.box(Vector3(0.3, 0.2, 0.03), Vector3(0.1, TOP + 0.2, -0.32), dark)  # écran
	batch.box(Vector3(0.26, 0.16, 0.01), Vector3(0.1, TOP + 0.2, -0.305), Palette.SCREEN)
	batch.box(Vector3(0.06, 0.1, 0.06), Vector3(0.1, TOP + 0.05, -0.32), steel)  # pied d'écran
	batch.build(self)
	Mesher.collider(self, [[Vector3(1.8, 0.88, 0.9), Vector3(0, 0.44, 0)]])
