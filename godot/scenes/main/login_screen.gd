extends Control
## Connexion : adresse du serveur (salle : http://IP:8000 ; distance : https://nom-de-domaine), identifiant,
## mot de passe. Un mot de passe provisoire doit être changé avant d'aller plus loin (ADR 0004).

signal navigate(target: String)

var _server: LineEdit
var _username: LineEdit
var _password: LineEdit
var _login_button: Button
var _status: Label
var _change_box: VBoxContainer
var _new_password: LineEdit
var _confirm: LineEdit


func _ready() -> void:
	# Carte centrée ; si la fenêtre est trop basse pour elle (message d'erreur long), l'écran défile.
	var scroll := ScrollContainer.new()
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)
	var center := CenterContainer.new()
	center.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.add_child(center)
	var panel := Ui.panel(center)
	panel.custom_minimum_size.x = 540
	var box := Ui.vbox(panel, 12)
	box.add_child(Ui.label("G-mix Open World", 34))
	box.add_child(Ui.label("Business games en monde ouvert", 0, Ui.MUTED, true))
	_server = _row(box, "Serveur", Ui.field("http://192.168.1.20:8000"))
	_server.text = AppConfig.api_base_url
	_username = _row(box, "Identifiant", Ui.field("identifiant"))
	_username.text = AppConfig.last_username
	_password = _row(box, "Mot de passe", Ui.field("mot de passe", true))
	_password.text_submitted.connect(func(_text: String) -> void: _login())
	_login_button = Ui.button("Se connecter", _login, true)
	box.add_child(_login_button)

	_change_box = Ui.vbox(box, 8)
	_change_box.visible = false
	_change_box.add_child(Ui.label("Mot de passe provisoire : choisissez le vôtre (8 caractères minimum).", 0, Ui.WARN, true))
	_new_password = _row(_change_box, "Nouveau", Ui.field("nouveau mot de passe", true))
	_confirm = _row(_change_box, "Confirmation", Ui.field("confirmation", true))
	_confirm.text_submitted.connect(func(_text: String) -> void: _change_password())
	_change_box.add_child(Ui.button("Enregistrer et continuer", _change_password, true))

	_status = Ui.label("", 0, Ui.ERROR, true)
	box.add_child(_status)
	box.add_child(Ui.button("Diagnostic du serveur", func() -> void: navigate.emit("diagnostic")))
	(_password if not _username.text.is_empty() else _username).grab_focus.call_deferred()


func _row(parent: Node, caption: String, field: LineEdit) -> LineEdit:
	var row := Ui.hbox(parent)
	var title := Ui.label(caption)
	title.custom_minimum_size.x = 150
	row.add_child(title)
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(field)
	return field


func _login() -> void:
	var username := _username.text.strip_edges()
	if username.is_empty() or _password.text.is_empty():
		_status.text = "Identifiant et mot de passe obligatoires"
		return
	_status.text = ""
	_login_button.disabled = true
	AppConfig.set_server(_server.text, username)
	var res: Dictionary = await Api.login(username, _password.text)
	_login_button.disabled = false
	if not res["ok"]:
		_status.text = res["error"]
		return
	if Api.user.get("must_change_password", false):
		_login_button.visible = false
		_change_box.visible = true
		_new_password.grab_focus()
		return
	navigate.emit("home")


func _change_password() -> void:
	if _new_password.text != _confirm.text:
		_status.text = "Les deux saisies diffèrent"
		return
	var body := {"current_password": _password.text, "new_password": _new_password.text}
	var res: Dictionary = await Api.post_json("/api/v1/auth/password", body)
	if not res["ok"]:
		_status.text = res["error"]
		return
	Api.user["must_change_password"] = false
	navigate.emit("home")
