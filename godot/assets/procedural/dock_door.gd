@tool
extends GmixAsset
## Porte de quai sectionnelle de 3 m (relevée : le passage est toujours libre) avec butoirs, rails, tablier de mise
## à niveau et un feu libre (vert) ou occupé (rouge) visible des deux côtés. Façade (+Z) = côté camions.
## Deux portes côte à côte (x = -1,5 et 1,5) couvrent l'ouverture de 6 m du plan (x de -3 à 3, z = 15), avec un
## montant commun de 0,3 m entre les deux passages.
## Propriété : state (« libre » ou « occupe »). Variante : etat.
## Collision : seulement les deux montants (butoirs compris). L'ouverture libre (2,7 m de large, 2,7 m de haut,
## x de -1,35 à 1,35) n'a AUCUN CollisionObject3D : elle ne compte pas comme obstacle pour la navigation.
## Emprise : 3,0 (X) x 0,5 (Z, façade et butoirs compris) x 3,6 m.

const WIDTH := 3.0
const HEIGHT := 3.6
const JAMB := 0.15
const OPENING_HEIGHT := 2.7
const LIT := {"libre": Color(0.2, 0.95, 0.35), "occupe": Color(1.0, 0.2, 0.15)}

@export_enum("libre", "occupe") var state := "libre":
	set(value):
		if not LIT.has(value):
			push_warning("%s : état inconnu « %s » (libre affiché)" % [asset_id, value])
			value = "libre"
		state = value
		_refresh()

var _lamps: MeshInstance3D


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	_lamps = null
	var gray := Color(0.52, 0.55, 0.6)
	var light := Color(0.84, 0.86, 0.88)
	var dark := Color(0.22, 0.24, 0.27)
	var yellow := Color(0.98, 0.78, 0.1)
	var batch := Mesher.Batch.new()
	for side in [-1.0, 1.0]:
		var x: float = side * (WIDTH - JAMB) / 2.0
		batch.box(Vector3(JAMB, HEIGHT, 0.3), Vector3(x, HEIGHT / 2.0, 0), gray)  # montant
		batch.box(Vector3(JAMB + 0.02, 0.5, 0.32), Vector3(x, 0.25, 0), yellow)  # protection de pied
		batch.box(Vector3(0.2, 0.3, 0.1), Vector3(x, 1.15, 0.2), dark)  # butoir en caoutchouc
		batch.box(Vector3(0.05, OPENING_HEIGHT, 0.06), Vector3(side * (WIDTH / 2.0 - JAMB - 0.025), OPENING_HEIGHT / 2.0, -0.18), dark)  # rail
		batch.box(Vector3(0.22, 0.46, 0.08), Vector3(x, 2.25, 0.19), dark)  # boîtier du feu, côté camions
		batch.box(Vector3(0.22, 0.46, 0.08), Vector3(x, 2.25, -0.19), dark)  # boîtier du feu, côté usine
	batch.box(Vector3(WIDTH, 0.9, 0.4), Vector3(0, OPENING_HEIGHT + 0.45, -0.05), light)  # caisson du tablier relevé
	for y in [2.95, 3.2, 3.45]:
		batch.box(Vector3(WIDTH - 2.0 * JAMB, 0.03, 0.02), Vector3(0, y, 0.16), gray)  # lames du tablier
	batch.box(Vector3(WIDTH - 2.0 * JAMB, 0.04, 0.35), Vector3(0, 0.02, 0.075), Color(0.4, 0.42, 0.46))  # tablier de mise à niveau
	batch.box(Vector3(WIDTH - 2.0 * JAMB, 0.045, 0.04), Vector3(0, 0.0225, 0.23), yellow)
	batch.build(self)
	Mesher.collider(self, [
		[Vector3(JAMB, HEIGHT, 0.4), Vector3(-(WIDTH - JAMB) / 2.0, HEIGHT / 2.0, 0.05)],
		[Vector3(JAMB, HEIGHT, 0.4), Vector3((WIDTH - JAMB) / 2.0, HEIGHT / 2.0, 0.05)],
	])
	_refresh()


func _refresh() -> void:
	if not is_node_ready():
		return
	if _lamps != null:
		remove_child(_lamps)
		_lamps.queue_free()
	var batch := Mesher.Batch.new()
	var x := (WIDTH - JAMB) / 2.0
	for z in [0.24, -0.24]:
		var green: Color = LIT["libre"]
		var red: Color = LIT["occupe"]
		batch.box(Vector3(0.12, 0.12, 0.02), Vector3(x, 2.1, z), green if state == "libre" else green.darkened(0.75))
		batch.box(Vector3(0.12, 0.12, 0.02), Vector3(x, 2.4, z), red if state == "occupe" else red.darkened(0.75))
	_lamps = batch.build(self, Mesher.vertex_material(true))
