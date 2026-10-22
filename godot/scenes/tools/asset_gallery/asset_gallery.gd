extends Node3D
## Galerie de tous les assets du catalogue, une rangée par catégorie (vérification visuelle des échelles,
## orientations et enseignes). Captures par catégorie :
##   Godot.exe --path godot res://scenes/tools/asset_gallery/asset_gallery.tscn -- --screenshots=C:/dossier

const CATALOG := "res://assets/catalog.json"
const ROW_GAP := 8.0

var _rows: Dictionary = {}  # catégorie -> AABB de la rangée
var _row_nodes: Dictionary = {}  # catégorie -> nœud parent de la rangée (isolée pendant les captures)

@onready var _camera: Camera3D = $Camera3D


func _ready() -> void:
	_build_environment()
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	var by_category: Dictionary = {}
	for entry: Dictionary in catalog["assets"]:
		by_category.get_or_add(entry["category"], []).append(entry)
	var z := 0.0
	for category: String in by_category:
		var x := 0.0
		var depth := 0.0
		var row := AABB()
		var row_node := Node3D.new()
		row_node.name = category
		add_child(row_node)
		_row_nodes[category] = row_node
		for entry: Dictionary in by_category[category]:
			var footprint: Dictionary = entry["footprint"]
			var w := float(footprint["w"])
			var d := float(footprint["d"])
			var h := float(footprint["h"])
			var scene := load(entry["scene"]) as PackedScene
			if scene == null:
				push_warning("Scène absente : %s" % entry["scene"])
				continue
			var node := scene.instantiate() as Node3D
			x += w / 2.0
			node.position = Vector3(x, 0, z)
			row_node.add_child(node)
			if entry["sign"]:
				node.set("sign_text", entry["name"])
			_add_label(row_node, entry["id"], Vector3(x, h + maxf(0.3, h * 0.08), z), h)
			var box := AABB(Vector3(x - w / 2.0, 0, z - d / 2.0), Vector3(w, h, d))
			row = box if row.size == Vector3.ZERO else row.merge(box)
			x += w / 2.0 + maxf(1.0, w * 0.35)
			depth = maxf(depth, d)
		_rows[category] = row
		z += depth + ROW_GAP
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--screenshots="):
			_capture(arg.trim_prefix("--screenshots="))
			return
	if not _rows.is_empty():
		_frame(_rows.values()[0])


func _capture(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	for category: String in _rows:
		for other: String in _row_nodes:
			(_row_nodes[other] as Node3D).visible = other == category
		_frame(_rows[category])
		for i in 4:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(directory.path_join("%s.png" % category))
		print("capture : %s" % category)
	get_tree().quit()


func _frame(box: AABB) -> void:
	var size := box.size
	var distance := maxf(size.x * 0.62, size.y * 1.6) * 1.15 + 2.0
	var target := box.get_center() + Vector3(0, -size.y * 0.15, 0)
	_camera.position = target + Vector3(0, distance * 0.38, distance)
	_camera.look_at(target)


func _add_label(parent: Node3D, text: String, at: Vector3, height: float) -> void:
	var label := Label3D.new()
	label.text = text
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 48
	label.pixel_size = clampf(height / 300.0, 0.002, 0.03)
	label.outline_size = 10
	label.position = at
	parent.add_child(label)


func _build_environment() -> void:
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	var world := WorldEnvironment.new()
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 35, 0)
	sun.shadow_enabled = true
	add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(2000, 2000)
	ground.mesh = plane
	ground.material_override = Mesher.material(Color(0.55, 0.6, 0.55))
	ground.position = Vector3(0, -0.01, 0)
	add_child(ground)
