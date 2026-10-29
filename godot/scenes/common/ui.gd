class_name Ui
extends RefCounted
## Constructeurs d'interface partagés : les écrans sont construits en code (comme l'écran de diagnostic), avec le même
## thème et les mêmes couleurs partout. Fenêtre de référence 1280x720 (project.godot : étirement `canvas_items`,
## aspect `expand`) : la zone visible fait toujours au moins 1280x720, quelle que soit la fenêtre. Règles : tout contenu
## long dans un ScrollContainer, textes à retour automatique, corps 18 px, jamais sous 15 px, aucune largeur fixe qui
## dépasse la zone visible. Couleurs, rayons, espacements et polices : jetons de ui_tokens.gd (UiTokens).

# Alias historiques des jetons de ui_tokens.gd (seul endroit où l'on règle la direction artistique).
const OK := UiTokens.OK
const WARN := UiTokens.WARN
const ERROR := UiTokens.ERROR
const MUTED := UiTokens.MUTED
const ACCENT := UiTokens.LIME
const TEXT := UiTokens.INK
const BACKDROP := UiTokens.BACKDROP  # fond des écrans avant-jeu
const PANEL := UiTokens.PANEL
const FIELD := UiTokens.FIELD
const EDGE := UiTokens.EDGE
const BODY_FONT := UiTokens.BODY_SIZE
const MIN_FONT := UiTokens.MIN_SIZE
const DIALOG_MAX := Vector2i(1000, 600)  # taille souhaitée d'une fenêtre de lecture, réduite à 85 % de la zone visible
const DIALOG_RATIO := 0.85  # la barre de titre déborde au-dessus de la fenêtre : il faut de la marge


static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = BODY_FONT
	var body := _font(UiTokens.FONT_BODY)
	if body != null:
		theme.default_font = body
	theme.set_stylebox("panel", "PanelContainer", _box(PANEL, UiTokens.RADIUS_PANEL, EDGE, 1, UiTokens.PANEL_PAD.x, UiTokens.PANEL_PAD.y))
	theme.set_color("font_color", "Label", TEXT)
	theme.set_color("default_color", "RichTextLabel", TEXT)
	_style_fonts(theme)
	_style_buttons(theme)
	_style_fields(theme)
	_style_tabs(theme)
	_style_popups(theme)
	_style_scrollbars(theme)
	return theme


## Police déposée dans assets/fonts (absente : null, donc police par défaut).
static func _font(path: String) -> Font:
	return load(path) as Font if ResourceLoader.exists(path) else null


## Titres en Manrope (`label` dès HEADING_FROM px), étiquettes en DM Mono (`theme_type_variation = "MonoLabel"`), corps en DM Sans.
static func _style_fonts(theme: Theme) -> void:
	theme.add_type("HeadingLabel")
	theme.set_type_variation("HeadingLabel", "Label")
	theme.add_type("MonoLabel")
	theme.set_type_variation("MonoLabel", "Label")
	var display := _font(UiTokens.FONT_DISPLAY)
	if display != null:
		theme.set_font("font", "HeadingLabel", display)
		theme.set_font("font", "TabContainer", display)
		theme.set_font("title_font", "Window", display)
	var mono := _font(UiTokens.FONT_MONO)
	if mono != null:
		theme.set_font("font", "MonoLabel", mono)
		theme.set_font("mono_font", "RichTextLabel", mono)
	var bold := _font(UiTokens.FONT_BODY_BOLD)
	if bold != null:
		theme.set_font("bold_font", "RichTextLabel", bold)
		theme.set_font("font", "PrimaryButton", bold)


static func _box(bg: Color, radius: int, border: Color, border_width: int, margin_x: int, margin_y: int) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = bg
	box.set_corner_radius_all(radius)
	box.border_color = border
	box.set_border_width_all(border_width)
	box.content_margin_left = margin_x
	box.content_margin_right = margin_x
	box.content_margin_top = margin_y
	box.content_margin_bottom = margin_y
	return box


