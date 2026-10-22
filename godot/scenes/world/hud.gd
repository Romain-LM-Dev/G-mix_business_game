class_name GmixHud
extends CanvasLayer
## Interface du monde 3D : phase et rôle, KPI, notifications, invite d'interaction et panneaux modaux (décisions,
## dialogue avec un PNJ, indicateurs, menu, débrief). Données : Session (API + WebSocket) ; aucune règle ici.

signal modal_changed(open: bool)
signal leave_requested

const NOTICE_SECONDS := 8.0
const HELP := "ZQSD (WASD en QWERTY) : se déplacer · Maj : courir · Espace : sauter · E : interagir · Tab : décisions · Échap : menu"
const TALK_TIMEOUT_S := 90.0  # premier message : le modèle de dialogue peut devoir se charger en VRAM

var _phase: RichTextLabel
var _role: Label
var _kpis: RichTextLabel
var _notices: VBoxContainer
var _prompt: Label
var _overlay: CenterContainer
var _panels: Dictionary = {}
var _decisions_box: VBoxContainer
var _dialogue_title: Label
var _dialogue_log: RichTextLabel
var _dialogue_input: LineEdit
var _dialogue_send: Button
var _big_kpis: RichTextLabel
var _debrief_text: RichTextLabel
var _menu_debrief: Button
var _npc: Dictionary = {}
var _last_events: Array = []
var _last_status := ""


func _ready() -> void:
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var column := Ui.vbox(_passthrough(Ui.screen_margin(root, 16)))
	_passthrough(column)
	var top := Ui.hbox(column, 16)
	_passthrough(top)
	var phase_panel := _sized(Ui.panel(top), 560)
	phase_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN  # pas étiré à la hauteur du panneau des KPI
	var phase_box := Ui.vbox(phase_panel, 6)
	_phase = Ui.rich()
	phase_box.add_child(_phase)
	_role = Ui.label("", 0, Ui.MUTED, true)
	phase_box.add_child(_role)
	_notices = Ui.vbox(top, 6)
	_notices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_passthrough(_notices)
	_kpis = Ui.rich()
	var kpi_panel := _sized(Ui.panel(top), 520)
	kpi_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	kpi_panel.add_child(_kpis)
	var filler := Control.new()
	filler.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(_passthrough(filler))
	var bottom := Ui.hbox(column)
	_passthrough(bottom)
	bottom.add_child(Ui.label(HELP, 15, Ui.MUTED))
	_passthrough(Ui.spacer(bottom))
	_prompt = Ui.label("", 22, Ui.ACCENT)
	bottom.add_child(_prompt)

	_overlay = CenterContainer.new()
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	root.add_child(_overlay)
	_build_decisions()
	_build_dialogue()
	_build_kpis()
	_build_menu()
	_build_debrief()

	var state := Session.state()
	_last_status = state.get("status", "")
	for event: Dictionary in state.get("events", []):
		_last_events.append(event["id"])
	Session.lobby_changed.connect(_render)
	EventBus.lobby_state_changed.connect(_on_state_event)
	_render()


# --- API utilisée par le monde ---------------------------------------------------------------------------


func is_modal() -> bool:
	return _overlay.visible


func set_prompt(text: String) -> void:
	_prompt.text = text


func open_dialogue(npc: Dictionary) -> void:
	_npc = npc
	_dialogue_title.text = "%s · %s" % [npc["name"], npc["job"]]
	_render_dialogue()
	_open("dialogue")
	_dialogue_input.grab_focus()


func open_kpis() -> void:
	_open("kpis")


func toggle_decisions() -> void:
	if _panels["decisions"].visible:
		close_panels()
	else:
		_render_decisions()
		_open("decisions")


## Échap : ferme le panneau ouvert, sinon ouvre le menu.
func toggle_menu() -> void:
	if is_modal():
		close_panels()
	else:
		_menu_debrief.visible = Session.is_manager() or Session.state().get("status") == "finished"
		_open("menu")


func close_panels() -> void:
	for panel: Control in _panels.values():
		panel.visible = false
	_overlay.visible = false
	modal_changed.emit(false)


func notice(text: String, color := Color.WHITE) -> void:
	var panel := Ui.panel(_notices)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(Ui.label(text, 0, color, true))
	await get_tree().create_timer(NOTICE_SECONDS).timeout
	if is_instance_valid(panel):
		panel.queue_free()


# --- rendu -----------------------------------------------------------------------------------------------


func _render() -> void:
	var spec := Session.spec()
	var state := Session.state()
	_phase.text = GameText.phase_bbcode(state)
	_kpis.text = GameText.kpis_bbcode(spec, state)
	_big_kpis.text = "%s\n\n%s" % [GameText.phase_bbcode(state), GameText.kpis_bbcode(spec, state)]
	if Session.is_manager():
		_role.text = "Vous pilotez la partie : vous pouvez trancher toute décision."
	elif Session.lobby.get("my_role") == null:
		_role.text = "Aucun rôle : choisissez-en un dans la salle du lobby (Échap, puis Retour au lobby)."
	else:
		_role.text = "Votre rôle : %s" % GameText.role_title(spec, Session.lobby["my_role"])
	if _panels.has("decisions") and _panels["decisions"].visible:
		_render_decisions()


