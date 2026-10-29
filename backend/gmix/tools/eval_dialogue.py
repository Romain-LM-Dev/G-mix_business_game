"""Évalue les répliques RÉELLES des agents PNJ (tâche npc.dialogue) avec le vrai modèle Ollama.

Chaque cas de ai/evals/npc.dialogue.jsonl fabrique une situation avec le moteur (semaine calme, aléa annoncé, rupture
d'un composant, livraison en retard, retours qualité, trésorerie basse), puis fait parler l'agent par `agent_reply`
comme le fait l'API : filtre d'intention (tev1), RAG, faits du moteur, mémoire. Mesures automatiques : deux phrases
et 320 caractères (sortie brute du modèle), nombres absents du prompt, fait le plus important dit à la salutation,
réponse fixe aux hors-sujets et injections (sans fausse alerte), mémoire, répétition, propreté (langue, markdown,
préfixe). Le ton, le naturel et l'utilité se jugent en relisant le rapport Markdown, qui consigne chaque réplique.

Usage (depuis backend\\) :
  python -m gmix.tools.eval_dialogue --series A --label small-avant        (une série = une soixantaine de répliques)
  python -m gmix.tools.eval_dialogue --series B --model main --cold 3      (autre modèle, latence à froid x3)
  python -m gmix.tools.eval_dialogue --facts                               (faits du moteur par situation, sans modèle)
  python -m gmix.tools.eval_dialogue --series F --label filtre-reglage      (filtres seuls, jeu de RÉGLAGE)
  python -m gmix.tools.eval_dialogue --series C --label filtre-controle     (filtres seuls, jeu de CONTRÔLE neuf)
  options utiles pour F et C : --no-corpus (PostgreSQL arrêté), --intent-model decide (filtre tev1:4b)

Filtre d'intention : trois couches mesurées séparément sur les cas hors-sujet, injection et légitimes : (a) pré-filtre
lexical `looks_like_injection`, (b) tev1 seul (player.intent, sans pré-filtre), (c) chaîne complète `agent_reply`.
La série F a servi à régler les questions de player.intent : ses chiffres sont optimistes. La série C
(ai/evals/player.intent.control.jsonl) est le jeu de contrôle : ne JAMAIS s'en servir pour régler questions ni seuil.
"""

import argparse
import asyncio
import datetime
import difflib
import json
import math
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx
import yaml

from gmix.db import get_engine, get_sessionmaker
from gmix.game import engine, npc
from gmix.game.generation import generate
from gmix.game.npc import INJECTION_REPLY, MAX_CHARS, OFF_TOPIC_REPLY, agent_reply, looks_like_injection
from gmix.game.spec import GameParams, load_sim_catalog
from gmix.llm.prompts import load_prompt, load_questions, load_thresholds
from gmix.llm.service import LLMService
from gmix.llm.tokens import estimate_tokens
from gmix.logging_setup import setup_logging
from gmix.settings import get_settings

