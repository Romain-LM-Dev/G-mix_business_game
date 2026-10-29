class_name Ui
extends RefCounted
## Constructeurs d'interface partagés : les écrans sont construits en code (comme l'écran de diagnostic), avec le même
## thème et les mêmes couleurs partout. Fenêtre de référence 1280x720 (project.godot : étirement `canvas_items`,
## aspect `expand`) : la zone visible fait toujours au moins 1280x720, quelle que soit la fenêtre. Règles : tout contenu
## long dans un ScrollContainer, textes à retour automatique, corps 18 px, jamais sous 15 px, aucune largeur fixe qui
## dépasse la zone visible.

const OK := Color(0.45, 0.85, 0.5)
const WARN := Color(1.0, 0.72, 0.3)
const ERROR := Color(1.0, 0.45, 0.4)
const MUTED := Color(0.68, 0.72, 0.8)
const ACCENT := Color(0.45, 0.7, 1.0)
const TEXT := Color(0.93, 0.95, 0.98)
const BACKDROP := Color(0.07, 0.08, 0.11)  # fond des écrans avant-jeu
const PANEL := Color(0.12, 0.135, 0.175)
const FIELD := Color(0.055, 0.065, 0.09)
const EDGE := Color(0.32, 0.38, 0.5)
const BODY_FONT := 18
const MIN_FONT := 15
const DIALOG_MAX := Vector2i(1000, 600)  # taille souhaitée d'une fenêtre de lecture, réduite à 85 % de la zone visible
const DIALOG_RATIO := 0.85  # la barre de titre déborde au-dessus de la fenêtre : il faut de la marge


static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = BODY_FONT
	theme.set_stylebox("panel", "PanelContainer", _box(PANEL, 8, EDGE, 1, 16, 14))
	theme.set_color("font_color", "Label", TEXT)
	theme.set_color("default_color", "RichTextLabel", TEXT)
	_style_buttons(theme)
	_style_fields(theme)
	_style_tabs(theme)
	_style_popups(theme)
	return theme


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
	var states := {
		"normal": [Color(0.2, 0.25, 0.34), EDGE],
		"hover": [Color(0.27, 0.34, 0.47), ACCENT],
		"pressed": [Color(0.14, 0.18, 0.26), ACCENT],
		"hover_pressed": [Color(0.14, 0.18, 0.26), ACCENT],
		"disabled": [Color(0.12, 0.14, 0.19), Color(0.2, 0.23, 0.3)],
	}
	for state: String in states:
		theme.set_stylebox(state, "Button", _box(states[state][0], 6, states[state][1], 1, 14, 7))
	var focus := _box(Color.TRANSPARENT, 6, ACCENT, 2, 14, 7)
	focus.draw_center = false
	theme.set_stylebox("focus", "Button", focus)
	for key in ["font_color", "font_focus_color", "font_pressed_color", "font_hover_color", "font_hover_pressed_color"]:
		theme.set_color(key, "Button", TEXT if key != "font_hover_color" else Color.WHITE)
	theme.set_color("font_disabled_color", "Button", Color(0.58, 0.61, 0.69))
	# Bouton de l'action principale d'un écran (`Ui.button(…, true)`).
	theme.add_type("PrimaryButton")
	theme.set_type_variation("PrimaryButton", "Button")
	var primary := {"normal": Color(0.16, 0.36, 0.68), "hover": Color(0.22, 0.45, 0.8), "pressed": Color(0.12, 0.28, 0.55), "hover_pressed": Color(0.12, 0.28, 0.55)}
	for state: String in primary:
		theme.set_stylebox(state, "PrimaryButton", _box(primary[state], 6, Color(0.4, 0.65, 0.95), 1, 14, 7))
	theme.set_color("font_color", "PrimaryButton", Color.WHITE)
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
	theme.set_stylebox("normal", "LineEdit", _box(FIELD, 6, EDGE, 1, 10, 7))
	theme.set_stylebox("focus", "LineEdit", _box(FIELD, 6, ACCENT, 2, 10, 7))
	theme.set_stylebox("read_only", "LineEdit", _box(PANEL, 6, EDGE, 1, 10, 7))
	theme.set_color("font_color", "LineEdit", TEXT)
	theme.set_color("font_placeholder_color", "LineEdit", Color(0.55, 0.6, 0.7))
	theme.set_color("caret_color", "LineEdit", ACCENT)
	theme.set_color("selection_color", "LineEdit", Color(0.25, 0.45, 0.8, 0.6))


static func _style_tabs(theme: Theme) -> void:
	var styles := {"tab_selected": [PANEL, ACCENT], "tab_unselected": [Color(0.09, 0.1, 0.14), EDGE], "tab_hovered": [Color(0.17, 0.2, 0.28), ACCENT], "tab_disabled": [Color(0.09, 0.1, 0.14), EDGE]}
	for style: String in styles:
		var tab := _box(styles[style][0], 8, styles[style][1], 0, 20, 9)
		tab.corner_radius_bottom_left = 0
		tab.corner_radius_bottom_right = 0
		tab.border_width_top = 3
		theme.set_stylebox(style, "TabContainer", tab)
	var panel := StyleBoxEmpty.new()
	panel.content_margin_top = 8
	theme.set_stylebox("panel", "TabContainer", panel)
	theme.set_color("font_selected_color", "TabContainer", Color.WHITE)
	theme.set_color("font_unselected_color", "TabContainer", Color(0.78, 0.82, 0.9))
	theme.set_color("font_hovered_color", "TabContainer", Color.WHITE)
	theme.set_font_size("font_size", "TabContainer", 20)


static func _style_popups(theme: Theme) -> void:
	theme.set_stylebox("panel", "AcceptDialog", _box(PANEL, 0, EDGE, 0, 16, 14))
	theme.set_stylebox("panel", "PopupMenu", _box(Color(0.1, 0.115, 0.15), 6, EDGE, 1, 8, 8))
	theme.set_stylebox("hover", "PopupMenu", _box(Color(0.22, 0.3, 0.45), 4, Color.TRANSPARENT, 0, 4, 4))
	theme.set_constant("v_separation", "PopupMenu", 10)
	theme.set_stylebox("panel", "TooltipPanel", _box(Color(0.1, 0.115, 0.15, 0.98), 6, EDGE, 1, 10, 6))
	theme.set_font_size("font_size", "TooltipLabel", 16)
	theme.set_color("font_color", "TooltipLabel", TEXT)


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
