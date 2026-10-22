class_name Mesher
extends RefCounted
## Construction de géométrie low-poly pour les assets procéduraux (style proche des kits Kenney).
## Les nœuds générés n'ont pas de propriétaire : ils ne sont jamais enregistrés dans les .tscn et sont
## reconstruits à chaque chargement à partir des propriétés exportées.

const GENERATED := &"gmix_generated"

static var _materials: Dictionary = {}


static func material(color: Color, emission := Color.BLACK) -> StandardMaterial3D:
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
