class_name GameText
extends RefCounted
## Mise en forme des données de jeu renvoyées par l'API (KPI, phase, débrief, spec) en BBCode pour RichTextLabel.
## Tout texte venant de l'API ou de l'IA passe par esc() : un « [ » ne doit jamais être lu comme une balise.

const GREEN := "#7fd98a"
const ORANGE := "#ffb84d"
const GREY := "#9aa3b2"


static func esc(text: Variant) -> String:
	return str(text).replace("[", "[lb]")


static func number(value: Variant) -> String:
	if value == null:
		return "-"
	var f := float(value)
	return str(int(f)) if is_equal_approx(f, roundf(f)) else "%.1f" % f


static func kpi_met(kpi: Dictionary, value: Variant) -> bool:
	if value == null:
		return false
	if kpi["direction"] == "higher_is_better":
		return float(value) >= float(kpi["target"])
	return float(value) <= float(kpi["target"])


## Lignes {name, value, unit} pour l'écran des KPI du monde 3D.
static func kpi_rows(spec: Dictionary, state: Dictionary) -> Array:
	var values: Dictionary = state.get("kpis", {})
	var rows := []
	for kpi: Dictionary in spec.get("kpis", []):
		rows.append({"name": kpi["name"], "value": number(values.get(kpi["id"])), "unit": kpi["unit"]})
	return rows


static func kpis_bbcode(spec: Dictionary, state: Dictionary) -> String:
	var values: Dictionary = state.get("kpis", {})
	var lines := PackedStringArray()
	for kpi: Dictionary in spec.get("kpis", []):
		var value: Variant = values.get(kpi["id"])
		var color := GREEN if kpi_met(kpi, value) else ORANGE
		var arrow := "↑" if kpi["direction"] == "higher_is_better" else "↓"
		lines.append(
			"[color=%s]●[/color] %s : [b]%s %s[/b]  [color=%s]cible %s %s %s[/color]"
			% [color, esc(kpi["name"]), number(value), esc(kpi["unit"]), GREY, arrow, number(kpi["target"]), esc(kpi["unit"])]
		)
	return "\n".join(lines)


static func phase_bbcode(state: Dictionary) -> String:
	var phase: Dictionary = state.get("phase", {})
	var status: String = state.get("status", "waiting")
	var head := "En attente du lancement par le formateur"
	if status == "running":
		head = "Phase %d / %d : %s" % [int(state.get("phase_index", 0)) + 1, int(state.get("phase_count", 1)), esc(phase.get("title", ""))]
	elif status == "finished":
		head = "Partie terminée : place au débrief"
	var goal := "" if status == "finished" else "\n[color=%s]%s[/color]" % [GREY, esc(phase.get("goal", ""))]
	return "[b]%s[/b]%s" % [head, goal]


static func role_title(spec: Dictionary, role_id: Variant) -> String:
	for role: Dictionary in spec.get("roles", []):
		if role["id"] == role_id:
			return role["title"]
	return str(role_id) if role_id != null else "aucun rôle"


static func debrief_bbcode(report: Dictionary) -> String:
	var out := PackedStringArray(["[font_size=24][b]Indicateurs[/b][/font_size]"])
	for kpi: Dictionary in report.get("kpis", []):
		var met: Variant = kpi.get("met")
		var mark := "[color=%s]atteint[/color]" % GREEN if met == true else "[color=%s]non atteint[/color]" % ORANGE
		out.append(
			"• %s : %s → [b]%s %s[/b] (cible %s) %s"
			% [esc(kpi["name"]), number(kpi["initial"]), number(kpi.get("final")), esc(kpi["unit"]), number(kpi["target"]), mark]
		)
	out.append("\n[font_size=24][b]Décisions et explications[/b][/font_size]")
	for decision: Dictionary in report.get("decisions", []):
		out.append("\n[b]%s[/b]  [color=%s](%s)[/color]" % [esc(decision["prompt"]), GREY, esc(decision["phase"])])
		if decision.get("chosen") == null:
			out.append("[color=%s]Décision non prise[/color]" % ORANGE)
		for option: Dictionary in decision.get("options", []):
			var chosen: bool = option.get("chosen", false)
			var label := "[b]► %s (votre choix)[/b]" % esc(option["label"]) if chosen else "○ %s" % esc(option["label"])
			out.append("%s\n    [color=%s]%s[/color]" % [label, GREY, esc(option["rationale"])])
	var events: Array = report.get("events", [])
	if not events.is_empty():
		out.append("\n[font_size=24][b]Aléas survenus[/b][/font_size]")
		for event: Dictionary in events:
			out.append("• [b]%s[/b] : %s" % [esc(event["title"]), esc(event["description"])])
	out.append("\n[font_size=24][b]À retenir[/b][/font_size]")
	for takeaway in report.get("key_takeaways", []):
		out.append("• %s" % esc(takeaway))
	out.append("\n[font_size=24][b]Questions de débrief[/b][/font_size]")
	for question: Dictionary in report.get("questions", []):
		out.append("[b]%s[/b]" % esc(question["question"]))
		for point in question.get("expected_points", []):
			out.append("    [color=%s]– %s[/color]" % [GREY, esc(point)])
	out.append(sources_bbcode(report.get("sources", [])))
	return "\n".join(out)