TASK = "npc.dialogue"
SPEAKER = "Alice"
MODULES = ["approvisionnement", "production", "maintenance", "qualite", "commercial", "transport", "finance"]
EVENT_FOR = {  # aléa annoncé qui concerne l'agent (sans effet sur la voix du client : il ne reçoit pas d'aléa)
    "approvisionnement": "perturbation_maritime", "production": "operation_promotionnelle",
    "maintenance": "panne_ligne", "qualite": "lot_defectueux", "commercial": "operation_promotionnelle",
    "transport": "greve_transport", "finance": "hausse_matieres", "client": "operation_promotionnelle",
    "fournisseur": "perturbation_maritime", "direction": "hausse_matieres",
}  # fmt: skip
FILTER_KINDS = ("hors_sujet", "injection", "legit")  # cas qui mesurent le filtre d'intention
FIXED_REPLIES = (OFF_TOPIC_REPLY, INJECTION_REPLY)
CONTROL_FILE = "player.intent.control.jsonl"  # série C : jeu de contrôle, jamais utilisé pour régler le filtre
COVERAGE_MIN = 0.4  # part des mots-clés du fait le plus important à retrouver dans la réplique (voir `coverage`)
QUOTES = '"«»“” '
SPACES = r" \N{NO-BREAK SPACE}\N{NARROW NO-BREAK SPACE}"
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
NUMBER = re.compile(rf"\d{{1,3}}(?:[{SPACES}.]\d{{3}})+(?:,\d+)?|\d+(?:[.,]\d+)?")
NUMBER_WORDS = re.compile(
    r"\b(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|douze|quinze|vingt|trente|quarante|cinquante|cent|mille)\b", re.I
)
STOP = frozenset(
    "avec dans pour cette sont plus mais comme sans tout tous elle elles nous vous leur leurs votre vos notre nos "
    "etre avoir fait faut sous chez depuis entre vers cela ceci ainsi alors donc aussi encore tres bien deja quand "
    "dont autre autres meme apres avant pendant cest ligne".split()
)
BAD_FORMAT = {
    "anglais": re.compile(
        r"\b(the|and|you|your|with|this|that|have|please|sorry|thank|hello|week|it|keep|brief|alright|will|can|just|not|here|what|how)\b",
        re.I,
    ),
    "markdown": re.compile(r"\*\*|^#+ |^\s*[-*•] |^\s*\d+[.)] ", re.M),
    "sortie de rôle": re.compile(
        r"\b(assistant|intelligence artificielle|modèle de langage|prompt|chatgpt|qwen)\b", re.I
    ),
    "balise source": re.compile(r"\[S\d+\]"),
}
TU = re.compile(r"\b(?:tu|te|toi|ton|ta|tes)\b|(?<!\w)t'", re.I)
VOUS = re.compile(r"\b(?:vous|votre|vos)\b", re.I)


# --- situations fabriquées avec le moteur ------------------------------------------------------------------


def build_spec() -> dict[str, Any]:
    params = GameParams(
        theme="industrie", modules=MODULES, extra_agents=["client", "fournisseur", "direction"], products=3,
        weeks=8, seed=42, events="aucun", difficulty="equilibre",
    )  # fmt: skip
    return generate(params)


def find_agent(spec: dict[str, Any], key: str) -> dict[str, Any]:
    return next(a for a in spec["agents"] if (a["module_id"] or a["kind"]) == key)


def make_state(spec: dict[str, Any], situation: str, key: str) -> dict[str, Any]:
    """Semaine 3 sans souci (deux semaines de pilote automatique, stocks confortables), puis la situation voulue.
    `debut` : première semaine, rien n'a été joué. `rupture` : un composant à zéro, avec ses conséquences (stock de
    produits fini bas, ventes perdues et OTIF en baisse la semaine dernière)."""
    state = engine.start(spec, engine.initial_state(spec))
    if situation == "debut":
        return state
    for _ in range(2):
        state = engine.advance(spec, state, autopilot_all=True)
    state["event"], state["pending"], state["cash"] = None, [], max(state["cash"], spec["economy"]["initial_cash"])
    for c in spec["components"]:
        state["components"][c["id"]] = c["usage"] * 4
    for p in spec["products"]:
        state["stocks"][p["id"]] = p["demand"] * 2
    for line in state["lines"].values():
        line.update(trs=88.0, down=False)
    for sale in state["last"]["sales"].values():
        sale.update(returns=0, lost=0)
    state["history"][-1].update(otif=97.0, margin=1200, lost=0, returns=0)
    first, week = spec["components"][0], state["week"]
    if situation == "alea":
        state["event"] = EVENT_FOR[key]
    elif situation == "rupture":
        product = spec["products"][0]
        state["components"][first["id"]], state["stocks"][product["id"]] = 0, 40
        state["last"]["sales"][product["id"]]["lost"] = 25
        state["history"][-1].update(otif=93.0, lost=25)
    elif situation == "retard":
        offer = next(o for o in spec["offers"] if o["component_id"] == first["id"] and o["profile"] == "standard")
        state["pending"].append(
            {"id": "cmd90", "offer_id": offer["id"], "supplier_id": offer["supplier_id"], "component_id": first["id"],
             "quantity": 300, "unit_cost": offer["unit_cost"], "ordered_week": week - 3, "arrival_week": week,
             "delays": 1}
        )  # fmt: skip
    elif situation == "retours":
        state["last"]["sales"][spec["products"][0]["id"]]["returns"] = 9
        state["history"][-1].update(otif=91.0, returns=9)
    elif situation == "tresorerie":
        state["cash"] = -3200.0
        state["history"][-1]["margin"] = -1800
    elif situation != "calme":
        raise ValueError(f"situation inconnue : {situation}")
    return state


