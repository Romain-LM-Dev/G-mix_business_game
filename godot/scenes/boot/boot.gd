extends Control
## Écran de diagnostic : liaison Godot -> API -> (PostgreSQL, Kafka, stockage, Ollama), puis test du
## pipeline complet API -> Kafka -> worker IA -> Kafka -> WebSocket (formateur ou admin connecté).
##
## Mode sans interface (agents, CI) : Godot_console.exe --headless --path godot -- --smoke
## -> journalise les résultats et quitte avec le code 0 (tout est OK) ou 1. Le jeton d'un compte admin
## jetable arrive par GMIX_SMOKE_TOKEN (scripts\smoke.ps1) ; sans lui, seule la santé du backend est testée.

const MAIN_SCENE := "res://scenes/main/main.tscn"
const SERVICES := ["database", "kafka", "storage", "ollama"]
const WS_TIMEOUT_MS := 10_000
const PONG_TIMEOUT_MS := 120_000

var _status_labels: Dictionary = {}
var _log: RichTextLabel
var _pipeline_button: Button
var _last_pong: Dictionary = {}
var _smoke := "--smoke" in OS.get_cmdline_user_args()


func _ready() -> void:
	if _smoke and Api.token.is_empty():
		Api.token = OS.get_environment("GMIX_SMOKE_TOKEN")
	_build_ui()
	Realtime.connected.connect(_on_ws_connected)
	Realtime.disconnected.connect(_on_ws_disconnected)
	Realtime.message_received.connect(_on_message)
	if not Api.token.is_empty() and not Realtime.is_open():
		Realtime.connect_to_server()
	if _smoke:
		_run_smoke()
	else:
		_refresh_health()


func _refresh_health() -> bool:
	for service in SERVICES:
		_set_status(service, "…", Color.GRAY)
	var res: Dictionary = await Api.get_json("/health")
	if not res["ok"]:
		for service in SERVICES:
			_set_status(service, "inconnu", Color.ORANGE)
		_log_line("[color=red]API injoignable : %s[/color]" % res["error"])
		return false
	var services: Dictionary = res["data"]["services"]
	for service in SERVICES:
		var report: Dictionary = services.get(service, {})
		var ok: bool = report.get("ok", false)
		_set_status(service, _summarize(report), Color.LIME_GREEN if ok else Color.TOMATO)
	var healthy: bool = res["data"]["status"] == "ok"
	_log_line("État global du backend : [b]%s[/b]" % res["data"]["status"])
	EventBus.backend_status_changed.emit(healthy, res["data"])
	return healthy


func _test_pipeline() -> bool:
	if Api.token.is_empty():
		_log_line("[color=orange]Test du pipeline : se connecter avec un compte formateur ou admin[/color]")
		return false
	if not Realtime.is_open():
		_log_line("[color=orange]WebSocket fermé : reconnexion, réessayez dans un instant[/color]")
		Realtime.connect_to_server()
		return false
	_pipeline_button.disabled = true
	_last_pong = {}
	_log_line("Ping envoyé dans le pipeline Kafka -> worker IA…")
	var res: Dictionary = await Api.post_json("/api/v1/system/ping", {"message": "ping depuis Godot"})
	if not res["ok"]:
		_pipeline_button.disabled = false
		_log_line("[color=red]Ping refusé : %s[/color]" % res["error"])
		return false
	var deadline := Time.get_ticks_msec() + PONG_TIMEOUT_MS
	while _last_pong.is_empty() and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	_pipeline_button.disabled = false
	if _last_pong.is_empty():
		_log_line("[color=red]Pas de réponse : le worker system_ping tourne-t-il ? (scripts/worker.ps1)[/color]")
		return false
	var checks: Dictionary = _last_pong.get("checks", {})
	var all_ok := not checks.is_empty()
	for check in checks:
		var detail: Dictionary = checks[check]
		var ok: bool = detail.get("ok", false)
		all_ok = all_ok and ok
		_log_line("[color=%s]%s[/color] : %s" % ["lime" if ok else "red", check, _summarize(detail)])
	return all_ok


func _run_smoke() -> void:
	var healthy: bool = await _refresh_health()
	if Api.token.is_empty():
		_log_line("Pipeline non testé : pas de jeton (lancer scripts\\smoke.ps1)")
		_log_line("SMOKE %s (backend=%s)" % ["OK" if healthy else "KO", healthy])
		get_tree().quit(0 if healthy else 1)
		return
	var deadline := Time.get_ticks_msec() + WS_TIMEOUT_MS
	while not Realtime.is_open() and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	var pipeline_ok: bool = await _test_pipeline()
	var success := healthy and pipeline_ok
	_log_line("SMOKE %s (backend=%s, pipeline=%s)" % ["OK" if success else "KO", healthy, pipeline_ok])
	get_tree().quit(0 if success else 1)


func _on_message(type: String, payload: Dictionary) -> void:
	match type:
		"session.welcome":
			_log_line("Session WebSocket ouverte (%s)" % payload.get("client_id", ""))
		"system.pong":
			_last_pong = payload
		_:
			_log_line("Événement %s : %s" % [type, payload])


func _on_ws_connected() -> void:
	_set_status("websocket", "connecté", Color.LIME_GREEN)


func _on_ws_disconnected() -> void:
	_set_status("websocket", "déconnecté", Color.TOMATO)


func _summarize(report: Dictionary) -> String:
	var parts := PackedStringArray()
	for key in report:
		var value: Variant = report[key]
		if key == "ok" or (value is Array and value.is_empty()):
			continue
		parts.append("%s=%s" % [key, value])
	return ", ".join(parts)


func _set_status(service: String, text: String, color: Color) -> void:
	var label: Label = _status_labels[service]
	label.text = text
	label.add_theme_color_override("font_color", color)


func _log_line(text: String) -> void:
	_log.append_text("%s  %s\n" % [Time.get_time_string_from_system(), text])
	print_rich(text)


func _build_ui() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 32)
	add_child(margin)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	margin.add_child(column)

	var title := Label.new()
	title.text = "G-mix Open World : diagnostic de l'environnement"
	title.add_theme_font_size_override("font_size", 28)
	column.add_child(title)

	var info := Label.new()
	var who: String = Api.user.get("display_name", "non connecté")
	info.text = "API %s   |   %s" % [AppConfig.api_base_url, who]
	column.add_child(info)

	var grid := GridContainer.new()
	grid.columns = 2
	column.add_child(grid)
	for service in SERVICES + ["websocket"]:
		var name_label := Label.new()
		name_label.text = service
		name_label.custom_minimum_size.x = 160
		grid.add_child(name_label)
		var status_label := Label.new()
		status_label.text = "…"
		grid.add_child(status_label)
		_status_labels[service] = status_label

	var buttons := HBoxContainer.new()
	column.add_child(buttons)
	var back := Button.new()
	back.text = "Retour"
	back.pressed.connect(func() -> void: get_tree().change_scene_to_file(MAIN_SCENE))
	buttons.add_child(back)
	var refresh := Button.new()
	refresh.text = "Rafraîchir l'état"
	refresh.pressed.connect(_refresh_health)
	buttons.add_child(refresh)
	_pipeline_button = Button.new()
	_pipeline_button.text = "Tester le pipeline Kafka -> IA"
	_pipeline_button.pressed.connect(_test_pipeline)
	buttons.add_child(_pipeline_button)

	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_following = true
	_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(_log)
