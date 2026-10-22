"""Génération d'un business game par petites étapes contraintes (docs/ai-runtime.md, « Pipeline de génération »).

0 contrôle de la demande (décision tev1, aucun texte généré) · 1 plan ancré sur le RAG (game.outline) ·
2 PNJ (game.npcs, zones du gabarit en enum) · 3 détail de chaque phase (game.phase_detail : rôles, KPI, PNJ et
sources en enum) · 4 assets par zone (pgvector puis game.asset_mapping en enum) · 5 débrief (game.debrief) ·
6 assemblage, réparations déterministes, schéma complet puis gmix.game.coherence.
Chaque réparation est listée dans le résultat : le formateur voit ce que le code a corrigé.
"""

import copy
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gmix.assets_catalog import load_assets_catalog
from gmix.db.models import KnowledgeChunk, KnowledgeDocument
from gmix.domains import DomainSpec
from gmix.game.assets import candidate_assets, restrict_schema_to
from gmix.game.coherence import check_spec, evaluate_formula
from gmix.game.world import DEFAULT_TEMPLATE, template_zones
from gmix.llm import schemas
from gmix.llm.ollama import ChatResult
from gmix.llm.prompts import load_prompt, load_questions, load_thresholds
from gmix.llm.service import InvalidOutput, LLMService
from gmix.rag.retrieval import build_context, search

log = logging.getLogger("gmix.generation")

Progress = Callable[[str, int], Awaitable[None]]
DEBRIEF_MINUTES = 10
# Part de l'écart entre valeur initiale et cible d'un KPI déplacée par un effet : quelques bons choix
# « moyens » suffisent à atteindre la cible, une seule option ne règle jamais tout.
STRENGTH = {"faible": 0.15, "moyenne": 0.3, "forte": 0.5}
SOURCE_LINE = re.compile(r"^> Source : (.+)$", re.MULTILINE)  # en-tête des fiches du corpus (knowledge/*/…md)


class GenerationRefused(Exception):
    """Demande refusée avant toute génération ; le message s'adresse au formateur."""


class GenerationFailed(Exception):
    """Étape en échec après ses essais ; le message s'adresse au formateur."""


@dataclass(slots=True)
class GameRequest:
    domain: DomainSpec
    brief: str
    level: str = "intermediaire"
    duration_minutes: int = 90
    players_min: int = 2
    players_max: int = 6
    competencies: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GenerationResult:
    spec: dict[str, Any]
    usage: dict[str, dict[str, Any]]
    warnings: list[str]
    repairs: list[str]


