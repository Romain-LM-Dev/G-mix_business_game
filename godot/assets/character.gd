@tool
extends GmixAsset
## Personnage animé du catalogue (Kenney Mini Characters). Animations disponibles : static, idle, walk, sprint,
## jump, fall, crouch, sit, drive, die, pick-up, emote-yes. Joue `animation` en boucle en jeu (pas dans l'éditeur).

@export var animation := "idle":
	set(value):
		animation = value
		_play()


func _ready() -> void:
	super()
	_play()


func _play() -> void:
	if not is_node_ready() or Engine.is_editor_hint():
		return
	var player := find_child("AnimationPlayer", true, false) as AnimationPlayer
	if player != null and player.has_animation(animation):
		player.get_animation(animation).loop_mode = Animation.LOOP_LINEAR
		player.play(animation)
