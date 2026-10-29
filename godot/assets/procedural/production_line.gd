@tool
extends GmixAsset
## Machine d'une ligne de production, reprise du jeu de référence G-mix Business_game (makeMachine, three.js) :
## bâti, capot de couleur, écran, roulettes, tapis d'alimentation à rouleaux à l'avant (+Z) et trois voyants.
## Variantes : titre (nom de la ligne), etat (ok, alerte, arret : voyant allumé et texte d'état).
## Emprise : 2,7 x 2,7 m, hauteur 2,4 m (voyants compris).

const STATES := ["ok", "alerte", "arret"]
const LIGHT_COLORS := [Color(0.46, 0.82, 0.55), Color(0.9, 0.72, 0.31), Color(0.85, 0.4, 0.35)]
const Z0 := -0.5  # le bâti recule pour centrer bâti + tapis sur l'origine

@export var title := "Ligne":
	set(value):
		title = value
		_refresh()
@export_enum("ok", "alerte", "arret") var state := "ok":
	set(value):
		state = value
		_refresh()
@export var accent := Color(0.47, 0.66, 0.61):
	set(value):
		accent = value
		_rebuild()

var _lights: Array[MeshInstance3D] = []
var _label: Label3D


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	_lights.clear()
	var frame := Mesher.material(Color(0.27, 0.36, 0.35))
	var dark := Mesher.material(Color(0.16, 0.24, 0.23))
	var steel := Mesher.material(Color(0.75, 0.77, 0.7))
	Mesher.box(self, Vector3(2.65, 1.1, 1.7), Vector3(0, 0.72, Z0), frame)
	Mesher.box(self, Vector3(2.3, 0.72, 1.32), Vector3(0, 1.42, Z0), Mesher.material(Color(0.45, 0.54, 0.49)))
	Mesher.box(self, Vector3(2.35, 0.18, 1.36), Vector3(0, 1.88, Z0), Mesher.material(accent))
	Mesher.box(self, Vector3(0.55, 0.38, 0.035), Vector3(0.55, 1.43, Z0 + 0.68), dark)
	Mesher.box(self, Vector3(0.35, 0.2, 0.045), Vector3(0.55, 1.44, Z0 + 0.71), Mesher.material(Color(0.55, 0.76, 0.55), Color(0.15, 0.33, 0.17)))
	for px in [-0.85, 0.85]:
		for pz in [-0.9, 0.9]:
			Mesher.cylinder(self, 0.22, 0.14, Vector3(px, 0.2, Z0 + pz), dark, true)
	Mesher.box(self, Vector3(1.35, 0.22, 0.8), Vector3(0, 0.57, Z0 + 1.48), frame)  # tapis d'alimentation
	for i in 5:
		Mesher.cylinder(self, 0.08, 0.78, Vector3(-0.52 + i * 0.26, 0.62, Z0 + 1.48), steel, true)
	for px in [-0.6, 0.6]:
		Mesher.box(self, Vector3(0.06, 0.46, 0.06), Vector3(px, 0.23, Z0 + 1.48), dark)
	for i in 3:
		var light := MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius = 0.065
		sphere.height = 0.13
		light.mesh = sphere
		light.position = Vector3(-0.85 + i * 0.2, 2.0, Z0 + 0.68)
		Mesher.adopt(self, light)
		_lights.append(light)
	_label = Label3D.new()
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.font_size = 40
	_label.pixel_size = 0.007
	_label.outline_size = 10
	_label.position = Vector3(0, 2.6, Z0)
	Mesher.adopt(self, _label)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(2.7, 2.0, 2.75)
	shape.shape = box
	shape.position = Vector3(0, 1.0, Z0 + 0.5)
	body.add_child(shape)
	Mesher.adopt(self, body)
	_refresh()


func _refresh() -> void:
	if _label == null:
		return
	var lit := STATES.find(state)
	_label.text = title if state == "ok" else "%s\n%s" % [title, "ARRÊT" if state == "arret" else "ALERTE"]
	for i in _lights.size():
		var color: Color = LIGHT_COLORS[i]
		_lights[i].material_override = Mesher.material(color, color * 0.9) if i == lit else Mesher.material(color.darkened(0.6))
