extends Control
## Accueil après connexion. Joueur : rejoindre une partie avec son code, reprendre ses parties.
## Formateur et admin : business games (génération par paramètres, import, relecture, export), lobbies, comptes.
## L'interface masque ce que le rôle ne permet pas, mais seule l'API fait foi (docs/roles.md).

signal navigate(target: String)

const ROLE_NAMES := {"player": "joueur", "trainer": "formateur", "admin": "administrateur"}
const GAME_STATUS := {"draft": "brouillon", "generating": "génération", "ready": "prêt", "failed": "échec"}
const LOBBY_STATUS := {"ready": "ouvert", "running": "en cours", "closed": "terminé", "draft": "brouillon"}

var _status: Label
var _games: VBoxContainer
var _lobbies: VBoxContainer
var _users: VBoxContainer
var _options: Dictionary = {}  # GET /api/v1/games/options
var _form: VBoxContainer
var _pack_select: OptionButton  # seulement s'il y a plusieurs packs (`packs[]` des options)
var _pack_index := 0
var _option_getters: Dictionary = {}  # id d'une option du pack -> Callable qui lit sa valeur
var _option_controls: Dictionary = {}  # id d'une option du pack -> SpinBox ou OptionButton
var _theme_select: OptionButton
var _theme_info: Label
var _module_checks: Array = []  # [[id, CheckBox]]
var _agent_checks: Array = []
var _tone_select: OptionButton
var _difficulty_select: OptionButton
var _events_select: OptionButton
var _weeks: SpinBox
var _products: SpinBox
var _company: LineEdit
var _players_min: SpinBox
var _players_max: SpinBox
var _generate_button: Button
var _new_username: LineEdit
var _new_name: LineEdit
var _new_password: LineEdit
var _new_role: OptionButton
var _roles_offered: Array = []


func _ready() -> void:
	var column := Ui.vbox(Ui.screen_margin(self), 14)
	var header := Ui.hbox(column)
	header.add_child(Ui.label("Bonjour %s" % Api.user.get("display_name", ""), 28, Color.WHITE, true))
	header.add_child(Ui.label(ROLE_NAMES.get(Api.role(), Api.role()), 0, Ui.MUTED))
	header.add_child(Ui.button("Actualiser", _refresh))
	header.add_child(Ui.button("Diagnostic", func() -> void: navigate.emit("diagnostic")))
	header.add_child(Ui.button("Se déconnecter", func() -> void: navigate.emit("logout")))
	_status = Ui.label("", 0, Ui.ACCENT, true)
	column.add_child(_status)
	if Api.role() == "player":
		_build_player(column)
	else:
		_build_staff(column)
	_refresh()


# --- construction ---------------------------------------------------------------------------------------


func _build_player(column: VBoxContainer) -> void:
	var box := Ui.vbox(Ui.panel(column))
	box.add_child(Ui.label("Rejoindre une partie", 22))
	var row := Ui.hbox(box)
	var code := Ui.field("Code donné par le formateur", false, 340)
	code.max_length = 8
	row.add_child(code)
	code.text_submitted.connect(func(text: String) -> void: _join(text))
	row.add_child(Ui.button("Rejoindre", func() -> void: _join(code.text), true))
	code.grab_focus.call_deferred()
	var mine := Ui.panel(column)
	mine.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var list_box := Ui.vbox(mine)
	list_box.add_child(Ui.label("Mes parties", 22))
	_lobbies = Ui.scroll_list(list_box)


