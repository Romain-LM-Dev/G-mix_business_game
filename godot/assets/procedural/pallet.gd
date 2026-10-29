@tool
extends GmixAsset
## Palette Europe EPAL : 1 200 x 800 x 144 mm (3 semelles, 9 dés, 3 traverses, 5 planches de plateau),
## vide ou chargée de colis filmés. Variantes : chargee, hauteur_charge.

const LENGTH := 1.2
const WIDTH := 0.8
const HEIGHT := 0.144

@export var loaded := true:
	set(value):
		loaded = value
		_rebuild()
@export_range(0.2, 1.6, 0.05) var load_height := 1.0:
	set(value):
		load_height = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var wood := Palette.WOOD
	var block := Palette.WOOD_DARK
	var batch := Mesher.Batch.new()  # un seul maillage par palette (une vingtaine d'appels de rendu auparavant)
	for z in [-0.35, 0.0, 0.35]:
		batch.box(Vector3(LENGTH, 0.022, 0.1), Vector3(0, 0.011, z), wood)  # semelles
		batch.box(Vector3(LENGTH, 0.022, 0.1), Vector3(0, 0.111, z), wood)  # traverses
		for x in [-0.55, 0.0, 0.55]:
			batch.box(Vector3(0.14, 0.078, 0.1), Vector3(x, 0.061, z), block)  # dés
	for x in [-0.55, -0.275, 0.0, 0.275, 0.55]:
		batch.box(Vector3(0.1, 0.022, WIDTH), Vector3(x, 0.133, 0), wood)  # plateau
	if loaded:
		batch.box(Vector3(LENGTH - 0.04, load_height, WIDTH - 0.04), Vector3(0, HEIGHT + load_height / 2.0, 0), Palette.CARDBOARD)
		batch.box(Vector3(LENGTH - 0.02, 0.04, WIDTH - 0.02), Vector3(0, HEIGHT + load_height, 0), Palette.FILM)  # film
	batch.build(self)
