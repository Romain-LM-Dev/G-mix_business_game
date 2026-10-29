@tool
extends GmixAsset
## Tableau d'affichage sur pieds (panneau blanc de 1,7 x 0,9 m, bas à 0,85 m, bandeau-titre vert) : suivi d'une
## ligne (OF en cours) ou liste des interventions. Face vers +Z. Se pose n'importe où dans le hall.
## Propriétés : title (bandeau, le texte rétrécit pour tenir), lines (textes, une ligne par entrée ; 6 lignes
## visibles, 30 caractères au plus, le reste est coupé par « … »). Variantes : titre, lignes.
## Emprise : 1,8 (X) x 0,5 (Z) x 1,9 m. Collision : le panneau et les deux pieds.

const MAX_LINES := 6
const MAX_CHARS := 30
const TITLE_WIDTH := 1.6  # largeur utile du bandeau (m) : le titre rétrécit pour y tenir

@export var title := "Tableau":
	set(value):
		title = value
		_refresh()
@export var lines: Array = []:
	set(value):
		lines = value
		_refresh()

var _title_label: Label3D
var _body_label: Label3D


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var frame := Color(0.2, 0.22, 0.26)
	var batch := Mesher.Batch.new()
	for x in [-0.8, 0.8]:
		batch.box(Vector3(0.06, 0.85, 0.06), Vector3(x, 0.425, 0), frame)  # pieds
		batch.box(Vector3(0.1, 0.05, 0.5), Vector3(x, 0.025, 0), frame)  # semelles
	batch.box(Vector3(1.8, 1.0, 0.06), Vector3(0, 1.35, 0), frame)  # cadre
	batch.box(Vector3(1.7, 0.9, 0.02), Vector3(0, 1.35, 0.035), Color(0.96, 0.97, 0.98))  # surface blanche
	batch.box(Vector3(1.7, 0.2, 0.022), Vector3(0, 1.7, 0.036), Color(0.15, 0.5, 0.45))  # bandeau-titre
	batch.build(self)
	_title_label = _label(56, Vector3(-0.8, 1.7, 0.05), Color.WHITE, 0.0032)
	_body_label = _label(34, Vector3(-0.8, 1.55, 0.05), Color(0.1, 0.12, 0.16), 0.0028)
	Mesher.collider(self, [
		[Vector3(1.8, 1.9, 0.12), Vector3(0, 0.95, 0)],
		[Vector3(0.1, 0.1, 0.5), Vector3(-0.8, 0.05, 0)],
		[Vector3(0.1, 0.1, 0.5), Vector3(0.8, 0.05, 0)],
	])
	_refresh()


func _label(font_size: int, at: Vector3, color: Color, pixel_size: float) -> Label3D:
	var label := Label3D.new()
	label.font_size = font_size
	label.pixel_size = pixel_size
	label.outline_size = 0
	label.modulate = color
	label.double_sided = false  # vu de dos, le tableau reste muet au lieu d'afficher le texte en miroir
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	label.vertical_alignment = VERTICAL_ALIGNMENT_TOP if font_size < 50 else VERTICAL_ALIGNMENT_CENTER
	label.position = at
	Mesher.adopt(self, label)
	return label


func _refresh() -> void:
	if _title_label == null:
		return
	_title_label.text = title
	_title_label.pixel_size = clampf(TITLE_WIDTH / (maxf(title.length(), 1.0) * 56.0 * 0.55), 0.0015, 0.0032)
	var shown := PackedStringArray()
	for line in lines.slice(0, MAX_LINES):
		var text := str(line)
		shown.append(text if text.length() <= MAX_CHARS else text.left(MAX_CHARS - 1) + "…")
	_body_label.text = "\n".join(shown)
