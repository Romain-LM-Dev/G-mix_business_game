class_name GameText
extends RefCounted
## Mise en forme des données de jeu renvoyées par l'API (semaine, indicateurs, postes, tableau de bord, débrief,
## spec) en BBCode pour RichTextLabel. Tout texte venant de l'API ou de l'IA passe par esc() : un « [ » ne doit
## jamais être lu comme une balise.

const GREEN := UiTokens.OK_HEX
const ORANGE := UiTokens.WARN_HEX
const GREY := UiTokens.MUTED_HEX
## Indicateurs de l'état public : [id, nom, unité, clé de l'objectif dans targets ("" : aucun), plus haut = mieux].
const KPIS := [
	["otif", "OTIF", "%", "otif", true],
	["service", "Taux de service", "%", "", true],
	["trs", "TRS moyen", "%", "trs", true],
	["stockouts", "Références en rupture", "", "stockouts", false],
	["coverage_days", "Couverture du stock", "j", "", true],
	["stock_value", "Stock immobilisé", "€", "", false],
	["cash", "Trésorerie", "€", "cash_final", true],
	["margin", "Résultat de la semaine", "€", "", true],
]
const SCREEN_KPIS := ["otif", "trs", "stockouts", "coverage_days", "cash"]
const LEVELS := {"aucune": "aucun entretien", "preventive": "entretien préventif", "renforcee": "entretien renforcé"}
const MODES := {"economique": "groupage", "standard": "messagerie", "express": "express"}
const PRICES := {"0.9": "promotion (-10 %)", "1.0": "prix catalogue", "1.1": "prix +10 %"}
const LINE_STATES := {"ok": "en marche", "alerte": "sous l'objectif de TRS", "arret": "en panne"}
## États d'une machine d'usine (MachineState, ADR 0007 annexe §1).
const MACHINE_STATES := {
	"arret": "à l'arrêt", "marche": "en marche", "pause": "en pause", "reglage": "en réglage", "panne": "en panne",
	"attente_matiere": "attend de la matière", "sortie_pleine": "sortie pleine",
}
const COSTS := {
	"achats": "achats", "production": "production", "maintenance": "maintenance", "controle": "contrôle",
	"transport": "transport", "possession": "possession du stock", "interets": "intérêts",
}


static func esc(text: Variant) -> String:
	return str(text).replace("[", "[lb]")


static func number(value: Variant) -> String:
	if value == null:
		return "-"
	var f := float(value)
	if absf(f) >= 1000.0 or is_equal_approx(f, roundf(f)):
		return grouped(roundi(f))
	return ("%.1f" % f).replace(".", ",")


## 12345 -> « 12 345 » (espaces insécables : un nombre ne se coupe pas en fin de ligne).
static func grouped(value: int) -> String:
	var digits := str(absi(value))
	var out := ""
	while digits.length() > 3:
		out = "\u00a0" + digits.right(3) + out
		digits = digits.left(digits.length() - 3)
	return ("-" if value < 0 else "") + digits + out


static func money(value: Variant) -> String:
	return "-" if value == null else "%s\u00a0€" % grouped(roundi(float(value)))


static func price(value: Variant) -> String:
	return ("%.2f €" % float(value)).replace(".", ",")


static func kpi_value(unit: String, value: Variant) -> String:
	if value == null:
		return "-"
	if unit == "€":
		return money(value)
	return ("%s %s" % [number(value), unit]).strip_edges()


## true / false selon l'objectif, null s'il n'y en a pas (ou pas encore de valeur).
static func kpi_met(kpi: Array, value: Variant, targets: Dictionary) -> Variant:
	if kpi[3] == "" or value == null or not targets.has(kpi[3]):
		return null
	var target := float(targets[kpi[3]])
	return float(value) >= target if kpi[4] else float(value) <= target


static func kpis_bbcode(state: Dictionary) -> String:
	var values: Dictionary = state.get("kpis", {})
	var targets: Dictionary = state.get("targets", {})
	var lines := PackedStringArray()
	for kpi: Array in KPIS:
		var value: Variant = values.get(kpi[0])
		var met: Variant = kpi_met(kpi, value, targets)
		var dot := "" if met == null else "[color=%s]●[/color] " % (GREEN if met else ORANGE)
		var goal := ""
		if kpi[3] != "" and targets.has(kpi[3]):
			var when := " en fin de partie" if kpi[3] == "cash_final" else ""
			goal = "  [color=%s]objectif%s %s %s[/color]" % [GREY, when, "≥" if kpi[4] else "≤", kpi_value(kpi[2], targets[kpi[3]])]
		lines.append("%s%s : [b]%s[/b]%s" % [dot, kpi[1], kpi_value(kpi[2], value), goal])
	return "\n".join(lines)


