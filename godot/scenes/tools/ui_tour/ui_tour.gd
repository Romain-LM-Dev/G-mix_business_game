extends Control  # un Control, pas un Node : le thème de la fenêtre ne traverse pas un simple Node
## Contrôle de lisibilité des écrans avant-jeu (connexion, diagnostic, accueils joueur / formateur / admin, salle du
## lobby, fenêtres de dialogue) et des panneaux du HUD (sans le monde 3D), à plusieurs tailles de fenêtre : mesure les
## dépassements (Control hors de la fenêtre, de son cadre ou de sa zone de défilement), les polices sous 15 px, les
## textes tronqués et les erreurs de script. Code de sortie 0 si tout est lisible.
##   Sans GPU (la zone visible, donc la mise en page, ne dépend que de la taille de la fenêtre) :
##   Godot_console.exe --headless --path godot res://scenes/tools/ui_tour/ui_tour.tscn --
##       --api=http://127.0.0.1:8000 [--sizes=1280x720,1366x768,1920x1080,1024x600,1152x648]
##   Avec captures (--snapshot : un dossier par taille ; fenêtre et GPU requis, pas la version console) :
##   Godot.exe --path godot res://scenes/tools/ui_tour/ui_tour.tscn -- --api=… --snapshot=C:/dossier
## Jetons de comptes jetables dans l'environnement : GMIX_TOUR_ADMIN_TOKEN (admin) et GMIX_TOUR_PLAYER_TOKEN. Le
## parcours crée deux business games et douze lobbies au nom du compte admin : à supprimer avec les comptes.
## Aucun dialogue avec un agent : pas d'appel au modèle de langue.

const MAIN := preload("res://scenes/main/main.tscn")
const BOOT := preload("res://scenes/boot/boot.tscn")
const SIZES := "1280x720,1366x768,1920x1080,1024x600,1152x648"
const MIN_FONT := 15
const TOLERANCE := 1.5  # pixels : arrondis de mise en page
const LONG_NAME := "Session de formation à la gestion des flux logistiques : groupe du lundi matin, promotion 2026, site de Mulhouse"
const LONG_PROMPT := "E : parler à Marie-Charlotte de Saint-Exupéry-Delacroix (responsable de l'approvisionnement des fournisseurs internationaux)"
const LONG_MESSAGE := (
	"Spec refusée : modules/2/actions/0/values/quantity : la valeur dépasse la borne autorisée par le catalogue ; "
	+ "vérifiez le fichier exporté puis réimportez-le (message volontairement long pour contrôler le retour à la ligne)."
)

## Intercepte les erreurs du moteur et des scripts (SCRIPT ERROR, ERROR:) pour les attribuer à l'écran en cours.
class ErrorCatcher:
	extends Logger

	var _mutex := Mutex.new()
	var _entries: Array[String] = []

	func _log_error(
		function: String, file: String, line: int, code: String, rationale: String,
		_editor_notify: bool, error_type: int, _backtraces: Array[ScriptBacktrace]
	) -> void:
		if error_type == ERROR_TYPE_WARNING:
			return
		_mutex.lock()
		_entries.append("%s:%d (%s) %s %s" % [file, line, function, code, rationale])
		_mutex.unlock()

	func take() -> Array[String]:
		_mutex.lock()
		var out := _entries.duplicate()
		_entries.clear()
		_mutex.unlock()
		return out


var _args: Dictionary = {}
var _catcher := ErrorCatcher.new()
var _snapshot_dir := ""
var _tokens: Dictionary = {}
var _users: Dictionary = {}
var _data: Dictionary = {}
var _main: Control
var _size_tag := ""
var _screens := 0
var _failures: Array[String] = []
var _done := false


func _ready() -> void:
	_args = _arguments()
	_snapshot_dir = str(_args.get("snapshot", ""))
	OS.add_logger(_catcher)
	var watchdog := get_tree().create_timer(float(_args.get("timeout", "480")))
	watchdog.timeout.connect(func() -> void: _finish("délai global dépassé"))
	_run()


