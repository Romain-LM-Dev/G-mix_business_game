@tool
extends GmixAsset
## Pièce symbolique (au plus 0,4 x 0,4 x 0,3 m) : la forme ET la couleur disent l'état du produit, pour suivre les
## produits sur le flux sans les modéliser un à un. Sans collision (jeton posé sur une table ou un convoyeur).
## Propriété : product_state (variante etat_produit) : en_cours, a_controler, conforme, a_retoucher, rebut, emballe,
## stock_pf, expedie.

const STATES := ["en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie"]

@export_enum("en_cours", "a_controler", "conforme", "a_retoucher", "rebut", "emballe", "stock_pf", "expedie") var product_state := "en_cours":
	set(value):
		if not value in STATES:
			push_warning("%s : état inconnu « %s » (en_cours affiché)" % [asset_id, value])
			value = "en_cours"
		product_state = value
		_rebuild()


func _ready() -> void:
	super()
	_rebuild()


func _rebuild() -> void:
	if not is_node_ready():
		return
	Mesher.clear(self)
	var batch := Mesher.Batch.new()
	match product_state:
		"en_cours":  # bloc brut ocre
			batch.box(Vector3(0.3, 0.2, 0.3), Vector3(0, 0.1, 0), Palette.OCHRE)
		"a_controler":  # disque turquoise
			batch.cylinder(0.17, 0.16, Vector3(0, 0.08, 0), Palette.TURQUOISE, Vector3.AXIS_Y, 12)
		"conforme":  # bloc vert surmonté d'une pastille claire
			batch.box(Vector3(0.3, 0.18, 0.3), Vector3(0, 0.09, 0), Palette.OK)
			batch.box(Vector3(0.14, 0.04, 0.14), Vector3(0, 0.2, 0), Palette.LABEL_TEXT)
		"a_retoucher":  # plaque ambre de travers
			batch.box(Vector3(0.34, 0.08, 0.26), Vector3(0, 0.1, 0), Palette.WARN, Vector3(0, 28, 6))
			batch.box(Vector3(0.1, 0.1, 0.1), Vector3(0.08, 0.2, 0), Palette.DARK)
		"rebut":  # bloc rouille renversé
			batch.box(Vector3(0.28, 0.2, 0.28), Vector3(0, 0.13, 0), Palette.RUST, Vector3(18, 40, 22))
		"emballe":  # carton fermé et ruban
			batch.box(Vector3(0.36, 0.24, 0.3), Vector3(0, 0.12, 0), Palette.CARDBOARD)
			batch.box(Vector3(0.08, 0.245, 0.31), Vector3(0, 0.122, 0), Palette.FILM)
		"stock_pf":  # carton sur palette miniature, vert sauge
			batch.box(Vector3(0.38, 0.05, 0.3), Vector3(0, 0.025, 0), Palette.WOOD)
			batch.box(Vector3(0.32, 0.22, 0.26), Vector3(0, 0.16, 0), Palette.SAGE)
		"expedie":  # carton bleu-gris avec fanion
			batch.box(Vector3(0.3, 0.2, 0.3), Vector3(0, 0.1, 0), Palette.BLUE)
			batch.box(Vector3(0.03, 0.1, 0.03), Vector3(0.12, 0.25, 0.12), Palette.STEEL_DARK)
			batch.box(Vector3(0.12, 0.05, 0.02), Vector3(0.18, 0.28, 0.12), Palette.WARN)
	batch.build(self)
