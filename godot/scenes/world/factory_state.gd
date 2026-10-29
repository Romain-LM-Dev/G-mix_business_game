class_name GmixFactoryState
extends RefCounted
## Lecture de la spec et de l'état public d'une usine (ADR 0007, annexe §1 et §2) pour le monde 3D : fonctions pures,
## sans nœud ni règle de jeu. Le moteur calcule, le client regarde : états des machines et des agents, remplissage des
## tables, des racks et du bac à rebut. Tout ce qui est affiché vient de `spec.factory`, `spec.departments` et de
## `state.factory` ; rien n'est supposé d'un domaine précis (les noms de lieux et de machines sont ceux de la spec).

## Code d'état d'un agent (annexe §1, AgentState) -> [libellé affiché, couleur du texte au-dessus de sa tête].
const AGENT_STATES := {
	"disponible": ["disponible", Color(0.62, 0.95, 0.68)],
	"occupe": ["occupé", Color(1.0, 0.78, 0.35)],
	"deplacement": ["en déplacement", Color(0.58, 0.8, 1.0)],
	"pause": ["en pause", Color(0.78, 0.8, 0.86)],
	"absent": ["absent", Color(1.0, 0.55, 0.5)],
}
## Titre des figurants (CrewMember.job est un code) ; un code inconnu devient « Code mis en forme ».
const CREW_TITLES := {
	"operateur": "Opérateur",
	"chauffeur_fournisseur": "Chauffeur du fournisseur",
	"chauffeur_client": "Chauffeur du client",
}
## Couleurs des zones des départements internes (une par département, dans l'ordre de la spec) et des extérieurs.
const ZONE_COLORS := [
	Color(0.95, 0.72, 0.15), Color(0.2, 0.62, 0.62), Color(0.35, 0.52, 0.85), Color(0.9, 0.5, 0.2),
	Color(0.6, 0.45, 0.8), Color(0.45, 0.7, 0.35), Color(0.85, 0.4, 0.5), Color(0.3, 0.6, 0.85),
]
const ZONE_EXTERNAL := Color(0.55, 0.6, 0.68)


static func is_factory(spec: Dictionary) -> bool:
	return _as_dict(spec.get("world")).get("template", "atelier") == "usine"


## `value` si c'est un dictionnaire, sinon {} : la spec et l'état d'un atelier portent `factory: null`, pas une clé absente.
static func _as_dict(value: Variant) -> Dictionary:
	return value if value is Dictionary else {}


## Une partie de `state.factory` (clé `key`), `fallback` si l'état n'a pas d'usine.
static func part(state: Dictionary, key: String, fallback: Variant = {}) -> Variant:
	return _as_dict(state.get("factory")).get(key, fallback)


static func state_text(code: String) -> String:
	return AGENT_STATES[code][0] if AGENT_STATES.has(code) else code


static func state_color(code: String) -> Color:
	return AGENT_STATES[code][1] if AGENT_STATES.has(code) else Color.WHITE


static func crew_title(job: String) -> String:
	return CREW_TITLES[job] if CREW_TITLES.has(job) else job.replace("_", " ").capitalize()


## {state, at} d'un agent ou d'un figurant dans `state.factory.agents`, {} s'il n'y est pas.
static func agent(state: Dictionary, id: String) -> Dictionary:
	var entry: Variant = (part(state, "agents") as Dictionary).get(id)
	return entry if entry is Dictionary else {}


## Machine de `state.factory.machines` par identifiant ({} si absente).
static func machine(state: Dictionary, id: String) -> Dictionary:
	for entry: Dictionary in part(state, "machines", []):
		if entry.get("id") == id:
			return entry
	return {}


## Remplissage d'une table d'attente (0 à 1) : unités posées / capacité, arrondi au vingtième (un changement de niveau
## reconstruit les bacs de la table, inutile pour un écart invisible).
static func buffer_fill(entry: Dictionary) -> float:
	return snappedf(clampf(float(entry.get("buffer", 0)) / maxf(1.0, float(entry.get("buffer_max", 1))), 0.0, 1.0), 0.05)


## Remplissage (0 à 1) du rayonnage d'une matière (palettes / places) ; -1 si l'état ne la connaît pas.
static func mp_fill(state: Dictionary, component_id: String) -> float:
	for entry: Dictionary in (part(state, "stocks") as Dictionary).get("mp", []):
		if entry.get("component_id") == component_id:
			return snappedf(clampf(float(entry["pallets"]) / maxf(1.0, float(entry["capacity_pallets"])), 0.0, 1.0), 0.05)
	return -1.0


## Remplissage (0 à 1) de l'entrepôt de produits finis ; -1 si absent.
static func pf_fill(state: Dictionary) -> float:
	var pf: Variant = (part(state, "stocks") as Dictionary).get("pf")
	if not pf is Dictionary:
		return -1.0
	return snappedf(clampf(float(pf["pallets"]) / maxf(1.0, float(pf["capacity_pallets"])), 0.0, 1.0), 0.05)


## Remplissage du bac à rebut : rebuts du tour / un lot (pure mise à l'échelle d'affichage, aucune règle).
static func scrap_fill(state: Dictionary, spec: Dictionary) -> float:
	var lot := float(_as_dict(spec.get("factory")).get("lot_size", 24))
	var scrap := float((part(state, "products") as Dictionary).get("rebut", 0))
	return snappedf(clampf(scrap / maxf(1.0, lot), 0.0, 1.0), 0.05)


static func zone_color(index: int, external: bool) -> Color:
	return ZONE_EXTERNAL if external else ZONE_COLORS[index % ZONE_COLORS.size()]


## Zone d'un département (x_min, z_min, x_max, z_max) en Rect2 du plan XZ.
static func area_rect(area: Array) -> Rect2:
	return Rect2(Vector2(float(area[0]), float(area[1])), Vector2(float(area[2]) - float(area[0]), float(area[3]) - float(area[1])))