## Lignes {name, value, unit} de l'écran des indicateurs de l'atelier.
static func kpi_rows(state: Dictionary) -> Array:
	var values: Dictionary = state.get("kpis", {})
	var rows := []
	for kpi: Array in KPIS:
		if kpi[0] in SCREEN_KPIS:
			rows.append({"name": kpi[1], "value": kpi_value(kpi[2], values.get(kpi[0])), "unit": ""})
	return rows


static func week_bbcode(spec: Dictionary, state: Dictionary) -> String:
	var meta: Dictionary = spec.get("meta", {})
	var status: String = state.get("status", "waiting")
	var head := "En attente du lancement par le formateur"
	if status == "running":
		head = "Semaine %d / %d" % [int(state.get("week", 1)), int(state.get("weeks", meta.get("weeks", 1)))]
	elif status == "finished":
		head = "Partie terminée : place au débrief"
	var lines := PackedStringArray(["[b]%s[/b]  ·  %s" % [head, esc(meta.get("company", ""))]])
	var event: Variant = state.get("event")
	if status == "running" and event is Dictionary:
		lines.append("[color=%s]Annoncé cette semaine : %s. %s[/color]" % [ORANGE, esc(event["title"]), esc(event["description"])])
	return "\n".join(lines)


static func role_title(spec: Dictionary, role_id: Variant) -> String:
	for role: Dictionary in spec.get("roles", []):
		if role["id"] == role_id:
			return role["title"]
	return str(role_id) if role_id != null else "aucun rôle"


static func module_title(spec: Dictionary, module_id: Variant) -> String:
	for module: Dictionary in spec.get("modules", []):
		if module["id"] == module_id:
			return module["title"]
	return str(module_id)


# --- postes de l'atelier --------------------------------------------------------------------------------------