def situation_for(base: dict[str, Any], case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """(spec avec le caractère voulu, vue publique, agent) : le préfixe d'alerte de la vue suit le caractère."""
    pid = case["personality"]
    spec = {**base, "agents": [dict(a) for a in base["agents"]]}
    agent = find_agent(spec, case["agent"])
    agent["personality"] = {"id": pid, **load_sim_catalog()["personalities"][pid]}
    view = engine.public_state(spec, make_state(spec, case["situation"], case["agent"]))
    return spec, view, agent


def top_fact(view: dict[str, Any], agent: dict[str, Any]) -> str:
    """Le fait le plus important de l'agent : l'urgent d'abord (celui de l'alerte), sinon le premier."""
    briefing = view["briefings"][agent["id"]]
    if briefing["line"]:
        return briefing["line"].removeprefix(agent["personality"]["prefix"]).strip()
    return briefing["facts"][0]


# --- mesures -----------------------------------------------------------------------------------------------


def numbers(text: str) -> set[str]:
    """Nombres d'un texte sous forme normalisée : « 20 000 » et « 20000 » sont le même, « 3,5 » devient « 3.5 »."""
    found = set()
    for raw in NUMBER.findall(re.sub(r"\[S\d+\]", " ", text)):
        value = re.sub(f"[{SPACES}]", "", raw)
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", value):
            value = value.replace(".", "")
        value = value.replace(",", ".")
        found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return found


def plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]+", plain(text)) if len(w) >= 4 and w not in STOP}


def coverage(reply: str, fact: str) -> float:
    """Part des mots-clés (radicaux de 5 lettres) et nombres du fait que la réplique reprend."""
    wanted_stems, wanted_numbers = stems(fact), numbers(fact)
    total = len(wanted_stems) + len(wanted_numbers)
    hit = len(wanted_stems & stems(reply)) + len(wanted_numbers & numbers(reply))
    return hit / total if total else 1.0


def clean(raw: str, name: str) -> str:
    """Sortie brute sans guillemets ni nom de l'agent en préfixe (le code les retire aussi), mais NON coupée."""
    text = raw.strip().strip(QUOTES)
    if text.lower().startswith(name.lower()):
        text = text[len(name) :].lstrip(" :,-—").strip(QUOTES)
    return text


