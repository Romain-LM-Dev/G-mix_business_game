class_name GmixHud
extends CanvasLayer
## Interface du monde 3D : semaine et indicateurs, annonces, invite d'interaction, vue active et aide des touches,
## info-bulle de survol, menu contextuel (vue Sims) et panneaux modaux (poste de travail avec les actions de ses
## modules, dialogue avec un agent, tableau de bord, menu, débrief).
## Données : Session (API + WebSocket) ; règles et chiffres viennent du serveur, rien n'est calculé ici.
## Le HUD est une CanvasLayer : le thème commun n'y descend pas tout seul, il est posé sur la racine `_root`.

signal modal_changed(open: bool)
signal leave_requested

const NOTICE_SECONDS := 8.0
const HELP_SIMS := (
	"Clic : marcher · Clic sur un agent ou un poste : menu · Molette : zoom · Clic droit + glisser ou flèches gauche et droite : "
	+ "tourner · ZQSD (WASD en QWERTY) : déplacer la caméra · C : suivre le joueur · V : troisième personne · E : interagir · "
	+ "Tab : tableau de bord · Échap : menu"
)
const HELP_THIRD := "ZQSD (WASD en QWERTY) : se déplacer · Maj : courir · Espace : sauter · E : interagir · V : vue Sims · Tab : tableau de bord · Échap : menu"
const TALK_TIMEOUT_S := 90.0  # premier message : le modèle de dialogue peut devoir se charger en VRAM
const SOURCE_KEYS := {"offers": "component_id", "lines": "id", "products": "id"}
const HUD_FONT := 16  # indicateurs et semaine : l'atelier reste visible derrière
const GLASS_ALPHA := UiTokens.GLASS_ALPHA  # panneaux du bandeau : lisibles, mais ils laissent deviner l'atelier
const MENU_WIDTH := 320
const HOVER_WIDTH := 360
const BREAK_EVERY := 28  # un mot plus long (chemin, message d'erreur) reçoit des points de coupure invisibles

var _root: Control
var _week: RichTextLabel
var _role: Label
var _kpis: RichTextLabel
var _notices: VBoxContainer
var _prompt: Label
var _prompt_panel: PanelContainer
var _prompt_text := ""  # texte demandé (le Label garde sa version coupée en lignes)
var _hover_text := ""
var _view_label: Label
var _help: Label
var _hover: PanelContainer
var _hover_label: Label
var _context_menu: PanelContainer
var _overlay: CenterContainer
var _panels: Dictionary = {}
var _station: Dictionary = {}
var _station_title: Label
var _station_info: RichTextLabel
var _station_actions: VBoxContainer
var _agent: Dictionary = {}
var _exchanges: Array = []  # [{message, reply}] de ce joueur avec l'agent ouvert
var _dialogue_title: Label
var _dialogue_tasks: Label
var _dialogue_log: RichTextLabel
var _dialogue_input: LineEdit
var _dialogue_send: Button
var _dashboard: RichTextLabel
var _debrief_text: RichTextLabel
var _menu_debrief: Button
var _last_event := ""
var _last_status := ""