static func _style_buttons(theme: Theme) -> void:
	var pad := UiTokens.CONTROL_PAD
	var radius := UiTokens.RADIUS_CONTROL
	var hover_edge := Color(UiTokens.LIME, 0.55)
	var states := {
		"normal": [UiTokens.BUTTON, EDGE],
		"hover": [UiTokens.BUTTON_HOVER, hover_edge],
		"pressed": [UiTokens.BUTTON_PRESSED, UiTokens.LIME],
		"hover_pressed": [UiTokens.BUTTON_PRESSED, UiTokens.LIME],
		"disabled": [UiTokens.BUTTON_OFF, UiTokens.BUTTON],
	}
	for state: String in states:
		theme.set_stylebox(state, "Button", _box(states[state][0], radius, states[state][1], 1, pad.x, pad.y))
	var focus := _box(Color.TRANSPARENT, radius, UiTokens.LIME, 2, pad.x, pad.y)
	focus.draw_center = false
	theme.set_stylebox("focus", "Button", focus)
	for key in ["font_color", "font_focus_color", "font_pressed_color", "font_hover_color", "font_hover_pressed_color"]:
		theme.set_color(key, "Button", TEXT)
	theme.set_color("font_disabled_color", "Button", UiTokens.TEXT_OFF)
	# Bouton de l'action principale d'un écran (`Ui.button(…, true)`) : lime plein, texte vert foncé.
	theme.add_type("PrimaryButton")
	theme.set_type_variation("PrimaryButton", "Button")
	var primary := {"normal": UiTokens.LIME, "hover": UiTokens.LIME_HOVER, "pressed": UiTokens.LIME_PRESSED, "hover_pressed": UiTokens.LIME_PRESSED}
	for state: String in primary:
		theme.set_stylebox(state, "PrimaryButton", _box(primary[state], radius, UiTokens.LIME_PRESSED, 1, pad.x, pad.y))
	for key in ["font_color", "font_focus_color", "font_pressed_color", "font_hover_color", "font_hover_pressed_color"]:
		theme.set_color(key, "PrimaryButton", UiTokens.ON_LIME)
	# Cases à cocher : sans cadre de bouton (leur type hérite sinon des styles de Button).
	var plain := StyleBoxEmpty.new()
	plain.content_margin_left = 4
	plain.content_margin_right = 4
	plain.content_margin_top = 4
	plain.content_margin_bottom = 4
	for kind in ["CheckBox", "CheckButton"]:
		for state in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
			theme.set_stylebox(state, kind, plain)
		theme.set_constant("h_separation", kind, 8)


static func _style_fields(theme: Theme) -> void:
	var pad := UiTokens.FIELD_PAD
	var radius := UiTokens.RADIUS_CONTROL
	theme.set_stylebox("normal", "LineEdit", _box(FIELD, radius, EDGE, 1, pad.x, pad.y))
	theme.set_stylebox("focus", "LineEdit", _box(FIELD, radius, UiTokens.LIME, 2, pad.x, pad.y))
	theme.set_stylebox("read_only", "LineEdit", _box(PANEL, radius, EDGE, 1, pad.x, pad.y))
	theme.set_color("font_color", "LineEdit", TEXT)
	theme.set_color("font_placeholder_color", "LineEdit", UiTokens.PLACEHOLDER)
	theme.set_color("caret_color", "LineEdit", UiTokens.LIME)
	theme.set_color("selection_color", "LineEdit", Color(UiTokens.LIME, 0.35))


static func _style_tabs(theme: Theme) -> void:
	var styles := {
		"tab_selected": [PANEL, UiTokens.LIME],
		"tab_unselected": [UiTokens.TAB_OFF, EDGE],
		"tab_hovered": [UiTokens.BUTTON_HOVER, Color(UiTokens.LIME, 0.55)],
		"tab_disabled": [UiTokens.TAB_OFF, EDGE],
	}
	for style: String in styles:
		var tab := _box(styles[style][0], UiTokens.RADIUS_PANEL, styles[style][1], 0, UiTokens.TAB_PAD.x, UiTokens.TAB_PAD.y)
		tab.corner_radius_bottom_left = 0
		tab.corner_radius_bottom_right = 0
		tab.border_width_top = 3
		theme.set_stylebox(style, "TabContainer", tab)
	var panel := StyleBoxEmpty.new()
	panel.content_margin_top = 8
	theme.set_stylebox("panel", "TabContainer", panel)
	theme.set_color("font_selected_color", "TabContainer", TEXT)
	theme.set_color("font_unselected_color", "TabContainer", MUTED)
	theme.set_color("font_hovered_color", "TabContainer", TEXT)
	theme.set_font_size("font_size", "TabContainer", UiTokens.TAB_SIZE)


