@tool
extends GmixAsset
## Marquage au sol d'une zone (département, dépose, quarantaine, conforme, à retoucher) : aplat de la couleur
## `color` bordé d'un ruban plein, avec `title` écrit à plat près du bord avant (+Z). Un seul maillage, 2 cm de
## haut, AUCUNE collision : ce n'est pas un obstacle pour la navigation (aucun CollisionObject3D dans l'asset).
## Propriétés : title, color, size (largeur X, profondeur Z, en m). Variantes : titre, couleur, taille.
## Zones imbriquées : décaler la zone intérieure de 5 mm en Y par niveau (sinon scintillement).

const BORDER := 0.12
const THICKNESS := 0.012  # l'aplat ; le ruban fait 2 cm

@export var title := "":
	set(value):
		title = value
		_rebuild()
@export var color := Palette.OCHRE:
	set(value):
		color = value
		_rebuild()
@export var size := Vector2(4.0, 3.0):
	set(value):
		size = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var w := maxf(size.x, 4.0 * BORDER)
	var d := maxf(size.y, 4.0 * BORDER)
	var fill := color.lerp(Palette.WALL_LIGHT, 0.72)
	var batch := Mesher.Batch.new()
	batch.box(Vector3(w, THICKNESS, d), Vector3(0, THICKNESS / 2.0, 0), fill)
	for z in [-1.0, 1.0]:
		batch.box(Vector3(w, 0.02, BORDER), Vector3(0, 0.01, z * (d - BORDER) / 2.0), color)
	for x in [-1.0, 1.0]:
		batch.box(Vector3(BORDER, 0.02, d - 2.0 * BORDER), Vector3(x * (w - BORDER) / 2.0, 0.01, 0), color)
	batch.build(self)
	if title.is_empty():
		return
	var line := clampf(minf(d * 0.16, w * 0.9 / maxf(title.length(), 1.0) * 1.6), 0.2, 0.8)  # hauteur de ligne visée (m)
	var label := Label3D.new()
	label.text = title
	label.font_size = 64
	label.pixel_size = line / 64.0
	label.outline_size = 10
	label.outline_modulate = Palette.WALL_LIGHT
	label.modulate = Palette.DARK_TEAL
	label.double_sided = false
	label.rotation_degrees = Vector3(-90, 0, 0)  # à plat, lisible depuis +Z
	label.position = Vector3(0, 0.03, d / 2.0 - BORDER - line * 0.8)
	Mesher.adopt(self, label)