func _render_decisions() -> void:
	Ui.clear(_decisions_box)
	var spec := Session.spec()
	var state := Session.state()
	var status: String = state.get("status", "waiting")
	if status != "running":
		var text := "Les décisions s'ouvrent quand le formateur lance la partie."
		if status == "finished":
			text = "Partie terminée : consultez le débrief."
		_decisions_box.add_child(Ui.label(text, 0, Ui.MUTED, true))
		return
	var phase: Dictionary = spec["phases"][int(state["phase_index"])]
	var taken: Dictionary = state.get("decisions", {})
	if phase["decisions"].is_empty():
		_decisions_box.add_child(Ui.label("Aucune décision dans cette phase : observez et préparez la suite.", 0, Ui.MUTED, true))
	for decision: Dictionary in phase["decisions"]:
		var card := Ui.vbox(Ui.panel(_decisions_box), 6)
		card.add_child(Ui.label(decision["prompt"], 20, Color.WHITE, true))
		var info := "Rôle : %s" % GameText.role_title(spec, decision["role"])
		if decision.get("advisor_npc"):
			info += "  ·  Conseil : allez voir %s" % _npc_name(spec, decision["advisor_npc"])
		card.add_child(Ui.label(info, 0, Ui.MUTED, true))
		if taken.has(decision["id"]):
			var chosen := _option_label(decision, taken[decision["id"]]["option_id"])
			card.add_child(Ui.label("Décision prise : %s" % chosen, 0, Ui.OK, true))
		elif _can_decide(decision):
			for option: Dictionary in decision["options"]:
				var button := Ui.button(option["label"], func() -> void: _decide(decision["id"], option["id"]))
				button.alignment = HORIZONTAL_ALIGNMENT_LEFT
				button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				card.add_child(button)
		else:
			card.add_child(Ui.label("Revient à un autre rôle : discutez-en avec votre équipe.", 0, Ui.WARN, true))


func _render_dialogue() -> void:
	var lines := PackedStringArray()
	lines.append(
		"[color=%s][i]%s : « Bonjour, je suis %s. Qu'aimeriez-vous comprendre ? »[/i][/color]"
		% [GameText.GREY, GameText.esc(_npc["name"]), GameText.esc(_npc["name"])]
	)
	for turn: Dictionary in Session.dialogues.get(_npc["id"], []):
		if turn["role"] == "user":
			lines.append("[b]Vous :[/b] %s" % GameText.esc(turn["content"]))
			continue
		lines.append("[b]%s :[/b] %s" % [GameText.esc(_npc["name"]), GameText.esc(turn["content"])])
		var sources := PackedStringArray()
		for source: Dictionary in turn.get("sources", []):
			sources.append("[lb]%s] %s" % [source["ref"], GameText.esc(source["title"])])
		if not sources.is_empty():
			lines.append("[font_size=14][color=%s]Sources : %s[/color][/font_size]" % [GameText.GREY, ", ".join(sources)])
	_dialogue_log.text = "\n\n".join(lines)


# --- actions ---------------------------------------------------------------------------------------------


func _decide(decision_id: String, option_id: String) -> void:
	var body := {"decision_id": decision_id, "option_id": option_id}
	var res: Dictionary = await Api.post_json(Session.url("/decisions"), body)
	if not res["ok"]:
		notice(res["error"], Ui.ERROR)
		return
	Session.apply_state(res["data"]["state"])
	notice("Décision enregistrée : ses effets apparaîtront dans les indicateurs.", Ui.OK)


func _send_message() -> void:
	var text := _dialogue_input.text.strip_edges()
	if text.is_empty() or not _dialogue_input.editable:
		return
	var npc_id: String = _npc["id"]
	var history: Array = Session.dialogues.get_or_add(npc_id, [])
	var previous := []
	for turn: Dictionary in history.slice(-6):
		previous.append({"role": turn["role"], "content": turn["content"]})
	history.append({"role": "user", "content": text})
	_dialogue_input.text = ""
	_dialogue_input.editable = false
	_dialogue_send.disabled = true
	_render_dialogue()
	_dialogue_log.append_text("\n\n[color=%s]…[/color]" % GameText.GREY)
	var url := Session.url("/npcs/%s/talk" % npc_id)
	var res: Dictionary = await Api.post_json(url, {"message": text, "history": previous}, TALK_TIMEOUT_S)
	_dialogue_input.editable = true
	_dialogue_send.disabled = false
	if not res["ok"]:
		history.pop_back()
		_dialogue_input.text = text
		notice("Pas de réponse : %s" % res["error"], Ui.ERROR)
	else:
		history.append({"role": "assistant", "content": res["data"]["reply"], "sources": res["data"].get("sources", [])})
	if _npc.get("id") == npc_id:
		_render_dialogue()
		_dialogue_input.grab_focus()