## Informations d'un poste (spec.stations) : ce qu'on voit en s'en approchant, avant d'agir.
static func station_bbcode(spec: Dictionary, state: Dictionary, station: Dictionary) -> String:
	var ref: Variant = station.get("ref")
	var last: Dictionary = state["last"] if state.get("last") is Dictionary else {}
	var settings: Dictionary = state.get("settings", {})
	var out := PackedStringArray()
	match station["kind"]:
		"rack_produit":
			var stock := _by_id(state.get("stocks", []), ref)
			out.append("En stock : [b]%s[/b] · stock de sécurité %s" % [number(stock.get("quantity")), number(stock.get("safety_stock"))])
			out.append("Demande attendue cette semaine : %s · couverture %s semaine(s)" % [number(stock.get("forecast")), number(stock.get("coverage_weeks"))])
			out.append("Prix de vente : %s (%s)" % [price(stock.get("price", 0)), PRICES.get(settings.get("price", {}).get(ref), "")])
			var sales: Dictionary = last.get("sales", {}).get(ref, {})
			if not sales.is_empty():
				out.append("Semaine dernière : %s vendus sur %s demandés, %s perdus, %s retours" % [number(sales["served"]), number(sales["demand"]), number(sales["lost"]), number(sales["returns"])])
		"rack_composant":
			var part := _by_id(state.get("components", []), ref)
			out.append("En stock : [b]%s[/b] · en commande : %s · consommation : %s par semaine" % [number(part.get("quantity")), number(part.get("pending")), number(part.get("usage"))])
			out.append("Point de commande : %s (consommation pendant le délai standard + stock de sécurité)" % number(part.get("reorder_point")))
			if int(part.get("quantity", 0)) + int(part.get("pending", 0)) < int(part.get("reorder_point", 0)):
				out.append("[color=%s]Sous le point de commande : il faut commander.[/color]" % ORANGE)
			out.append_array(_orders(state, part.get("name", "")))
		"ligne":
			var line := _by_id(state.get("lines", []), ref)
			var color := GREEN if line.get("status") == "ok" else ORANGE
			out.append("TRS : [b]%s %%[/b] · [color=%s]%s[/color]" % [number(line.get("trs")), color, LINE_STATES.get(line.get("status"), "")])
			out.append("Capacité : %s par semaine à 100 %%, %s au TRS actuel" % [number(line.get("capacity")), number(line.get("real_capacity"))])
			out.append("Plan de la semaine : %s · %s" % [number(line.get("plan")), LEVELS.get(line.get("maintenance"), "")])
			var report: Dictionary = last.get("lines", {}).get(ref, {})
			if not report.is_empty():
				var starved := " : composants manquants" if report["starved"] else ""
				out.append("Semaine dernière : %s produits pour %s prévus%s" % [number(report["produced"]), number(report["planned"]), starved])
		"poste_qualite":
			out.append("Contrôle avant expédition : [b]%s %% des lots[/b]" % settings.get("control", "-"))
			out.append("Taux de défaut des lignes : %s %%" % number(float(spec.get("economy", {}).get("defect_rate", 0)) * 100))
			if not last.is_empty():
				var scrapped := 0
				for report: Dictionary in last.get("lines", {}).values():
					scrapped += int(report["scrapped"])
				out.append("Semaine dernière : %s défauts arrêtés au contrôle, %s retours des magasins" % [number(scrapped), number(last["totals"]["returns"])])
		"bureau":
			var overdraft: Variant = settings.get("overdraft")
			var limit := "aucune limite (module finance non retenu)" if overdraft == null else money(int(overdraft))
			out.append("Trésorerie : [b]%s[/b] · découvert autorisé : %s" % [money(state.get("cash")), limit])
			for stock: Dictionary in state.get("stocks", []):
				out.append("%s : %s (%s)" % [esc(stock["name"]), price(stock["price"]), PRICES.get(settings.get("price", {}).get(stock["id"]), "")])
			if not last.is_empty():
				out.append("Semaine dernière : ventes %s, résultat %s" % [money(last["revenue"]), money(last["kpis"]["margin"])])
				var costs := PackedStringArray()
				for key: String in last["costs"]:
					costs.append("%s %s" % [COSTS.get(key, key), money(last["costs"][key])])
				out.append("[color=%s]Coûts : %s[/color]" % [GREY, ", ".join(costs)])
		"quai_reception":
			out.append_array(_orders(state, ""))
			if not last.is_empty():
				out.append("Semaine dernière : %d livraison(s) reçue(s), %d en retard" % [last["deliveries"].size(), last["delayed"].size()])
		"quai_expedition":
			var mode: String = settings.get("transport", "standard")
			var rate := float(spec.get("economy", {}).get("transport", {}).get(mode, {}).get("on_time", 0)) * 100
			out.append("Livraisons en [b]%s[/b] : %s %% à l'heure" % [MODES.get(mode, mode), number(rate)])
			if not last.is_empty():
				var totals: Dictionary = last["totals"]
				out.append("Semaine dernière : %s livrés sur %s demandés, %s perdus, OTIF %s %%" % [number(totals["served"]), number(totals["demand"]), number(totals["lost"]), number(last["kpis"]["otif"])])
		"ecran_kpi":
			out.append(kpis_bbcode(state))
			out.append(history_bbcode(state.get("history", [])))
		"machine":  # usine : la machine, d'après state.factory.machines (le panneau du pack viendra le compléter)
			var machine := GmixFactoryState.machine(state, str(ref))
			if not machine.is_empty():
				var code := str(machine.get("state", ""))
				out.append("%s : [b]%s[/b]%s" % [esc(machine.get("name", "?")), MACHINE_STATES.get(code, esc(code)), "  (goulot de la ligne)" if machine.get("bottleneck", false) else ""])
				out.append("Table d'attente en sortie : %s / %s · disponibilité mesurée %s %% · %s panne(s) au dernier tour" % [number(machine.get("buffer")), number(machine.get("buffer_max")), number(machine.get("availability")), number(machine.get("failures"))])
	return "\n".join(out)


static func _orders(state: Dictionary, component_name: String) -> PackedStringArray:
	var out := PackedStringArray()
	for order: Dictionary in state.get("pending", []):
		if component_name.is_empty() or order["component"] == component_name:
			var late := "  [color=%s]%d semaine(s) de retard[/color]" % [ORANGE, int(order["delays"])] if int(order["delays"]) > 0 else ""
			out.append("• %s %s de %s, arrivée semaine %d%s" % [number(order["quantity"]), esc(order["component"]), esc(order["supplier"]), int(order["arrival_week"]), late])
	if out.is_empty():
		out.append("[color=%s]Aucune commande en cours.[/color]" % GREY)
	return out


