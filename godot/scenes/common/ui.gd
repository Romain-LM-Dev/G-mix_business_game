class_name Ui
extends RefCounted
## Constructeurs d'interface partagés : les écrans sont construits en code (comme l'écran de diagnostic),
## avec le même thème et les mêmes couleurs partout.

const OK := Color(0.45, 0.85, 0.5)
const WARN := Color(1.0, 0.72, 0.3)
const ERROR := Color(1.0, 0.45, 0.4)
const MUTED := Color(0.68, 0.71, 0.78)
const ACCENT := Color(0.45, 0.7, 1.0)


static func make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = 18
	var panel := StyleBoxFlat.new()
	panel.bg_color = Color(0.09, 0.1, 0.13, 0.94)
	panel.set_corner_radius_all(8)
	panel.set_content_margin_all(16)
	theme.set_stylebox("panel", "PanelContainer", panel)
	return theme


static func label(text: String, font_size := 0, color := Color.WHITE, wrap := false) -> Label:
	var node := Label.new()
	node.text = text
	if wrap:
		node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if font_size > 0:
		node.add_theme_font_size_override("font_size", font_size)
	if color != Color.WHITE:
		node.add_theme_color_override("font_color", color)
	return node


static func button(text: String, action: Callable) -> Button:
	var node := Button.new()
	node.text = text
	node.pressed.connect(action)
	return node


static func field(placeholder: String, secret := false, width := 320) -> LineEdit:
	var node := LineEdit.new()
	node.placeholder_text = placeholder
	node.secret = secret
	node.custom_minimum_size.x = width
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


## Liste défilante : renvoie la colonne où ajouter les lignes.
static func scroll_list(parent: Node, min_height := 200) -> VBoxContainer:
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
static func show_text(parent: Node, title: String, bbcode: String, actions := {}) -> void:
	var dialog := AcceptDialog.new()
	dialog.title = title
	dialog.ok_button_text = "Fermer"
	var text := rich(560)
	text.custom_minimum_size.x = 1000
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
	dialog.popup_centered()


## Saisie d'un texte court dans une fenêtre modale ; `on_ok` reçoit le texte saisi.
static func ask_text(parent: Node, title: String, default_text: String, on_ok: Callable) -> void:
	var dialog := ConfirmationDialog.new()
	dialog.title = title
	dialog.ok_button_text = "Valider"
	dialog.cancel_button_text = "Annuler"
	var edit := LineEdit.new()
	edit.text = default_text
	edit.custom_minimum_size.x = 480
	dialog.add_child(edit)
	dialog.register_text_enter(edit)
	dialog.confirmed.connect(
		func() -> void:
			dialog.queue_free()
			on_ok.call(edit.text.strip_edges())
	)
	dialog.canceled.connect(dialog.queue_free)
	parent.add_child(dialog)
	dialog.popup_centered()
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