func _run() -> void:
	_tokens = {
		"admin": OS.get_environment("GMIX_TOUR_ADMIN_TOKEN"),
		"player": OS.get_environment("GMIX_TOUR_PLAYER_TOKEN"),
	}
	if str(_tokens["admin"]).is_empty() or str(_tokens["player"]).is_empty():
		_finish("jetons GMIX_TOUR_ADMIN_TOKEN et GMIX_TOUR_PLAYER_TOKEN requis")
		return
	print("TOUR api=%s écran=%s" % [AppConfig.api_base_url, DisplayServer.screen_get_size()])
	if not await _prepare():
		_finish("préparation des données impossible")
		return
	await _become("")
	_main = MAIN.instantiate() as Control
	add_child(_main)
	for text in str(_args.get("sizes", SIZES)).split(","):
		var parts := text.split("x")
		await _resize(Vector2i(int(parts[0]), int(parts[1])))
		await _tour()
	_finish("")


func _finish(reason: String) -> void:
	if _done:
		return
	_done = true
	if not reason.is_empty():
		_failures.append(reason)
	print("TOUR %s : %d écran(s) contrôlé(s), %d défaut(s)" % ["OK" if _failures.is_empty() else "KO", _screens, _failures.size()])
	for failure in _failures:
		print("TOUR DEFAUT %s" % failure)
	get_tree().quit(0 if _failures.is_empty() else 1)


# --- parcours -----------------------------------------------------------------------------------------------------


func _tour() -> void:
	await _become("")
	await _show("login")
	await _look("01-connexion")
	var login := _screen()
	(login.get("_server") as LineEdit).text = "https://serveur-distant-avec-un-nom-de-domaine-vraiment-tres-long.exemple.org:8443"
	(login.get("_change_box") as Control).visible = true
	(login.get("_login_button") as Control).visible = false
	(login.get("_status") as Label).text = LONG_MESSAGE
	await _look("02-connexion-mot-de-passe-provisoire")

	await _become("admin")
	var diagnostic := BOOT.instantiate() as Control
	_main.visible = false
	add_child(diagnostic)
	var first := (diagnostic.get("_status_labels") as Dictionary)["database"] as Label
	await _wait(func() -> bool: return first.text != "…", 15.0)  # le temps que /health réponde
	await _look("03-diagnostic", diagnostic)
	diagnostic.queue_free()
	_main.visible = true

	await _become("player")
	await _show("home")
	var home := _screen()
	await _wait_lists(home)
	await _look("04-accueil-joueur")
	await _open_lobby(_data["lobby_wait"])
	await _look("05-salle-joueur-sans-role")
	await _open_lobby(_data["lobby_run"])
	await _look("06-salle-joueur-en-cours")

	await _become("admin")
	await _show("home")
	home = _screen()
	await _wait_lists(home)
	(home.get("_status") as Label).text = LONG_MESSAGE
	await _look("07-accueil-formateur-jeux")
	var sector := home.get("_theme_select") as OptionButton
	sector.show_popup()
	await _look("07b-liste-deroulante")
	sector.get_popup().hide()
	await _frames(2)
	await _pack_forms(home)
	var tabs := home.find_children("*", "TabContainer", true, false)[0] as TabContainer
	tabs.current_tab = 1
	await _look("08-accueil-formateur-lobbies")
	tabs.current_tab = 2
	await _look("09-accueil-formateur-comptes")
	tabs.current_tab = 0
	await home.call("_show_game", _data["game_a"])
	await _look("10-relecture-business-game")
	await _close_dialogs(home)
	home.call("_ask_lobby_name", {"id": _data["game_a"], "title": _data["game_a_title"]})
	await _look("11-nom-du-lobby")
	await _close_dialogs(home)

	await _open_lobby(_data["lobby_wait"])
	await _look("12-salle-formateur-en-attente")
	await _open_lobby(_data["lobby_run"])
	await _look("13-salle-formateur-en-cours")
	_screen().call("_confirm_advance")
	await _look("14-confirmation-semaine")
	await _close_dialogs(_screen())
	await _open_lobby(_data["lobby_done"])
	await _look("15-salle-formateur-terminee")
	await _screen().call("_debrief")
	await _look("16-debrief")
	await _close_dialogs(_screen())
	await _open_lobby(_data["lobby_run"])
	await _hud_tour()


## Formulaire de génération avec chaque autre pack de GET /games/options (choix du pack, options propres au pack) : lisible
## à toutes les tailles ; revient ensuite au premier pack.
func _pack_forms(home: Control) -> void:
	var packs: Array = (home.get("_options") as Dictionary).get("packs", [])
	if packs.size() < 2:
		return
	for index in range(1, packs.size()):
		_pick_pack(home, index)
		await _frames(4)
		await _look("07c-formulaire-pack-%s" % packs[index]["id"])
		(home.get("_company") as LineEdit).text = LONG_NAME  # un nom d'entreprise très long reste dans la colonne
		await _look("07d-formulaire-pack-%s-nom-long" % packs[index]["id"])
	_pick_pack(home, 0)
	await _frames(4)