func _build_staff(column: VBoxContainer) -> void:
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(tabs)

	var games_tab := HBoxContainer.new()
	games_tab.name = "Business games"
	games_tab.add_theme_constant_override("separation", 16)
	tabs.add_child(games_tab)
	# Les deux panneaux se partagent la largeur (2 : 3) : aucune largeur fixe, la fenêtre peut être étroite.
	var list_panel := Ui.panel(games_tab)
	list_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list_panel.size_flags_stretch_ratio = 2.0
	var list_box := Ui.vbox(list_panel)
	var list_header := Ui.flow(list_box)  # le bouton passe sous le titre quand le panneau est étroit
	var list_title := Ui.label("Mes business games", 22)
	list_title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	list_header.add_child(list_title)
	list_header.add_child(Ui.button("Importer une spec JSON", _import_spec))
	_games = Ui.scroll_list(list_box)
	var form_panel := Ui.panel(games_tab)
	form_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form_panel.size_flags_stretch_ratio = 3.0
	var form_box := Ui.vbox(form_panel)
	form_box.add_child(Ui.label("Nouveau business game", 22))
	form_box.add_child(Ui.label("Aucun texte à rédiger : choisissez les paramètres, le jeu est assemblé et vérifié aussitôt.", 0, Ui.MUTED, true))
	_form = Ui.scroll_list(form_box)
	_generate_button = Ui.button("Générer le business game", _generate, true)
	form_box.add_child(_generate_button)

	var lobbies_tab := PanelContainer.new()
	lobbies_tab.name = "Lobbies"
	tabs.add_child(lobbies_tab)
	var lobbies_box := Ui.vbox(lobbies_tab)
	lobbies_box.add_child(Ui.label("Créez un lobby depuis un business game prêt, puis donnez le code aux joueurs.", 0, Ui.MUTED, true))
	_lobbies = Ui.scroll_list(lobbies_box)

	var accounts_tab := HBoxContainer.new()
	accounts_tab.name = "Comptes"
	accounts_tab.add_theme_constant_override("separation", 16)
	tabs.add_child(accounts_tab)
	var account_panel := Ui.panel(accounts_tab)
	account_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	account_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN  # un panneau s'étire sinon à la hauteur de l'onglet
	_build_account_form(account_panel)
	var users_panel := Ui.panel(accounts_tab)
	users_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var users_box := Ui.vbox(users_panel)
	users_box.add_child(Ui.label("Comptes que vous avez créés" if Api.role() == "trainer" else "Tous les comptes", 22))
	_users = Ui.scroll_list(users_box)


## Pack choisi dans le formulaire (GET /games/options, `packs[]`) ; un ancien serveur sans `packs` : les clés de premier
## niveau (pack atelier, bornes dans `ranges`).
func _current_pack() -> Dictionary:
	var packs: Array = _options.get("packs", [])
	if packs.is_empty():
		return _options.duplicate().merged({"id": "atelier", "limits": _options.get("ranges", {}), "params": []})
	return packs[clampi(_pack_index, 0, packs.size() - 1)]


## Paramètres proposés par l'API pour le pack choisi (ai/simulation.yaml ou ai/packs/<id>.yaml) : secteur, modules,
## agents, caractère, difficulté, durée, options propres au pack (lignes de production de l'usine…).
func _build_generation_form() -> void:
	var kept_company := _company.text if _company != null else ""
	Ui.clear(_form)
	var box := _form
	var pack := _current_pack()
	var packs: Array = _options.get("packs", [])
	if packs.size() > 1:  # un seul pack : rien à choisir
		_pack_select = _select(packs, "label")
		_pack_select.selected = _pack_index
		_pack_select.item_selected.connect(_choose_pack)
		_form_row(box, "Type de jeu", _pack_select)
	var about := str(pack.get("description", ""))
	if not about.is_empty() and packs.size() > 1:
		box.add_child(Ui.label(about, 16, Ui.MUTED, true))
	_theme_select = _select(pack["themes"], "label")
	_theme_select.item_selected.connect(func(_index: int) -> void: _show_theme())
	_form_row(box, "Secteur", _theme_select)
	_theme_info = Ui.label("", 16, Ui.MUTED, true)
	box.add_child(_theme_info)
	_show_theme()
	box.add_child(Ui.label("Modules joués (les autres tournent en pilote automatique)", 0, Color.WHITE, true))
	_module_checks = _checks(box, pack["modules"])
	_agent_checks = []
	if not (pack["extra_agents"] as Array).is_empty():
		box.add_child(Ui.label("Agents en plus des responsables de module", 0, Color.WHITE, true))
		_agent_checks = _checks(box, pack["extra_agents"])
	_tone_select = _select(pack["tones"], "label")
	_tone_select.selected = 1 if pack["tones"].size() > 1 else 0
	_form_row(box, "Caractère des agents", _tone_select)
	_difficulty_select = _select(pack["difficulties"], "label")
	_difficulty_select.selected = 1 if pack["difficulties"].size() > 1 else 0
	_form_row(box, "Difficulté", _difficulty_select)
	_events_select = _select(pack["events"], "label")
	_events_select.selected = 1 if pack["events"].size() > 1 else 0
	_form_row(box, "Aléas", _events_select)
	var limits: Dictionary = pack["limits"]  # [min, max, défaut], le même format que `ranges`
	_weeks = _spin(limits["weeks"][0], limits["weeks"][1], limits["weeks"][2], 1)
	_form_row(box, "Semaines", _weeks, false)
	_products = _spin(limits["products"][0], limits["products"][1], limits["products"][2], 1)
	if limits["products"][1] > limits["products"][0]:  # un pack à produit unique n'en demande pas le nombre
		_form_row(box, "Produits", _products, false)
	_option_getters = {}
	_option_controls = {}
	for option: Dictionary in pack.get("params", []):
		_build_option(box, option)
	_company = Ui.field("tirée au hasard si vide")
	_company.max_length = 40
	_company.text = kept_company
	_form_row(box, "Nom de l'entreprise", _company)
	var players := HBoxContainer.new()
	_players_min = _spin(1, 60, 2, 1)
	_players_max = _spin(1, 60, 6, 1)
	players.add_child(_players_min)
	players.add_child(Ui.label(" à "))
	players.add_child(_players_max)
	_form_row(box, "Joueurs", players, false)


