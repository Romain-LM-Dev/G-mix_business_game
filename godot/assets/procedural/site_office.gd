@tool
extends GmixAsset
## Bureau d'atelier, repris du jeu de référence G-mix Business_game (bureau de direction, three.js) : cabine
## de 3,3 x 3,0 m, toit débordant, porte et fenêtre en façade (+Z). Variante : enseigne (texte au-dessus).


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	Mesher.box(self, Vector3(3.3, 2.7, 3.0), Vector3(0, 1.35, 0), Mesher.material(Palette.WALL_WARM, Color.BLACK, "concrete"))
	Mesher.box(self, Vector3(3.5, 0.15, 3.2), Vector3(0, 2.78, 0), Mesher.material(Palette.STATION_CONTROL, Color.BLACK, "steel"))
	Mesher.box(self, Vector3(0.9, 1.0, 0.06), Vector3(0.6, 1.55, 1.53), Mesher.material(Palette.GLASS, Palette.GLASS * 0.15))
	Mesher.box(self, Vector3(0.8, 2.0, 0.06), Vector3(-0.8, 1.0, 1.53), Mesher.material(Palette.STEEL_DARK, Color.BLACK, "steel"))
	var sign := Label3D.new()
	sign.name = "Sign"
	sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sign.font_size = 64
	sign.pixel_size = 0.01
	sign.outline_size = 12
	sign.outline_modulate = Palette.LABEL_OUTLINE
	sign.modulate = Palette.LABEL_TEXT
	sign.position = Vector3(0, 3.35, 0)
	Mesher.adopt(self, sign)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(3.4, 2.8, 3.1)
	shape.shape = box
	shape.position.y = 1.4
	body.add_child(shape)
	Mesher.adopt(self, body)
	_apply_sign()