func _ready() -> void:
	_root = Control.new()
	_root.theme = Ui.make_theme()
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_root)
	var column := Ui.vbox(_passthrough(Ui.screen_margin(_root, 16)))
	_passthrough(column)
	var top := Ui.hbox(column, 16)
	_passthrough(top)
	var week_panel := _sized(_glass(Ui.panel(top)), 440)
	week_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var week_box := Ui.vbox(week_panel, 6)
	_week = _hud_text(Ui.rich())
	week_box.add_child(_week)
	_role = Ui.label("", HUD_FONT, Ui.MUTED, true)
	week_box.add_child(_role)
	_notices = Ui.vbox(top, 6)
	_notices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_passthrough(_notices)
	_kpis = _hud_text(Ui.rich())
	var kpi_panel := _sized(_glass(Ui.panel(top)), 440)
	kpi_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	kpi_panel.add_child(_kpis)
	var filler := Control.new()
	filler.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(_passthrough(filler))
	var bottom := Ui.vbox(column, 8)  # invite d'interaction au centre, au-dessus de l'aide des touches
	_passthrough(bottom)
	_prompt_panel = _glass(Ui.panel(bottom))
	_prompt_panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_prompt_panel.visible = false
	_prompt = Ui.label("", 22, Ui.ACCENT, true)
	_prompt_panel.add_child(_prompt)
	var help_panel := _glass(Ui.panel(bottom))
	var help_box := Ui.vbox(help_panel, 2)
	_view_label = Ui.label("", 16, Ui.ACCENT, true)
	_view_label.theme_type_variation = "MonoLabel"
	help_box.add_child(_view_label)
	_help = Ui.label("", Ui.MIN_FONT, Ui.MUTED, true)
	help_box.add_child(_help)

	_hover = _glass(Ui.panel(_root))
	_hover.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hover.visible = false
	_hover_label = Ui.label("", 16, Color.WHITE, true)
	_hover.add_child(_hover_label)

	var dim := ColorRect.new()  # voile derrière les panneaux modaux, comme les modales du jeu de référence
	dim.color = Color(UiTokens.BACKDROP, 0.6)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	dim.visible = false
	_root.add_child(dim)
	_overlay = CenterContainer.new()
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.visible = false
	_overlay.visibility_changed.connect(func() -> void: dim.visible = _overlay.visible)
	_root.add_child(_overlay)
	_build_station()
	_build_dialogue()
	_build_dashboard()
	_build_menu()
	_build_debrief()
	set_view(true, true)

	var state := Session.state()
	_last_status = state.get("status", "")
	var event: Variant = state.get("event")
	_last_event = str(event["id"]) if event is Dictionary else ""
	Session.lobby_changed.connect(_render)
	EventBus.lobby_state_changed.connect(_on_state_event)
	_render()


# --- API utilisée par le monde ---------------------------------------------------------------------------


func is_modal() -> bool:
	return _overlay.visible


func set_prompt(text: String) -> void:
	_prompt_panel.visible = not text.is_empty()
	if _prompt_text != text:
		_prompt_text = text
		_set_wrapped(_prompt, text, get_viewport().get_visible_rect().size.x - 96.0)


## Vue active et aide des touches qui va avec. `follow` : la caméra de la vue Sims suit le joueur (sinon elle est libre).
func set_view(sims: bool, follow: bool) -> void:
	if sims:
		_view_label.text = "Vue Sims · caméra %s" % ("suivie" if follow else "libre")
	else:
		_view_label.text = "Vue à la troisième personne"
	_help.text = HELP_SIMS if sims else HELP_THIRD


## Info-bulle de survol près du curseur (`at` en pixels de la fenêtre de référence) ; texte vide : la masque.
func show_hover(text: String, at: Vector2) -> void:
	_hover.visible = not text.is_empty() and not _overlay.visible and not is_context_menu_open()
	if not _hover.visible:
		return
	if _hover_text != text:
		_hover_text = text
		_set_wrapped(_hover_label, text, HOVER_WIDTH)
	_hover.size = _hover.get_combined_minimum_size()
	_hover.position = _keep_inside(at + Vector2(18.0, 22.0), _hover.size)


## Menu contextuel d'un objet ou d'un agent, près du clic ; `entries` : [[libellé, Callable]]. Un choix ferme le menu
## puis appelle son action. Il se ferme aussi par Échap, par un clic ailleurs ou à l'ouverture d'un panneau.
func open_context_menu(title: String, entries: Array, at: Vector2) -> void:
	close_context_menu()
	var panel := PanelContainer.new()
	panel.custom_minimum_size.x = minf(MENU_WIDTH, get_viewport().get_visible_rect().size.x - 16.0)
	panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	var box := Ui.vbox(panel, 6)
	box.add_child(Ui.label(_breakable(title), 18, Ui.ACCENT, true))
	for entry: Array in entries:
		var action: Callable = entry[1]
		var button := Ui.button(_breakable(entry[0]), func() -> void:
			close_context_menu()
			action.call()
		)
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(button)
	_root.add_child(panel)
	_context_menu = panel
	_hover.visible = false
	panel.position = _keep_inside(at, panel.get_combined_minimum_size())
	_settle_menu.call_deferred(panel, at)


