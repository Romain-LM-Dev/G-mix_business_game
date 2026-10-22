@tool
extends GmixAsset
## Chariot élévateur frontal à contrepoids (environ 2,5 m sans les fourches, 1,15 m de large,
## protège-conducteur à 2,15 m, fourches de 1,15 m). Avant (fourches) vers +Z, comme tous les assets.
## Variante : hauteur_fourches (0 à 3 m), animable par le jeu.

@export_range(0.0, 3.0, 0.05) var fork_height := 0.1:
	set(value):
		fork_height = value
		_place_forks()

var _carriage: Node3D


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var yellow := Mesher.material(Color(0.98, 0.74, 0.12))
	var dark := Mesher.material(Color(0.16, 0.16, 0.18))
	var steel := Mesher.material(Color(0.56, 0.58, 0.62))
	# Géométrie décrite fourches vers -Z, puis pivotée d'un demi-tour : avant vers +Z.
	var body := Mesher.adopt(self, Node3D.new()) as Node3D
	body.rotation.y = PI
	Mesher.box(body, Vector3(1.1, 0.7, 1.9), Vector3(0, 0.6, 0.25), yellow)  # châssis
	Mesher.box(body, Vector3(1.12, 0.65, 0.45), Vector3(0, 0.95, 1.12), dark)  # contrepoids
	Mesher.box(body, Vector3(0.5, 0.12, 0.5), Vector3(0, 1.01, 0.35), dark)  # siège
	Mesher.box(body, Vector3(0.45, 0.5, 0.08), Vector3(0, 1.3, 0.6), dark)  # dossier
	Mesher.box(body, Vector3(0.35, 0.3, 0.3), Vector3(0, 1.1, -0.35), dark)  # tableau de bord
	for x in [-0.5, 0.5]:
		for z in [-0.45, 0.8]:
			Mesher.box(body, Vector3(0.06, 1.2, 0.06), Vector3(x, 1.55, z), dark)  # montants du protège-conducteur
		Mesher.cylinder(body, 0.3, 0.26, Vector3(x, 0.3, -0.45), dark, true)  # roues avant
		Mesher.cylinder(body, 0.24, 0.2, Vector3(x, 0.24, 0.95), dark, true)  # roues arrière
	Mesher.box(body, Vector3(1.1, 0.06, 1.35), Vector3(0, 2.15, 0.17), dark)  # toit
	for x in [-0.35, 0.35]:
		Mesher.box(body, Vector3(0.08, 2.5, 0.12), Vector3(x, 1.3, -0.85), steel)  # mât
	_carriage = Mesher.adopt(body, Node3D.new()) as Node3D
	Mesher.box(_carriage, Vector3(0.9, 0.5, 0.06), Vector3(0, 0.25, 0), dark)  # tablier
	for x in [-0.28, 0.28]:
		Mesher.box(_carriage, Vector3(0.12, 0.045, 1.15), Vector3(x, 0.02, -0.6), steel)  # fourches
	_place_forks()


func _place_forks() -> void:
	if _carriage != null:
		_carriage.position = Vector3(0, fork_height, -0.95)
