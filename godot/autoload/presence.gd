extends Node
## Présence multijoueur (ADR 0005) : positions et animations des joueurs d'un lobby, par le réseau Godot (ENet).
## Le même script tourne côté serveur (processus headless lancé par l'API : -- --server --lobby=… --port=…) et
## côté client : les RPC passent par ce nœud, /root/Presence, identique des deux côtés.
## Le serveur n'accepte un pair qu'après vérification de son ticket (JWT HS256 de 60 s signé par l'API avec
## JWT_SECRET, reçu par la variable d'environnement GMIX_JWT_SECRET). Kafka et l'API ne voient pas ce trafic.
## Sonde de test : -- --presence-probe --host=127.0.0.1 --port=7000 --ticket=… (code de sortie 0 si accepté).

## Côté client : instantané reçu du serveur, peer_id -> {name, role, position, yaw, animation}.
signal peers_changed(states: Dictionary)
signal status_changed(text: String)

const SEND_INTERVAL := 0.1  # 10 mises à jour par seconde suffisent à un business game
const MAX_SPEED := 15.0  # m/s : au-delà, déplacement refusé (pas de téléportation)
const AUTH_TIMEOUT_MS := 5000

var is_server := false
var _lobby_id := ""
var _secret := PackedByteArray()
var _players := {}  # serveur : peer_id -> état
var _pending := {}  # serveur : peer_id -> instant de connexion, tant que le ticket n'est pas vérifié
var _elapsed := 0.0
var _ticket := ""
var _avatar: Node3D  # client : joueur local à diffuser
var _welcomed := false
var _probe := false


func _ready() -> void:
	var args := _arguments()
	if args.has("server"):
		_start_server(int(args.get("port", "7000")), str(args.get("lobby", "")))
	elif args.has("presence-probe"):
		_probe = true
		_connect(str(args.get("host", "127.0.0.1")), int(args.get("port", "7000")), str(args.get("ticket", "")))
		get_tree().create_timer(8.0).timeout.connect(func() -> void: _finish_probe(false))
	set_process(is_server)


## Client : entre dans la présence du lobby (au chargement du monde 3D). Sans serveur, la partie reste jouable seul.
func join(lobby_id: String, avatar: Node3D) -> void:
	leave()
	_avatar = avatar
	var res: Dictionary = await Api.post_json("/api/v1/lobbies/%s/presence" % lobby_id)
	if not res["ok"]:
		status_changed.emit("Présence des autres joueurs indisponible : %s" % res["error"])
		return
	var host := AppConfig.api_base_url.get_slice("://", 1).get_slice("/", 0).get_slice(":", 0)
	_connect(host, int(res["data"]["port"]), str(res["data"]["ticket"]))


func leave() -> void:
	_welcomed = false
	_avatar = null
	set_process(false)
	if multiplayer.multiplayer_peer is ENetMultiplayerPeer:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null
	peers_changed.emit({})


func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed < SEND_INTERVAL:
		return
	_elapsed = 0.0
	if is_server:
		_server_tick()
	elif _welcomed and is_instance_valid(_avatar):
		var yaw: float = _avatar.call("model_yaw") if _avatar.has_method("model_yaw") else _avatar.rotation.y
		var animation: String = _avatar.call("animation_name") if _avatar.has_method("animation_name") else "idle"
		update_state.rpc_id(1, _avatar.global_position, yaw, animation)


# --- serveur ---------------------------------------------------------------------------------------------


func _start_server(port: int, lobby_id: String) -> void:
	_lobby_id = lobby_id
	_secret = OS.get_environment("GMIX_JWT_SECRET").to_utf8_buffer()
	if _secret.size() < 32 or lobby_id.is_empty():
		printerr("Serveur de partie : GMIX_JWT_SECRET (32 caractères min.) et --lobby obligatoires")
		get_tree().quit(1)
		return
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_server(port, 64)
	if err != OK:
		printerr("Serveur de partie : port %d indisponible (%s)" % [port, error_string(err)])
		get_tree().quit(1)
		return
	multiplayer.multiplayer_peer = peer
	multiplayer.peer_connected.connect(func(id: int) -> void: _pending[id] = Time.get_ticks_msec())
	multiplayer.peer_disconnected.connect(
		func(id: int) -> void:
			_pending.erase(id)
			_players.erase(id)
	)
	is_server = true
	print("Serveur de partie du lobby %s : port UDP %d" % [lobby_id, port])


func _server_tick() -> void:
	var now := Time.get_ticks_msec()
	for id: int in _pending.keys():
		if now - int(_pending[id]) > AUTH_TIMEOUT_MS:
			_pending.erase(id)
			multiplayer.multiplayer_peer.disconnect_peer(id)
	if _players.is_empty():
		return
	var states := {}
	for id: int in _players:
		var player: Dictionary = _players[id]
		states[id] = {
			"name": player["name"], "role": player["role"], "position": player["position"],
			"yaw": player["yaw"], "animation": player["animation"],
		}
	for id: int in _players:
		snapshot.rpc_id(id, states)


