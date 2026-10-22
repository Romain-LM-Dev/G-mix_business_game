extends Node
## Configuration du client : adresses du backend (res://config/client.cfg, surchargé par user://client.cfg,
## puis par la ligne de commande : -- --api=http://192.168.1.20:8000 [--ws=ws://…/ws]).
## L'écran de connexion permet aussi de changer de serveur ; le choix est gardé dans user://client.cfg.

const DEFAULT_PATH := "res://config/client.cfg"
const USER_PATH := "user://client.cfg"

var api_base_url := "http://127.0.0.1:8000"
var ws_url := "ws://127.0.0.1:8000/ws"
var request_timeout_s := 15.0
var last_username := ""


func _ready() -> void:
	_load(DEFAULT_PATH)
	_load(USER_PATH)
	_apply_command_line()


## Serveur choisi à l'écran de connexion (salle : http://IP:8000 ; distance : https://nom-de-domaine).
func set_server(api_url: String, username: String) -> void:
	api_base_url = api_url.strip_edges().trim_suffix("/")
	ws_url = ws_url_for(api_base_url)
	last_username = username
	var cfg := ConfigFile.new()
	cfg.load(USER_PATH)
	cfg.set_value("backend", "api_base_url", api_base_url)
	cfg.set_value("backend", "ws_url", ws_url)
	cfg.set_value("session", "last_username", username)
	cfg.save(USER_PATH)


func _load(path: String) -> void:
	var cfg := ConfigFile.new()
	if cfg.load(path) != OK:
		return
	api_base_url = str(cfg.get_value("backend", "api_base_url", api_base_url))
	ws_url = str(cfg.get_value("backend", "ws_url", ws_url))
	request_timeout_s = float(cfg.get_value("backend", "request_timeout_s", request_timeout_s))
	last_username = str(cfg.get_value("session", "last_username", last_username))


func _apply_command_line() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--api="):
			api_base_url = arg.trim_prefix("--api=").trim_suffix("/")
			ws_url = ws_url_for(api_base_url)
		elif arg.begins_with("--ws="):
			ws_url = arg.trim_prefix("--ws=")


static func ws_url_for(api_url: String) -> String:
	if api_url.begins_with("https://"):
		return "wss://" + api_url.trim_prefix("https://") + "/ws"
	return "ws://" + api_url.trim_prefix("http://") + "/ws"