def format_problems(raw: str, text: str) -> list[str]:
    problems = [name for name, pattern in BAD_FORMAT.items() if pattern.search(raw)]
    names = [unicodedata.name(c, "") for c in raw]
    if any(n.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL")) for n in names):
        problems.append("caractères asiatiques")
    if any(unicodedata.category(c) == "So" and ord(c) > 0x2000 for c in raw):
        problems.append("emoji ou symbole")
    if TU.search(text) and VOUS.search(text):
        problems.append("tu et vous mélangés")
    if not text:
        problems.append("réplique vide")
    return problems


def measure(turn: dict[str, Any], probe: "Probe", view: dict[str, Any], agent: dict[str, Any]) -> None:
    """Remplit turn["checks"] (True = critère tenu) et turn["notes"] (détails à relire)."""
    case, reply, kind = turn["case"], turn["reply"], turn["kind"]
    checks: dict[str, bool] = {"sans_secours": not turn["fallback"]}  # la réplique de secours est un échec du modèle
    notes: list[str] = []
    turn["checks"], turn["notes"] = checks, notes
    # Filtré = réponse fixe, ou intention « injection » / « hors_sujet » (le pré-filtre lexical répond par les faits de
    # l'agent, sans appel au modèle, et marque seulement l'intention : agent_reply).
    fixed = reply in FIXED_REPLIES or turn["intent"] in ("injection", "hors_sujet")
    if kind in ("hors_sujet", "injection"):
        checks["filtre"] = fixed
        if not fixed and not turn["fallback"]:  # le filtre a laissé passer : la réplique doit au moins rester propre
            problems = format_problems(turn["raw"], clean(turn["raw"], agent["name"]))
            checks["propre"] = not problems
            notes += problems
        return
    checks["pas_de_fausse_alerte"] = not fixed  # un message du jeu ne doit jamais recevoir la réponse fixe
    if fixed or turn["fallback"]:  # pas de réplique du modèle à juger : les critères de contenu sont manqués
        if kind == "salutation":
            checks["essentiel"] = False
        if case.get("expect_any"):
            checks["attendu"] = False
        return
    prompt = " ".join(m["content"] for m in probe.messages or [])
    text = clean(turn["raw"], agent["name"])
    invented = sorted(numbers(text) - numbers(prompt) - numbers(turn["message"]))
    sentences = [s for s in SENTENCE.split(text) if s]
    checks["nombres"] = not invented
    checks["longueur"] = len(sentences) <= 2 and len(text) <= MAX_CHARS
    if invented:
        notes.append(f"nombres inventés : {', '.join(invented)}")
    if not checks["longueur"]:
        notes.append(f"{len(sentences)} phrases, {len(text)} caractères")
    spoken = sorted({w.lower() for w in NUMBER_WORDS.findall(text)} - {w.lower() for w in NUMBER_WORDS.findall(prompt)})
    if spoken:
        notes.append(f"nombre en lettres à vérifier : {', '.join(spoken)}")
    problems = format_problems(turn["raw"], text)
    checks["propre"] = not problems
    if problems:
        notes.append("défauts : " + ", ".join(problems))
    best = top_fact(view, agent)
    turn["top_fact"], turn["coverage"] = best, round(coverage(text, best), 2)
    if kind == "salutation":
        checks["essentiel"] = turn["coverage"] >= COVERAGE_MIN
    elif kind == "question":
        checks["essentiel_aussi"] = turn["coverage"] >= COVERAGE_MIN  # indicatif : la question passe avant
    if case.get("expect_any"):
        checks["attendu"] = any(plain(word) in plain(text) for word in case["expect_any"])
    if turn["previous_reply"] and not case.get("expect_any"):
        ratio = difflib.SequenceMatcher(None, plain(text), plain(turn["previous_reply"])).ratio()
        checks["sans_repetition"] = ratio < 0.6
        if ratio >= 0.6:
            notes.append(f"répète la réplique précédente ({ratio:.0%})")


# --- exécution ---------------------------------------------------------------------------------------------


class Probe:
    """Enveloppe d'un LLMService : chronomètre l'intention, l'embedding et la génération, garde le prompt envoyé."""

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm
        self.reset()

    def reset(self) -> None:
        self.timings: dict[str, float] = {}
        self.messages: list[dict[str, str]] | None = None
        self.result: Any = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.llm, name)

    async def _timed(self, step: str, call: Any) -> Any:
        start = time.perf_counter()
        try:
            return await call
        finally:
            self.timings[step] = time.perf_counter() - start

    async def decide(self, *args: Any, **kwargs: Any) -> Any:
        return await self._timed("intention", self.llm.decide(*args, **kwargs))

    async def embed_query(self, *args: Any, **kwargs: Any) -> Any:
        return await self._timed("embedding", self.llm.embed_query(*args, **kwargs))

    async def text(self, task: str, messages: list[dict[str, str]]) -> Any:
        self.messages = messages
        self.result = await self._timed("génération", self.llm.text(task, messages))
        return self.result


async def filter_layers(llm: LLMService, message: str, week: int, intent: str | None) -> dict[str, Any]:
    """Les couches du filtre sur un message : `lexical` (pré-filtre de gmix.game.npc), `tev1` (verdict du seul
    player.intent, lu comme agent_reply : même état, mêmes questions, même seuil ; None = laisse passer) et `chain`
    (verdict d'agent_reply, tiré de son `intent`). La lecture de tev1 recopie celle d'agent_reply : le rapport compte
    les écarts chaîne / tev1 seul hors pré-filtre pour déceler une dérive."""
    layers: dict[str, Any] = {"lexical": looks_like_injection(message), "tev1": None, "p_injection": None}
    layers["chain"] = intent in ("injection", "hors_sujet")
    state = f"Semaine {week}\nJoueur : {message}"
    try:
        answers = (await llm.decide("player.intent", state, load_questions("player.intent"))).get("answers") or {}
    except Exception as exc:  # noqa: BLE001 - une panne de tev1 est un résultat de la mesure
        layers["tev1"] = f"erreur {type(exc).__name__}"
        return layers
    noul = (answers.get("injection") or {}).get("noul")
    layers["p_injection"] = float(noul) if isinstance(noul, int | float) else None
    layers["tev1_intent"] = (answers.get("intent") or {}).get("choice")
    if layers["p_injection"] is not None and layers["p_injection"] >= load_thresholds("player.intent")["injection"]:
        layers["tev1"] = "injection"
    elif layers["tev1_intent"] == "hors_sujet":
        layers["tev1"] = "hors_sujet"
    return layers


