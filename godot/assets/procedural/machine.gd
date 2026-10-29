@tool
extends GmixAsset
## Machine d'un poste de ligne (M1 à M4) : machine.glb de Kenney Factory Kit (CC0, crédité avec prop_cnc_machine)
## à l'échelle 1,4, avec une colonne d'état sur le toit et l'étiquette du poste. Le modèle est un tunnel ouvert aux
## deux extrémités en X (les pièces circulent le long de X, de gauche à droite) ; sa fenêtre de contrôle est sur
## la face +Z (avant). Emprise : 1,68 (X) x 2,10 (Z) x 2,40 m (colonne comprise).
## Propriétés : title (ex. « M3 · Soudage »), state (MachineState). Variantes : titre, etat.
## Collision : un bloc plein sur le corps de la machine (pas sur la colonne, au-dessus de la tête).

const MODEL := "res://assets/_sources/kenney-factory-kit/machine.glb"
const MODEL_SCALE := 1.4  # 1,2 x 1,3 x 1,5 m d'origine -> 1,68 x 1,82 x 2,10 m
const BODY := Vector3(1.68, 1.82, 2.1)
## état -> [texte affiché, couleur du voyant, voyant allumé]
const STATES := {
	"arret": ["ARRÊT", Color(0.42, 0.44, 0.48), false],
	"marche": ["MARCHE", Color(0.2, 0.85, 0.3), true],
	"pause": ["PAUSE", Color(0.92, 0.93, 0.98), true],
	"reglage": ["RÉGLAGE", Color(0.25, 0.45, 1.0), true],
	"panne": ["PANNE", Color(1.0, 0.15, 0.12), true],
	"attente_matiere": ["ATTENTE MATIÈRE", Color(1.0, 0.8, 0.1), true],
	"sortie_pleine": ["SORTIE PLEINE", Color(1.0, 0.5, 0.08), true],
}

@export var title := "":
	set(value):
		title = value
		_refresh()
@export_enum("arret", "marche", "pause", "reglage", "panne", "attente_matiere", "sortie_pleine") var state := "arret":
	set(value):
		if not STATES.has(value):
			push_warning("%s : état inconnu « %s » (arret affiché)" % [asset_id, value])
			value = "arret"
		state = value
		_refresh()

var _lamp: MeshInstance3D
var _label: Label3D


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var packed := load(MODEL) as PackedScene
	if packed != null:
		var model := packed.instantiate() as Node3D
		model.scale = Vector3.ONE * MODEL_SCALE
		Mesher.adopt(self, model)
	var steel := Color(0.3, 0.32, 0.36)
	var batch := Mesher.Batch.new()
	batch.cylinder(0.035, 0.22, Vector3(0, BODY.y + 0.11, -0.4), steel)  # mât de la colonne
	batch.cylinder(0.11, 0.05, Vector3(0, BODY.y + 0.02, -0.4), steel)  # platine
	batch.cylinder(0.12, 0.04, Vector3(0, BODY.y + 0.44, -0.4), steel)  # chapeau
	batch.build(self)
	_lamp = MeshInstance3D.new()
	var lens := CylinderMesh.new()
	lens.top_radius = 0.1
	lens.bottom_radius = 0.1
	lens.height = 0.2
	lens.radial_segments = 12
	_lamp.mesh = lens
	_lamp.position = Vector3(0, BODY.y + 0.32, -0.4)
	Mesher.adopt(self, _lamp)
	_label = Label3D.new()
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.font_size = 48
	_label.pixel_size = 0.006
	_label.outline_size = 12
	_label.outline_modulate = Color(0.08, 0.1, 0.16)
	_label.position = Vector3(0, BODY.y + 0.95, -0.4)
	Mesher.adopt(self, _label)
	Mesher.collider(self, [[BODY, Vector3(0, BODY.y / 2.0, 0)]])
	_refresh()


func _refresh() -> void:
	if _label == null:
		return
	var info: Array = STATES[state]
	var color: Color = info[1]
	_label.text = info[0] if title.is_empty() else "%s\n%s" % [title, info[0]]
	_lamp.material_override = Mesher.material(color, color) if info[2] else Mesher.material(color)