## Ferme le menu contextuel ; vrai s'il était ouvert (le clic qui le ferme ne doit pas aussi donner un ordre).
func close_context_menu() -> bool:
	var was_open := is_instance_valid(_context_menu)
	if was_open:
		_context_menu.hide()  # sinon il reçoit encore un clic poussé avant la fin de l'image
		_context_menu.queue_free()
	_context_menu = null
	return was_open


func is_context_menu_open() -> bool:
	return is_instance_valid(_context_menu)


func open_station(station: Dictionary) -> void:
	_station = station
	_station_title.text = station["label"]
	_render_station()
	_open("station")


func open_dialogue(agent: Dictionary) -> void:
	_agent = agent
	_exchanges = []
	var personality: Dictionary = agent.get("personality", {})
	_dialogue_title.text = "%s · %s · %s" % [agent["name"], agent["job"], personality.get("label", "")]
	_dialogue_tasks.text = "Ses tâches : %s." % ", ".join(agent.get("tasks", []))
	var now := GmixFactoryState.agent(Session.state(), str(agent["id"]))  # usine : disponible, occupé, en déplacement, en pause, absent
	if not now.is_empty():
		_dialogue_tasks.text += " État : %s." % GmixFactoryState.state_text(str(now["state"]))
	_render_dialogue()
	_open("dialogue")
	_dialogue_input.grab_focus()
	var res: Dictionary = await Api.get_json(Session.url("/npcs/%s/memory" % agent["id"]))
	if res["ok"] and _agent.get("id") == agent["id"]:  # l'agent se souvient : le fil reprend où il s'était arrêté
		_exchanges = res["data"]
		_render_dialogue()


func toggle_dashboard() -> void:
	if _panels["dashboard"].visible:
		close_panels()
	else:
		_render_dashboard()
		_open("dashboard")


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
	var panel := _glass(Ui.panel(_notices))
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(Ui.label(_breakable(text), 0, color, true))
	await get_tree().create_timer(NOTICE_SECONDS).timeout
	if is_instance_valid(panel):
		panel.queue_free()


# --- rendu -----------------------------------------------------------------------------------------------


func _render() -> void:
	var spec := Session.spec()
	var state := Session.state()
	_week.text = GameText.week_bbcode(spec, state)
	_kpis.text = GameText.kpis_bbcode(state)
	if Session.is_manager():
		_role.text = "Vous pilotez la partie : vous pouvez agir sur tous les modules."
	elif Session.lobby.get("my_role") == null:
		_role.text = "Aucun rôle : vous aidez sur les modules sans titulaire (Échap, Retour à la salle pour en choisir un)."
	else:
		var role_id: String = Session.lobby["my_role"]
		_role.text = "Votre rôle : %s" % GameText.role_title(spec, role_id)
		for role: Dictionary in spec.get("roles", []):
			if role["id"] == role_id:
				_role.text += " · %s" % role["mission"]
	if _panels.has("station") and _panels["station"].visible:
		_render_station()
	if _panels.has("dashboard") and _panels["dashboard"].visible:
		_render_dashboard()
	if _panels.has("dialogue") and _panels["dialogue"].visible:
		_render_dialogue()