func _pick_pack(home: Control, index: int) -> void:
	var select := home.get("_pack_select") as OptionButton
	select.select(index)
	select.item_selected.emit(index)


## Bandeau et panneaux modaux du HUD, sans le monde 3D : leur taille ne doit pas dépasser la zone visible.
func _hud_tour() -> void:
	var hud := GmixHud.new()
	_main.visible = false
	add_child(hud)
	await _look("17-hud-bandeau", hud)
	# Vue Sims : indicateur de vue, invite et annonce très longues, info-bulle et menu contextuel au bord de la fenêtre.
	hud.set_prompt(LONG_PROMPT)
	hud.notice(LONG_MESSAGE, Ui.WARN)
	hud.set_view(false, false)
	await _look("17b-hud-troisieme-personne-invite-longue", hud)
	hud.set_prompt("")
	hud.set_view(true, false)
	hud.show_hover(LONG_NAME, Vector2(1240.0, 690.0))
	await _look("17c-hud-info-bulle", hud)
	hud.show_hover("", Vector2.ZERO)
	hud.open_context_menu(
		LONG_NAME.left(70),
		[["Parler à Marie-Charlotte de Saint-Exupéry-Delacroix", Callable()], ["Utiliser : Stock de composants à très longue désignation", Callable()], ["S'approcher", Callable()]],
		Vector2(1260.0, 700.0)
	)
	await _look("17d-hud-menu-contextuel", hud)
	hud.close_context_menu()
	hud.set_view(true, true)
	var spec := Session.spec()
	var stations: Array = spec["stations"]
	var with_forms := stations.filter(func(station: Dictionary) -> bool: return not (station["modules"] as Array).is_empty())
	hud.open_station(with_forms[0] if not with_forms.is_empty() else stations[0])
	await _look("18-hud-poste", hud)
	hud.close_panels()
	await hud.open_dialogue((spec["agents"] as Array)[0])  # relit la mémoire de l'agent : aucun message envoyé
	await _look("19-hud-dialogue", hud)
	hud.close_panels()
	hud.toggle_dashboard()
	await _look("20-hud-tableau-de-bord", hud)
	hud.close_panels()
	hud.toggle_menu()
	await _look("21-hud-menu", hud)
	hud.close_panels()
	await hud.call("_show_debrief")
	await _look("22-hud-debrief", hud)
	hud.close_panels()
	hud.queue_free()
	_main.visible = true