## Option d'un pack (format ActionField : entier borné ou choix) ; sa valeur se lit par `_option_getters[id]`.
func _build_option(box: Node, option: Dictionary) -> void:
	var control: Control
	if option["type"] == "int":
		var spin := _spin(option["min"], option["max"], option["default"] if option.get("default") != null else option["min"], option["step"] if option.get("step") != null else 1)
		_option_getters[option["id"]] = func() -> Variant: return int(spin.value)
		control = spin
	else:
		var choices: Array = option.get("options", [])
		var select := _select(choices, "label")
		_option_getters[option["id"]] = func() -> Variant: return choices[select.selected]["id"]
		control = select
	_option_controls[option["id"]] = control
	_form_row(box, str(option["label"]), control, option["type"] != "int")


func _choose_pack(index: int) -> void:
	_pack_index = index
	_build_generation_form.call_deferred()  # le formulaire se reconstruit : pas pendant le signal de la liste qui le porte


## Liste de choix : libellé = item[key] ; l'infobulle reprend la description de l'API.
func _select(items: Array, key: String) -> OptionButton:
	var labels := []
	for item: Dictionary in items:
		labels.append(item[key])
	var select := Ui.select(labels)
	for i in items.size():
		select.set_item_tooltip(i, items[i].get("description", items[i].get("detail", "")))
	return select


## Cases à cocher sur deux colonnes, toutes cochées au départ ; renvoie [[id, CheckBox]]. Le texte passe à la ligne :
## un titre long ne pousse pas le formulaire hors de l'écran.
func _checks(parent: Node, items: Array) -> Array:
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	parent.add_child(grid)
	var checks := []
	for item: Dictionary in items:
		var check := CheckBox.new()
		check.text = item["title"]
		check.tooltip_text = item["description"]
		check.button_pressed = true
		check.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		check.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(check)
		checks.append([item["id"], check])
	return checks


func _show_theme() -> void:
	var sector: Dictionary = _current_pack()["themes"][_theme_select.selected]
	_theme_info.text = "%s Produits : %s." % [sector["description"], ", ".join(sector["products"])]


func _build_account_form(panel: PanelContainer) -> void:
	var box := Ui.vbox(panel)
	box.add_child(Ui.label("Créer un compte", 22))
	_new_username = Ui.field("lettres, chiffres, . _ -")
	_form_row(box, "Identifiant", _new_username)
	_new_name = Ui.field("Prénom Nom")
	_form_row(box, "Nom affiché", _new_name)
	_new_password = Ui.field("8 caractères minimum")
	_form_row(box, "Mot de passe provisoire", _new_password)
	_roles_offered = [["player", "Joueur"]]
	if Api.role() == "admin":
		_roles_offered += [["trainer", "Formateur"], ["admin", "Administrateur"]]
	_new_role = Ui.select(_roles_offered.map(func(role: Array) -> String: return role[1]))
	_form_row(box, "Rôle", _new_role)
	box.add_child(Ui.button("Créer le compte", _create_account, true))
	box.add_child(Ui.label("La personne change ce mot de passe à sa première connexion.", 0, Ui.MUTED, true))


## Ligne « légende + champ » ; la légende garde une largeur fixe et passe à la ligne si elle est longue.
## `expand` : le champ prend toute la largeur (faux pour les nombres).
func _form_row(parent: Node, caption: String, control: Control, expand := true) -> void:
	var row := Ui.hbox(parent)
	var title := Ui.label(caption, 0, Color.WHITE, true)
	title.size_flags_horizontal = Control.SIZE_FILL
	title.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	title.custom_minimum_size.x = 190
	row.add_child(title)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL if expand else Control.SIZE_SHRINK_BEGIN
	control.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(control)