static func _by_id(items: Array, id: Variant) -> Dictionary:
	for item: Dictionary in items:
		if item.get("id") == id:
			return item
	return {}


# --- tableau de bord, débrief ---------------------------------------------------------------------------------


static func history_bbcode(history: Array) -> String:
	if history.is_empty():
		return "[color=%s]Aucune semaine jouée.[/color]" % GREY
	var out := PackedStringArray(["[b]Semaines jouées[/b]"])
	for row: Dictionary in history:
		var event := "  [color=%s]%s[/color]" % [ORANGE, esc(row["event"])] if row.get("event") else ""
		out.append(
			"S%d : OTIF %s %% · TRS %s %% · ruptures %s · trésorerie %s · résultat %s%s"
			% [int(row["week"]), number(row["otif"]), number(row["trs"]), number(row["stockouts"]), money(row["cash"]), money(row["margin"]), event]
		)
	return "\n".join(out)


## Tableau de bord d'une usine (`state.factory`, ADR 0007 annexe §2) : lignes, machines, stocks. Provisoire : les panneaux
## déclarés par le pack (`spec.panels`) le remplaceront ; toutes les lectures sont tolérantes aux clés absentes.
static func factory_dashboard_bbcode(spec: Dictionary, state: Dictionary) -> String:
	var factory: Dictionary = state.get("factory", {})
	var out := PackedStringArray([week_bbcode(spec, state), "", kpis_bbcode(state), "", "[b]Lignes[/b]"])
	for line: Dictionary in factory.get("lines", []):
		out.append("• %s : goulot %s, %s bons / h attendus pour %s mesurés, encours %s" % [esc(line.get("name", "?")), esc(line.get("bottleneck_id", "-")), number(line.get("expected_h")), number(line.get("real_h")), number(line.get("wip"))])
	out.append("\n[b]Machines[/b]")
	for machine: Dictionary in factory.get("machines", []):
		var state_code := str(machine.get("state", ""))
		var color := GREEN if state_code == "marche" else (ORANGE if state_code in ["panne", "sortie_pleine", "attente_matiere"] else GREY)
		out.append("• %s : [color=%s]%s[/color], table %s / %s, %s pannes" % [esc(machine.get("name", "?")), color, MACHINE_STATES.get(state_code, esc(state_code)), number(machine.get("buffer")), number(machine.get("buffer_max")), number(machine.get("failures"))])
	var stocks: Dictionary = factory.get("stocks", {})
	out.append("\n[b]Stocks[/b]")
	for entry: Dictionary in stocks.get("mp", []):
		out.append("• %s : %s palettes sur %s places, %s en commande" % [esc(entry.get("name", "?")), number(entry.get("pallets")), number(entry.get("capacity_pallets")), number(entry.get("pending"))])
	var finished: Variant = stocks.get("pf")
	if finished is Dictionary:
		out.append("• Produits finis : %s palettes sur %s places" % [number(finished.get("pallets")), number(finished.get("capacity_pallets"))])
	out.append("\n" + history_bbcode(state.get("history", [])))
	return "\n".join(out)


## Nom de l'endroit où se joue la partie, pour les libellés (« Observer l'atelier 3D », « Entrer dans l'usine 3D »).
static func world_noun(spec: Dictionary) -> String:
	return "l'usine" if spec.get("world", {}).get("template", "atelier") == "usine" else "l'atelier"


