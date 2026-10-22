extends Control
## Accueil après connexion. Joueur : rejoindre une partie avec son code, reprendre ses parties.
## Formateur et admin : business games (génération par l'IA, import, relecture, export), lobbies, comptes.
## L'interface masque ce que le rôle ne permet pas, mais seule l'API fait foi (docs/roles.md).

signal navigate(target: String)

const ROLE_NAMES := {"player": "joueur", "trainer": "formateur", "admin": "administrateur"}
const LEVELS := [["debutant", "Débutant"], ["intermediaire", "Intermédiaire"], ["avance", "Avancé"]]
const GAME_STATUS := {"draft": "brouillon", "generating": "génération", "ready": "prêt", "failed": "échec"}
const LOBBY_STATUS := {"ready": "ouvert", "running": "en cours", "closed": "terminé", "draft": "brouillon"}
const STAGES := {
	"brief_check": "contrôle de la demande", "outline": "plan du jeu", "npcs": "PNJ", "assets": "monde 3D",
	"debrief": "débrief", "assemble": "contrôles finaux", "review": "vérification des effets",
}

var _status: Label
var _games: VBoxContainer
var _lobbies: VBoxContainer
var _users: VBoxContainer
var _domains: Array = []
var _progress: Dictionary = {}  # game_id -> texte de progression reçu par WebSocket
var _domain_select: OptionButton
var _level_select: OptionButton
var _duration: SpinBox
var _players_min: SpinBox
var _players_max: SpinBox
var _brief: TextEdit
var _generate_button: Button
var _new_username: LineEdit
var _new_name: LineEdit
var _new_password: LineEdit
var _new_role: OptionButton
var _roles_offered: Array = []


func _ready() -> void:
	var column := Ui.vbox(Ui.screen_margin(self), 14)
	var header := Ui.hbox(column)
	header.add_child(Ui.label("Bonjour %s" % Api.user.get("display_name", ""), 28))
	header.add_child(Ui.label(ROLE_NAMES.get(Api.role(), Api.role()), 0, Ui.MUTED))
	Ui.spacer(header)
	header.add_child(Ui.button("Actualiser", _refresh))
	header.add_child(Ui.button("Diagnostic", func() -> void: navigate.emit("diagnostic")))
	header.add_child(Ui.button("Se déconnecter", func() -> void: navigate.emit("logout")))
	_status = Ui.label("", 0, Ui.ACCENT, true)
	column.add_child(_status)
	if Api.role() == "player":
		_build_player(column)
	else:
		_build_staff(column)
	EventBus.generation_event.connect(_on_generation_event)
	_refresh()


# --- construction ---------------------------------------------------------------------------------------


func _build_player(column: VBoxContainer) -> void:
	var box := Ui.vbox(Ui.panel(column))
	box.add_child(Ui.label("Rejoindre une partie", 22))
	var row := Ui.hbox(box)
	var code := Ui.field("Code donné par le formateur", false, 320)
	code.max_length = 8
	row.add_child(code)
	code.text_submitted.connect(func(text: String) -> void: _join(text))
	row.add_child(Ui.button("Rejoindre", func() -> void: _join(code.text)))
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
	var list_panel := Ui.panel(games_tab)
	list_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var list_box := Ui.vbox(list_panel)
	var list_header := Ui.hbox(list_box)
	list_header.add_child(Ui.label("Mes business games", 22))
	Ui.spacer(list_header)
	list_header.add_child(Ui.button("Importer une spec JSON", _import_spec))
	_games = Ui.scroll_list(list_box)
	_build_generation_form(Ui.panel(games_tab))

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
	_build_account_form(Ui.panel(accounts_tab))
	var users_panel := Ui.panel(accounts_tab)
	users_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var users_box := Ui.vbox(users_panel)
	users_box.add_child(Ui.label("Comptes que vous avez créés" if Api.role() == "trainer" else "Tous les comptes", 22))
	_users = Ui.scroll_list(users_box)


func _build_generation_form(panel: PanelContainer) -> void:
	panel.custom_minimum_size.x = 620
	var box := Ui.vbox(panel)
	box.add_child(Ui.label("Nouveau business game", 22))
	_domain_select = OptionButton.new()
	_form_row(box, "Domaine", _domain_select)
	_level_select = OptionButton.new()
	for level: Array in LEVELS:
		_level_select.add_item(level[1])
	_level_select.selected = 1
	_form_row(box, "Niveau", _level_select)
	_duration = _spin(30, 240, 90, 15)
	_form_row(box, "Durée (min)", _duration)
	var players := HBoxContainer.new()
	_players_min = _spin(1, 60, 3, 1)
	_players_max = _spin(1, 60, 6, 1)
	players.add_child(_players_min)
	players.add_child(Ui.label(" à "))
	players.add_child(_players_max)
	_form_row(box, "Joueurs", players)
	box.add_child(Ui.label("Besoin pédagogique : entreprise, public, notions à faire comprendre.", 0, Ui.MUTED, true))
	_brief = TextEdit.new()
	_brief.custom_minimum_size.y = 180
	_brief.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_brief.placeholder_text = "Ex. : une PME de distribution subit des ruptures et des surstocks ; les joueurs doivent comprendre le stock de sécurité et le point de commande."
	box.add_child(_brief)
	_generate_button = Ui.button("Générer avec l'IA (quelques minutes)", _generate)
	box.add_child(_generate_button)