async def play(
    case: dict[str, Any], base: dict[str, Any], probe: Probe, session: Any, *, cold: bool = False
) -> list[dict]:
    """Un cas = un tour, ou deux si `first` est donné (salutation réelle, puis relance qui s'appuie sur elle)."""
    spec, view, agent = situation_for(base, case)
    memory = [dict(m) for m in case.get("memory", [])]
    plan = [(case["kind"], case["message"], "")]
    if case.get("first"):
        plan = [("salutation", case["first"], ".1"), (case["kind"], case["message"], ".2")]
    turns = []
    for kind, message, suffix in plan:
        probe.reset()
        start = time.perf_counter()
        error = None
        try:
            result = await agent_reply(
                probe, session, spec=spec, view=view, agent=agent, message=message, speaker=SPEAKER, memory=memory
            )
        except Exception as exc:  # noqa: BLE001 - une panne d'un tour est un résultat, pas la fin de la série
            result, error = {"reply": "", "intent": None, "sources": []}, f"{type(exc).__name__}: {exc}"
        result.setdefault("fallback", False)
        wall = time.perf_counter() - start
        usage = probe.result.usage if probe.result else None
        turn = {
            "id": case["id"] + suffix, "case": case, "kind": kind, "message": message, "memory": list(memory),
            "reply": result["reply"], "intent": result.get("intent"), "fallback": result["fallback"],
            "sources": [s["title"] for s in result.get("sources", [])],
            "raw": probe.result.content if probe.result else "", "error": error, "cold": cold,
            "truncated": probe.result is not None and probe.result.done_reason == "length",
            "previous_reply": memory[-1]["reply"] if memory else None,
            "facts": view["briefings"][agent["id"]]["facts"], "wall": wall, "timings": dict(probe.timings),
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "load_ms": usage.load_ms if usage else 0.0, "name": agent["name"],
        }  # fmt: skip
        if error:
            turn["checks"], turn["notes"] = {"sans_erreur": False}, [error]
        else:
            if kind in FILTER_KINDS:
                turn["layers"] = await filter_layers(probe.llm, message, view["week"], turn["intent"])
            measure(turn, probe, view, agent)
        turns.append(turn)
        if not error:
            memory.append({"speaker": SPEAKER, "message": message, "reply": result["reply"]})
    return turns


async def unload(models: set[str]) -> None:
    async with httpx.AsyncClient(base_url=get_settings().ollama_base_url, timeout=60) as http:
        for name in models:
            await http.post("/api/generate", json={"model": name, "keep_alive": 0})
    await asyncio.sleep(1)


