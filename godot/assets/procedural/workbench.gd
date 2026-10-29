@tool
extends GmixAsset
## Établi de maintenance (plan en bois à 0,88 m, tablette basse, étau, caisse à outils, clé et marteau) et servante
## d'outils rouge à roulettes à sa droite (+X). Le technicien se tient côté +Z.
## Emprise : 2,6 (X) x 0,8 (Z) x 1,05 m. Un seul maillage fusionné ; collision : l'établi et la servante.

const TOP := 0.88


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var wood := Color(0.7, 0.54, 0.34)
	var frame := Color(0.28, 0.36, 0.46)
	var steel := Color(0.62, 0.65, 0.7)
	var red := Color(0.76, 0.15, 0.12)
	var dark := Color(0.16, 0.17, 0.2)
	var batch := Mesher.Batch.new()
	batch.box(Vector3(1.9, 0.05, 0.75), Vector3(-0.35, TOP - 0.025, 0), wood)  # plan de travail
	for x in [-1.25, 0.55]:
		for z in [-0.33, 0.33]:
			batch.box(Vector3(0.06, TOP - 0.05, 0.06), Vector3(x, (TOP - 0.05) / 2.0, z), frame)  # pieds
	batch.box(Vector3(1.8, 0.04, 0.68), Vector3(-0.35, 0.25, 0), frame)  # tablette basse
	batch.box(Vector3(1.8, 0.06, 0.04), Vector3(-0.35, TOP - 0.08, 0.34), frame)  # traverses
	batch.box(Vector3(1.8, 0.06, 0.04), Vector3(-0.35, TOP - 0.08, -0.34), frame)
	batch.box(Vector3(0.18, 0.12, 0.22), Vector3(-1.1, TOP + 0.06, 0.18), Color(0.3, 0.34, 0.42))  # étau : corps
	batch.box(Vector3(0.18, 0.1, 0.04), Vector3(-1.1, TOP + 0.17, 0.3), Color(0.3, 0.34, 0.42))  # mâchoire
	batch.box(Vector3(0.2, 0.025, 0.025), Vector3(-1.1, TOP + 0.1, 0.34), steel, Vector3(0, 25, 0))  # vis de serrage
	batch.box(Vector3(0.45, 0.14, 0.22), Vector3(-0.35, TOP + 0.07, -0.05), red)  # caisse à outils
	batch.box(Vector3(0.3, 0.025, 0.03), Vector3(-0.35, TOP + 0.16, -0.05), dark)  # poignée
	batch.box(Vector3(0.3, 0.015, 0.04), Vector3(0.15, TOP + 0.008, 0.15), steel, Vector3(0, 20, 0))  # clé plate
	batch.box(Vector3(0.28, 0.03, 0.03), Vector3(0.15, TOP + 0.015, -0.12), wood, Vector3(0, -15, 0))  # marteau : manche
	batch.box(Vector3(0.1, 0.05, 0.05), Vector3(0.28, TOP + 0.025, -0.15), dark, Vector3(0, -15, 0))  # marteau : tête
	batch.box(Vector3(0.62, 0.8, 0.48), Vector3(1.0, 0.48, 0), red)  # servante
	batch.box(Vector3(0.64, 0.03, 0.5), Vector3(1.0, 0.895, 0), dark)  # dessus
	for y in [0.3, 0.46, 0.62, 0.78]:
		batch.box(Vector3(0.3, 0.025, 0.02), Vector3(1.0, y, 0.25), steel)  # poignées de tiroirs
		batch.box(Vector3(0.58, 0.008, 0.01), Vector3(1.0, y - 0.07, 0.241), dark)  # joints de tiroirs
	for x in [0.74, 1.26]:
		for z in [-0.17, 0.17]:
			batch.cylinder(0.04, 0.04, Vector3(x, 0.04, z), dark, Vector3.AXIS_X, 8)  # roulettes
	batch.build(self)
	Mesher.collider(self, [
		[Vector3(1.9, 0.93, 0.75), Vector3(-0.35, 0.465, 0)],
		[Vector3(0.62, 0.92, 0.48), Vector3(1.0, 0.46, 0)],
	])