func _spin(low: float, high: float, value: float, step: float) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = low
	spin.max_value = high
	spin.step = step
	spin.value = value
	spin.custom_minimum_size.x = 110
	return spin


# --- données ------------------------------------------------------------------------------------------


func _refresh() -> void:
	if Api.role() != "player":
		if _options.is_empty():
			await _load_options()
		await _load_games()
		await _load_users()
	await _load_lobbies()


func _load_options() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/games/options")
	if not res["ok"]:
		_status.text = res["error"]
		return
	_options = res["data"]
	_build_generation_form()


func _load_games() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/games")
	if not res["ok"]:
		_status.text = res["error"]
		return
	Ui.clear(_games)
	if res["data"].is_empty():
		_games.add_child(Ui.label("Aucun business game : générez-en un ou importez une spec.", 0, Ui.MUTED, true))
	for game: Dictionary in res["data"]:
		# Une ligne = le titre (retour à la ligne), puis ses boutons, puis un filet : lisible même dans un panneau étroit.
		var row := Ui.vbox(_games, 6)
		var status: String = game["status"]
		var color := Ui.OK if status == "ready" else (Ui.ERROR if status == "failed" else Ui.WARN)
		row.add_child(Ui.label("%s  [%s]" % [game["title"], GAME_STATUS.get(status, status)], 0, color, true))
		var buttons := Ui.flow(row)
		buttons.add_child(Ui.button("Relire", func() -> void: _show_game(str(game["id"]))))
		if status == "ready":
			buttons.add_child(Ui.button("Créer un lobby", func() -> void: _ask_lobby_name(game)))
		row.add_child(HSeparator.new())


func _load_lobbies() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/lobbies")
	if not res["ok"]:
		_status.text = res["error"]
		return
	Ui.clear(_lobbies)
	if res["data"].is_empty():
		_lobbies.add_child(Ui.label("Aucune partie pour l'instant.", 0, Ui.MUTED))
	for lobby: Dictionary in res["data"]:
		var row := Ui.hbox(_lobbies)
		var text := "%s  ·  %s  ·  %s" % [lobby["name"], lobby.get("game_title", ""), LOBBY_STATUS.get(lobby["status"], lobby["status"])]
		if lobby.get("join_code") and lobby["status"] != "closed":  # un code ne sert plus une fois la partie terminée
			text += "  ·  code [%s]" % lobby["join_code"]
		row.add_child(Ui.label(text, 0, Color.WHITE, true))
		row.add_child(Ui.button("Ouvrir", func() -> void: _open_lobby(str(lobby["id"]))))


func _load_users() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/users")
	if not res["ok"]:
		return
	Ui.clear(_users)
	for user: Dictionary in res["data"]:
		var pending := "  (mot de passe provisoire)" if user["must_change_password"] else ""
		var text := "%s  ·  %s  ·  %s%s" % [user["display_name"], user["username"], ROLE_NAMES.get(user["role"], user["role"]), pending]
		_users.add_child(Ui.label(text, 0, Color.WHITE, true))


# --- actions -------------------------------------------------------------------------------------------


func _join(code: String) -> void:
	if code.strip_edges().is_empty():
		_status.text = "Saisissez le code donné par le formateur"
		return
	var res: Dictionary = await Api.post_json("/api/v1/lobbies/join", {"code": code.strip_edges()})
	if not res["ok"]:
		_status.text = res["error"]
		return
	Session.open(res["data"])
	navigate.emit("lobby")


func _open_lobby(lobby_id: String) -> void:
	var res: Dictionary = await Api.get_json("/api/v1/lobbies/%s" % lobby_id)
	if not res["ok"]:
		_status.text = res["error"]
		return
	Session.open(res["data"])
	navigate.emit("lobby")