func _render_station() -> void:
	var spec := Session.spec()
	var state := Session.state()
	_station_info.text = GameText.station_bbcode(spec, state, _station)
	Ui.clear(_station_actions)
	var module_ids: Array = _station.get("modules", [])
	if module_ids.is_empty():
		if _station["kind"] != "ecran_kpi" and _station["kind"] != "rack_produit":
			_station_actions.add_child(Ui.label("Aucun module de ce poste n'a été retenu pour cette partie : il est géré automatiquement.", 0, Ui.MUTED, true))
		return
	var running: bool = state.get("status") == "running"
	for module: Dictionary in spec.get("modules", []):
		if not module["id"] in module_ids:
			continue
		var box := Ui.vbox(Ui.panel(_station_actions), 6)
		box.add_child(Ui.label(module["title"], 20, Ui.ACCENT))
		box.add_child(Ui.label(module["description"], 0, Ui.MUTED, true))
		var blocked := _blocked_reason(module)
		if not running:
			blocked = "Les actions s'ouvrent quand le formateur lance la partie." if state.get("status") == "waiting" else "Partie terminée."
		if not blocked.is_empty():
			box.add_child(Ui.label(blocked, 0, Ui.WARN, true))
		for action: Dictionary in module["actions"]:
			_action_form(box, module, action, blocked.is_empty())


## Formulaire d'une action à partir de ses champs (spec.modules[].actions[].fields) : liste de choix ou nombre.
func _action_form(parent: Node, module: Dictionary, action: Dictionary, enabled: bool) -> void:
	parent.add_child(Ui.label(action["label"], 18))
	var getters := {}
	for field: Dictionary in action["fields"]:
		var row := Ui.hbox(parent)
		var caption := Ui.label(field["label"], 0, Ui.MUTED)
		caption.custom_minimum_size.x = 240
		row.add_child(caption)
		if field["type"] == "int":
			var spin := SpinBox.new()
			spin.min_value = field["min"]
			spin.max_value = field["max"]
			spin.step = field["step"] if field.get("step") != null else 1
			spin.value = field["default"] if field.get("default") != null else field["min"]
			spin.editable = enabled
			row.add_child(spin)
			getters[field["id"]] = func() -> Variant: return int(spin.value)
		else:
			var choices := _choices(field)
			var select := OptionButton.new()
			select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			select.clip_text = true
			var current: Variant = _current(field["id"])
			for i in choices.size():
				select.add_item(choices[i][1])
				if choices[i][0] == current:
					select.selected = i
			select.disabled = not enabled
			row.add_child(select)
			getters[field["id"]] = func() -> Variant: return choices[select.selected][0]
	var submit := Ui.button("Valider", func() -> void: _act(module["id"], action["id"], getters))
	submit.disabled = not enabled
	parent.add_child(submit)


## [[id, libellé]] d'un champ ; au pied d'un rayonnage ou d'une ligne, seuls son composant, sa ligne ou son produit.
func _choices(field: Dictionary) -> Array:
	var source: Variant = field.get("source")
	if source == null:
		return field["options"].map(func(option: Dictionary) -> Array: return [option["id"], option["label"]])
	var items: Array = Session.spec().get(source, [])
	var ref: Variant = _station.get("ref")
	var local := items.filter(func(item: Dictionary) -> bool: return item.get(SOURCE_KEYS[source]) == ref)
	return (local if not local.is_empty() else items).map(
		func(item: Dictionary) -> Array: return [item["id"], item.get("label", item.get("name", item["id"]))]
	)


## Réglage en vigueur pour présélectionner la liste (entretien de la ligne du poste, contrôle, transport, découvert).
func _current(field_id: String) -> Variant:
	var settings: Dictionary = Session.state().get("settings", {})
	match field_id:
		"level":
			return settings.get("maintenance", {}).get(_station.get("ref"))
		"rate":
			return settings.get("control")
		"mode":
			return settings.get("transport")
		"limit":
			return settings.get("overdraft")
	return null


## Un rôle tenu par un autre joueur garde la main sur son module (l'API tranche, ceci évite un aller-retour).
func _blocked_reason(module: Dictionary) -> String:
	var role_id: String = module["role_id"]
	if Session.is_manager() or Session.lobby.get("my_role") == role_id:
		return ""
	for member: Dictionary in Session.lobby.get("members", []):
		if member.get("game_role") == role_id:
			return "Revient à %s (%s) : allez en discuter." % [member["display_name"], GameText.role_title(Session.spec(), role_id)]
	return ""


