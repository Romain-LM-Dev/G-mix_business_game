@tool
extends GmixAsset
## Table d'attente (tampon) entre deux machines : convoyeur à rouleaux basse (plateau à 0,48 m, pour s'aligner sur
## l'ouverture des machines), les pièces circulent le long de X vers +X. Les bacs turquoise posés dessus montrent le
## remplissage : jusqu'à 12 (2 rangées de 6), rangés depuis l'extrémité aval (+X). Une étiquette donne « n / capacité ».
## Propriétés : fill_level (0 à 1), capacity (places de la table). Variantes : niveau_remplissage, capacite.
## Emprise : 1,6 (X) x 0,9 (Z) x 0,65 m (bacs compris). Collision : un bloc.

const LENGTH := 1.6
const WIDTH := 0.9
const TOP := 0.48
const SLOTS := 12  # 6 colonnes x 2 rangées

@export_range(0.0, 1.0, 0.01) var fill_level := 0.0:
	set(value):
		fill_level = clampf(value, 0.0, 1.0)
		_refresh()
@export_range(1, 500) var capacity := 10:
	set(value):
		capacity = maxi(value, 1)
		_refresh()

var _bins: MeshInstance3D
var _label: Label3D
var _shown := -1  # nombre de bacs actuellement construits


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	_bins = null
	var steel := Palette.STEEL_DARK
	var frame := Palette.STATION_CONTROL
	var roller := Palette.STEEL_PALE
	var batch := Mesher.Batch.new()
	for x in [-0.72, 0.72]:
		for z in [-0.38, 0.38]:
			batch.box(Vector3(0.05, 0.42, 0.05), Vector3(x, 0.21, z), steel)  # pieds
	for z in [-0.4, 0.4]:
		batch.box(Vector3(LENGTH, 0.07, 0.05), Vector3(0, 0.43, z), frame)  # longerons
		batch.box(Vector3(LENGTH, 0.1, 0.03), Vector3(0, 0.53, z * 1.04), steel)  # guides latéraux
	for x in [-0.75, 0.75]:
		batch.box(Vector3(0.05, 0.05, WIDTH - 0.1), Vector3(x, 0.4, 0), steel)  # traverses
	for i in 15:
		batch.cylinder(0.03, WIDTH - 0.12, Vector3(-0.7 + i * 0.1, TOP - 0.03, 0), roller, Vector3.AXIS_Z, 6)  # rouleaux
	batch.build(self)
	_label = Label3D.new()
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.font_size = 40
	_label.pixel_size = 0.005
	_label.outline_size = 10
	_label.outline_modulate = Palette.LABEL_OUTLINE
	_label.position = Vector3(0, 0.95, 0)
	Mesher.adopt(self, _label)
	Mesher.collider(self, [[Vector3(LENGTH, 0.64, WIDTH), Vector3(0, 0.32, 0)]])
	_shown = -1
	_refresh()


func _refresh() -> void:
	if _label == null:
		return
	var pieces := roundi(fill_level * capacity)
	_label.text = "%d / %d" % [pieces, capacity]
	_label.modulate = Palette.OCHRE if fill_level >= 1.0 else (Palette.STEEL_PALE if pieces == 0 else Palette.LABEL_TEXT)
	var bins := 0 if pieces == 0 else clampi(ceili(fill_level * SLOTS), 1, SLOTS)
	if bins == _shown:
		return
	_shown = bins
	if _bins != null:
		remove_child(_bins)
		_bins.queue_free()
		_bins = null
	var batch := Mesher.Batch.new()
	for i in bins:
		var at := Vector3(0.6 - (i / 2) * 0.24, TOP + 0.07, 0.19 if i % 2 == 0 else -0.19)
		batch.box(Vector3(0.22, 0.14, 0.34), at, Palette.TURQUOISE)  # bac
		batch.box(Vector3(0.16, 0.03, 0.26), at + Vector3(0, 0.075, 0), Palette.CARDBOARD)  # pièces dans le bac
	_bins = batch.build(self)
