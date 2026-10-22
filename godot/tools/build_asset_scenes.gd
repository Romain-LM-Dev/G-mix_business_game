extends SceneTree
## Construit res://assets/<category>/<id>/<id>.tscn pour chaque asset importé de res://assets/catalog.json :
## modèle GLB mis à l'échelle de son emprise réelle (footprint, en mètres) selon `fit`, origine au sol au centre,
## collision boîte (sauf personnages), panneau d'enseigne si la variante « enseigne » existe.
## Les assets procéduraux (source_path nul) sont des scènes écrites à la main : non modifiés.
## Usage : Godot_console.exe --headless --path godot --script res://tools/build_asset_scenes.gd

const CATALOG := "res://assets/catalog.json"
const ASSET_SCRIPT := "res://assets/asset.gd"
const CHARACTER_SCRIPT := "res://assets/character.gd"


func _initialize() -> void:
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	var built := 0
	var failures := 0
	for entry: Dictionary in catalog["assets"]:
		if entry["source_path"] == null:
			continue
		var error := _build(entry)
		if error.is_empty():
			built += 1
		else:
			failures += 1
			printerr("ÉCHEC %s : %s" % [entry["id"], error])
	print("Scènes construites : %d, échecs : %d" % [built, failures])
	quit(1 if failures > 0 else 0)


func _build(entry: Dictionary) -> String:
	var packed := load(entry["source_path"]) as PackedScene
	if packed == null:
		return "modèle introuvable (%s) : lancer d'abord --import" % entry["source_path"]
	var model := packed.instantiate() as Node3D
	var bounds := _bounds(model, Transform3D.IDENTITY)
	if bounds.size == Vector3.ZERO:
		model.free()
		return "modèle sans géométrie"
	var factor := _fit_factor(bounds.size, entry["footprint"], entry["fit"])
	var center := bounds.get_center()
	model.name = "Model"
	model.scale = Vector3.ONE * factor
	model.position = Vector3(-center.x, -bounds.position.y, -center.z) * factor
	var size := bounds.size * factor

	var root := Node3D.new()
	root.name = entry["id"]
	root.set_script(load(CHARACTER_SCRIPT if entry["category"] == "character" else ASSET_SCRIPT))
	root.set("asset_id", entry["id"])
	_attach(root, model)
	if entry["category"] != "character":
		var body := StaticBody3D.new()
		body.name = "Collision"
		_attach(root, body)
		var shape := CollisionShape3D.new()
		shape.name = "Shape"
		var box := BoxShape3D.new()
		box.size = size
		shape.shape = box
		shape.position = Vector3(0, size.y / 2.0, 0)
		body.add_child(shape)
		shape.owner = root
	if entry["sign"]:
		var label := Label3D.new()
		label.name = "Sign"
		label.font_size = 96
		label.pixel_size = clampf(size.x / 1500.0, 0.004, 0.03)
		label.outline_size = 16
		label.outline_modulate = Color(0.08, 0.1, 0.16)
		label.position = Vector3(0, size.y * 0.78, size.z / 2.0 + 0.08)
		label.visible = false
		_attach(root, label)

	var path: String = entry["scene"]
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var scene := PackedScene.new()
	var pack_error := scene.pack(root)
	var save_error := ResourceSaver.save(scene, path) if pack_error == OK else pack_error
	root.free()
	if save_error != OK:
		return "enregistrement impossible : %s" % error_string(save_error)
	print("%-30s x%7.3f  ->  %5.2f x %5.2f x %5.2f m" % [entry["id"], factor, size.x, size.z, size.y])
	return ""


func _attach(root: Node3D, child: Node) -> void:
	root.add_child(child)
	child.owner = root


func _fit_factor(size: Vector3, footprint: Dictionary, fit: String) -> float:
	match fit:
		"h":
			return float(footprint["h"]) / maxf(size.y, 0.0001)
		"w":
			return float(footprint["w"]) / maxf(size.x, 0.0001)
		"d":
			return float(footprint["d"]) / maxf(size.z, 0.0001)
	return maxf(float(footprint["w"]), float(footprint["d"])) / maxf(maxf(size.x, size.z), 0.0001)


## Boîte englobante des maillages, dans le repère du modèle (transformations des nœuds cumulées).
func _bounds(node: Node, parent_transform: Transform3D) -> AABB:
	var transform := parent_transform
	if node is Node3D:
		transform = parent_transform * (node as Node3D).transform
	var result := AABB()
	var found := false
	if node is MeshInstance3D:
		result = transform * (node as MeshInstance3D).get_aabb()
		found = true
	for child in node.get_children():
		var child_bounds := _bounds(child, transform)
		if child_bounds.size == Vector3.ZERO:
			continue
		result = result.merge(child_bounds) if found else child_bounds
		found = true
	return result
