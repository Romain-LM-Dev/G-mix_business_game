@tool
class_name Mesher
extends RefCounted
## Construction de géométrie low-poly pour les assets procéduraux (style proche des kits Kenney).
## Les nœuds générés n'ont pas de propriétaire : ils ne sont jamais enregistrés dans les .tscn et sont
## reconstruits à chaque chargement à partir des propriétés exportées.

const GENERATED := &"gmix_generated"

static var _materials: Dictionary = {}


## `grain` (« concrete », « cardboard », « steel », voir Palette) : matériau à grain léger ; vide : couleur unie.
static func material(color: Color, emission := Color.BLACK, grain := "") -> StandardMaterial3D:
	if not grain.is_empty():
		return Palette.material(color, grain, emission)
	var key := color.to_html() + emission.to_html()
	if not _materials.has(key):
		var mat := StandardMaterial3D.new()
		mat.albedo_color = color
		mat.roughness = 0.85
		if emission != Color.BLACK:
			mat.emission_enabled = true
			mat.emission = emission
		_materials[key] = mat
	return _materials[key]


static func box(parent: Node3D, size: Vector3, at: Vector3, mat: Material) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	return _add_mesh(parent, mesh, at, mat)


## Cylindre d'axe X (roues) ou Y (poteaux) selon `axis_x`.
static func cylinder(parent: Node3D, radius: float, length: float, at: Vector3, mat: Material, axis_x := false) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = length
	mesh.radial_segments = 12
	var node := _add_mesh(parent, mesh, at, mat)
	if axis_x:
		node.rotation = Vector3(0, 0, PI / 2.0)
	return node


## Matériau des maillages fusionnés (couleur par sommet, sRGB) ; `unshaded` : voyants lisibles sans éclairage.
static func vertex_material(unshaded := false) -> StandardMaterial3D:
	var key := "vertex_unshaded" if unshaded else "vertex"
	if not _materials.has(key):
		var mat := StandardMaterial3D.new()
		mat.vertex_color_use_as_albedo = true
		mat.vertex_color_is_srgb = true
		mat.roughness = 0.85
		if unshaded:
			mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		else:  # grain fin (triplanaire) multiplié par la couleur de sommet
			mat.albedo_texture = Palette.grain("steel")
			mat.uv1_triplanar = true
			mat.uv1_scale = Vector3.ONE / float(Palette.GRAIN_TILE["steel"])
		_materials[key] = mat
	return _materials[key]


## Collision propre d'un asset : un StaticBody3D « Collision » (adopté) avec une boîte par entrée de `boxes`
## ([taille, centre], ...). Un asset sans StaticBody3D n'est pas un obstacle pour la navigation.
static func collider(parent: Node3D, boxes: Array) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = "Collision"
	for entry: Array in boxes:
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = entry[0]
		shape.shape = box
		shape.position = entry[1]
		body.add_child(shape)
	adopt(parent, body)
	return body


## Fusionne boîtes et prismes colorés (couleur par sommet) en UN maillage : un appel de rendu par lot au lieu
## d'un par pièce. Les couleurs ne sont pas animables : ce qui change d'état (voyant, bacs) a son propre lot.
class Batch:
	extends RefCounted

	## (normale, axe t, axe b) de chaque face, avec t x b = normale.
	const FACES := [
		[Vector3.RIGHT, Vector3.UP, Vector3.BACK],
		[Vector3.LEFT, Vector3.BACK, Vector3.UP],
		[Vector3.UP, Vector3.BACK, Vector3.RIGHT],
		[Vector3.DOWN, Vector3.RIGHT, Vector3.BACK],
		[Vector3.BACK, Vector3.RIGHT, Vector3.UP],
		[Vector3.FORWARD, Vector3.UP, Vector3.RIGHT],
	]

	var _surface := SurfaceTool.new()
	var _empty := true

	func _init() -> void:
		_surface.begin(Mesh.PRIMITIVE_TRIANGLES)

	## Boîte de `size` centrée en `at`, tournée de `euler_deg` (degrés).
	func box(size: Vector3, at: Vector3, color: Color, euler_deg := Vector3.ZERO) -> Batch:
		var basis := Basis.from_euler(euler_deg * (PI / 180.0))
		var half := size / 2.0
		for face: Array in FACES:
			var n: Vector3 = face[0]
			var center := n * half
			var t: Vector3 = (face[1] as Vector3) * half
			var b: Vector3 = (face[2] as Vector3) * half
			var p0 := center - t - b
			var p1 := center + t - b
			var p2 := center + t + b
			var p3 := center - t + b
			for corner: Vector3 in [p0, p3, p2, p0, p2, p1]:  # sens horaire vu de l'extérieur
				_vertex(basis * corner + at, basis * n, color)
		return self

	## Prisme régulier à `segments` côtés, d'axe Y (défaut), X ou Z (`axis` : Vector3.AXIS_*).
	func cylinder(radius: float, length: float, at: Vector3, color: Color, axis := Vector3.AXIS_Y, segments := 8) -> Batch:
		var basis := Basis.IDENTITY
		if axis == Vector3.AXIS_X:
			basis = Basis.from_euler(Vector3(0, 0, PI / 2.0))
		elif axis == Vector3.AXIS_Z:
			basis = Basis.from_euler(Vector3(PI / 2.0, 0, 0))
		var h := length / 2.0
		for i in segments:
			var a0 := TAU * i / segments
			var a1 := TAU * (i + 1) / segments
			var d0 := Vector3(cos(a0), 0, sin(a0))
			var d1 := Vector3(cos(a1), 0, sin(a1))
			var b0 := d0 * radius + Vector3(0, -h, 0)
			var b1 := d1 * radius + Vector3(0, -h, 0)
			var t0 := d0 * radius + Vector3(0, h, 0)
			var t1 := d1 * radius + Vector3(0, h, 0)
			for v: Array in [[b0, d0], [b1, d1], [t0, d0], [b1, d1], [t1, d1], [t0, d0]]:
				_vertex(basis * v[0] + at, basis * v[1], color)
			for v: Array in [[Vector3(0, h, 0), Vector3.UP], [t0, Vector3.UP], [t1, Vector3.UP],
					[Vector3(0, -h, 0), Vector3.DOWN], [b1, Vector3.DOWN], [b0, Vector3.DOWN]]:
				_vertex(basis * v[0] + at, basis * v[1], color)
		return self

	## Ajoute le maillage fusionné à `parent` (null si le lot est vide).
	func build(parent: Node3D, material: Material = null) -> MeshInstance3D:
		if _empty:
			return null
		var node := MeshInstance3D.new()
		node.mesh = _surface.commit()
		node.material_override = material if material != null else Mesher.vertex_material()
		Mesher.adopt(parent, node)
		return node

	func _vertex(at: Vector3, normal: Vector3, color: Color) -> void:
		_surface.set_color(color)
		_surface.set_normal(normal)
		_surface.add_vertex(at)
		_empty = false


static func adopt(parent: Node, child: Node) -> Node:
	child.set_meta(GENERATED, true)
	parent.add_child(child)
	return child


static func clear(parent: Node) -> void:
	for child in parent.get_children():
		if child.has_meta(GENERATED):
			parent.remove_child(child)
			child.queue_free()


static func _add_mesh(parent: Node3D, mesh: Mesh, at: Vector3, mat: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.position = at
	node.material_override = mat
	adopt(parent, node)
	return node