func _render_dialogue() -> void:
	var who := GameText.esc(_agent.get("name", ""))
	var briefing: Dictionary = Session.state().get("briefings", {}).get(_agent.get("id"), {})
	var facts: Array = briefing.get("facts", [])
	var opening: Variant = briefing.get("line")
	if not opening is String:
		opening = facts[0] if not facts.is_empty() else "Bonjour, que puis-je pour toi ?"
	var lines := PackedStringArray()
	for exchange: Dictionary in _exchanges:
		var week := "[color=%s]S%d[/color] " % [GameText.GREY, int(exchange["week"])] if exchange.get("week") != null else ""
		lines.append("%s[b]Vous :[/b] %s" % [week, GameText.esc(exchange["message"])])
		lines.append("[b]%s :[/b] %s" % [who, GameText.esc(exchange["reply"])])
		for source: Dictionary in exchange.get("sources", []):
			lines.append("[font_size=16][color=%s][lb]%s] %s[/color][/font_size]" % [GameText.GREY, source["ref"], GameText.esc(source["title"])])
	lines.append("[i][b]%s :[/b] %s[/i]" % [who, GameText.esc(opening)])  # ce que l'agent a à dire maintenant
	_dialogue_log.text = "\n\n".join(lines)


func _render_dashboard() -> void:
	_dashboard.text = GameText.dashboard_bbcode(Session.spec(), Session.state())


# --- actions ---------------------------------------------------------------------------------------------


func _act(module_id: String, action_id: String, getters: Dictionary) -> void:
	var values := {}
	for key: String in getters:
		values[key] = (getters[key] as Callable).call()
	var res: Dictionary = await Api.post_json(Session.url("/actions"), {"module": module_id, "action": action_id, "values": values})
	if not res["ok"]:
		notice(res["error"], Ui.ERROR)
		return
	notice(res["data"]["summary"], Ui.OK)
	Session.apply_state(res["data"]["state"])


func _send_message() -> void:
	var text := _dialogue_input.text.strip_edges()
	if text.is_empty() or not _dialogue_input.editable:
		return
	var agent_id: String = _agent["id"]
	_dialogue_input.text = ""
	_dialogue_input.editable = false
	_dialogue_send.disabled = true
	_dialogue_log.append_text("\n\n[b]Vous :[/b] %s\n\n[color=%s]…[/color]" % [GameText.esc(text), GameText.GREY])
	var res: Dictionary = await Api.post_json(Session.url("/npcs/%s/talk" % agent_id), {"message": text}, TALK_TIMEOUT_S)
	_dialogue_input.editable = true
	_dialogue_send.disabled = false
	if not res["ok"]:
		_dialogue_input.text = text
		notice("Pas de réponse : %s" % res["error"], Ui.ERROR)
	elif _agent.get("id") == agent_id:
		var data: Dictionary = res["data"]
		_exchanges.append({"message": text, "reply": data["reply"], "week": Session.state().get("week"), "sources": data.get("sources", [])})
	if _agent.get("id") == agent_id:
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
			notice("La partie commence : semaine 1. Allez aux postes (E) et parlez aux agents.", Ui.ACCENT)
		"advance":
			var last: Variant = state.get("last")
			if last is Dictionary:
				var kpis: Dictionary = last["kpis"]
				var lost := int(last["totals"]["lost"])
				notice(
					"Semaine %d simulée : OTIF %s %%, %d vente(s) perdue(s), trésorerie %s."
					% [int(last["week"]), GameText.number(kpis["otif"]), lost, GameText.money(kpis["cash"])],
					Ui.ACCENT if lost == 0 else Ui.WARN
				)
		"action":
			if action.get("by") != Api.user.get("display_name"):  # sa propre action est déjà annoncée par _act
				notice("%s : %s" % [action.get("by", "?"), action.get("summary", "")])
	var event: Variant = state.get("event")
	var event_id := str(event["id"]) if event is Dictionary else ""
	if not event_id.is_empty() and event_id != _last_event:
		notice("Annoncé cette semaine : %s. %s" % [event["title"], event["description"]], Ui.WARN)
	_last_event = event_id
	var status: String = state.get("status", "")
	if status == "finished" and _last_status != "finished":
		_show_debrief()
	_last_status = status