## Données de démonstration (appels d'API seulement) : deux business games, trois lobbies à des étapes différentes
## (en attente, en cours, terminé) et neuf autres pour remplir les listes.
func _prepare() -> bool:
	for kind: String in ["admin", "player"]:
		Api.token = _tokens[kind]
		var me: Dictionary = await Api.get_json("/api/v1/auth/me")
		if not me["ok"]:
			printerr("compte %s : %s" % [kind, me["error"]])
			return false
		_users[kind] = me["data"]
	_set_account("admin")
	var options: Variant = await _call("GET", "/api/v1/games/options")
	if options == null:
		return false
	var pack_id := str(_args.get("pack", "atelier"))  # --pack=usine : les jeux et lobbies du parcours sont ceux de ce pack
	if pack_id != "atelier":
		var found: Array = (options.get("packs", []) as Array).filter(func(entry: Dictionary) -> bool: return entry["id"] == pack_id)
		if found.is_empty():
			printerr("pack inconnu des options de l'API : %s" % pack_id)
			return false
		var chosen := found[0] as Dictionary
		var defaults := {}
		for option: Dictionary in chosen.get("params", []):
			defaults[option["id"]] = option["default"] if option.get("default") != null else option["min"]
		options = chosen.duplicate()  # mêmes clés que le pack atelier (themes, modules, tones…)
		options["pack"] = pack_id
		options["defaults"] = defaults
	var limits: Dictionary = options.get("limits", {"weeks": [5, 5, 5], "products": [3, 3, 3]})
	var params := {
		"pack": pack_id,
		"theme": options["themes"][0]["id"],
		"modules": _ids(options["modules"]),
		"extra_agents": _ids(options["extra_agents"]).slice(0, 3),
		"agent_tone": options["tones"][0]["id"],
		"difficulty": options["difficulties"][0]["id"],
		"events": options["events"][0]["id"],
		"weeks": 5 if pack_id == "atelier" else limits["weeks"][2],
		"products": 3 if pack_id == "atelier" else limits["products"][2],
		"players_min": 1,
		"players_max": 6,
		"company_name": "Compagnie Internationale des Transports",
	}
	if options.has("defaults"):
		params["options"] = options["defaults"]
	var game_a: Variant = await _call("POST", "/api/v1/games", params)
	params["theme"] = options["themes"][-1]["id"]
	params["agent_tone"] = options["tones"][-1]["id"]
	params["company_name"] = "Atelier Fromager de la Vallée d'Aulps"
	var game_b: Variant = await _call("POST", "/api/v1/games", params)
	if game_a == null or game_b == null:
		return false
	_data["game_a"] = game_a["id"]
	_data["game_a_title"] = game_a["title"]
	var lobbies := {}
	for key: String in ["lobby_wait", "lobby_run", "lobby_done"]:
		var names := {"lobby_wait": LONG_NAME, "lobby_run": "Groupe du mardi après-midi", "lobby_done": "Promotion 2025 : session terminée"}
		var created: Variant = await _call("POST", "/api/v1/lobbies", {"name": names[key], "business_game_id": game_b["id"] if key == "lobby_run" else game_a["id"]})
		if created == null:
			return false
		lobbies[key] = created
		_data[key] = created["id"]
	for i in 9:  # de quoi remplir (et faire défiler) les listes de parties ; le dernier créé (en tête de liste) : un nom sans espace
		var lobby_name := "Z".repeat(110) if i == 8 else "Groupe %d : %s" % [i + 1, LONG_NAME.left(70)]
		var extra: Variant = await _call("POST", "/api/v1/lobbies", {"name": lobby_name, "business_game_id": game_a["id"]})
		if extra == null:
			return false
		lobbies["extra_%d" % i] = extra
	_set_account("player")
	for key: String in lobbies:
		if await _call("POST", "/api/v1/lobbies/join", {"code": lobbies[key]["join_code"]}) == null:
			return false
	var role_id: String = lobbies["lobby_run"]["spec"]["roles"][0]["id"]
	if await _call("PUT", "/api/v1/lobbies/%s/role" % _data["lobby_run"], {"game_role": role_id}) == null:
		return false
	_set_account("admin")
	for key: String in ["lobby_run", "lobby_done"]:
		if await _call("POST", "/api/v1/lobbies/%s/start" % _data[key]) == null:
			return false
	for i in int(lobbies["lobby_done"]["spec"]["meta"]["weeks"]):
		if await _call("POST", "/api/v1/lobbies/%s/advance" % _data["lobby_done"]) == null:
			return false
	return await _call("POST", "/api/v1/lobbies/%s/advance" % _data["lobby_run"]) != null


func _call(method: String, path: String, body: Variant = {}) -> Variant:
	var res: Dictionary
	match method:
		"GET":
			res = await Api.get_json(path)
		"PUT":
			res = await Api.put_json(path, body)
		_:
			res = await Api.post_json(path, body)
	if not res["ok"]:
		printerr("%s %s : %s" % [method, path, res["error"]])
		return null
	return res["data"]


func _ids(items: Array) -> Array:
	return items.map(func(item: Dictionary) -> String: return item["id"])


func _set_account(kind: String) -> void:
	Api.token = _tokens[kind]
	Api.user = _users[kind]


func _become(kind: String) -> void:
	if kind.is_empty():
		Api.logout()
	else:
		_set_account(kind)
	await _frames()


func _show(target: String) -> void:
	_main.call("_show", target)
	await _frames(3)


func _screen() -> Control:
	return _main.get("_screen") as Control


func _open_lobby(lobby_id: String) -> void:
	var view: Variant = await _call("GET", "/api/v1/lobbies/%s" % lobby_id)
	if view != null:
		Session.open(view)
		await _show("lobby")


func _wait_lists(home: Control) -> void:
	await _wait(
		func() -> bool:
			var staff := Api.role() != "player"
			var lobbies := home.get("_lobbies") as Control
			var games := home.get("_games") as Control
			return (
				lobbies != null and lobbies.get_child_count() > 0
				and (not staff or (games != null and games.get_child_count() > 0 and not (home.get("_options") as Dictionary).is_empty()))
			),
		15.0
	)
	await _settle()


