extends Node
## Signaux globaux qui découplent UI, monde 3D et réseau.
## Règle : un signal n'est ajouté ici que s'il traverse plusieurs scènes ; sinon il reste local.

@warning_ignore("unused_signal")
signal backend_status_changed(healthy: bool, report: Dictionary)
## generation.progress | generation.completed | generation.failed (payload : job_id, game_id, stage, progress…)
@warning_ignore("unused_signal")
signal generation_event(type: String, payload: Dictionary)
## lobby.state : {lobby_status, state (état public), action {type, by, …}}
@warning_ignore("unused_signal")
signal lobby_state_changed(payload: Dictionary)
@warning_ignore("unused_signal")
signal lobby_members_changed(members: Array)