# --- construction ----------------------------------------------------------------------------------------


func _open(panel_name: String) -> void:
	close_context_menu()
	_hover.visible = false
	for key: String in _panels:
		(_panels[key] as Control).visible = key == panel_name
	_overlay.visible = true
	modal_changed.emit(true)


## Panneau modal : taille souhaitée, limitée à 88 % de la fenêtre de référence (la zone visible ne descend jamais
## en dessous : project.godot, aspect `expand`). Le contenu long défile dans le panneau (hauteurs minimales basses).
func _modal(panel_name: String, title: String, min_size: Vector2) -> VBoxContainer:
	var reference := Vector2(
		float(ProjectSettings.get_setting("display/window/size/viewport_width")),
		float(ProjectSettings.get_setting("display/window/size/viewport_height"))
	)
	var panel := PanelContainer.new()  # thème commun hérité de `_root` : panneau opaque, lisible
	panel.custom_minimum_size = min_size.min(reference * 0.88)
	panel.visible = false
	_overlay.add_child(panel)
	_panels[panel_name] = panel
	var box := Ui.vbox(panel)
	var header := Ui.hbox(box)
	var caption := Ui.label(title, 24)
	header.add_child(caption)
	Ui.spacer(header)
	header.add_child(Ui.button("Fermer", close_panels))
	return box


func _build_station() -> void:
	var box := _modal("station", "Poste", Vector2(980, 720))
	_station_title = Ui.label("", 22, Ui.ACCENT)
	box.add_child(_station_title)
	var list := Ui.scroll_list(box, 200)
	_station_info = Ui.rich()
	list.add_child(_station_info)
	_station_actions = Ui.vbox(list, 12)


func _build_dialogue() -> void:
	var box := _modal("dialogue", "Dialogue", Vector2(920, 660))
	_dialogue_title = Ui.label("", 20, Ui.ACCENT)
	box.add_child(_dialogue_title)
	_dialogue_tasks = Ui.label("", 14, Ui.MUTED, true)
	box.add_child(_dialogue_tasks)
	_dialogue_log = Ui.rich(200)
	_dialogue_log.scroll_following = true
	box.add_child(_dialogue_log)
	var row := Ui.hbox(box)
	_dialogue_input = Ui.field("Votre question ou votre réponse…")
	_dialogue_input.max_length = 300
	_dialogue_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_dialogue_input.text_submitted.connect(func(_text: String) -> void: _send_message())
	row.add_child(_dialogue_input)
	_dialogue_send = Ui.button("Envoyer", _send_message)
	row.add_child(_dialogue_send)
	box.add_child(Ui.label("L'agent répond avec les chiffres de la semaine, se souvient de vos échanges et ne décide pas à votre place.", 14, Ui.MUTED, true))


func _build_dashboard() -> void:
	var box := _modal("dashboard", "Tableau de bord", Vector2(1100, 760))
	_dashboard = Ui.rich(200)
	box.add_child(_dashboard)


func _build_menu() -> void:
	var box := _modal("menu", "Menu", Vector2(460, 0))
	box.add_child(Ui.button("Reprendre", close_panels))
	box.add_child(Ui.button("Tableau de bord", toggle_dashboard))
	_menu_debrief = Ui.button("Débrief", _show_debrief)
	box.add_child(_menu_debrief)
	box.add_child(Ui.button("Retour à la salle du lobby", func() -> void: leave_requested.emit()))