func _show_debrief() -> void:
	var res: Dictionary = await Api.get_json(Session.url("/debrief"))
	if not res["ok"]:
		notice(res["error"], Ui.ERROR)
		return
	_debrief_text.text = GameText.debrief_bbcode(res["data"])
	_open("debrief")


func _on_state_event(payload: Dictionary) -> void:
	var state: Dictionary = payload.get("state", {})
	var action: Dictionary = payload.get("action", {})
	match action.get("type", ""):
		"start":
			notice("La partie commence ! Tab pour voir les décisions de la phase.", Ui.ACCENT)
		"advance":
			if state.get("status") != "finished":
				notice("Nouvelle phase : %s" % state.get("phase", {}).get("title", ""), Ui.ACCENT)
		"decision":
			var label := _find_option_label(str(action.get("decision_id", "")), str(action.get("option_id", "")))
			notice("%s a décidé : %s" % [action.get("by", "?"), label])
	for event: Dictionary in state.get("events", []):
		if not event["id"] in _last_events:
			_last_events.append(event["id"])
			notice("Aléa : %s. %s" % [event["title"], event["description"]], Ui.WARN)
	var status: String = state.get("status", "")
	if status == "finished" and _last_status != "finished":
		_show_debrief()
	_last_status = status


# --- outils ----------------------------------------------------------------------------------------------


func _can_decide(decision: Dictionary) -> bool:
	return Session.is_manager() or Session.lobby.get("my_role") == decision["role"]


func _option_label(decision: Dictionary, option_id: Variant) -> String:
	for option: Dictionary in decision["options"]:
		if option["id"] == option_id:
			return option["label"]
	return str(option_id)


func _find_option_label(decision_id: String, option_id: String) -> String:
	for phase: Dictionary in Session.spec().get("phases", []):
		for decision: Dictionary in phase["decisions"]:
			if decision["id"] == decision_id:
				return _option_label(decision, option_id)
	return option_id


func _npc_name(spec: Dictionary, npc_id: String) -> String:
	for npc: Dictionary in spec.get("npcs", []):
		if npc["id"] == npc_id:
			return npc["name"]
	return npc_id


func _open(panel_name: String) -> void:
	for key: String in _panels:
		(_panels[key] as Control).visible = key == panel_name
	_overlay.visible = true
	modal_changed.emit(true)


func _modal(panel_name: String, title: String, min_size: Vector2) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = min_size
	panel.visible = false
	_overlay.add_child(panel)
	_panels[panel_name] = panel
	var box := Ui.vbox(panel)
	var header := Ui.hbox(box)
	header.add_child(Ui.label(title, 24))
	Ui.spacer(header)
	header.add_child(Ui.button("Fermer", close_panels))
	return box


func _build_decisions() -> void:
	var box := _modal("decisions", "Décisions de la phase", Vector2(920, 640))
	_decisions_box = Ui.scroll_list(box, 540)


func _build_dialogue() -> void:
	var box := _modal("dialogue", "Dialogue", Vector2(920, 660))
	_dialogue_title = Ui.label("", 20, Ui.ACCENT)
	box.add_child(_dialogue_title)
	_dialogue_log = Ui.rich(460)
	_dialogue_log.scroll_following = true
	box.add_child(_dialogue_log)
	var row := Ui.hbox(box)
	_dialogue_input = Ui.field("Votre question…")
	_dialogue_input.max_length = 500
	_dialogue_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_dialogue_input.text_submitted.connect(func(_text: String) -> void: _send_message())
	row.add_child(_dialogue_input)
	_dialogue_send = Ui.button("Envoyer", _send_message)
	row.add_child(_dialogue_send)
	box.add_child(Ui.label("Le PNJ s'appuie sur les sources du domaine et ne choisit pas à votre place.", 14, Ui.MUTED, true))


func _build_kpis() -> void:
	var box := _modal("kpis", "Écran des indicateurs", Vector2(820, 0))
	_big_kpis = Ui.rich()
	box.add_child(_big_kpis)


func _build_menu() -> void:
	var box := _modal("menu", "Menu", Vector2(460, 0))
	box.add_child(Ui.button("Reprendre", close_panels))
	box.add_child(Ui.button("Décisions de la phase", toggle_decisions))
	box.add_child(Ui.button("Indicateurs", open_kpis))
	_menu_debrief = Ui.button("Débrief", _show_debrief)
	box.add_child(_menu_debrief)
	box.add_child(Ui.button("Retour à la salle du lobby", func() -> void: leave_requested.emit()))


func _build_debrief() -> void:
	var box := _modal("debrief", "Débrief", Vector2(1100, 760))
	_debrief_text = Ui.rich(660)
	box.add_child(_debrief_text)


func _passthrough(control: Control) -> Control:
	control.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return control


func _sized(panel: PanelContainer, width: float) -> PanelContainer:
	panel.custom_minimum_size.x = width
	return panel
