@tool
extends GmixAsset
## Écran des KPI sur pieds (panneau 3 x 1,8 m, bas à 1,2 m) : le jeu y affiche les indicateurs de la partie.
## Variantes : titre, indicateurs. Face vers +Z.

const PANEL := Vector2(3.0, 1.8)
const BOTTOM := 1.2

@export var title := "Indicateurs":
	set(value):
		title = value
		_refresh_text()
@export_multiline var body := "Taux de service : 94 %\nCouverture de stock : 32 j\nTrésorerie : 150 k€":
	set(value):
		body = value
		_refresh_text()

var _title_label: Label3D
var _body_label: Label3D


func _ready() -> void:
	super()
	_rebuild()


## kpis : [{name, value, unit}] ; appelé par le jeu à chaque mise à jour de l'état.
func show_kpis(kpis: Array) -> void:
	var lines := PackedStringArray()
	for kpi: Dictionary in kpis:
		lines.append("%s : %s %s" % [kpi.get("name", "?"), kpi.get("value", "-"), kpi.get("unit", "")])
	body = "\n".join(lines)


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var frame := Mesher.material(Palette.DARK_TEAL, Color.BLACK, "steel")
	var screen := Mesher.material(Palette.LABEL_OUTLINE, Palette.LABEL_OUTLINE * 0.5)
	var center_y := BOTTOM + PANEL.y / 2.0
	for x in [-1.2, 1.2]:
		Mesher.box(self, Vector3(0.1, BOTTOM + 0.2, 0.1), Vector3(x, (BOTTOM + 0.2) / 2.0, 0), frame)  # pieds
		Mesher.box(self, Vector3(0.12, 0.05, 0.6), Vector3(x, 0.025, 0), frame)  # semelles
	Mesher.box(self, Vector3(PANEL.x + 0.1, PANEL.y + 0.1, 0.12), Vector3(0, center_y, 0), frame)
	Mesher.box(self, Vector3(PANEL.x, PANEL.y, 0.02), Vector3(0, center_y, 0.065), screen)
	_title_label = _label(64, Vector3(-PANEL.x / 2.0 + 0.12, BOTTOM + PANEL.y - 0.12, 0.08))
	_body_label = _label(44, Vector3(-PANEL.x / 2.0 + 0.12, BOTTOM + PANEL.y - 0.5, 0.08))
	_refresh_text()


func _label(font_size: int, at: Vector3) -> Label3D:
	var label := Label3D.new()
	label.font_size = font_size
	label.pixel_size = 0.005
	label.outline_size = 0
	label.double_sided = false  # vu de dos, l'écran reste muet au lieu d'afficher le texte en miroir
	label.modulate = Palette.LABEL_TEXT
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	label.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.width = (PANEL.x - 0.24) / label.pixel_size
	label.position = at
	Mesher.adopt(self, label)
	return label


func _refresh_text() -> void:
	if _title_label != null:
		_title_label.text = title
		_body_label.text = body