func _build_debrief() -> void:
	var box := _modal("debrief", "Débrief", Vector2(1100, 760))
	_debrief_text = Ui.rich(200)
	box.add_child(_debrief_text)


func _passthrough(control: Control) -> Control:
	control.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return control


## Panneau du bandeau : fond du thème commun, un peu transparent, marges serrées.
func _glass(panel: PanelContainer) -> PanelContainer:
	var box := StyleBoxFlat.new()
	box.bg_color = Color(Ui.PANEL, GLASS_ALPHA)
	box.set_corner_radius_all(UiTokens.RADIUS_PANEL)
	box.border_color = Ui.EDGE
	box.set_border_width_all(1)
	box.content_margin_left = 12
	box.content_margin_right = 12
	box.content_margin_top = 8
	box.content_margin_bottom = 8
	box.shadow_color = Color(UiTokens.BACKDROP, 0.3)  # ombre douce du verre
	box.shadow_size = 8
	panel.add_theme_stylebox_override("panel", box)
	return panel


func _hud_text(text: RichTextLabel) -> RichTextLabel:
	for size_name in ["normal_font_size", "bold_font_size", "italics_font_size", "bold_italics_font_size", "mono_font_size"]:
		text.add_theme_font_size_override(size_name, HUD_FONT)
	return text


## Texte coupé en lignes d'au plus `max_width` px (coupures aux espaces, au caractère près pour un mot trop long). Les
## retours à la ligne sont posés ici et non par le Label : un Label à retour automatique ne donne sa hauteur qu'après sa
## mise en page, et une info-bulle ou une invite placée à la main resterait trop haute pendant une image.
func _set_wrapped(label: Label, text: String, max_width: float) -> void:
	var font := label.get_theme_font("font")
	var px := label.get_theme_font_size("font_size")
	var limit := maxf(max_width, 120.0)
	var lines := PackedStringArray()
	var line := ""
	for word in text.split(" "):
		while font.get_string_size(word, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > limit:
			var cut := word.length() - 1
			while cut > 1 and font.get_string_size(word.left(cut), HORIZONTAL_ALIGNMENT_LEFT, -1, px).x > limit:
				cut -= 1
			if not line.is_empty():
				lines.append(line)
				line = ""
			lines.append(word.left(cut))
			word = word.substr(cut)
		var joined := word if line.is_empty() else "%s %s" % [line, word]
		if line.is_empty() or font.get_string_size(joined, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x <= limit:
			line = joined
		else:
			lines.append(line)
			line = word
	lines.append(line)
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	label.text = "\n".join(lines)


## Coupures possibles dans les mots très longs (espaces de largeur nulle) : sans elles, un chemin ou un message d'erreur
## sans espace impose sa largeur à toute la colonne.
static func _breakable(text: String) -> String:
	var words := PackedStringArray()
	for word in text.split(" "):
		var chunks := PackedStringArray()
		while word.length() > BREAK_EVERY:
			chunks.append(word.left(BREAK_EVERY))
			word = word.substr(BREAK_EVERY)
		chunks.append(word)
		words.append("\u200b".join(chunks))
	return " ".join(words)


## Garde un contrôle de cette taille dans la zone visible (marge de 8 px).
func _keep_inside(where: Vector2, extent: Vector2) -> Vector2:
	var area := get_viewport().get_visible_rect().size
	return Vector2(
		clampf(where.x, 8.0, maxf(8.0, area.x - extent.x - 8.0)),
		clampf(where.y, 8.0, maxf(8.0, area.y - extent.y - 8.0))
	)


## La taille d'un menu (textes qui passent à la ligne) n'est connue qu'après sa mise en page : replace-le alors.
func _settle_menu(panel: PanelContainer, at: Vector2) -> void:
	await get_tree().process_frame
	if is_instance_valid(panel) and not panel.is_queued_for_deletion():
		panel.reset_size()
		panel.position = _keep_inside(at, panel.size)


func _sized(panel: PanelContainer, width: float) -> PanelContainer:
	panel.custom_minimum_size.x = width
	return panel