async def run(args: argparse.Namespace) -> int:
    base = build_spec()
    control = args.series == "C"  # jeu de contrôle : fichier distinct, jamais mêlé aux séries de réglage
    path = get_settings().gmix_ai_dir / "evals" / (CONTROL_FILE if control else "npc.dialogue.jsonl")
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wanted = {"C"} if control else {args.series, "F"} if args.series != "all" else {c["series"] for c in cases}
    cases = [c for c in cases if c["series"] in wanted and (not args.only or c["id"] in args.only)]
    if args.facts:
        return dump_facts(base, cases)
    if (
        args.no_corpus
    ):  # filtres seuls sans PostgreSQL : le filtre décide AVANT la recherche, ses verdicts sont inchangés

        async def no_hits(*_args: Any, **_kwargs: Any) -> list:
            return []

        npc.search = no_hits
    llm = LLMService.from_settings(with_cache=False)
    task = llm.catalog.task(TASK)
    if args.model:
        task.model, task.fallback = args.model, None
    if args.intent_model:  # autre modèle de décision pour le filtre (decide = tev1:4b), sans repli
        intent_task = llm.catalog.task("player.intent")
        intent_task.model, intent_task.fallback = args.intent_model, None
    for item in args.set:
        key, value = item.split("=")
        task.options[key] = float(value) if "." in value else int(value)
    probe = Probe(llm)
    turns: list[dict] = []
    colds: list[dict] = []
    try:
        _, dialogue_model = await llm.resolve(TASK)
        _, intent_model = await llm.resolve("player.intent")
        async with get_sessionmaker()() as session:
            greeting = next((c for c in cases if c["kind"] == "salutation"), None)
            for _ in range(args.cold if greeting else 0):  # modèles de la conversation déchargés avant l'appel
                await unload({dialogue_model.name, intent_model.name})
                colds += await play({**greeting, "id": "froid"}, base, probe, session, cold=True)
            for case in cases:
                turns += await play(case, base, probe, session)
                last = turns[-1]
                verdict = "OK" if all(last["checks"].values()) else "KO"
                print(f"{last['id']:<8} {verdict}  {last['wall']:.1f}s  {last['reply'][:90]}", flush=True)
    finally:
        await llm.aclose()
        await get_engine().dispose()
    label = args.label or f"{dialogue_model.name.replace(':', '-')}-{args.series}"
    print("\n" + report(turns, colds, args, dialogue_model.name, label, task.options, intent_model.name))
    return 0


RELOAD_MS = 1000  # au-delà, le modèle a été (re)chargé en VRAM pendant l'appel (en dessous : simple vérification)
CRITERIA = {
    "nombres": "Aucun nombre inventé",
    "longueur": "Deux phrases, 320 caractères (sortie brute)",
    "essentiel": "Fait le plus important dit à la salutation",
    "essentiel_aussi": "Idem sur une question précise (indicatif)",
    "attendu": "Mémoire / notion attendue présente",
    "sans_repetition": "Sans répétition de la réplique précédente",
    "propre": "Propre (français, sans markdown, tu/vous)",
    "filtre": "Hors-sujet et injection filtrés (chaîne complète)",
    "pas_de_fausse_alerte": "Message du jeu non bloqué",
    "sans_erreur": "Sans erreur d'appel",
}


def rate(turns: list[dict], check: str) -> tuple[int, int]:
    values = [t["checks"][check] for t in turns if check in t["checks"]]
    return sum(values), len(values)


def wilson(good: int, total: int) -> tuple[float, float]:
    """Intervalle de confiance à 95 % (Wilson) d'une proportion : avec 8 ou 9 cas, il est très large."""
    z, p = 1.96, good / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - half), min(1.0, centre + half)


LAYERS = {
    "lexical": "(a) Pré-filtre lexical (looks_like_injection, sans modèle)",
    "tev1": "(b) tev1 seul (player.intent, sans pré-filtre)",
    "chain": "(c) Chaîne complète (agent_reply)",
}
FILTER_COLUMNS = {
    "injection": "Injections détectées", "hors_sujet": "Hors-sujet détectés", "legit": "Légitimes bloqués à tort",
}  # fmt: skip


def flagged(layers: dict[str, Any], layer: str) -> bool:
    """La couche a-t-elle filtré le message (réponse fixe, ou faits de l'agent sans génération) ?"""
    if layer == "tev1":
        return layers["tev1"] in ("injection", "hors_sujet")
    return bool(layers[layer])


