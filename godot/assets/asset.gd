@tool
class_name GmixAsset
extends Node3D
## Racine de tout asset du catalogue (ai/assets.yaml). Les « variantes » du catalogue sont des propriétés que
## le générateur de lobby peut régler ; les autres restent fixes.
## Conventions : 1 unité = 1 m ; origine au sol, au centre ; avant (façade, portes, phares, fourches, écran) vers +Z.

@export var asset_id := ""
## Variante « enseigne » : texte affiché sur la façade (vide = pas d'enseigne).
@export var sign_text := "":
	set(value):
		sign_text = value
		_apply_sign()


func _ready() -> void:
	_apply_sign()


func _apply_sign() -> void:
	var label := get_node_or_null("Sign") as Label3D
	if label != null:
		label.text = sign_text
		label.visible = not sign_text.is_empty()
