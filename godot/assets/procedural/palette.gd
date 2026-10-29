@tool
class_name Palette
extends RefCounted
## Direction artistique commune de G-mix : jour clair, tons sauge et turquoise désaturés, accents ocre.
## Valeurs reprises de la direction artistique du jeu de référence Business_game (hex sRGB, comme les `Color` de Godot).
## Les constantes servent à colorer les assets procéduraux, l'environnement du monde et l'interface ;
## `material()` donne un matériau à grain léger et `restyle()` ramène les modèles de packs tiers (Kenney) dans la palette.

# --- Environnement (rendu) ---------------------------------------------------------------------------------
const BACKGROUND := Color("cbd9d1")  # fond de scène ET brouillard (portée conseillée : 32 à 78 m)
const SKY := Color("e5f3ef")  # lumière ambiante du dessus
const GROUND_BOUNCE := Color("52635b")  # lumière ambiante du dessous
const SUN := Color("ffedcf")  # lumière directionnelle (blanc chaud)

# --- Sol et murs --------------------------------------------------------------------------------------------
const WALL := Color("d6d9d0")  # murs ouvragés
const WALL_LIGHT := Color("e5e6dc")
const WALL_WARM := Color("e4e3d8")
const CONCRETE := Color("b5b8ae")  # dalle du hall
const GRASS := Color("9bad8e")
const FORECOURT := Color("b6c3af")  # parvis, aire des camions
const CURB := Color("45665d")  # bordures vert forêt
const AISLE := Color("87958c")  # allée piétonne
const MARK_YELLOW := Color("e8cb77")  # marquage jaune
const MARK_PALE := Color("f2df9e")

# --- Acier, bois, carton ------------------------------------------------------------------------------------
const STEEL := Color("66756e")  # acier gris-vert
const STEEL_DARK := Color("415c56")  # montants, châssis
const STEEL_LIGHT := Color("87958c")
const STEEL_PALE := Color("bfc4b2")  # rouleaux, plans inox
const DARK := Color("34413d")  # pièces sombres : pneus, sièges, boîtiers
const DARK_TEAL := Color("253b39")
const FRAME := Color("455d58")  # bâti de machine
const COVER := Color("748a7d")  # capot de machine
const CARDBOARD := Color("b9905d")
const CARDBOARD_DARK := Color("9d774a")  # dérivé : intérieur, rabats
const CARDBOARD_LIGHT := Color("d4a064")
const WOOD := Color("d4a064")  # planches de palette, plans de travail
const WOOD_DARK := Color("b78043")  # dés de palette, lisses de rayonnage
const FILM := Color("dde7e1")  # film étirable
const RUST := Color("b56d54")  # rouille : rebut, servante, alerte douce
const RUST_DARK := Color("8a4f3c")  # dérivé

# --- Teintes des stations et accents -------------------------------------------------------------------------
const SAGE := Color("8eb7a5")  # réception
const TURQUOISE := Color("70c1bb")  # production et qualité
const OCHRE := Color("d4a45c")  # emballage, accent chaud
const BLUE := Color("7c98b0")  # bleu-gris des machines et du réglage
const STATION_RECEPTION := Color("8eb7a5")
const STATION_STOCK := Color("9cad8d")
const STATION_PRODUCTION := Color("70c1bb")
const STATION_PACKING := Color("d4a45c")
const STATION_MAINTENANCE := Color("80958d")
const STATION_CONTROL := Color("53766a")  # pilotage
const MACHINE_ACCENTS := [Color("79a69b"), Color("d4a064"), Color("91a96e"), Color("7c98b0")]

# --- Personnel ---------------------------------------------------------------------------------------------
const WORKER_JACKETS := [Color("4f8c7c"), Color("4b718a"), Color("7d8153"), Color("8c6855")]
const HARDHAT := Color("e4bd54")
const HARDHAT_PLAYER := Color("d8ed82")  # lime : le joueur
const SKIN := Color("dcae88")
const PANTS := Color("334b4a")

# --- Voyants d'état (vert, ambre, rouge) -------------------------------------------------------------------
const OK := Color("75d28b")
const WARN := Color("e5b74e")
const ALERT := Color("d86759")
const SCREEN := Color("8dc38d")  # écran allumé
const SCREEN_GLOW := Color("27552c")
const GLASS := Color("9bc8c2")

# --- Véhicules ----------------------------------------------------------------------------------------------
const FORKLIFT := Color("d8ad4f")
const FORKLIFT_FORKS := Color("c6aa72")
const BEACON := Color("ffb339")
const TRUCK_CARGO := Color("456b61")
const TRUCK_CAB := Color("e8e6d8")
const WHEEL := Color("293638")

# --- Étiquettes en 3D ---------------------------------------------------------------------------------------
const LABEL_TEXT := Color("fff9dc")  # texte crème
const LABEL_OUTLINE := Color("183a36")  # contour vert profond

const GRAIN_SIZE := 128
## Mètres par répétition de la texture de grain, selon la matière (le béton s'étale, le carton se resserre).
const GRAIN_TILE := {"concrete": 8.0, "cardboard": 1.2, "steel": 0.8}
const MUTE := 0.62  # part de saturation conservée par `restyle`
const VALUE := 0.9  # luminosité conservée (les packs tiers sont plus clairs que la palette)
const HUE_PULL := 0.7  # part de l'écart de teinte comblée vers la teinte la plus proche de la palette
const HUES := [0.04, 0.10, 0.42, 0.49, 0.58]  # rouille, ocre, sauge, turquoise, bleu-gris
## Modèles tiers dont la teinte d'origine ne se rattrape pas (colis rose saumon) : matière unie de la palette.
const FLAT := {"prop_box_large": CARDBOARD, "prop_box_small": CARDBOARD}
const RESTYLE_SIZE := 128  # côté des textures de palette de pack après retouche (de simples nuanciers)

