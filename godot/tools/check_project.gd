extends SceneTree
## Vérifie que tous les scripts et scènes du projet se chargent sans erreur (hors addons/ et tools/).
## Usage : Godot_console.exe --headless --path godot --script res://tools/check_project.gd
## Code de sortie : 0 si tout est valide, 1 sinon. Appelé par scripts/godot.ps1 -Check.

const SKIPPED_ROOT_DIRS := ["addons", "tools"]


func _initialize() -> void:
	var files: Array[String] = []
	_collect("res://", files)
	var failures: Array[String] = []
	for path in files:
		if path.ends_with(".gd"):
			var script := load(path) as GDScript
			if script == null or not script.can_instantiate():
				failures.append(path)
		elif path.ends_with(".tscn"):
			var scene := load(path) as PackedScene
			if scene == null or not scene.can_instantiate():
				failures.append(path)
	print("Fichiers vérifiés : %d, en échec : %d" % [files.size(), failures.size()])
	for path in failures:
		printerr("ÉCHEC %s" % path)
	quit(1 if failures.size() > 0 else 0)


func _collect(dir_path: String, out: Array[String]) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		if sub.begins_with(".") or (dir_path == "res://" and sub in SKIPPED_ROOT_DIRS):
			continue
		_collect(dir_path.path_join(sub), out)
	for file in dir.get_files():
		if file.get_extension() in ["gd", "tscn"]:
			out.append(dir_path.path_join(file))