static func dashboard_bbcode(spec: Dictionary, state: Dictionary) -> String:
	if spec.get("factory") is Dictionary:
		return factory_dashboard_bbcode(spec, state)
	var out := PackedStringArray([week_bbcode(spec, state), "", kpis_bbcode(state), "", "[b]Produits finis[/b]"])
	for stock: Dictionary in state.get("stocks", []):
		out.append("• %s : %s en stock, %s attendus, couverture %s semaine(s)" % [esc(stock["name"]), number(stock["quantity"]), number(stock["forecast"]), number(stock["coverage_weeks"])])
	out.append("\n[b]Composants[/b]")
	for part: Dictionary in state.get("components", []):
		var alert := "  [color=%s]sous le point de commande[/color]" % ORANGE if int(part["quantity"]) + int(part["pending"]) < int(part["reorder_point"]) else ""
		out.append("• %s : %s en stock, %s en commande, point de commande %s%s" % [esc(part["name"]), number(part["quantity"]), number(part["pending"]), number(part["reorder_point"]), alert])
	out.append("\n[b]Lignes[/b]")
	for line: Dictionary in state.get("lines", []):
		out.append("• %s : TRS %s %%, %s, plan %s / capacité réelle %s" % [esc(line["name"]), number(line["trs"]), LINE_STATES.get(line["status"], ""), number(line["plan"]), number(line["real_capacity"])])
	out.append("\n[b]Commandes en cours[/b]")
	out.append_array(_orders(state, ""))
	out.append("\n" + history_bbcode(state.get("history", [])))
	var log: Array = state.get("log", [])
	if not log.is_empty():
		out.append("\n[b]Dernières actions[/b]")
		for entry: Dictionary in log.slice(-8):
			out.append("[color=%s]S%d · %s :[/color] %s" % [GREY, int(entry["week"]), esc(entry.get("name", "?")), esc(entry["summary"])])
	return "\n".join(out)


static func debrief_bbcode(report: Dictionary) -> String:
	var out := PackedStringArray(["[font_size=24][b]Objectifs[/b][/font_size]"])
	for kpi: Dictionary in report.get("kpis", []):
		var met: Variant = kpi.get("met")
		var mark := "[color=%s]atteint[/color]" % GREEN if met == true else "[color=%s]non atteint[/color]" % ORANGE
		var unit: String = kpi.get("unit", "")
		out.append("• %s : [b]%s[/b] (objectif %s) %s" % [esc(kpi["name"]), kpi_value(unit, kpi.get("final")), kpi_value(unit, kpi["target"]), mark])
	out.append("\n[font_size=24][b]À retenir[/b][/font_size]")
	for lesson in report.get("lessons", []):
		out.append("• %s" % esc(lesson))
	var events: Array = report.get("events", [])
	if not events.is_empty():
		out.append("\n[font_size=24][b]Aléas survenus[/b][/font_size]")
		for event: Dictionary in events:
			out.append("• Semaine %d : %s" % [int(event["week"]), esc(event["title"])])
	out.append("\n" + history_bbcode(report.get("history", [])))
	var notions: Array = report.get("notions", [])
	if not notions.is_empty():
		out.append("\n[font_size=24][b]Notions et sources[/b][/font_size]")
		for notion: Dictionary in notions:
			out.append("[b]%s[/b] : %s\n    [color=%s]%s[/color]" % [esc(notion["title"]), esc(notion["text"]), GREY, esc(notion["citation"])])
	var log: Array = report.get("log", [])
	if not log.is_empty():
		out.append("\n[font_size=24][b]Décisions de l'équipe[/b][/font_size]")
		for entry: Dictionary in log:
			out.append("[color=%s]S%d · %s :[/color] %s" % [GREY, int(entry["week"]), esc(entry.get("name", "?")), esc(entry["summary"])])
	return "\n".join(out)


## Relecture d'une usine : lignes, journée, départements, et d'où vient chaque valeur (`spec.provenance` : sourcée, calibrée
## pour la jouabilité, ou exemple non sourcé) : le formateur voit ce qui n'est pas vérifié (exigence n° 1).
static func _factory_review(spec: Dictionary) -> PackedStringArray:
	var factory: Dictionary = spec["factory"]
	var per_line := {}
	for machine: Dictionary in factory["machines"]:
		per_line[machine["line_id"]] = int(per_line.get(machine["line_id"], 0)) + 1
	var clock: Dictionary = factory.get("clock", {})
	var out := PackedStringArray(["\n[b]Usine[/b]"])
	out.append("• %d ligne(s) de machines en série (%s machines au total), un tour = %d jour(s) de %d minutes, lot de %d" % [per_line.size(), number(factory["machines"].size()), int(clock.get("days_per_turn", 5)), int(clock.get("minutes_per_day", 480)), int(factory["lot_size"])])
	var places := PackedStringArray()
	for department: Dictionary in spec.get("departments", []):
		places.append("%s%s" % [esc(department["label"]), " (extérieur)" if department.get("external", false) else ""])
	if not places.is_empty():
		out.append("• Lieux : %s" % ", ".join(places))
	var counts := {"source": 0, "calibre": 0, "exemple": 0}
	var unverified := PackedStringArray()
	for key: String in spec.get("provenance", {}):
		var status := str(spec["provenance"][key].get("status"))
		counts[status] = int(counts.get(status, 0)) + 1
		if status == "exemple":
			unverified.append(key)
	out.append("• Valeurs : %d sourcée(s), %d calibrée(s) pour la jouabilité, %d d'exemple sans source" % [counts["source"], counts["calibre"], counts["exemple"]])
	if not unverified.is_empty():
		out.append("    [color=%s]D'exemple, à ne pas présenter comme des faits : %s.[/color]" % [GREY, esc(", ".join(unverified))])
	return out


