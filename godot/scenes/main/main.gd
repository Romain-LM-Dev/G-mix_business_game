extends Control
## Coquille du client : connexion, puis accueil selon le rôle (joueur, formateur, admin) et salle du lobby.
## Le monde 3D est une scène à part (scenes/world) ; au retour, on revient à la salle du lobby ouvert.
## Mode --smoke : écran de diagnostic headless (scripts\smoke.ps1). Modes --server et --presence-probe :
## serveur de partie et sonde de présence, sans interface (autoload Presence).

const BOOT := "res://scenes/boot/boot.tscn"
const WORLD := "res://scenes/world/world.tscn"
const SCREENS := {
	"login": preload("res://scenes/main/login_screen.gd"),
	"home": preload("res://scenes/main/home_screen.gd"),
	"lobby": preload("res://scenes/lobby/lobby_screen.gd"),
}

var _screen: Control


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if "--server" in args or "--presence-probe" in args:
		return  # processus sans interface : l'autoload Presence fait tout
	if "--smoke" in args:
		get_tree().change_scene_to_file.call_deferred(BOOT)
		return
	Api.unauthorized.connect(_on_unauthorized)
	if Api.token.is_empty():
		_show("login")
	elif not Session.lobby.is_empty():
		_show("lobby")
	else:
		_show("home")


func _show(target: String) -> void:
	match target:
		"diagnostic":
			get_tree().change_scene_to_file(BOOT)
			return
		"world":
			get_tree().change_scene_to_file(WORLD)
			return
		"logout":
			Session.close()
			Realtime.disconnect_from_server()
			Api.logout()
			target = "login"
		"home":
			Session.close()
			if not Realtime.is_open():
				Realtime.connect_to_server()
	if _screen != null:
		_screen.queue_free()
	_screen = SCREENS[target].new()
	_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_screen.connect("navigate", _show)
	add_child(_screen)


func _on_unauthorized() -> void:
	_show("logout")