func _close_dialogs(parent: Node) -> void:
	for child in parent.get_children():
		if child is AcceptDialog and (child as AcceptDialog).visible:
			(child as AcceptDialog).hide()
			child.queue_free()
	await _frames(2)


func _resize(size: Vector2i) -> void:
	var window := get_window()
	if DisplayServer.get_name() != "headless":
		window.borderless = true
		window.position = Vector2i.ZERO
	window.size = size
	_size_tag = "%dx%d" % [size.x, size.y]
	await _frames(8)
	print("TAILLE demandée=%s fenêtre=%s viewport=%s" % [size, window.size, get_viewport().get_visible_rect().size])
	if window.size != size:
		_failures.append("%s : taille de fenêtre non obtenue (%s)" % [_size_tag, window.size])


# --- contrôle ------------------------------------------------------------------------------------------------------


func _look(screen_name: String, root: Node = null) -> void:
	await _settle()
	var findings: Array[String] = []
	var bounds := get_viewport().get_visible_rect()
	_walk(root if root != null else _main, [_frame(bounds, true, true)], findings)
	_screens += 1
	if findings.is_empty():
		print("  ok  %s %s" % [_size_tag, screen_name])
	for finding in findings:
		print("  KO  %s %s : %s" % [_size_tag, screen_name, finding])
		_failures.append("%s %s : %s" % [_size_tag, screen_name, finding])
	for error in _catcher.take():
		print("  KO  %s %s : erreur de script : %s" % [_size_tag, screen_name, error])
		_failures.append("%s %s : erreur de script : %s" % [_size_tag, screen_name, error])
	if not _snapshot_dir.is_empty() and DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		var path := _snapshot_dir.path_join(_size_tag).path_join(screen_name + ".png")
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		get_viewport().get_texture().get_image().save_png(path)


func _frame(rect: Rect2, check_x: bool, check_y: bool) -> Dictionary:
	return {"rect": rect, "x": check_x, "y": check_y}


## Parcourt les Control visibles. `frames` : les cadres qui contiennent le nœud (fenêtre, cadre d'un panneau, zone de
## défilement) ; un défilement libère l'axe correspondant pour tous les cadres extérieurs. Renvoie true si un
## dépassement a été trouvé sous `node` : seul le Control le plus profond est signalé (le coupable, pas ses parents).
func _walk(node: Node, frames: Array, out: Array[String]) -> bool:
	var found := false
	for child in node.get_children(true):
		if child is Window:
			var window := child as Window
			if not window.visible:
				continue
			# La barre de titre et la bordure d'une fenêtre intégrée débordent de sa zone de contenu.
			var title := float(window.get_theme_constant("title_height")) if window.is_embedded() else 0.0
			var outer := Rect2(Vector2(window.position) - Vector2(6.0, title + 6.0), Vector2(window.size) + Vector2(12.0, title + 12.0))
			var outside := _outside(outer, frames)
			var below := _walk(window, [_frame(Rect2(Vector2.ZERO, Vector2(window.size)), true, true)], out)
			if not outside.is_empty() and not below:
				out.append("fenêtre « %s » hors de la fenêtre principale : %s" % [window.title, outside])
			found = found or below or not outside.is_empty()
		elif child is Control:
			var control := child as Control
			if not control.visible:
				continue
			var rect := control.get_global_rect()
			var outside := ""
			if rect.size.x >= 1.0 and rect.size.y >= 1.0:
				outside = _outside(rect, frames)
				out.append_array(_text_defects(control))
			var inner := frames
			if control is ScrollContainer:
				inner = _inside_scroll(frames, control as ScrollContainer, rect)
			elif control is PanelContainer or control is TabContainer:
				inner = frames + [_frame(rect, true, true)]
			var below := _walk(control, inner, out)
			if not outside.is_empty() and not below:
				out.append("%s hors de son cadre : %s" % [_describe(control), outside])
			found = found or below or not outside.is_empty()
		elif _walk(child, frames, out):
			found = true
	return found