## Relecture d'un business game par le formateur : contexte, modules et rôles, agents, chaîne logistique,
## partie de référence jouée par le pilote automatique, notions sourcées.
static func game_bbcode(game: Dictionary) -> String:
	var spec: Variant = game.get("spec")
	if not spec is Dictionary:
		return "Spec pas encore disponible."
	var meta: Dictionary = spec["meta"]
	var out := PackedStringArray(["[font_size=26][b]%s[/b][/font_size]\n%s" % [esc(meta["title"]), esc(meta["pitch"])]])
	out.append("[color=%s]%s · %d semaines · %d à %d joueurs · graine %d[/color]" % [GREY, esc(meta["difficulty_label"]), int(meta["weeks"]), int(meta["players"]["min"]), int(meta["players"]["max"]), int(spec["seed"])])
	var autopilot: Dictionary = game.get("review", {}).get("autopilot", {})
	if not autopilot.is_empty():
		out.append(
			"\n[b]Partie de référence (pilote automatique)[/b] : OTIF moyen %s %%, TRS moyen %s %%, %d semaine(s) de rupture, trésorerie finale %s"
			% [number(autopilot["otif_mean"]), number(autopilot["trs_mean"]), int(autopilot["stockout_weeks"]), money(autopilot["final_cash"])]
		)
	var targets: Dictionary = spec["targets"]
	out.append("[b]Objectifs[/b] : OTIF ≥ %s %%, TRS ≥ %s %%, aucune rupture en fin de partie, trésorerie finale ≥ %s (départ %s)" % [number(targets["otif"]), number(targets["trs"]), money(targets["cash_final"]), money(spec["economy"]["initial_cash"])])
	out.append("\n[b]Modules et rôles[/b]")
	for module: Dictionary in spec["modules"]:
		var actions := PackedStringArray()
		for action: Dictionary in module["actions"]:
			actions.append(action["label"])
		out.append("• [b]%s[/b] (%s) : %s\n    [color=%s]Actions : %s. Sans joueur : %s.[/color]" % [esc(module["title"]), esc(role_title(spec, module["role_id"])), esc(module["description"]), GREY, esc(", ".join(actions)), esc(module["autopilot"])])
	out.append("\n[b]Agents[/b]")
	for agent: Dictionary in spec["agents"]:
		out.append("• [b]%s[/b], %s · %s (%s)\n    [color=%s]%s[/color]" % [esc(agent["name"]), esc(agent["job"]), esc(agent["personality"]["label"]), esc(agent["personality"]["traits"]), GREY, esc(", ".join(agent["tasks"]))])
	out.append("\n[b]Produits, lignes et fournisseurs[/b]")
	for product: Dictionary in spec["products"]:
		var line := _by_id(spec["lines"], product["line_id"])
		out.append("• [b]%s[/b] : %s, demande %s / semaine, %s (capacité %s)" % [esc(product["name"]), price(product["price"]), number(product["demand"]), esc(line.get("name", "")), number(line.get("capacity"))])
		for offer: Dictionary in spec["offers"]:
			if offer["component_id"] == product["component_id"]:
				out.append("    [color=%s]%s[/color]" % [GREY, esc(offer["label"])])
	if spec.get("factory") is Dictionary:
		out.append_array(_factory_review(spec))
	out.append("\n[b]Aléas possibles[/b] (probabilité %s %% par semaine)" % number(float(spec["economy"]["events_probability"]) * 100))
	for event: Dictionary in spec["events"]:
		out.append("• %s : %s" % [esc(event["title"]), esc(event["description"])])
	out.append("\n[b]Notions et sources[/b]")
	for notion: Dictionary in spec["notions"]:
		out.append("• %s [color=%s](%s)[/color]" % [esc(notion["title"]), GREY, esc(notion["citation"])])
	return "\n".join(out)
