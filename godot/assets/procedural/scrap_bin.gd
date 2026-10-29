@tool
extends GmixAsset
## Bac à rebut rouge (0,8 x 0,6 x 0,8 m, étiqueté « REBUT » sur la face +Z) : le tas de pièces et une jauge à
## barre sur la face avant (lisible de loin) montent avec fill_level.
## Propriété : fill_level (0 à 1). Variante : niveau_remplissage. Collision : un bloc.

const FLOOR := 0.1  # dessus du fond intérieur
const STEPS := 20  # le tas n'est reconstruit que si son niveau change d'un vingtième

@export_range(0.0, 1.0, 0.01) var fill_level := 0.0:
	set(value):
		fill_level = clampf(value, 0.0, 1.0)
		_refresh()

var _heap: MeshInstance3D
var _shown := -1


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	_heap = null
	var red := Color(0.78, 0.14, 0.12)
	var dark_red := Color(0.55, 0.1, 0.09)
	var batch := Mesher.Batch.new()
	for x in [-0.36, 0.36]:
		batch.box(Vector3(0.08, 0.06, 0.08), Vector3(x, 0.03, 0.26), Color(0.15, 0.15, 0.17))  # patins
		batch.box(Vector3(0.08, 0.06, 0.08), Vector3(x, 0.03, -0.26), Color(0.15, 0.15, 0.17))
	batch.box(Vector3(0.8, 0.04, 0.6), Vector3(0, 0.08, 0), dark_red)  # fond
	batch.box(Vector3(0.8, 0.7, 0.03), Vector3(0, 0.43, 0.285), red)  # face avant
	batch.box(Vector3(0.8, 0.7, 0.03), Vector3(0, 0.43, -0.285), red)
	batch.box(Vector3(0.03, 0.7, 0.54), Vector3(-0.385, 0.43, 0), red)
	batch.box(Vector3(0.03, 0.7, 0.54), Vector3(0.385, 0.43, 0), red)
	for z in [-0.305, 0.305]:
		batch.box(Vector3(0.84, 0.04, 0.05), Vector3(0, 0.8, z), dark_red)  # rebord (le creux reste ouvert : on voit le tas)
	for x in [-0.405, 0.405]:
		batch.box(Vector3(0.05, 0.04, 0.56), Vector3(x, 0.8, 0), dark_red)
	batch.box(Vector3(0.06, 0.6, 0.012), Vector3(0.34, 0.42, 0.3), Color(0.3, 0.05, 0.05))  # jauge de niveau : fond
	batch.build(self)
	var label := Label3D.new()
	label.text = "REBUT"
	label.font_size = 48
	label.pixel_size = 0.0036
	label.outline_size = 8
	label.outline_modulate = Color(0.45, 0.06, 0.05)
	label.double_sided = false
	label.position = Vector3(-0.05, 0.58, 0.305)
	Mesher.adopt(self, label)
	Mesher.collider(self, [[Vector3(0.8, 0.8, 0.6), Vector3(0, 0.4, 0)]])
	_shown = -1
	_refresh()


func _refresh() -> void:
	var steps := roundi(fill_level * STEPS)
	if not is_node_ready() or steps == _shown:
		return
	_shown = steps
	if _heap != null:
		remove_child(_heap)
		_heap.queue_free()
		_heap = null
	if steps == 0:
		return
	var top := FLOOR + (0.72 - FLOOR) * steps / STEPS
	var batch := Mesher.Batch.new()
	batch.box(Vector3(0.7, top - FLOOR, 0.5), Vector3(0, (top + FLOOR) / 2.0, 0), Color(0.3, 0.31, 0.35))  # masse du tas
	var pieces := [Color(0.72, 0.74, 0.78), Color(0.9, 0.55, 0.15), Color(0.55, 0.58, 0.64)]
	for i in mini(steps, 6):  # pièces qui dépassent
		var at := Vector3(-0.22 + (i % 3) * 0.22, top + 0.02, -0.12 + (i / 3) * 0.24)
		batch.box(Vector3(0.14, 0.05, 0.1), at, pieces[i % 3], Vector3(10 * i, 35 * i, 8 * i))
	var bar := 0.6 * steps / STEPS
	batch.box(Vector3(0.04, bar, 0.014), Vector3(0.34, 0.12 + bar / 2.0, 0.3), Color(1.0, 0.93, 0.6))  # jauge de niveau : barre
	_heap = batch.build(self)