def filter_table(turns: list[dict]) -> list[str]:
    """Les trois couches par type de message (cas de `FILTER_KINDS`), avec l'intervalle de Wilson."""
    measured = [t for t in turns if "layers" in t]
    if not measured:
        return []
    lines = ["| Couche | " + " | ".join(FILTER_COLUMNS.values()) + " |", "|---|---|---|---|"]
    for layer, title in LAYERS.items():
        cells = []
        for kind in FILTER_COLUMNS:
            mine = [t for t in measured if t["kind"] == kind]
            hits = sum(flagged(t["layers"], layer) for t in mine)
            low, high = wilson(hits, len(mine)) if mine else (0, 0)
            cells.append(f"{hits}/{len(mine)} ({hits / len(mine):.0%}, IC95 {low:.0%}-{high:.0%})" if mine else "n/a")
        lines.append(f"| {title} | " + " | ".join(cells) + " |")
    missed = [t["id"] for t in measured if t["kind"] != "legit" and not t["layers"]["chain"]]
    blocked = [t["id"] for t in measured if t["kind"] == "legit" and t["layers"]["chain"]]
    drift = [
        t["id"] for t in measured if not t["layers"]["lexical"] and t["layers"]["chain"] != flagged(t["layers"], "tev1")
    ]
    errors = [t["id"] for t in measured if str(t["layers"]["tev1"]).startswith("erreur")]
    skipped = [t["id"] for t in turns if t["kind"] in FILTER_KINDS and "layers" not in t]  # erreur d'appel : exclus
    lines += [
        "",
        f"Non filtrés par la chaîne : {', '.join(missed) or 'aucun'} · légitimes bloqués à tort : "
        f"{', '.join(blocked) or 'aucun'}",
        f"Écarts chaîne / tev1 seul hors pré-filtre (aucun attendu) : {', '.join(drift) or 'aucun'} · erreurs de tev1 "
        f"seul : {', '.join(errors) or 'aucune'} · cas exclus par une erreur d'appel : {', '.join(skipped) or 'aucun'}",
    ]
    return lines


def questions_version() -> int:
    path = get_settings().gmix_ai_dir / "prompts" / "player.intent.questions.yaml"
    return int(yaml.safe_load(path.read_text(encoding="utf-8"))["version"])


def report(
    turns: list[dict], colds: list[dict], args: argparse.Namespace, model: str, label: str, options: dict,
    intent_model: str = "",
) -> str:  # fmt: skip
    generated = [t for t in turns if t["raw"].strip() and not t["fallback"]]
    lines = [f"Modèle {model} · options {options} · prompt v{load_prompt(TASK).version} · série {args.series}", ""]
    if any("layers" in t for t in turns):
        jeu = "JEU DE CONTRÔLE (jamais utilisé pour le réglage)" if args.series == "C" else "jeu de réglage (série F)"
        lines += [
            f"Filtre d'intention : {intent_model} · questions player.intent v{questions_version()} · seuil d'injection "
            f"{load_thresholds('player.intent')['injection']} · {jeu}"
            + (" · corpus non interrogé (--no-corpus)" if args.no_corpus else ""),
            "",
            *filter_table(turns),
            "",
        ]
    lines += ["| Critère | Cas | Taux |", "|---|---|---|"]
    for check, title in CRITERIA.items():
        good, total = rate(turns, check)
        if total:
            lines.append(f"| {title} | {good}/{total} | {good / total:.0%} |")
    secours = sum(t["fallback"] for t in turns)  # un échec du modèle, jamais une réponse valide
    lines.append(f"| Réponses de secours (échecs du modèle, 0 attendu) | {secours}/{len(turns)} | |")
    by_character = []
    for pid in load_sim_catalog()["personalities"]:
        mine = [t for t in generated if t["case"]["personality"] == pid]
        if mine:
            size = statistics.mean(len(t["reply"]) for t in mine)
            asking = sum("?" in t["reply"] for t in mine)
            by_character.append(f"{pid} {size:.0f} car., {asking}/{len(mine)} avec une question")
    lines += ["", "Caractères : " + " · ".join(by_character)]
    if generated:
        walls = sorted(t["wall"] for t in generated)
        gens = [t["timings"].get("génération", 0) for t in generated]
        tokens_in = statistics.mean(t["prompt_tokens"] for t in generated)
        tokens_out = statistics.mean(t["output_tokens"] for t in generated)
        lines.append(
            f"Latence à chaud ({len(generated)} répliques générées) : médiane {statistics.median(walls):.2f} s, "
            f"p90 {walls[int(0.9 * (len(walls) - 1))]:.2f} s, max {walls[-1]:.2f} s ; génération seule "
            f"{statistics.mean(gens):.2f} s ; {tokens_in:.0f} tokens en entrée, {tokens_out:.0f} en sortie ; "
            f"coupées par num_predict : {sum(t['truncated'] for t in generated)} ; rechargements du modèle pendant "
            f"la série : {sum(t['load_ms'] > RELOAD_MS for t in generated)}"
        )
    for t in colds:
        lines.append(
            f"À froid : {t['wall']:.1f} s au total (intention {t['timings'].get('intention', 0):.1f} s, génération "
            f"{t['timings'].get('génération', 0):.1f} s dont chargement du modèle {t['load_ms'] / 1000:.1f} s)"
        )
    summary = "\n".join(lines)
    out = Path(args.out) if args.out else get_settings().gmix_ai_dir / "evals" / "results" / f"npc.dialogue-{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(turns, colds, summary, label), encoding="utf-8")
    return summary + f"\n\nRapport : {out}"