static func sources_bbcode(sources: Array) -> String:
	if sources.is_empty():
		return "\n[color=%s]Aucune source du corpus : contenu à faire valider par un expert.[/color]" % ORANGE
	var out := PackedStringArray(["\n[font_size=24][b]Sources[/b][/font_size]"])
	for source: Dictionary in sources:
		out.append("[lb]%s] %s" % [esc(source["id"]).to_upper(), esc(source["citation"])])
	return "\n".join(out)


## Relecture d'un business game par le formateur : contenu, contrôles, réparations, coût.
static func game_bbcode(game: Dictionary) -> String:
	var out := PackedStringArray()
	var review: Dictionary = game.get("review", {})
	var job: Variant = game.get("job")
	if job is Dictionary and job.get("error"):
		out.append("[color=#%s][b]Échec :[/b] %s[/color]" % [Ui.ERROR.to_html(false), esc(job["error"])])
	for warning in review.get("warnings", []):
		out.append("[color=%s]À vérifier : %s[/color]" % [ORANGE, esc(warning)])
	for repair in review.get("repairs", []):
		out.append("[color=%s]Corrigé automatiquement : %s[/color]" % [GREY, esc(repair)])
	var spec: Variant = game.get("spec")
	if not spec is Dictionary:
		return "\n".join(out) if not out.is_empty() else "Spec pas encore disponible."
	var meta: Dictionary = spec["meta"]
	out.append("[font_size=26][b]%s[/b][/font_size]\n%s" % [esc(meta["title"]), esc(meta["pitch"])])
	var company: Dictionary = spec["context"]["company"]
	out.append("[b]Entreprise :[/b] %s (%s, %s). %s" % [esc(company["name"]), esc(company["sector"]), company["size"], esc(company["description"])])
	out.append("[b]Situation :[/b] %s" % esc(spec["context"]["situation"]))
	out.append("\n[b]Objectifs pédagogiques[/b]")
	for objective: Dictionary in spec["learning_objectives"]:
		out.append("• %s [color=%s](%s)[/color]" % [esc(objective["statement"]), GREY, objective["bloom_level"]])
	out.append("\n[b]Rôles[/b]")
	for role: Dictionary in spec["roles"]:
		out.append("• %s : %s" % [esc(role["title"]), esc(role["mission"])])
	out.append("\n[b]KPI[/b]")
	for kpi: Dictionary in spec["kpis"]:
		var formula := " = %s" % esc(kpi["formula"]) if kpi.get("formula") else ""
		out.append("• %s (%s) : %s → %s%s. %s" % [esc(kpi["name"]), esc(kpi["unit"]), number(kpi["initial"]), number(kpi["target"]), formula, esc(kpi["definition"])])
	for phase: Dictionary in spec["phases"]:
		out.append("\n[b]%s[/b] (%d min) : %s" % [esc(phase["title"]), int(phase["duration_minutes"]), esc(phase["goal"])])
		for decision: Dictionary in phase["decisions"]:
			out.append("  [b]Décision (%s)[/b] : %s" % [esc(role_title(spec, decision["role"])), esc(decision["prompt"])])
			for option: Dictionary in decision["options"]:
				out.append("    ○ %s [color=%s]%s[/color]" % [esc(option["label"]), GREY, _effects_text(option.get("effects", []))])
				out.append("       [color=%s]%s[/color]" % [GREY, esc(option.get("rationale", ""))])
		for event: Dictionary in phase["events"]:
			out.append("  [b]Aléa[/b] : %s. %s [color=%s]%s[/color]" % [esc(event["title"]), esc(event["description"]), GREY, _effects_text(event["effects"])])
	out.append("\n[b]PNJ[/b]")
	for npc: Dictionary in spec["npcs"]:
		out.append("• %s, %s : %s" % [esc(npc["name"]), esc(npc["job"]), esc(", ".join(npc["expertise"]))])
	out.append(sources_bbcode(spec.get("sources", [])))
	return "\n".join(out)


static func _effects_text(effects: Array) -> String:
	var parts := PackedStringArray()
	for effect: Dictionary in effects:
		var sign: String = {"add": "+", "multiply": "×", "set": "="}.get(effect["operation"], "?")
		var value := number(effect["value"])
		if effect["operation"] == "add" and float(effect["value"]) < 0:
			sign = ""
		var delay := int(effect.get("delay_phases", 0))
		parts.append("%s %s%s%s" % [effect["kpi"], sign, value, " (+%d phase)" % delay if delay > 0 else ""])
	return "[lb]" + ", ".join(parts) + "]" if not parts.is_empty() else ""