func _inside_scroll(frames: Array, scroll: ScrollContainer, rect: Rect2) -> Array:
	var free_x := scroll.horizontal_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED
	var free_y := scroll.vertical_scroll_mode != ScrollContainer.SCROLL_MODE_DISABLED
	var inner: Array = []
	for frame: Dictionary in frames:
		var copy := frame.duplicate()
		copy["x"] = frame["x"] and not free_x
		copy["y"] = frame["y"] and not free_y
		inner.append(copy)
	inner.append(_frame(rect, not free_x, not free_y))
	return inner


func _outside(rect: Rect2, frames: Array) -> String:
	for frame: Dictionary in frames:
		var box: Rect2 = frame["rect"]
		if frame["x"] and (rect.position.x < box.position.x - TOLERANCE or rect.end.x > box.end.x + TOLERANCE):
			return "horizontalement x=%.0f..%.0f pour un cadre x=%.0f..%.0f" % [rect.position.x, rect.end.x, box.position.x, box.end.x]
		if frame["y"] and (rect.position.y < box.position.y - TOLERANCE or rect.end.y > box.end.y + TOLERANCE):
			return "verticalement y=%.0f..%.0f pour un cadre y=%.0f..%.0f" % [rect.position.y, rect.end.y, box.position.y, box.end.y]
	return ""


## Polices sous MIN_FONT px et textes tronqués (ellipse, découpe) d'un Control.
func _text_defects(control: Control) -> Array[String]:
	var out: Array[String] = []
	var px := -1
	if control is RichTextLabel:
		px = control.get_theme_font_size("normal_font_size")
		for tag in RegEx.create_from_string("\\[font_size=(\\d+)\\]").search_all((control as RichTextLabel).text):
			if int(tag.get_string(1)) < MIN_FONT:
				out.append("%s : police de %s px" % [_describe(control), tag.get_string(1)])
	elif control is Label or control is Button or control is LineEdit or control is TabContainer:
		var text := str(control.get("text")) if "text" in control else "-"
		if not text.is_empty() or control is TabContainer:
			px = control.get_theme_font_size("font_size")
	if px > 0 and px < MIN_FONT:
		out.append("%s : police de %d px" % [_describe(control), px])
	if _truncated(control):
		out.append("%s : texte tronqué" % _describe(control))
	return out


func _truncated(control: Control) -> bool:
	if control is Label:
		var label := control as Label
		if label.max_lines_visible > 0 and label.get_line_count() > label.max_lines_visible:
			return true
		if label.text.is_empty() or (label.text_overrun_behavior == TextServer.OVERRUN_NO_TRIMMING and not label.clip_text):
			return false
		return _text_width(label, label.text) > label.size.x + TOLERANCE
	if control is Button:
		var button := control as Button
		var trims := button.clip_text or button.text_overrun_behavior != TextServer.OVERRUN_NO_TRIMMING
		if button.text.is_empty() or not trims or button.autowrap_mode != TextServer.AUTOWRAP_OFF:
			return false
		var margins := button.get_theme_stylebox("normal").get_minimum_size().x + (36.0 if button is OptionButton else 0.0)
		return _text_width(button, button.text) + margins > button.size.x + TOLERANCE
	return false


func _text_width(control: Control, text: String) -> float:
	var font := control.get_theme_font("font")
	var px := control.get_theme_font_size("font_size")
	var widest := 0.0
	for line in text.split("\n"):
		widest = maxf(widest, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, px).x)
	return widest


func _describe(control: Control) -> String:
	var rect := control.get_global_rect()
	var text := str(control.get("text")).replace("\n", " ").left(45) if "text" in control else ""
	var shown := (" « %s »" % text) if not text.is_empty() else ""
	return "%s%s [x=%.0f y=%.0f %.0fx%.0f]" % [control.get_class(), shown, rect.position.x, rect.position.y, rect.size.x, rect.size.y]


# --- attentes ------------------------------------------------------------------------------------------------------


func _arguments() -> Dictionary:
	var result := {}
	for arg in OS.get_cmdline_user_args():
		var pair := arg.trim_prefix("--").split("=", true, 1)
		result[pair[0]] = pair[1] if pair.size() > 1 else ""
	return result


func _frames(count := 2) -> void:
	for i in count:
		await get_tree().process_frame


## Laisse le temps aux conteneurs et aux textes à retour automatique de se stabiliser.
func _settle() -> void:
	await _frames(8)
	await get_tree().create_timer(0.3).timeout
	await _frames(4)


func _wait(condition: Callable, timeout_s: float) -> void:
	var deadline := Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() < deadline and not condition.call():
		await get_tree().process_frame
