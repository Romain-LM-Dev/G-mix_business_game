@tool
extends GmixAsset
## Bâtiment d'un site du réseau logistique (ADR 0009), à poser sur la cellule d'un site de la carte. Façade et
## quais vers +Z (côté route). Propriété : kind (« fournisseur », « client » ou « entrepot » = entrepôt externe) ;
## chaque id du catalogue (bld_site_supplier, bld_site_client, bld_site_warehouse) fixe le sien. Variante : enseigne
## (texte au-dessus de la façade). Collision : le volume du bâtiment.

@export_enum("fournisseur", "client", "entrepot") var kind := "fournisseur":
	set(value):
		kind = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var batch := Mesher.Batch.new()
	var body: Vector3  # largeur, hauteur, profondeur du volume
	var back_z: float  # centre du volume en Z (l'emprise de 16 m laisse un parvis devant)
	match kind:
		"client":
			body = Vector3(20, 8, 12)
			back_z = -2.0
			_client(batch, body, back_z)
		"entrepot":
			body = Vector3(24, 7, 14)
			back_z = -1.0
			_warehouse(batch, body, back_z)
		_:
			body = Vector3(24, 7, 12)
			back_z = -2.0
			_supplier(batch, body, back_z)
	batch.build(self)
	var sign := Label3D.new()
	sign.name = "Sign"
	sign.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sign.font_size = 64
	sign.pixel_size = 0.04
	sign.outline_size = 12
	sign.outline_modulate = Palette.LABEL_OUTLINE
	sign.modulate = Palette.LABEL_TEXT
	sign.position = Vector3(0, body.y + 4.0 if kind == "fournisseur" else body.y + 2.2, back_z + body.z / 2.0)
	Mesher.adopt(self, sign)
	Mesher.collider(self, [[body, Vector3(0, body.y / 2.0, back_z)]])
	_apply_sign()


## Portes de quai alignées sur la façade : `count` portes de 3 m, centrées.
func _doors(batch: Mesher.Batch, front_z: float, count: int, color: Color) -> void:
	for i in count:
		var x := (i - (count - 1) / 2.0) * 5.0
		batch.box(Vector3(3.2, 3.6, 0.3), Vector3(x, 1.8, front_z + 0.1), Palette.DARK)  # embrasure
		batch.box(Vector3(2.8, 3.2, 0.1), Vector3(x, 1.7, front_z + 0.27), color)  # rideau
		batch.box(Vector3(3.4, 0.2, 1.6), Vector3(x, 3.9, front_z + 0.8), Palette.STEEL_DARK)  # auvent


func _supplier(batch: Mesher.Batch, body: Vector3, z: float) -> void:
	var front := z + body.z / 2.0
	batch.box(body, Vector3(0, body.y / 2.0, z), Palette.WALL)
	batch.box(Vector3(body.x + 0.4, 0.4, body.z + 0.4), Vector3(0, 0.2, z), Palette.CONCRETE)  # soubassement
	batch.box(Vector3(body.x, 0.5, 0.2), Vector3(0, 4.6, front + 0.1), Palette.TURQUOISE)  # bandeau
	for i in 4:  # toit en sheds : verrière inclinée vers le nord
		var x := -9.0 + i * 6.0
		batch.box(Vector3(5.6, 1.6, 0.3), Vector3(x, body.y + 0.8, z - 2.0), Palette.STEEL, Vector3(-25, 0, 0))
		batch.box(Vector3(5.6, 1.6, 0.1), Vector3(x, body.y + 0.8, z - 1.55), Palette.GLASS, Vector3(-25, 0, 0))
	batch.cylinder(0.9, 12.0, Vector3(-9.5, 6.0, z - 3.0), Palette.STEEL_DARK, Vector3.AXIS_Y, 10)  # cheminée
	batch.cylinder(1.0, 0.5, Vector3(-9.5, 11.8, z - 3.0), Palette.RUST, Vector3.AXIS_Y, 10)
	_doors(batch, front, 3, Palette.STEEL_LIGHT)
	for x in [-9.0, 9.0]:
		batch.box(Vector3(1.2, 1.2, 0.1), Vector3(x, 2.4, front + 0.06), Palette.GLASS)  # fenêtres


func _client(batch: Mesher.Batch, body: Vector3, z: float) -> void:
	var front := z + body.z / 2.0
	batch.box(body, Vector3(0, body.y / 2.0, z), Palette.WALL_WARM)
	batch.box(Vector3(body.x, 3.4, 0.2), Vector3(-0.0, 1.9, front + 0.1), Palette.GLASS)  # vitrine du rez-de-chaussée
	for x in [-6.0, -2.0, 2.0, 6.0]:
		batch.box(Vector3(0.2, 3.4, 0.3), Vector3(x, 1.9, front + 0.15), Palette.STEEL_DARK)  # meneaux
	batch.box(Vector3(body.x, 0.3, 2.0), Vector3(0, 3.9, front + 1.0), Palette.OCHRE)  # auvent
	for x in [-6.0, -2.0, 2.0, 6.0]:
		batch.box(Vector3(1.8, 1.4, 0.1), Vector3(x, 6.0, front + 0.06), Palette.GLASS)  # fenêtres de l'étage
	batch.box(Vector3(body.x + 0.4, 0.4, body.z + 0.4), Vector3(0, body.y + 0.2, z), Palette.OCHRE)  # acrotère
	# quai de livraison sur le côté droit
	batch.box(Vector3(3.2, 3.2, 0.3), Vector3(8.0, 1.6, front + 0.14), Palette.DARK)
	batch.box(Vector3(2.8, 2.9, 0.1), Vector3(8.0, 1.5, front + 0.31), Palette.STEEL_LIGHT)


func _warehouse(batch: Mesher.Batch, body: Vector3, z: float) -> void:
	var front := z + body.z / 2.0
	batch.box(body, Vector3(0, body.y / 2.0, z), Palette.WALL_LIGHT)
	batch.box(Vector3(body.x + 0.4, 0.4, body.z + 0.4), Vector3(0, 0.2, z), Palette.CONCRETE)
	batch.box(Vector3(body.x, 0.5, 0.2), Vector3(0, 5.4, front + 0.1), Palette.SAGE)  # bandeau
	batch.box(Vector3(body.x + 0.6, 0.3, body.z + 0.6), Vector3(0, body.y + 0.15, z), Palette.STEEL)  # toit plat débordant
	batch.box(Vector3(body.x - 4.0, 0.8, 3.0), Vector3(0, body.y + 0.7, z), Palette.STEEL_LIGHT)  # lanterneau
	_doors(batch, front, 4, Palette.SAGE)
	for x in [-10.5, 10.5]:
		batch.box(Vector3(1.2, 1.2, 0.1), Vector3(x, 2.4, front + 0.06), Palette.GLASS)