static func _style_popups(theme: Theme) -> void:
	theme.set_stylebox("panel", "AcceptDialog", _box(PANEL, 0, EDGE, 0, UiTokens.PANEL_PAD.x, UiTokens.PANEL_PAD.y))
	theme.set_stylebox("panel", "PopupMenu", _box(FIELD, UiTokens.RADIUS_CONTROL, EDGE, 1, 8, 8))
	theme.set_stylebox("hover", "PopupMenu", _box(UiTokens.MENU_HOVER, 4, Color.TRANSPARENT, 0, 4, 4))
	theme.set_color("font_color", "PopupMenu", TEXT)
	theme.set_color("font_hover_color", "PopupMenu", TEXT)
	theme.set_constant("v_separation", "PopupMenu", 10)
	theme.set_stylebox("panel", "TooltipPanel", _box(Color(UiTokens.BACKDROP, 0.98), UiTokens.RADIUS_CONTROL, EDGE, 1, 10, 6))
	theme.set_font_size("font_size", "TooltipLabel", UiTokens.TIP_SIZE)
	theme.set_color("font_color", "TooltipLabel", TEXT)
	# Fenêtres intégrées : cadre du thème par défaut (il réserve la place de la barre de titre), repeint aux couleurs de la DA.
	theme.set_color("title_color", "Window", TEXT)
	theme.set_font_size("title_font_size", "Window", UiTokens.WINDOW_TITLE_SIZE)
	for kind in ["embedded_border", "embedded_unfocused_border"]:
		var base := ThemeDB.get_default_theme().get_stylebox(kind, "Window") as StyleBoxFlat
		if base == null:
			continue
		var frame := base.duplicate() as StyleBoxFlat
		frame.bg_color = PANEL
		frame.border_color = EDGE
		frame.set_corner_radius_all(UiTokens.RADIUS_MODAL)
		theme.set_stylebox(kind, "Window", frame)


## Ascenseurs fins aux couleurs de la DA (le style par défaut est bleu-gris).
static func _style_scrollbars(theme: Theme) -> void:
	for kind in ["VScrollBar", "HScrollBar"]:
		var track := _box(FIELD, 4, Color.TRANSPARENT, 0, 6 if kind == "VScrollBar" else 0, 6 if kind == "HScrollBar" else 0)
		theme.set_stylebox("scroll", kind, track)
		theme.set_stylebox("scroll_focus", kind, track)
		theme.set_stylebox("grabber", kind, _box(EDGE.lightened(0.25), 4, Color.TRANSPARENT, 0, 0, 0))
		theme.set_stylebox("grabber_highlight", kind, _box(EDGE.lightened(0.5), 4, Color.TRANSPARENT, 0, 0, 0))
		theme.set_stylebox("grabber_pressed", kind, _box(UiTokens.LIME, 4, Color.TRANSPARENT, 0, 0, 0))

## Texte d'interface. `wrap` : retour à la ligne automatique, la colonne prend la largeur disponible. La police n'est
## jamais inférieure à MIN_FONT.
static func label(text: String, font_size := 0, color := Color.WHITE, wrap := false) -> Label:
	var node := Label.new()
	node.text = text
	if wrap:
		node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if font_size > 0:
		node.add_theme_font_size_override("font_size", maxi(font_size, MIN_FONT))
		if font_size >= UiTokens.HEADING_FROM:
			node.theme_type_variation = "HeadingLabel"  # titres en Manrope
	if color != Color.WHITE:
		node.add_theme_color_override("font_color", color)
	return node


## Bouton centré verticalement dans sa rangée (sinon il s'étire à la hauteur d'un titre sur plusieurs lignes).
static func button(text: String, action: Callable, primary := false) -> Button:
	var node := Button.new()
	node.text = text
	node.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if primary:
		node.theme_type_variation = "PrimaryButton"
	node.pressed.connect(action)
	return node


static func field(placeholder: String, secret := false, width := 160) -> LineEdit:
	var node := LineEdit.new()
	node.placeholder_text = placeholder
	node.secret = secret
	node.custom_minimum_size.x = width
	return node


## Liste déroulante dont la largeur ne dépend pas du plus long choix (sinon elle pousse le formulaire hors de l'écran).
static func select(items: Array) -> OptionButton:
	var node := OptionButton.new()
	node.clip_text = true
	node.fit_to_longest_item = false
	for item: String in items:
		node.add_item(item)
	return node


static func rich(min_height := 0) -> RichTextLabel:
	var node := RichTextLabel.new()
	node.bbcode_enabled = true
	node.fit_content = min_height == 0
	node.custom_minimum_size.y = min_height
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.size_flags_vertical = Control.SIZE_EXPAND_FILL if min_height > 0 else Control.SIZE_FILL
	return node


static func vbox(parent: Node, separation := 10) -> VBoxContainer:
	var node := VBoxContainer.new()
	node.add_theme_constant_override("separation", separation)
	parent.add_child(node)
	return node


static func hbox(parent: Node, separation := 10) -> HBoxContainer:
	var node := HBoxContainer.new()
	node.add_theme_constant_override("separation", separation)
	parent.add_child(node)
	return node


## Rangée de boutons qui passent à la ligne quand la place manque.
static func flow(parent: Node, separation := 10) -> HFlowContainer:
	var node := HFlowContainer.new()
	node.add_theme_constant_override("h_separation", separation)
	node.add_theme_constant_override("v_separation", separation)
	parent.add_child(node)
	return node


