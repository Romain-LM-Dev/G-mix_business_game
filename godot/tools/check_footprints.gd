extends SceneTree
## Mesure chaque scène d'asset (maillages réels, une fois ses nœuds générés) et la compare à son emprise du catalogue :
## échec si la scène déborde de plus de 3 % ou si elle n'a pas la collision attendue (voir EXEMPT_COLLISION).
## Les personnages et la nature sont hors grille. Usage : Godot_console.exe --headless --path godot --script res://tools/check_footprints.gd
## Option : -- --verbose (affiche les tailles mesurées). Appelé par scripts/assets.ps1.

const CATALOG := "res://assets/catalog.json"
const SKIPPED := ["character", "nature"]
const TOLERANCE := 1.03
## Sans collision par conception : marquage au sol, pièce symbolique (annexe 0007), tuiles de route.
const EXEMPT_COLLISION := ["prop_floor_zone", "prop_part_token", "veh_forklift"]

var _queue: Array = []
var _failures := 0
var _verbose := OS.get_cmdline_user_args().has("--verbose")


func _initialize() -> void:
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for entry: Dictionary in catalog["assets"]:
		if not entry["category"] in SKIPPED:
			_queue.append(entry)


func _process(_delta: float) -> bool:
	if _queue.is_empty():
		print("Emprises vérifiées, échecs : %d" % _failures)
		quit(1 if _failures > 0 else 0)
		return true
	_check(_queue.pop_front())
	return false


func _check(entry: Dictionary) -> void:
	var id: String = entry["id"]
	var packed := load(entry["scene"]) as PackedScene
	if packed == null:
		return _fail(id, "scène introuvable")
	var node := packed.instantiate() as Node3D
	root.add_child(node)
	var box := _bounds(node, Transform3D.IDENTITY)
	var fp: Dictionary = entry["footprint"]
	var limit := Vector3(float(fp["w"]), float(fp["h"]), float(fp["d"])) * TOLERANCE
	if _verbose:
		print("%-28s mesuré %5.2f x %5.2f x %5.2f  emprise %5.2f x %5.2f x %5.2f" % [id, box.size.x, box.size.z, box.size.y, fp["w"], fp["d"], fp["h"]])
	if box.size.x > limit.x or box.size.y > limit.y or box.size.z > limit.z:
		_fail(id, "déborde de son emprise : %.2f x %.2f x %.2f (l x p x h) pour %s x %s x %s" % [box.size.x, box.size.z, box.size.y, fp["w"], fp["d"], fp["h"]])
	if absf(box.position.y) > 0.05 or absf(box.get_center().x) > 0.5 * limit.x or absf(box.get_center().z) > 0.5 * limit.z:
		_fail(id, "origine hors du sol ou du centre (boîte %s)" % box)
	if not id in EXEMPT_COLLISION and node.find_children("*", "CollisionObject3D", true, false).is_empty():
		_fail(id, "aucune collision (CollisionObject3D)")
	root.remove_child(node)
	node.free()


func _fail(id: String, message: String) -> void:
	_failures += 1
	printerr("ÉCHEC %s : %s" % [id, message])


## Boîte englobante des maillages (hors étiquettes et nœuds cachés), dans le repère de la racine.
func _bounds(node: Node, parent_transform: Transform3D) -> AABB:
	var transform := parent_transform
	if node is Node3D:
		if not (node as Node3D).visible:
			return AABB()
		transform = parent_transform * (node as Node3D).transform
	var result := AABB()
	var found := false
	if node is MeshInstance3D:
		result = transform * (node as MeshInstance3D).get_aabb()
		found = true
	for child in node.get_children():
		var child_box := _bounds(child, transform)
		if child_box.size == Vector3.ZERO:
			continue
		result = result.merge(child_box) if found else child_box
		found = true
	return result
