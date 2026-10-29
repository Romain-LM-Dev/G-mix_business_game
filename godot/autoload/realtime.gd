extends Node
## Canal temps réel WebSocket vers l'API : événements du lobby (état, participants) relayés depuis Kafka.
## Messages JSON {type, payload, meta}. Les positions des joueurs NE passent PAS ici (réseau Godot dédié).
## Reconnexion automatique tant que l'utilisateur est connecté ; le lobby suivi est réabonné à chaque connexion.

signal connected
signal disconnected
signal message_received(type: String, payload: Dictionary)

const RETRY_S := 3.0

var _socket := WebSocketPeer.new()
var _last_state := WebSocketPeer.STATE_CLOSED
var _lobby_id := ""
var _wanted := false


func _ready() -> void:
	set_process(false)


## Exige d'être connecté : le jeton part dans l'en-tête Authorization (ADR 0004).
func connect_to_server() -> void:
	_wanted = true
	_socket = WebSocketPeer.new()
	_socket.handshake_headers = Api.auth_headers()
	_last_state = WebSocketPeer.STATE_CLOSED
	var err := _socket.connect_to_url(AppConfig.ws_url)
	if err != OK:
		push_warning("WebSocket : connexion impossible (%s)" % error_string(err))
		disconnected.emit()
		_retry()
		return
	set_process(true)


func disconnect_from_server() -> void:
	_wanted = false
	_lobby_id = ""
	_socket.close()


func is_open() -> bool:
	return _socket.get_ready_state() == WebSocketPeer.STATE_OPEN


## Un seul lobby suivi à la fois ; "" pour ne plus en suivre.
func subscribe_lobby(lobby_id: String) -> void:
	_lobby_id = lobby_id
	if is_open() and not lobby_id.is_empty():
		send_message("lobby.subscribe", {"lobby_id": lobby_id})


func send_message(type: String, payload: Dictionary = {}) -> void:
	if is_open():
		_socket.send_text(JSON.stringify({"type": type, "payload": payload}))


func _process(_delta: float) -> void:
	_socket.poll()
	var state := _socket.get_ready_state()
	if state != _last_state:
		_last_state = state
		if state == WebSocketPeer.STATE_OPEN:
			connected.emit()
			subscribe_lobby(_lobby_id)
		elif state == WebSocketPeer.STATE_CLOSED:
			set_process(false)
			disconnected.emit()
			_retry()
	while _socket.get_ready_state() == WebSocketPeer.STATE_OPEN and _socket.get_available_packet_count() > 0:
		var message: Variant = JSON.parse_string(_socket.get_packet().get_string_from_utf8())
		if message is Dictionary and message.has("type"):
			var payload: Variant = message.get("payload", {})
			_route(str(message["type"]), payload if payload is Dictionary else {"value": payload})


func _route(type: String, payload: Dictionary) -> void:
	message_received.emit(type, payload)
	match type:
		"lobby.state":
			EventBus.lobby_state_changed.emit(payload)
		"lobby.members":
			EventBus.lobby_members_changed.emit(payload.get("members", []))


func _retry() -> void:
	if not _wanted or Api.token.is_empty():
		return
	await get_tree().create_timer(RETRY_S).timeout
	if _wanted and not is_open() and not Api.token.is_empty():
		connect_to_server()