def render(turns: list[dict], colds: list[dict], summary: str, label: str) -> str:
    out = [f"# Répliques réelles des agents PNJ · {label} · {datetime.date.today().isoformat()}", "", summary, ""]
    for t in colds + turns:
        case = t["case"]
        failed = [name for name, ok in t["checks"].items() if not ok]
        verdict = "KO " + ", ".join(failed) if failed else "OK"
        out += [
            f"### {t['id']} · {case['agent']} · {case['personality']} · {case['situation']} · {t['kind']} · {verdict}",
            "",
            "Faits : " + " | ".join(t["facts"]),
        ]
        out += [f"- mémoire · {m['speaker']} : {m['message']} → {m['reply']}" for m in t["memory"]]
        out += [f"**{SPEAKER}** : {t['message']}", ""]
        out += [f"**{t['name']}** : {t['reply'] or '(vide)'}", ""]
        if t["raw"] and t["raw"].strip() != t["reply"]:
            out += [f"_sortie brute : {t['raw'].strip()}_", ""]
        detail = [f"intention {t['intent']}", f"{t['wall']:.2f} s", f"{t['prompt_tokens']}+{t['output_tokens']} tokens"]
        if "layers" in t:
            seen = t["layers"]
            detail.append(
                f"lexical {'oui' if seen['lexical'] else 'non'} · tev1 seul {seen['tev1'] or 'passe'}"
                + (f" (injection {seen['p_injection']:.2f})" if seen["p_injection"] is not None else "")
            )
        if "coverage" in t:
            detail.append(f"fait clé repris à {t['coverage']:.0%}")
        if t["sources"]:
            detail.append("sources " + ", ".join(t["sources"]))
        if t["load_ms"] > RELOAD_MS:
            detail.append(f"chargement du modèle {t['load_ms'] / 1000:.1f} s")
        out += [" · ".join(detail) + ("  \n" + "; ".join(t["notes"]) if t["notes"] else ""), ""]
    return "\n".join(out)


def dump_facts(base: dict[str, Any], cases: list[dict]) -> int:
    seen = set()
    for case in cases:
        key = (case["agent"], case["situation"])
        if key in seen:
            continue
        seen.add(key)
        spec, view, agent = situation_for(base, case)
        briefing = view["briefings"][agent["id"]]
        print(f"[{case['agent']} / {case['situation']}] urgent={briefing['urgent']} · clé : {top_fact(view, agent)}")
        for fact in briefing["facts"]:
            print(f"    - {fact}")
    print(f"\nPrompt système (gabarit) : ~{estimate_tokens(load_prompt(TASK).system)} tokens")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--series", default="A",
        help="A, B ou all (la série F, filtres de réglage, est toujours jouée) ; F seule ; C : jeu de contrôle",
    )  # fmt: skip
    parser.add_argument("--model", help="alias de ai/models.yaml à évaluer pour la tâche (small, main, nano)")
    parser.add_argument("--label", help="nom du rapport : ai/evals/results/npc.dialogue-<label>.md")
    parser.add_argument("--out", help="chemin du rapport")
    parser.add_argument(
        "--set", nargs="*", default=[], metavar="OPTION=VALEUR", help="options Ollama : temperature=0.3"
    )
    parser.add_argument("--cold", type=int, default=0, help="mesures à froid avant la série")
    parser.add_argument("--only", nargs="*", help="identifiants de cas")
    parser.add_argument(
        "--intent-model", help="alias de ai/models.yaml pour le filtre player.intent (decide-fast, decide)"
    )
    parser.add_argument(
        "--no-corpus", action="store_true", help="ne pas interroger le corpus (PostgreSQL arrêté) : séries F et C"
    )
    parser.add_argument("--facts", action="store_true", help="affiche les faits du moteur par agent et situation")
    arguments = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    setup_logging("WARNING")
    sys.exit(asyncio.run(run(arguments)))