static var _grains: Dictionary = {}
static var _materials: Dictionary = {}
static var _textures: Dictionary = {}
static var _restyled: Dictionary = {}


## Texture de grain (niveaux de gris proches du blanc : elle nuance la couleur sans la changer), tuilable à l'œil,
## générée une fois (aucun fichier image) : « concrete » (marbrures), « cardboard » (fibres), « steel » (fines mouchetures).
static func grain(kind: String) -> ImageTexture:
	if not _grains.has(kind):
		var rng := RandomNumberGenerator.new()
		rng.seed = hash(kind)
		var image := Image.create(GRAIN_SIZE, GRAIN_SIZE, false, Image.FORMAT_L8)
		image.fill(Color(0.97, 0.97, 0.97))
		for _i in GRAIN_SIZE * GRAIN_SIZE / 8:
			var v := rng.randf_range(0.9, 1.0)
			image.fill_rect(Rect2i(rng.randi() % GRAIN_SIZE, rng.randi() % GRAIN_SIZE, rng.randi_range(1, 2), rng.randi_range(1, 2)), Color(v, v, v))
		if kind == "concrete":
			for _i in 180:
				var v := rng.randf_range(0.9, 0.97)
				image.fill_rect(Rect2i(rng.randi() % GRAIN_SIZE, rng.randi() % GRAIN_SIZE, rng.randi_range(2, 5), rng.randi_range(2, 5)), Color(v, v, v))
		elif kind == "cardboard":
			for y in range(8, GRAIN_SIZE, 16):
				image.fill_rect(Rect2i(0, y, GRAIN_SIZE, 1), Color(0.9, 0.9, 0.9))
		image.generate_mipmaps()
		_grains[kind] = ImageTexture.create_from_image(image)
	return _grains[kind]


## Matériau mat à grain (projection triplanaire : aucune UV requise, la même texture pour tous les maillages).
static func material(color: Color, kind := "steel", emission := Color.BLACK) -> StandardMaterial3D:
	var key := "%s|%s|%s" % [color.to_html(), kind, emission.to_html()]
	if not _materials.has(key):
		var mat := StandardMaterial3D.new()
		mat.albedo_color = color
		mat.roughness = 0.85
		mat.albedo_texture = grain(kind)
		mat.uv1_triplanar = true
		mat.uv1_scale = Vector3.ONE / float(GRAIN_TILE.get(kind, 0.8))
		if emission != Color.BLACK:
			mat.emission_enabled = true
			mat.emission = emission
		_materials[key] = mat
	return _materials[key]


## Ramène les matériaux d'un modèle de pack tiers dans la palette (moins saturés, teintes tirées vers rouille, ocre,
## sauge, turquoise et bleu-gris) sans toucher à sa géométrie : copies mises en cache par matériau et par texture
## (les nuanciers de pack font 512 px, réduits à RESTYLE_SIZE), donc quasi gratuit à l'exécution.
static func restyle(root: Node, asset_id := "") -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var instance := node as MeshInstance3D
		if FLAT.has(asset_id):
			instance.material_override = material(FLAT[asset_id], "cardboard")
			continue
		for i in instance.get_surface_override_material_count():
			var source := instance.get_active_material(i) as StandardMaterial3D
			if source != null and not source.has_meta(&"gmix_restyled"):
				instance.set_surface_override_material(i, _restyled_material(source))


## Couleur d'un modèle tiers ramenée dans la palette : teinte tirée vers la plus proche de HUES, saturation réduite ;
## les gris prennent une pointe de sauge.
static func mute(color: Color) -> Color:
	var hue := color.h
	var nearest := 0.0
	var gap := 1.0
	for anchor: float in HUES:
		var d := fposmod(anchor - hue + 0.5, 1.0) - 0.5
		if absf(d) < gap:
			gap = absf(d)
			nearest = d
	hue += nearest * HUE_PULL
	var saturation := color.s * MUTE
	var grey := clampf(1.0 - color.s / 0.12, 0.0, 1.0)
	if grey > 0.0:
		hue = HUES[2]
		saturation = lerpf(saturation, 0.07, grey)
	return Color.from_hsv(fposmod(hue, 1.0), saturation, color.v * VALUE, color.a)


static func _restyled_material(source: StandardMaterial3D) -> StandardMaterial3D:
	if not _restyled.has(source):
		var mat := source.duplicate() as StandardMaterial3D
		if source.albedo_texture != null:
			mat.albedo_texture = _muted_texture(source.albedo_texture)
		else:
			mat.albedo_color = mute(source.albedo_color)
		mat.set_meta(&"gmix_restyled", true)
		_restyled[source] = mat
	return _restyled[source]


static func _muted_texture(texture: Texture2D) -> Texture2D:
	if not _textures.has(texture):
		var image := texture.get_image()  # null sans rendu (mode headless) : le modèle garde alors ses couleurs
		var result := texture
		if image != null:
			if image.is_compressed():
				image.decompress()
			image.convert(Image.FORMAT_RGBA8)
			image.resize(RESTYLE_SIZE, RESTYLE_SIZE, Image.INTERPOLATE_BILINEAR)
			for y in RESTYLE_SIZE:
				for x in RESTYLE_SIZE:
					var c := image.get_pixel(x, y)
					if c.a > 0.0:
						image.set_pixel(x, y, mute(c))
			image.generate_mipmaps()
			result = ImageTexture.create_from_image(image)
		_textures[texture] = result
	return _textures[texture]
