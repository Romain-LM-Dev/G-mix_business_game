extends Node
## Client HTTP JSON vers l'API FastAPI. Seul point d'accès HTTP du jeu.
## Usage : var res: Dictionary = await Api.get_json("/health")
## Résultat : {ok: bool, status: int, data: Variant, error: String} ; `error` reprend le message de l'API.
## Une fois connecté, `token` (jeton de connexion, ADR 0004) accompagne chaque requête et le WebSocket.

## Jeton refusé ou expiré : l'interface revient à l'écran de connexion.
signal unauthorized

var token := ""
var user: Dictionary = {}  # {id, username, display_name, role, must_change_password}


func get_json(path: String) -> Dictionary:
	return await _request(HTTPClient.METHOD_GET, path, null)


## `timeout_s` > 0 : délai propre à la requête (ex. réponse d'un PNJ quand le modèle se charge en VRAM).
func post_json(path: String, body: Variant = {}, timeout_s := 0.0) -> Dictionary:
	return await _request(HTTPClient.METHOD_POST, path, body, timeout_s)


func put_json(path: String, body: Variant = {}) -> Dictionary:
	return await _request(HTTPClient.METHOD_PUT, path, body)


func auth_headers() -> PackedStringArray:
	return PackedStringArray(["Authorization: Bearer " + token]) if not token.is_empty() else PackedStringArray()


func login(username: String, password: String) -> Dictionary:
	var res: Dictionary = await post_json("/api/v1/auth/login", {"username": username, "password": password})
	if res["ok"]:
		token = res["data"]["access_token"]
		user = res["data"]["user"]
	return res


func logout() -> void:
	token = ""
	user = {}


func role() -> String:
	return str(user.get("role", ""))


func _request(method: HTTPClient.Method, path: String, body: Variant, timeout_s := 0.0) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = timeout_s if timeout_s > 0.0 else AppConfig.request_timeout_s
	add_child(http)
	var headers := PackedStringArray(["Accept: application/json"])
	headers.append_array(auth_headers())
	var payload := ""
	if body != null:
		headers.append("Content-Type: application/json")
		payload = JSON.stringify(body)
	var err := http.request(AppConfig.api_base_url + path, headers, method, payload)
	if err != OK:
		http.queue_free()
		return _result(false, 0, null, "requête impossible : %s" % error_string(err))
	var response: Array = await http.request_completed
	http.queue_free()
	var result: int = response[0]
	var status: int = response[1]
	var text := (response[3] as PackedByteArray).get_string_from_utf8()
	var data: Variant = JSON.parse_string(text) if not text.is_empty() else null
	if result != HTTPRequest.RESULT_SUCCESS:
		return _result(false, status, data, "erreur réseau %d : le serveur est-il démarré ?" % result)
	if status == 401 and not token.is_empty():
		unauthorized.emit()
	if status >= 400:
		return _result(false, status, data, _error_text(status, data))
	return _result(true, status, data, "")


static func _error_text(status: int, data: Variant) -> String:
	if data is Dictionary and data.has("detail"):
		var detail: Variant = data["detail"]
		if detail is String:
			return detail
		if detail is Dictionary:
			return str(detail.get("message", detail))
		if detail is Array and not detail.is_empty() and detail[0] is Dictionary:
			return "%s (%s)" % [detail[0].get("msg", "invalide"), "/".join(detail[0].get("loc", []))]
	return "HTTP %d" % status


func _result(ok: bool, status: int, data: Variant, error: String) -> Dictionary:
	return {"ok": ok, "status": status, "data": data, "error": error}
