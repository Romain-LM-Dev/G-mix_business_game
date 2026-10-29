@tool
extends GmixAsset
## Filmeuse de palettes : plateau tournant de 1,7 m sur un socle, mât porte-bobine de 2,4 m au fond (-Z) avec
## chariot et bobine de film étirable, coffret de commande jaune. La palette entre par l'avant (+Z).
## Emprise : 1,9 (X) x 2,2 (Z) x 2,4 m. Un seul maillage fusionné ; collision : un bloc sur toute l'emprise.


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var base := Color(0.3, 0.33, 0.38)
	var plate := Color(0.78, 0.8, 0.84)
	var blue := Color(0.2, 0.4, 0.7)
	var yellow := Color(0.97, 0.76, 0.12)
	var film := Color(0.9, 0.94, 0.98)
	var batch := Mesher.Batch.new()
	batch.box(Vector3(1.9, 0.1, 2.2), Vector3(0, 0.05, 0), base)  # socle
	batch.cylinder(0.85, 0.1, Vector3(0, 0.15, 0.1), plate, Vector3.AXIS_Y, 24)  # plateau tournant
	batch.cylinder(0.2, 0.02, Vector3(0, 0.21, 0.1), base, Vector3.AXIS_Y, 12)  # moyeu
	batch.box(Vector3(0.9, 0.012, 0.06), Vector3(0, 0.206, 0.1), yellow)  # repère de centrage
	batch.box(Vector3(0.06, 0.012, 0.9), Vector3(0, 0.206, 0.1), yellow)
	batch.box(Vector3(0.4, 0.06, 0.5), Vector3(0, 0.13, -0.85), base)  # pied du mât
	batch.box(Vector3(0.22, 2.4, 0.22), Vector3(0, 1.2, -0.95), Color(0.55, 0.58, 0.62))  # mât
	batch.box(Vector3(0.36, 0.5, 0.3), Vector3(0, 1.3, -0.72), blue)  # chariot porte-bobine
	batch.cylinder(0.14, 0.46, Vector3(0, 1.3, -0.52), film, Vector3.AXIS_Y, 12)  # bobine de film
	batch.box(Vector3(0.04, 0.54, 0.04), Vector3(0, 1.3, -0.52), base)  # axe de bobine
	batch.box(Vector3(0.26, 0.38, 0.14), Vector3(0.3, 1.2, -0.9), yellow)  # coffret de commande
	batch.box(Vector3(0.16, 0.1, 0.02), Vector3(0.3, 1.3, -0.82), Color(0.15, 0.4, 0.3))  # afficheur
	batch.box(Vector3(0.1, 0.06, 0.02), Vector3(0.3, 1.14, -0.82), Color(0.8, 0.12, 0.1))  # arrêt d'urgence
	batch.build(self)
	Mesher.collider(self, [[Vector3(1.9, 2.4, 2.2), Vector3(0, 1.2, 0)]])
