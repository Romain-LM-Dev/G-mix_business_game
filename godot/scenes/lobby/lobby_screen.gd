extends Control
## Salle du lobby. Joueur : choisir son rôle, entrer dans le monde 3D, lire le débrief à la fin.
## Formateur ou admin : code d'accès, participants, lancement, passage des phases, débrief, observation en 3D.
## Tenue à jour par le WebSocket (Session.lobby_changed) ; les règles restent côté API.

signal navigate(target: String)

var _title: Label
var _code: Label
var _status: Label
var _phase: RichTextLabel
var _kpis: RichTextLabel
var _members: VBoxContainer
var _role_box: VBoxContainer
var _role_select: OptionButton
var _role_mission: Label
var _enter_button: Button
var _start_button: Button
var _advance_button: Button
var _debrief_button: Button
var _role_ids: Array = []


func _ready() -> void:
	var column := Ui.vbox(Ui.screen_margin(self), 14)
	var header := Ui.hbox(column)
	_title = Ui.label("", 28)
	header.add_child(_title)
	Ui.spacer(header)
	header.add_child(Ui.button("Actualiser", func() -> void: Session.reload()))
	header.add_child(Ui.button("Retour à l'accueil", func() -> void: navigate.emit("home")))
	_status = Ui.label("", 0, Ui.ACCENT, true)
	column.add_child(_status)
	var body := Ui.hbox(column, 16)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL

	var left := Ui.panel(body)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var left_box := Ui.vbox(left, 14)
	_code = Ui.label("", 30, Ui.ACCENT)
	left_box.add_child(_code)
	_phase = Ui.rich()
	left_box.add_child(_phase)
	_kpis = Ui.rich()
	left_box.add_child(_kpis)
	var actions := Ui.hbox(left_box)
	_enter_button = Ui.button("Entrer dans le monde 3D", func() -> void: navigate.emit("world"))
	_start_button = Ui.button("Lancer la partie", _start)
	_advance_button = Ui.button("Phase suivante", _confirm_advance)
	_debrief_button = Ui.button("Débrief", _debrief)
	for button in [_enter_button, _start_button, _advance_button, _debrief_button]:
		actions.add_child(button)

	var right := Ui.panel(body)
	right.custom_minimum_size.x = 540
	var right_box := Ui.vbox(right)
	_role_box = Ui.vbox(right_box)
	_role_box.add_child(Ui.label("Mon rôle", 22))
	_role_select = OptionButton.new()
	_role_select.item_selected.connect(_choose_role)
	_role_box.add_child(_role_select)
	_role_mission = Ui.label("", 0, Ui.MUTED, true)
	_role_box.add_child(_role_mission)
	right_box.add_child(Ui.label("Participants", 22))
	_members = Ui.scroll_list(right_box, 260)
	Session.lobby_changed.connect(_render)
	_render()


func _render() -> void:
	var lobby := Session.lobby
	if lobby.is_empty():
		return
	var spec := Session.spec()
	var state := Session.state()
	var manager := Session.is_manager()
	var game_status: String = state.get("status", "waiting")
	_title.text = "%s  ·  %s" % [lobby["name"], spec.get("meta", {}).get("title", "")]
	_code.text = "Code d'accès : %s" % lobby["join_code"] if manager and lobby.get("join_code") else ""
	_code.visible = not _code.text.is_empty() and game_status != "finished"
	_phase.text = GameText.phase_bbcode(state)
	_kpis.text = GameText.kpis_bbcode(spec, state)
	_start_button.visible = manager and game_status == "waiting"
	_advance_button.visible = manager and game_status == "running"
	var last_phase := int(state.get("phase_index", 0)) + 1 >= int(state.get("phase_count", 1))
	_advance_button.text = "Terminer la partie" if last_phase else "Phase suivante"
	_debrief_button.visible = manager or game_status == "finished"
	_enter_button.text = "Observer le monde 3D" if manager else "Entrer dans le monde 3D"
	_enter_button.visible = game_status != "finished"

	var my_role: Variant = lobby.get("my_role")
	_role_box.visible = not manager
	_role_ids = [null] if my_role == null else []
	_role_select.clear()
	if my_role == null:
		_role_select.add_item("Choisir un rôle…")
	for role: Dictionary in spec.get("roles", []):
		_role_ids.append(role["id"])
		_role_select.add_item(role["title"])
		if role["id"] == my_role:
			_role_select.selected = _role_ids.size() - 1
			_role_mission.text = "Mission : %s" % role["mission"]
	if my_role == null:
		_role_mission.text = "Choisissez un rôle pour prendre les décisions qui lui reviennent."
	_role_select.disabled = my_role != null and game_status != "waiting"

	Ui.clear(_members)
	var members: Array = lobby.get("members", [])
	if members.is_empty():
		_members.add_child(Ui.label("Personne pour l'instant : donnez le code aux joueurs.", 0, Ui.MUTED, true))
	for member: Dictionary in members:
		var role_text := GameText.role_title(spec, member.get("game_role"))
		_members.add_child(Ui.label("%s  ·  %s" % [member["display_name"], role_text], 0, Color.WHITE, true))


func _choose_role(index: int) -> void:
	var role_id: Variant = _role_ids[index]
	if role_id == null:
		return
	var res: Dictionary = await Api.put_json(Session.url("/role"), {"game_role": role_id})
	if not res["ok"]:
		_status.text = res["error"]
		await Session.reload()
		return
	_status.text = ""
	Session.open(res["data"])


func _start() -> void:
	var res: Dictionary = await Api.post_json(Session.url("/start"))
	if not res["ok"]:
		_status.text = res["error"]
		return
	_status.text = "Partie lancée : les joueurs peuvent décider."
	Session.apply_state(res["data"]["state"])


func _confirm_advance() -> void:
	var dialog := ConfirmationDialog.new()
	dialog.title = _advance_button.text
	dialog.dialog_text = "Les effets différés et les aléas de la phase suivante vont s'appliquer. Continuer ?"
	dialog.ok_button_text = "Continuer"
	dialog.cancel_button_text = "Annuler"
	dialog.confirmed.connect(
		func() -> void:
			dialog.queue_free()
			_advance()
	)
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _advance() -> void:
	var res: Dictionary = await Api.post_json(Session.url("/advance"))
	if not res["ok"]:
		_status.text = res["error"]
		return
	Session.apply_state(res["data"]["state"])


func _debrief() -> void:
	var res: Dictionary = await Api.get_json(Session.url("/debrief"))
	if not res["ok"]:
		_status.text = res["error"]
		return
	Ui.show_text(self, "Débrief", GameText.debrief_bbcode(res["data"]))
