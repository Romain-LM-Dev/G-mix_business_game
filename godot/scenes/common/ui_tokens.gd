class_name UiTokens
extends RefCounted
## Jetons de direction artistique : seul endroit où l'on règle couleurs, rayons, espacements, polices et ambiance 3D.
## Source : jeu de référence Business_game, avec l'accord de son autrice (aucun crédit à ajouter) : verre vert profond,
## accent lime, tons sauge. Tailles ramenées à la lisibilité de G-mix (corps 18 px, jamais sous 15 px).
## shortcut : constantes figées, pas de thème choisi à l'exécution ; pour un thème de pack ou de formateur, en faire une
## ressource chargée par Session et passer ses valeurs à `Ui.make_theme()`.
## `contrast_failures()` (appelée par `-Check`) calcule le rapport de contraste de chaque texte sur son fond (>= 4,5:1).

# --- Texte et accents (UI sombre) ---
const INK := Color("#f5f2e9")  # texte principal
const MUTED_HEX := "#b4c1bb"  # légendes, aide, texte secondaire (hex aussi pour le BBCode)
const MUTED := Color(MUTED_HEX)
const LIME := Color("#d9f18a")  # accent : titres de panneau, bouton principal, focus
const LIME_HOVER := Color("#e6f5a9")
const LIME_PRESSED := Color("#c3db75")
const ON_LIME := Color("#233b32")  # texte sur un fond lime
const OK_HEX := "#8dc687"
const WARN_HEX := "#e5b74e"
const ERROR_HEX := "#f5a193"
const INFO_HEX := "#92c2dd"
const OK := Color(OK_HEX)
const WARN := Color(WARN_HEX)
const ERROR := Color(ERROR_HEX)
const INFO := Color(INFO_HEX)

# --- Fonds et traits ---
const BACKDROP := Color("#0d1b1c")  # fond des écrans avant-jeu
const PANEL := Color("#132527")  # verre vert profond : opaque dans les fenêtres, à GLASS_ALPHA sur le monde
const GLASS_ALPHA := 0.86
const FIELD := Color("#0e2021")  # champs de saisie
const EDGE := Color("#3b5452")  # filet des panneaux et champs
const BUTTON := Color("#24423f")
const BUTTON_HOVER := Color("#2f5551")
const BUTTON_PRESSED := Color("#1a312f")
const BUTTON_OFF := Color("#172a2b")
const TEXT_OFF := Color("#8a9a93")  # texte d'un contrôle inactif
const PLACEHOLDER := Color("#8fa098")
const TAB_OFF := Color("#0f1f21")
const MENU_HOVER := Color("#2f5551")

# --- Rayons, espacements ---
const RADIUS_CONTROL := 6
const RADIUS_PANEL := 8
const RADIUS_MODAL := 12
const PANEL_PAD := Vector2i(16, 14)
const CONTROL_PAD := Vector2i(14, 7)
const FIELD_PAD := Vector2i(10, 7)
const TAB_PAD := Vector2i(20, 9)
const GAP := 10

# --- Polices (fichiers déposés par assets-3d ; absents : police par défaut de Godot) ---
const FONT_DISPLAY := "res://assets/fonts/ManropeBold.tres"  # titres
const FONT_BODY := "res://assets/fonts/DMSans.ttf"  # corps
const FONT_BODY_BOLD := "res://assets/fonts/DMSansBold.tres"  # gras du corps
const FONT_MONO := "res://assets/fonts/DMMono.ttf"  # étiquettes et chiffres
const BODY_SIZE := 18
const MIN_SIZE := 15
const HEADING_FROM := 20  # `Ui.label` pose la police des titres à partir de cette taille
const TAB_SIZE := 20
const TIP_SIZE := 16
const WINDOW_TITLE_SIZE := 18

# --- Ambiance 3D (atelier et usine) ---
# Couleurs : palette 3D de assets/procedural/palette.gd (assets-3d), qui reste la seule source.
const SKY_TOP := Palette.SKY  # hémisphère : ciel
const SKY_HORIZON := Palette.BACKGROUND  # fond et brouillard
const GROUND := Palette.GROUND_BOUNCE  # hémisphère : sol
const SUN := Palette.SUN  # soleil chaud
const FOG := Palette.BACKGROUND
const LAWN := Palette.GRASS  # herbe autour du hall
const TONE_EXPOSURE := 0.6  # l'ACES de Godot éclaircit (gain 1/0,6 en entrée) : exposition réduite pour garder le sauge de la palette
const AMBIENT_ENERGY := 0.45
const SUN_ENERGY := 0.8


## Rapport de contraste WCAG entre deux couleurs opaques (1 à 21).
static func contrast(a: Color, b: Color) -> float:
	var la := a.srgb_to_linear().get_luminance()
	var lb := b.srgb_to_linear().get_luminance()
	return (maxf(la, lb) + 0.05) / (minf(la, lb) + 0.05)


## Textes de l'interface avec leur fond : [légende, texte, fond]. Le verre sur le monde est pris sur du blanc (pire cas).
static func text_pairs() -> Array:
	var glass := PANEL.lerp(Color.WHITE, 1.0 - GLASS_ALPHA)
	var pairs: Array = [
		["texte sur panneau", INK, PANEL],
		["légende sur panneau", MUTED, PANEL],
		["accent sur panneau", LIME, PANEL],
		["texte sur champ", INK, FIELD],
		["indice de champ", PLACEHOLDER, FIELD],
		["texte sur bouton", INK, BUTTON],
		["texte sur bouton survolé", INK, BUTTON_HOVER],
		["texte sur bouton enfoncé", INK, BUTTON_PRESSED],
		["texte de contrôle inactif", TEXT_OFF, BUTTON_OFF],
		["bouton principal", ON_LIME, LIME],
		["bouton principal survolé", ON_LIME, LIME_HOVER],
		["bouton principal enfoncé", ON_LIME, LIME_PRESSED],
		["onglet choisi", INK, PANEL],
		["onglet", MUTED, TAB_OFF],
		["menu survolé", INK, MENU_HOVER],
	]
	for pair: Array in [["texte", INK], ["légende", MUTED], ["accent", LIME], ["ok", OK], ["alerte", WARN], ["erreur", ERROR], ["info", INFO]]:
		pairs.append(["%s sur verre (monde clair derrière)" % pair[0], pair[1], glass])
		pairs.append(["%s sur panneau" % pair[0], pair[1], PANEL])
	return pairs


## Légendes des couples qui n'atteignent pas 4,5:1 (liste vide : tout est lisible).
static func contrast_failures() -> Array[String]:
	var failures: Array[String] = []
	for pair: Array in text_pairs():
		var ratio := contrast(pair[1], pair[2])
		if ratio < 4.5:
			failures.append("%s : %.2f:1" % [pair[0], ratio])
	return failures