func _generate() -> void:
	if _options.is_empty():
		_status.text = "Paramètres indisponibles : vérifiez la connexion au serveur."
		return
	var modules := _checked(_module_checks)
	if modules.is_empty():
		_status.text = "Cochez au moins un module."
		return
	var pack := _current_pack()
	var body := {
		"pack": pack["id"],
		"theme": pack["themes"][_theme_select.selected]["id"],
		"modules": modules,
		"extra_agents": _checked(_agent_checks),
		"agent_tone": pack["tones"][_tone_select.selected]["id"],
		"difficulty": pack["difficulties"][_difficulty_select.selected]["id"],
		"events": pack["events"][_events_select.selected]["id"],
		"weeks": int(_weeks.value),
		"products": int(_products.value),
		"players_min": int(_players_min.value),
		"players_max": int(_players_max.value),
	}
	if not _option_getters.is_empty():
		var chosen := {}
		for option_id: String in _option_getters:
			chosen[option_id] = (_option_getters[option_id] as Callable).call()
		body["options"] = chosen
	var company := _company.text.strip_edges()
	if not company.is_empty():
		body["company_name"] = company
	_generate_button.disabled = true
	var res: Dictionary = await Api.post_json("/api/v1/games", body)
	_generate_button.disabled = false
	if not res["ok"]:
		_status.text = res["error"]
		return
	var autopilot: Dictionary = res["data"]["review"].get("autopilot", {})
	_status.text = (
		"Business game prêt : %s. Partie de référence en pilote automatique : OTIF moyen %s %%, trésorerie finale %s. Relisez-le, puis créez un lobby."
		% [res["data"]["title"], GameText.number(autopilot.get("otif_mean")), GameText.money(autopilot.get("final_cash"))]
	)
	await _load_games()


func _checked(checks: Array) -> Array:
	var ids := []
	for pair: Array in checks:
		if (pair[1] as CheckBox).button_pressed:
			ids.append(pair[0])
	return ids


func _show_game(game_id: String) -> void:
	var res: Dictionary = await Api.get_json("/api/v1/games/%s" % game_id)
	if not res["ok"]:
		_status.text = res["error"]
		return
	var game: Dictionary = res["data"]
	var actions := {}
	if game.get("spec") is Dictionary:
		actions["Exporter la spec"] = func() -> void: _export_spec(game)
		actions["Remplacer par un fichier"] = func() -> void: _replace_spec(game_id)
	Ui.show_text(self, game["title"], GameText.game_bbcode(game), actions)


func _export_spec(game: Dictionary) -> void:
	var on_path := func(path: String) -> void:
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file == null:
			_status.text = "Écriture impossible : %s" % error_string(FileAccess.get_open_error())
			return
		file.store_string(JSON.stringify(game["spec"], "  "))
		_status.text = "Spec exportée : %s (modifiable puis réimportable)" % path
	Ui.pick_json(self, true, on_path, "%s.json" % str(game["title"]).validate_filename())


func _replace_spec(game_id: String) -> void:
	Ui.pick_json(self, false, func(path: String) -> void: _send_spec(path, "/api/v1/games/%s/spec" % game_id, true))


func _import_spec() -> void:
	Ui.pick_json(self, false, func(path: String) -> void: _send_spec(path, "/api/v1/games/import", false))


func _send_spec(path: String, endpoint: String, replace: bool) -> void:
	var json := JSON.new()  # JSON.parse_string journalise une erreur du moteur sur un fichier vide ou absent
	var spec: Variant = json.data if json.parse(FileAccess.get_file_as_string(path)) == OK else null
	if not spec is Dictionary:
		_status.text = "Fichier illisible : JSON attendu"
		return
	var res: Dictionary
	if replace:
		res = await Api.put_json(endpoint, spec)
	else:
		res = await Api.post_json(endpoint, spec)
	if not res["ok"]:
		_status.text = "Spec refusée : %s" % res["error"]
		return
	_status.text = "Spec enregistrée : %s (vérifiée par une partie en pilote automatique, voir « Relire »)." % res["data"]["title"]
	await _load_games()


func _ask_lobby_name(game: Dictionary) -> void:
	var default_name := "%s : groupe du %s" % [game["title"], Time.get_date_string_from_system()]
	Ui.ask_text(self, "Nom du lobby", default_name, func(lobby_name: String) -> void: _create_lobby(game, lobby_name))


func _create_lobby(game: Dictionary, lobby_name: String) -> void:
	if lobby_name.is_empty():
		return
	var res: Dictionary = await Api.post_json("/api/v1/lobbies", {"name": lobby_name, "business_game_id": game["id"]})
	if not res["ok"]:
		_status.text = res["error"]
		return
	Session.open(res["data"])
	navigate.emit("lobby")


func _create_account() -> void:
	var body := {
		"username": _new_username.text.strip_edges(),
		"display_name": _new_name.text.strip_edges(),
		"password": _new_password.text,
		"role": _roles_offered[_new_role.selected][0],
	}
	var res: Dictionary = await Api.post_json("/api/v1/users", body)
	if not res["ok"]:
		_status.text = "Compte refusé : %s" % res["error"]
		return
	_status.text = "Compte créé : %s. Transmettez l'identifiant et le mot de passe provisoire." % body["username"]
	_new_username.text = ""
	_new_name.text = ""
	_new_password.text = ""
	await _load_users()