class Generator:
    def __init__(self, llm: LLMService, sessions: async_sessionmaker[AsyncSession], progress: Progress) -> None:
        self.llm = llm
        self.sessions = sessions
        self.progress = progress
        self.usage: dict[str, dict[str, Any]] = {}
        self.repairs: list[str] = []
        self.notes: list[str] = []  # avertissements propres à la génération (revue qualité, répétitions)
        self._sources: dict[str, str] = {}  # knowledge_documents.id -> id de source (s1…) : une source par document
        self._source_chunks: dict[str, int] = {}  # premier passage retenu de chaque document
        self._domain = ""

    async def run(self, req: GameRequest) -> GenerationResult:
        self._domain = req.domain.slug
        await self.progress("brief_check", 2)
        await self._check_brief(req)
        await self.progress("outline", 8)
        outline = await self._outline(req)
        zones = template_zones(DEFAULT_TEMPLATE)
        await self.progress("npcs", 30)
        npcs = await self._npcs(outline, req, zones)
        phases: list[dict[str, Any]] = []
        for index, phase in enumerate(outline["phases"]):
            await self.progress(f"phase_{index + 1}", 38 + 40 * index // len(outline["phases"]))
            phases.append(phase | await self._phase_detail(outline, phase, phases, npcs))
        await self.progress("assets", 80)
        world_zones = await self._world(outline, npcs, zones)
        await self.progress("debrief", 88)
        debrief = await self._debrief(outline, phases)
        await self.progress("assemble", 90)
        spec = {
            "spec_version": 1,
            **{key: outline[key] for key in ("meta", "learning_objectives", "context", "roles", "kpis")},
            "phases": phases,
            "npcs": npcs,
            "world": {"template": DEFAULT_TEMPLATE, "zones": world_zones},
            "debrief": debrief,
            "sources": await self._source_list(),
        }
        self._repair_references(spec)
        if errors := schemas.validation_errors(schemas.resolve("business_game"), spec):
            raise GenerationFailed("Spec assemblée invalide : " + "; ".join(errors[:5]))
        await self.progress("review", 94)
        await self._review(spec)
        warnings = check_spec(spec) + self.notes
        if not spec["sources"]:
            warnings.insert(
                0, "Aucun extrait du corpus pour ce domaine : contenu non sourcé, relecture experte indispensable"
            )
        return GenerationResult(spec=spec, usage=self.usage, warnings=warnings, repairs=self.repairs)

    # --- étapes ------------------------------------------------------------------------------------------

    async def _check_brief(self, req: GameRequest) -> None:
        state = f"Domaine : {req.domain.name}\nDemande : {req.brief}"
        verdict = await self.llm.decide("game.brief_check", state, load_questions("game.brief_check"))
        answers = verdict.get("answers") or {}
        scores = {q: float((answers.get(q) or {}).get("noul") or 0) for q in ("usable", "in_domain", "injection")}
        self.usage["brief_check"] = {"model": verdict.get("model"), "scores": scores, **(verdict.get("usage") or {})}
        limits = load_thresholds("game.brief_check")
        if scores["injection"] >= limits["injection"]:
            raise GenerationRefused(
                "La demande contient des consignes sans rapport avec un business game : reformulez-la."
            )
        if scores["usable"] < limits["usable"]:
            raise GenerationRefused(
                "Demande trop vague : décrivez l'entreprise, le public et ce que les joueurs doivent apprendre."
            )
        if scores["in_domain"] < limits["in_domain"]:
            raise GenerationRefused(
                f"La demande ne semble pas relever du domaine « {req.domain.name} » : changez de domaine ou reformulez."
            )

    async def _outline(self, req: GameRequest) -> dict[str, Any]:
        domain = req.domain
        competencies = "; ".join(req.competencies or domain.competencies)
        messages = load_prompt("game.outline").render(
            domain_name=domain.name,
            domain_competencies=competencies,
            domain_kpis=", ".join(domain.kpis),
            domain_roles=", ".join(domain.roles),
            level=req.level,
            duration_minutes=req.duration_minutes,
            players_min=req.players_min,
            players_max=req.players_max,
            brief=req.brief,
            rag_context=await self._rag("game.outline", f"{req.brief}\n{competencies}"),
        )
        schema = _stage_schema("outline")
        defs = schema["$defs"]
        defs["learning_objectives"]["maxItems"] = defs["roles"]["maxItems"] = schema["properties"]["phases"][
            "maxItems"
        ] = 4
        defs["kpis"]["maxItems"] = 6
        defs["context"]["properties"]["constraints"]["maxItems"] = 4
        outline = await self._json("outline", "game.outline", messages, schema)
        self._repair_outline(outline, req)
        return outline

    async def _npcs(
        self, outline: dict[str, Any], req: GameRequest, zones: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        schema = _stage_schema("npcs_block")
        schema["properties"]["npcs"]["maxItems"] = 4
        npc = schema["$defs"]["npc"]["properties"]
        npc["zone"] = {"enum": list(zones)}
        npc["expertise"]["maxItems"] = npc["dialogue_goals"]["maxItems"] = 3
        messages = load_prompt("game.npcs").render(
            company=_company(outline),
            situation=outline["context"]["situation"],
            roles=_roles(outline),
            kpis=", ".join(k["name"] for k in outline["kpis"]),
            phases="; ".join(f"{p['title']} : {p['goal']}" for p in outline["phases"]),
            competencies="; ".join(req.competencies or req.domain.competencies),
            zones="\n".join(f"- {z['id']} : {z['name']}, {z['purpose']}" for z in zones.values()),
        )
        return (await self._json("npcs", "game.npcs", messages, schema))["npcs"]

    async def _phase_detail(
        self, outline: dict[str, Any], phase: dict[str, Any], done: list[dict[str, Any]], npcs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        context = await self._rag("game.phase_detail", f"{phase['title']} : {phase['goal']}")
        schema = _stage_schema("phase_detail")
        schema["properties"]["decisions"] |= {"minItems": 1, "maxItems": 2}
        schema["properties"]["events"]["maxItems"] = 2
        defs = schema["$defs"]
        defs["decision"]["properties"]["options"]["maxItems"] = 3
        defs["option"]["properties"]["effects"]["maxItems"] = 3
        defs["event"]["properties"]["effects"]["maxItems"] = 2
        # Tant que des rôles n'ont rien décidé, seuls ces rôles sont proposés : chaque joueur aura un choix
        # (mesuré : la consigne seule laissait deux rôles sur quatre sans aucune décision).
        decided = {d["role"] for p in done for d in p["decisions"]}
        idle = [r["id"] for r in outline["roles"] if r["id"] not in decided]
        defs["decision"]["properties"]["role"] = {"enum": idle or [r["id"] for r in outline["roles"]]}
        defs["decision"]["properties"]["advisor_npc"] = {"enum": [n["id"] for n in npcs]}
        # Le modèle choisit un sens et une ampleur, le code calcule le montant (_effect) : mesuré, qwen2.5:7b
        # inversait souvent le signe (« add -2 » sur un KPI où « plus bas = mieux ») et inventait des montants.
        defs["effect"] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["kpi", "sens", "ampleur"],
            "properties": {
                "kpi": {"enum": [k["id"] for k in outline["kpis"] if not k.get("formula")]},
                "sens": {"enum": ["hausse", "baisse"]},
                "ampleur": {"enum": list(STRENGTH)},
                "delay_phases": {"type": "integer", "minimum": 0, "maximum": 2},
            },
        }
        if self._sources:
            defs["option"]["properties"]["source_refs"]["items"] = {"enum": list(self._sources.values())}
        else:
            del defs["option"]["properties"]["source_refs"]
        # Seulement les énoncés : avec les libellés d'options, le modèle les recopiait d'une phase à l'autre.
        previous = [d["prompt"] for p in done for d in p["decisions"]]
        played = [_decision_words(d) for p in done for d in p["decisions"]]
        messages = load_prompt("game.phase_detail").render(
            company=_company(outline),
            situation=outline["context"]["situation"],
            roles=_roles(outline),
            kpis=_kpi_lines(outline),
            phase=f"{phase['title']} ({phase['duration_minutes']} min) : {phase['goal']}",
            previous="; ".join(previous) or "aucune, c'est la première phase",
            idle_roles=", ".join(idle) or "aucun",
            npcs=", ".join(f"{n['id']} ({n['name']}, {n['job']})" for n in npcs),
            rag_context=context,
        )
        detail = await self._json("phase_detail", "game.phase_detail", messages, schema)
        repeated = [d["prompt"] for d in detail["decisions"] if any(_similar(_decision_words(d), w) for w in played)]
        if repeated:  # la consigne « ne pas répéter » ne suffit pas toujours : un second essai, interdiction explicite
            messages[-1]["content"] += "\nInterdit, déjà joué : " + "; ".join(repeated)
            detail = await self._json("phase_detail", "game.phase_detail", messages, schema)
            if any(_similar(_decision_words(d), w) for d in detail["decisions"] for w in played):
                self.notes.append(f"{phase['id']} : décision proche d'une phase précédente, à varier")
        kpis = {k["id"]: k for k in outline["kpis"]}
        for item in [o for d in detail["decisions"] for o in d["options"]] + detail["events"]:
            item["effects"] = [_effect(impact, kpis[impact["kpi"]]) for impact in item["effects"]]
        return detail

    async def _world(
        self, outline: dict[str, Any], npcs: list[dict[str, Any]], zones: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Zones des PNJ plus le siège (écran des KPI) ; candidats pgvector + choix sûrs du gabarit."""
        catalog = load_assets_catalog().by_id()
        used = list(dict.fromkeys([next(iter(zones)), *(n["zone"] for n in npcs)]))
        sector = outline["context"]["company"]["sector"]
        options: dict[str, list[str]] = {}
        async with self.sessions() as session:
            for zone_id in used:
                zone = zones[zone_id]
                need = f"{zone['purpose']} ({sector})"
                found = await candidate_assets(session, self.llm, need, k=8, categories=zone["categories"])
                options[zone_id] = list(dict.fromkeys(zone["defaults"] + [c.id for c in found]))
        lines = [
            f"- {z} ({zones[z]['name']} : {zones[z]['purpose']}) : "
            + ", ".join(f"{a} ({catalog[a].name})" for a in options[z] if a in catalog)
            for z in used
        ]
        schema = restrict_schema_to(
            schemas.resolve("asset_selection"), sorted({a for ids in options.values() for a in ids})
        )
        schema["properties"]["zones"]["items"]["properties"]["zone_id"] = {"enum": used}
        messages = load_prompt("game.asset_mapping").render(company=_company(outline), zones="\n".join(lines))
        try:
            chosen = {
                z["zone_id"]: z["asset_ids"]
                for z in (await self._json("assets", "game.asset_mapping", messages, schema))["zones"]
            }
        except GenerationFailed as exc:
            self.repairs.append(f"assets : choix par défaut du gabarit ({exc})")
            chosen = {}
        world = []
        for zone_id in used:
            zone = zones[zone_id]
            picked = [a for a in dict.fromkeys(chosen.get(zone_id, [])) if a in options[zone_id] and a in catalog]
            building = next((a for a in picked if catalog[a].category == "building"), zone["defaults"][0])
            props = [a for a in picked if catalog[a].category != "building"]
            if len(props) < 2:  # zone vide ou choix raté : objets sûrs du gabarit
                props += [a for a in zone["defaults"][1:] if a not in props]
            world.append(
                {"id": zone_id, "name": zone["name"], "purpose": zone["purpose"], "asset_ids": [building, *props][:12]}
            )
        if "prop_kpi_screen" not in world[0]["asset_ids"]:
            world[0]["asset_ids"].insert(1, "prop_kpi_screen")  # les joueurs consultent les KPI au siège
            del world[0]["asset_ids"][12:]
        return world

    async def _debrief(self, outline: dict[str, Any], phases: list[dict[str, Any]]) -> dict[str, Any]:
        decisions = "\n".join(
            f"- {d['prompt']}\n" + "\n".join(f"  * {o['label']} : {o['rationale'][:160]}" for o in d["options"])
            for p in phases
            for d in p["decisions"]
        )
        messages = load_prompt("game.debrief").render(
            objectives="\n".join(f"- {o['statement']}" for o in outline["learning_objectives"]),
            kpis=_kpi_lines(outline),
            decisions=decisions or "(aucune)",
        )
        schema = _stage_schema("debrief")
        schema["properties"]["key_takeaways"]["maxItems"] = 5
        questions = schema["properties"]["questions"]
        questions["maxItems"] = 4
        questions["items"]["properties"]["expected_points"]["maxItems"] = 4
        return await self._json("debrief", "game.debrief", messages, schema)

    async def _review(self, spec: dict[str, Any]) -> None:
        """Étape 7 : le sens de chaque effet doit suivre l'explication de l'option, que les joueurs lisent au
        débrief. Le modèle de décision lit l'explication (une question fermée par effet, aucun texte généré) ;
        un effet qu'elle contredit est inversé et la réparation est listée pour le formateur."""
        template = load_questions("game.coherence_review")["direction"]
        threshold = load_thresholds("game.coherence_review")["direction"]
        kpis = {k["id"]: k for k in spec["kpis"]}
        for option in (o for p in spec["phases"] for d in p["decisions"] for o in d["options"]):
            effects = [e for e in option["effects"] if e["kpi"] in kpis and e["operation"] == "add" and e["value"]]
            if not effects:
                continue
            questions = {
                f"e{i}": template | {"instructions": template["instructions"].format(kpi=kpis[e["kpi"]]["name"])}
                for i, e in enumerate(effects)
            }
            state = f"Option : {option['label']}\nExplication : {option['rationale']}"
            verdict = await self.llm.decide("game.coherence_review", state, questions)
            self.usage.setdefault("review", {"model": verdict.get("model"), "calls": 0})["calls"] += 1
            for i, effect in enumerate(effects):
                answer = (verdict.get("answers") or {}).get(f"e{i}") or {}
                said = answer.get("choice")
                confidence = (answer.get("probabilities") or {}).get(said, 1.0 if verdict.get("emulated") else 0.0)
                actual = "hausse" if effect["value"] > 0 else "baisse"
                if said in ("hausse", "baisse") and said != actual and confidence >= threshold:
                    effect["value"] = -effect["value"]
                    name = kpis[effect["kpi"]]["name"]
                    self.repairs.append(
                        f"{option['id']} : effet sur « {name} » inversé ({actual} -> {said}), comme l'explication"
                    )

    # --- outils ------------------------------------------------------------------------------------------

    async def _rag(self, task: str, query: str) -> str:
        """Extraits numérotés dans la numérotation globale de la spec : [S3] dans un prompt = source s3."""
        profile, _ = await self.llm.resolve(task)
        rag = profile.rag
        vector = await self.llm.embed_query(query)
        async with self.sessions() as session:
            hits = await search(session, query_vector=vector, query_text=query, domain=self._domain, k=rag.top_k)
        context, local = build_context(hits, rag.max_context_tokens)
        ids = {}
        for source in local:
            document = str(source["document_id"])
            ids[source["ref"]] = self._sources.setdefault(document, f"s{len(self._sources) + 1}")
            self._source_chunks.setdefault(document, source["chunk_id"])
        context = re.sub(r"^\[(S\d+)\]", lambda m: f"[{ids[m.group(1)].upper()}]", context, flags=re.MULTILINE)
        return context or "(aucun extrait : rester général, ne citer aucun chiffre précis)"

    async def _json(
        self, stage: str, task: str, messages: list[dict[str, str]], schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Sortie JSON validée ; 2 essais (docs/ai-runtime.md, étape 8) puis échec explicite."""
        errors: list[str] = []
        for _ in range(2):
            try:
                data, result = await self.llm.json(task, messages, schema=schema)
            except InvalidOutput as exc:
                errors = exc.errors
                log.warning("étape %s : sortie invalide %s", stage, exc.errors[:3])
                continue
            self._track(stage, result)
            return data
        raise GenerationFailed(f"étape {stage} : sortie de l'IA invalide après 2 essais ({'; '.join(errors[:3])})")

    def _track(self, stage: str, result: ChatResult) -> None:
        entry = self.usage.setdefault(
            stage, {"model": result.usage.model, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "ms": 0}
        )
        entry["calls"] += 1
        entry["prompt_tokens"] += result.usage.prompt_tokens
        entry["completion_tokens"] += result.usage.completion_tokens
        entry["ms"] += round(result.usage.duration_ms)

    async def _source_list(self) -> list[dict[str, Any]]:
        """Sources de la spec : la ligne « > Source : » de la fiche (URL de la révision), sinon le titre."""
        if not self._sources:
            return []
        documents = [uuid.UUID(d) for d in self._sources]
        async with self.sessions() as session:
            query = select(KnowledgeDocument.id, KnowledgeDocument.title).where(KnowledgeDocument.id.in_(documents))
            titles = dict((await session.execute(query)).tuples().all())
            heads = await session.execute(
                select(KnowledgeChunk.document_id, KnowledgeChunk.content).where(
                    KnowledgeChunk.document_id.in_(documents), KnowledgeChunk.ordinal == 0
                )
            )
            origin = {doc: m.group(1).strip() for doc, content in heads if (m := SOURCE_LINE.search(content))}
        return [
            {
                "id": source_id,
                "citation": origin.get(uuid.UUID(document), titles[uuid.UUID(document)]),
                "chunk_id": self._source_chunks[document],
            }
            for document, source_id in self._sources.items()
            if uuid.UUID(document) in titles
        ]

    # --- réparations déterministes -------------------------------------------------------------------------

    def _repair_outline(self, outline: dict[str, Any], req: GameRequest) -> None:
        meta = outline["meta"]
        meta["domain"], meta["language"] = req.domain.slug, "fr"
        wanted = {
            "level": req.level,
            "duration_minutes": req.duration_minutes,
            "players": {"min": req.players_min, "max": req.players_max},
        }
        for key, value in wanted.items():
            if meta.get(key) != value:
                self.repairs.append(f"meta.{key} : {meta.get(key)} -> {value} (demande du formateur)")
                meta[key] = value
        base = {k["id"]: k["initial"] for k in outline["kpis"] if not k.get("formula")}
        for kpi in outline["kpis"]:
            if not kpi.get("formula"):
                continue
            try:  # sur des KPI de base seulement : ni chaîne ni cycle entre KPI dérivés
                value = round(evaluate_formula(kpi["formula"], base), 4)
            except ValueError as exc:
                problem = str(exc)
            else:
                gap = abs(value - kpi["initial"])
                if gap <= max(1e-6, 0.01 * abs(value)):
                    continue
                if gap <= 0.1 * max(abs(value), abs(kpi["initial"])):  # petite erreur de calcul du modèle
                    self.repairs.append(f"KPI {kpi['id']} : valeur initiale {kpi['initial']:g} -> {value:g} (formule)")
                    kpi["initial"] = value
                    continue
                # mesuré : « taux_de_service = 1 - taux_de_rupture » en % donnait -14 : on garde la valeur annoncée
                problem = f"donne {value:g} au lieu de {kpi['initial']:g}"
            self.repairs.append(f"KPI {kpi['id']} : formule « {kpi.pop('formula')} » retirée ({problem})")
            base[kpi["id"]] = kpi["initial"]
        budget = req.duration_minutes - DEBRIEF_MINUTES
        total = sum(p["duration_minutes"] for p in outline["phases"])
        if total > budget:
            for phase in outline["phases"]:
                phase["duration_minutes"] = max(5, phase["duration_minutes"] * budget // total)
            new_total = sum(p["duration_minutes"] for p in outline["phases"])
            self.repairs.append(f"durée des phases : {total} -> {new_total} min ({DEBRIEF_MINUTES} min de débrief)")
        kpi_ids = [k["id"] for k in outline["kpis"]]
        for objective in outline["learning_objectives"]:
            kept = [ref for ref in objective["assessed_by"] if ref in kpi_ids]
            if len(kept) != len(objective["assessed_by"]):
                objective["assessed_by"] = kept or kpi_ids[:1]
                self.repairs.append(f"{objective['id']} : évalué par {', '.join(objective['assessed_by'])}")

    def _repair_references(self, spec: dict[str, Any]) -> None:
        """Ids uniques dans toute la spec, déclencheurs d'aléas valides, aucun aléa orphelin."""
        taken = {x["id"] for key in ("learning_objectives", "roles", "kpis", "phases", "npcs") for x in spec[key]}
        taken |= {z["id"] for z in spec["world"]["zones"]} | {s["id"] for s in spec["sources"]}
        for phase in spec["phases"]:
            renamed = {}
            for event in phase["events"]:
                old = event["id"]
                event["id"] = renamed[old] = _unique(old, taken)
            for decision in phase["decisions"]:
                decision["id"] = _unique(decision["id"], taken)
                for option in decision["options"]:
                    option["id"] = _unique(option["id"], taken)
                    if "triggers_events" in option:
                        option["triggers_events"] = [renamed.get(e, e) for e in option["triggers_events"]]
        for question in spec["debrief"]["questions"]:
            question["id"] = _unique(question["id"], taken)
        events = {e["id"] for p in spec["phases"] for e in p["events"]}
        triggered = set()
        for option in (o for p in spec["phases"] for d in p["decisions"] for o in d["options"]):
            unknown = [e for e in option.get("triggers_events", []) if e not in events]
            if unknown:
                self.repairs.append(f"{option['id']} : déclencheurs inconnus retirés ({', '.join(unknown)})")
                option["triggers_events"] = [e for e in option["triggers_events"] if e in events]
            triggered |= set(option.get("triggers_events", []))
        for phase in spec["phases"]:
            orphans = [e["id"] for e in phase["events"] if e.get("trigger") == "on_option" and e["id"] not in triggered]
            if orphans:
                self.repairs.append(f"{phase['id']} : aléas jamais déclenchés retirés ({', '.join(orphans)})")
                phase["events"] = [e for e in phase["events"] if e["id"] not in orphans]


def _effect(impact: dict[str, Any], kpi: dict[str, Any]) -> dict[str, Any]:
    """Impact qualitatif du modèle (sens, ampleur) -> effet chiffré du moteur, proportionné à l'écart à la cible."""
    scale = abs(kpi["target"] - kpi["initial"]) or max(abs(kpi["initial"]) * 0.1, 1.0)
    value = STRENGTH[impact["ampleur"]] * scale * (1 if impact["sens"] == "hausse" else -1)
    value = round(value) if abs(value) >= 10 else (round(value, 1) or (0.1 if value > 0 else -0.1))
    effect: dict[str, Any] = {"kpi": impact["kpi"], "operation": "add", "value": value}
    if impact.get("delay_phases"):
        effect["delay_phases"] = impact["delay_phases"]
    return effect


def _decision_words(decision: dict[str, Any]) -> set[str]:
    """Mots d'au moins 4 lettres de l'énoncé et des libellés d'options d'une décision."""
    text = " ".join([decision["prompt"], *(o["label"] for o in decision["options"])])
    return set(re.findall(r"\w{4,}", text.lower()))


def _similar(words_a: set[str], words_b: set[str]) -> bool:
    """Même décision rejouée (Jaccard >= 0,4 sur énoncé + options). Mesuré le 2026-10-22 : « prévoir par
    régression ou par jugement » reformulé en phase 2 donnait 0,44 ; une décision sans rapport, 0,03."""
    return bool(words_a and words_b) and len(words_a & words_b) / len(words_a | words_b) >= 0.4


def _stage_schema(name: str) -> dict[str, Any]:
    """Copie modifiable du schéma d'une étape. Les plafonds (maxItems) y sont resserrés pour être imposés au
    décodage : mesuré le 2026-10-22, qwen2.5:3b dépassait num_predict sur une phase (JSON tronqué) quand seul
    le prompt les demandait. Le schéma complet de la spec reste plus large pour les modifications à la main."""
    return copy.deepcopy(schemas.resolve(f"business_game#/$defs/{name}"))


def _unique(identifier: str, taken: set[str]) -> str:
    candidate, n = identifier, 2
    while candidate in taken:
        candidate, n = f"{identifier}_{n}", n + 1
    taken.add(candidate)
    return candidate


def _company(outline: dict[str, Any]) -> str:
    company = outline["context"]["company"]
    return f"{company['name']} ({company['sector']}, {company['size']}) : {company['description']}"


def _roles(outline: dict[str, Any]) -> str:
    return "; ".join(f"{r['id']} = {r['title']} ({r['mission']})" for r in outline["roles"])


def _kpi_lines(outline: dict[str, Any]) -> str:
    return "\n".join(
        f"- {k['id']} : {k['name']}, {k['unit']}, {k['initial']:g} -> {k['target']:g}, "
        + ("plus haut = mieux" if k["direction"] == "higher_is_better" else "plus bas = mieux")
        + (f" (dérivé = {k['formula']}, ne pas modifier)" if k.get("formula") else "")
        for k in outline["kpis"]
    )