static func panel(parent: Node) -> PanelContainer:
	var node := PanelContainer.new()
	parent.add_child(node)
	return node


## Marge sur tout l'écran : racine habituelle d'un écran.
static func screen_margin(parent: Control, px := 24) -> MarginContainer:
	var node := MarginContainer.new()
	node.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		node.add_theme_constant_override("margin_" + side, px)
	parent.add_child(node)
	return node


## Zone défilante verticalement : renvoie la colonne où ajouter le contenu. La largeur ne défile jamais : le contenu
## doit tenir (textes à retour automatique, `select`).
static func scroll_list(parent: Node, min_height := 100) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.y = min_height
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 8)
	scroll.add_child(column)
	return column


static func spacer(parent: Node) -> Control:
	var node := Control.new()
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(node)
	return node


static func clear(node: Node) -> void:
	for child in node.get_children():
		child.queue_free()


## Fenêtre modale de lecture (détails, débrief) ; `actions` : {libellé du bouton: Callable}. Se libère à la fermeture.
## Le texte défile dans la fenêtre, dimensionnée sur la zone visible (jamais plus grande).
static func show_text(parent: Node, title: String, bbcode: String, actions := {}) -> void:
	var dialog := AcceptDialog.new()
	dialog.title = title
	dialog.ok_button_text = "Fermer"
	var text := rich(160)
	text.custom_minimum_size.x = 320
	text.text = bbcode
	dialog.add_child(text)
	for caption: String in actions:
		dialog.add_button(caption, false, caption)
	dialog.custom_action.connect(
		func(action: StringName) -> void:
			dialog.hide()
			dialog.queue_free()
			(actions[String(action)] as Callable).call()
	)
	dialog.confirmed.connect(dialog.queue_free)
	dialog.canceled.connect(dialog.queue_free)
	parent.add_child(dialog)
	dialog.popup_centered_clamped(DIALOG_MAX, DIALOG_RATIO)


## Confirmation d'une action : `on_ok` est appelée si l'utilisateur valide. Le message passe à la ligne ; sa hauteur est
## mesurée d'avance (un Label à retour automatique annonce d'abord une hauteur démesurée et la fenêtre ne rétrécit pas).
static func confirm(parent: Control, title: String, message: String, ok_text: String, on_ok: Callable) -> void:
	var dialog := ConfirmationDialog.new()
	dialog.title = title
	dialog.ok_button_text = ok_text
	dialog.cancel_button_text = "Annuler"
	dialog.get_label().visible = false
	var width := mini(560, int(parent.get_viewport().get_visible_rect().size.x * 0.9))
	var text := label(message, 0, Color.WHITE, true)
	var font := parent.get_theme_font("font", "Label")
	var height := font.get_multiline_string_size(message, HORIZONTAL_ALIGNMENT_LEFT, width, parent.get_theme_font_size("font_size", "Label")).y
	text.custom_minimum_size = Vector2(width, ceilf(height) + 4.0)
	dialog.add_child(text)
	dialog.confirmed.connect(
		func() -> void:
			dialog.queue_free()
			on_ok.call()
	)
	dialog.canceled.connect(dialog.queue_free)
	parent.add_child(dialog)
	dialog.popup_centered()


## Saisie d'un texte court dans une fenêtre modale ; `on_ok` reçoit le texte saisi.
static func ask_text(parent: Node, title: String, default_text: String, on_ok: Callable) -> void:
	var dialog := ConfirmationDialog.new()
	dialog.title = title
	dialog.ok_button_text = "Valider"
	dialog.cancel_button_text = "Annuler"
	var edit := LineEdit.new()
	edit.text = default_text
	dialog.add_child(edit)
	dialog.register_text_enter(edit)
	dialog.confirmed.connect(
		func() -> void:
			dialog.queue_free()
			on_ok.call(edit.text.strip_edges())
	)
	dialog.canceled.connect(dialog.queue_free)
	parent.add_child(dialog)
	dialog.popup_centered_clamped(Vector2i(760, 0), DIALOG_RATIO)
	edit.grab_focus()


## Choix d'un fichier JSON sur le disque (boîte de dialogue native) ; `on_path` reçoit le chemin.
static func pick_json(parent: Node, save: bool, on_path: Callable, default_name := "") -> void:
	var dialog := FileDialog.new()
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE if save else FileDialog.FILE_MODE_OPEN_FILE
	dialog.filters = PackedStringArray(["*.json ; Spec de business game"])
	dialog.use_native_dialog = true
	dialog.current_file = default_name
	dialog.file_selected.connect(
		func(path: String) -> void:
			dialog.queue_free()
			on_path.call(path)
	)
	dialog.canceled.connect(dialog.queue_free)
	parent.add_child(dialog)
	dialog.popup_centered_ratio(0.6)
