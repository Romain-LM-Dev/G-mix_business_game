extends Node
## État client de la séance : lobby ouvert (vue renvoyée par l'API, tenue à jour par le WebSocket). Les règles du
## jeu et la mémoire des agents restent côté serveur : rien n'est calculé ici.

signal lobby_changed

var lobby: Dictionary = {}


func _ready() -> void:
	get_tree().root.theme = Ui.make_theme()
	EventBus.lobby_state_changed.connect(_on_state)
	EventBus.lobby_members_changed.connect(_on_members)


func open(view: Dictionary) -> void:
	lobby = view
	Realtime.subscribe_lobby(str(view["id"]))
	lobby_changed.emit()


func reload() -> bool:
	if lobby.is_empty():
		return false
	var res: Dictionary = await Api.get_json("/api/v1/lobbies/%s" % lobby["id"])
	if res["ok"]:
		open(res["data"])
	return res["ok"]


func close() -> void:
	lobby = {}
	Realtime.subscribe_lobby("")


func spec() -> Dictionary:
	return lobby.get("spec", {})


func state() -> Dictionary:
	return lobby.get("state", {})


func is_manager() -> bool:
	return lobby.get("is_manager", false)


func url(suffix := "") -> String:
	return "/api/v1/lobbies/%s%s" % [lobby.get("id", ""), suffix]


## État public renvoyé par une action (start, advance, actions) : affiché sans attendre le WebSocket.
func apply_state(state_view: Dictionary) -> void:
	_on_state({"state": state_view, "lobby_status": "closed" if state_view.get("status") == "finished" else "running"})


func _on_state(payload: Dictionary) -> void:
	if lobby.is_empty():
		return
	lobby["state"] = payload.get("state", lobby.get("state", {}))
	lobby["status"] = payload.get("lobby_status", lobby.get("status", ""))
	lobby_changed.emit()


func _on_members(members: Array) -> void:
	if lobby.is_empty():
		return
	lobby["members"] = members
	lobby_changed.emit()