func _build_account_form(panel: PanelContainer) -> void:
	panel.custom_minimum_size.x = 520
	var box := Ui.vbox(panel)
	box.add_child(Ui.label("Créer un compte", 22))
	_new_username = Ui.field("identifiant (lettres, chiffres, . _ -)")
	_form_row(box, "Identifiant", _new_username)
	_new_name = Ui.field("Prénom Nom")
	_form_row(box, "Nom affiché", _new_name)
	_new_password = Ui.field("8 caractères minimum")
	_form_row(box, "Mot de passe provisoire", _new_password)
	_new_role = OptionButton.new()
	_roles_offered = [["player", "Joueur"]]
	if Api.role() == "admin":
		_roles_offered += [["trainer", "Formateur"], ["admin", "Administrateur"]]
	for role: Array in _roles_offered:
		_new_role.add_item(role[1])
	_form_row(box, "Rôle", _new_role)
	box.add_child(Ui.button("Créer le compte", _create_account))
	box.add_child(Ui.label("La personne change ce mot de passe à sa première connexion.", 0, Ui.MUTED, true))


func _form_row(parent: Node, caption: String, control: Control) -> void:
	var row := Ui.hbox(parent)
	var title := Ui.label(caption)
	title.custom_minimum_size.x = 210
	row.add_child(title)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(control)


func _spin(low: float, high: float, value: float, step: float) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = low
	spin.max_value = high
	spin.step = step
	spin.value = value
	return spin


# --- données ------------------------------------------------------------------------------------------


func _refresh() -> void:
	if Api.role() != "player":
		if _domains.is_empty():
			await _load_domains()
		await _load_games()
		await _load_users()
	await _load_lobbies()


func _load_domains() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/domains")
	if not res["ok"]:
		_status.text = res["error"]
		return
	_domains = res["data"]
	_domain_select.clear()
	for domain: Dictionary in _domains:
		var corpus := int(domain.get("corpus_chunks", 0))
		var note := "%d extraits sourcés" % corpus if corpus > 0 else "sans corpus : contenu non sourcé"
		_domain_select.add_item("%s (%s)" % [domain["name"], note])


func _load_games() -> void:
	var res: Dictionary = await Api.get_json("/api/v1/games")
	if not res["ok"]:
		_status.text = res["error"]
		return
	Ui.clear(_games)
	if res["data"].is_empty():
		_games.add_child(Ui.label("Aucun business game : générez-en un ou importez une spec.", 0, Ui.MUTED, true))
	for game: Dictionary in res["data"]:
		var row := Ui.hbox(_games)
		var status: String = game["status"]
		var color := Ui.OK if status == "ready" else (Ui.ERROR if status == "failed" else Ui.WARN)
		var text := "%s  [%s]" % [game["title"], GAME_STATUS.get(status, status)]
		if status == "generating":
			text += "  %s" % _progress.get(str(game["id"]), _job_text(game.get("job")))
		row.add_child(Ui.label(text, 0, color, true))
		row.add_child(Ui.button("Relire", func() -> void: _show_game(str(game["id"]))))
		if status == "ready":
			row.add_child(Ui.button("Créer un lobby", func() -> void: _ask_lobby_name(game)))


func _job_text(job: Variant) -> String:
	if not job is Dictionary:
		return ""
	return "%s %d %%" % [_stage_name(str(job.get("stage", ""))), int(job.get("progress", 0))]


func _stage_name(stage: String) -> String:
	if stage.begins_with("phase_"):
		return "phase %s" % stage.trim_prefix("phase_")
	return STAGES.get(stage, stage)


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
		if lobby.get("join_code"):
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
	var brief := _brief.text.strip_edges()
	if brief.length() < 20:
		_status.text = "Décrivez le besoin en quelques phrases (20 caractères minimum)."
		return
	if _domains.is_empty():
		_status.text = "Domaines indisponibles : vérifiez la connexion au serveur."
		return
	var body := {
		"domain": _domains[_domain_select.selected]["slug"],
		"brief": brief,
		"level": LEVELS[_level_select.selected][0],
		"duration_minutes": int(_duration.value),
		"players_min": int(_players_min.value),
		"players_max": int(_players_max.value),
	}
	_generate_button.disabled = true
	var res: Dictionary = await Api.post_json("/api/v1/games", body)
	_generate_button.disabled = false
	if not res["ok"]:
		_status.text = res["error"]
		return
	_brief.text = ""
	_status.text = "Génération lancée : la progression s'affiche dans la liste (quelques minutes)."
	await _load_games()


func _on_generation_event(type: String, payload: Dictionary) -> void:
	var game_id := str(payload.get("game_id", ""))
	match type:
		"generation.progress":
			_progress[game_id] = "%s %d %%" % [_stage_name(str(payload.get("stage", ""))), int(payload.get("progress", 0))]
		"generation.completed":
			_progress.erase(game_id)
			_status.text = "Business game prêt : %s. Relisez-le avant de créer un lobby." % payload.get("title", "")
		"generation.failed":
			_progress.erase(game_id)
			_status.text = "Génération en échec : %s" % payload.get("error", "")
	if _games != null:
		_load_games()


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
	var spec: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
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
	var warnings: Array = res["data"].get("review", {}).get("warnings", [])
	_status.text = "Spec enregistrée (%d point(s) à vérifier dans « Relire »)." % warnings.size()
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