@rpc("any_peer", "call_remote", "reliable")
func authenticate(ticket: String) -> void:
	if not is_server:
		return
	var id := multiplayer.get_remote_sender_id()
	var claims := verify_ticket(ticket, _secret)
	if claims.is_empty() or claims.get("lobby") != _lobby_id:
		print("Ticket refusé pour le pair %d" % id)
		multiplayer.multiplayer_peer.disconnect_peer(id)
		return
	_pending.erase(id)
	_players[id] = {
		"user_id": claims["sub"], "name": claims.get("name", "?"), "role": claims.get("role", ""),
		"position": Vector3.ZERO, "yaw": 0.0, "animation": "idle", "at": Time.get_ticks_msec(),
	}
	welcome.rpc_id(id, id)


@rpc("any_peer", "call_remote", "unreliable_ordered")
func update_state(position: Vector3, yaw: float, animation: String) -> void:
	if not is_server:
		return
	var player: Dictionary = _players.get(multiplayer.get_remote_sender_id(), {})
	if player.is_empty():
		return
	var now := Time.get_ticks_msec()
	var seconds := maxf((now - int(player["at"])) / 1000.0, SEND_INTERVAL)
	var previous: Vector3 = player["position"]
	if previous != Vector3.ZERO and position.distance_to(previous) > MAX_SPEED * seconds + 1.0:
		return
	player["position"] = position
	player["yaw"] = yaw
	player["animation"] = animation.left(16)
	player["at"] = now


## Vérifie un JWT HS256 de présence : signature, type, expiration. Renvoie ses revendications, ou {} si refusé.
static func verify_ticket(ticket: String, secret: PackedByteArray) -> Dictionary:
	var parts := ticket.split(".")
	if parts.size() != 3:
		return {}
	var signed := (parts[0] + "." + parts[1]).to_utf8_buffer()
	var expected := Crypto.new().hmac_digest(HashingContext.HASH_SHA256, secret, signed)
	if not Crypto.new().constant_time_compare(expected, _base64url(parts[2])):
		return {}
	var header: Variant = JSON.parse_string(_base64url(parts[0]).get_string_from_utf8())
	var claims: Variant = JSON.parse_string(_base64url(parts[1]).get_string_from_utf8())
	if not header is Dictionary or header.get("alg") != "HS256" or not claims is Dictionary:
		return {}
	if claims.get("typ") != "presence" or float(claims.get("exp", 0)) < Time.get_unix_time_from_system():
		return {}
	return claims


static func _base64url(text: String) -> PackedByteArray:
	var padded := text.replace("-", "+").replace("_", "/")
	while padded.length() % 4 != 0:
		padded += "="
	return Marshalls.base64_to_raw(padded)


# --- client ----------------------------------------------------------------------------------------------


func _connect(host: String, port: int, ticket: String) -> void:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_client(host, port)
	if err != OK:
		status_changed.emit("Connexion au serveur de partie impossible (%s)" % error_string(err))
		return
	_ticket = ticket
	multiplayer.multiplayer_peer = peer
	if not multiplayer.connected_to_server.is_connected(_on_connected):
		multiplayer.connected_to_server.connect(_on_connected)
		multiplayer.connection_failed.connect(_on_lost.bind("connexion refusée"))
		multiplayer.server_disconnected.connect(_on_lost.bind("serveur de partie arrêté"))
	set_process(true)


func _on_connected() -> void:
	authenticate.rpc_id(1, _ticket)


func _on_lost(reason: String) -> void:
	_welcomed = false
	status_changed.emit("Présence interrompue : %s" % reason)
	peers_changed.emit({})
	if _probe:
		_finish_probe(false)


@rpc("authority", "call_remote", "reliable")
func welcome(peer_id: int) -> void:
	_welcomed = true
	status_changed.emit("Présence active : les autres joueurs du lobby sont visibles")
	if _probe:
		print("PRESENCE OK (pair %d)" % peer_id)
		_finish_probe(true)


@rpc("authority", "call_remote", "unreliable_ordered")
func snapshot(states: Dictionary) -> void:
	peers_changed.emit(states)


func _finish_probe(success: bool) -> void:
	if _probe:
		_probe = false
		if not success:
			print("PRESENCE KO")
		get_tree().quit(0 if success else 1)


## Arguments utilisateur (après « -- ») : --clé=valeur ou --drapeau.
static func _arguments() -> Dictionary:
	var result := {}
	for arg in OS.get_cmdline_user_args():
		var pair := arg.trim_prefix("--").split("=", true, 1)
		result[pair[0]] = pair[1] if pair.size() > 1 else ""
	return result
