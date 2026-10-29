@tool
extends GmixAsset
## Semi-remorque de livraison (2,5 x 12 x 3,5 m) : cabine devant (+Z, pare-brise et phares), remorque fermée derrière,
## trois essieux. Roule sur la polyligne d'un lien (ADR 0009) : le client déplace la racine et règle `roll`.
## Propriété : roll = distance parcourue en mètres (les roues tournent de roll / rayon) ; lights = feux allumés.
## Collision : un bloc cabine et un bloc remorque.

const WHEEL_RADIUS := 0.5
## (z de l'essieu, doubles roues) : essieu avant, essieu moteur, tandem de la remorque.
const AXLES := [5.1, 3.9, -3.3, -4.5]

@export var roll := 0.0:
	set(value):
		roll = value
		_spin()
@export var lights := true:
	set(value):
		lights = value
		_rebuild()

var _wheels: Array[Node3D] = []


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	_wheels.clear()
	var batch := Mesher.Batch.new()
	batch.box(Vector3(2.0, 0.3, 11.2), Vector3(0, 0.75, -0.2), Palette.DARK_TEAL)  # châssis
	batch.box(Vector3(2.5, 2.5, 7.6), Vector3(0, 2.35, -2.2), Palette.TRUCK_CARGO)  # remorque
	batch.box(Vector3(2.52, 0.12, 7.6), Vector3(0, 3.55 - 0.06 - 0.05, -2.2), Palette.STEEL_PALE)  # arête de toit
	batch.box(Vector3(2.3, 2.2, 2.2), Vector3(0, 1.9, 4.9), Palette.TRUCK_CAB)  # cabine
	batch.box(Vector3(2.3, 0.9, 1.0), Vector3(0, 1.45, 5.9), Palette.TRUCK_CAB)  # capot court
	batch.box(Vector3(2.0, 0.8, 0.1), Vector3(0, 2.55, 6.0), Palette.GLASS)  # pare-brise
	batch.box(Vector3(2.4, 0.3, 0.3), Vector3(0, 0.6, 6.15), Palette.STEEL_DARK)  # pare-chocs
	batch.box(Vector3(2.35, 0.25, 2.3), Vector3(0, 1.0, 4.9), Palette.TRUCK_CAB.darkened(0.15))  # marchepied / jupe
	batch.box(Vector3(2.0, 0.5, 1.2), Vector3(0, 3.1, 4.4), Palette.TRUCK_CAB)  # déflecteur
	for x in [-1.05, 1.05]:
		batch.box(Vector3(0.05, 0.9, 0.9), Vector3(x * 1.1, 2.7, 4.2), Palette.GLASS)  # vitres latérales
	batch.build(self)
	if lights:
		var glow := Mesher.Batch.new()
		for x in [-0.8, 0.8]:
			glow.box(Vector3(0.35, 0.2, 0.06), Vector3(x, 1.1, 6.22), Palette.BEACON)  # phares
			glow.box(Vector3(0.3, 0.15, 0.06), Vector3(x, 1.0, -6.0), Palette.ALERT)  # feux arrière
		glow.build(self, Mesher.vertex_material(true))
	for z in AXLES:
		for side in [-1.0, 1.0]:
			var wheel := Mesher.adopt(self, Node3D.new()) as Node3D
			wheel.position = Vector3(side * 1.0, WHEEL_RADIUS, z)
			Mesher.cylinder(wheel, WHEEL_RADIUS, 0.3, Vector3(side * 0.1, 0, 0), Mesher.material(Palette.WHEEL), true)
			Mesher.cylinder(wheel, 0.25, 0.32, Vector3(side * 0.1, 0, 0), Mesher.material(Palette.STEEL_LIGHT), true)
			Mesher.box(wheel, Vector3(0.34, 0.1, 0.9), Vector3(side * 0.1, 0, 0), Mesher.material(Palette.STEEL_LIGHT))  # repère de rotation
			_wheels.append(wheel)
	Mesher.collider(self, [
		[Vector3(2.5, 3.5, 7.6), Vector3(0, 1.75, -2.2)],
		[Vector3(2.3, 3.2, 3.2), Vector3(0, 1.6, 4.9)],
	])
	_spin()


func _spin() -> void:
	for wheel in _wheels:
		wheel.rotation.x = roll / WHEEL_RADIUS
