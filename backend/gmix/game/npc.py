"""Agents PNJ des business games simulés : rôle, caractère, tâches et mémoire (docs/decisions/0006).

Chaque réplique part des informations essentielles calculées par le moteur (`public_state()["briefings"]`) :
le modèle les dit avec le caractère de l'agent, en une ou deux phrases, et se souvient des derniers échanges du
lobby avec cet agent (table npc_memories, tous joueurs confondus : « comme je l'ai dit à Léa… »).
Message hors sujet ou tentative d'injection : réponse fixe, aucun token généré.
Modèle indisponible, trop lent ou muet : l'agent répond quand même (`fallback_reply`, ses faits sans modèle).

Mémoire partagée = surface d'attaque : un joueur ne doit pas pouvoir y déposer une consigne rejouée aux autres.
`looks_like_injection` (lexical, déterministe, avant tout modèle) et le filtre tev1 (faible : 3/8 attaques variées)
décident via `should_remember` ; un tour douteux n'est ni enregistré ni rejoué (`result["remember"]`).
"""

import asyncio
import json
import logging
import re
import unicodedata
from collections.abc import Awaitable
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from gmix.llm.ollama import OllamaError
from gmix.llm.prompts import load_prompt, load_questions, load_thresholds
from gmix.llm.service import BudgetExceeded, LLMService, ModelUnavailable
from gmix.rag.retrieval import build_context, search

log = logging.getLogger("gmix.game.npc")

DOMAIN = "supply-chain"
MEMORY_TURNS = 6
MAX_CHARS = 320
# Délai (s) accordé au modèle pour toute la réplique (intention, corpus, génération). Le premier appel après un
# démarrage charge le modèle en 10 à 20 s ; passé ce délai, l'agent répond par son secours plutôt que de faire attendre.
REPLY_TIMEOUT_S = 60
# Pannes du modèle qui déclenchent le secours (JSONDecodeError : sortie invalide du modèle de décision émulé).
# Toute autre exception est un bug du code et reste visible.
MODEL_ERRORS = (ModelUnavailable, OllamaError, httpx.HTTPError, BudgetExceeded, json.JSONDecodeError)
OFF_TOPIC_REPLY = "On a du travail, restons sur l'entreprise. Qu'est-ce qui te préoccupe cette semaine ?"
INJECTION_REPLY = "Je ne peux t'aider que sur l'entreprise et vos décisions. Quelle est ta question ?"
QUOTES = '"«»“” '
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def short_reply(text: str, name: str) -> str:
    """Deux phrases au plus, sans le nom de l'agent en préfixe ni guillemets : un vrai échange oral."""
    text = text.strip().strip(QUOTES)
    if text.lower().startswith(name.lower()):
        text = text[len(name) :].lstrip(" :,-—").strip(QUOTES)
    sentences = [s for s in _SENTENCE.split(text) if s]
    reply = " ".join(sentences[:2])
    return reply if len(reply) <= MAX_CHARS else reply[: MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"


def fallback_reply(agent: dict[str, Any], view: dict[str, Any]) -> str:
    """Réplique sans modèle : le préfixe du caractère et le fait le plus important (le premier urgent, sinon le
    premier fait) ; sans aucun fait, une phrase neutre qui nomme la mission. Déterministe, deux phrases au plus."""
    brief = view["briefings"][agent["id"]]
    if brief["line"]:  # préfixe + premier fait urgent, déjà composés par le moteur
        text = brief["line"]
    elif brief["facts"]:
        text = f"{agent['personality']['prefix']} {brief['facts'][0]}"
    else:
        task = next(iter(agent["tasks"]), "suivre l'activité du site")
        text = f"Rien de particulier à signaler pour l'instant : je suis là pour {task}."
    return short_reply(text, agent["name"])


# --- pré-filtre lexical des injections (français et anglais) -----------------------------------------------------
# Texte normalisé : minuscules, sans accents ni caractères invisibles, apostrophes en espaces ("n'es" -> "n es").
# Choix : peu de faux positifs plutôt que beaucoup de détections (tev1 couvre le reste). Un verbe d'abandon seul
# ("on ignore le délai du fournisseur", "oublie ce que j'ai dit, je commande 40 unités") n'est JAMAIS une alerte :
# il faut en plus un objet de consigne (instructions, rôle, prompt, ou règles/consignes/limites précédées de
# « tes / toutes les / previous »). Un faux positif ne bloque pas la partie (le dialogue ne passe aucune décision au
# moteur) : l'agent redit simplement ses faits et le tour n'est pas mémorisé. Limite connue : « ignore toutes les
# consignes. » (sans complément) est signalé, « ignore les instructions de montage » ne l'est pas.
_VERB = (
    r"\b(?:ignor\w*|oubli\w*|neglig\w*|desobei\w*|contourn\w*|annul\w*|efface\w*|supprim\w*"
    r"|forget\w*|disregard\w*|override\w*|bypass\w*)\b(?:\s+\w+){0,3}?\s+"
)
_MARK = (  # possessif, « précédent » ou « tous (les) »
    r"(?:tes|ton|ta|vos|votre|your|previous|prior|earlier|(?:toutes?|tous|all|any|every)(?:\s+(?:les|tes|vos|the|your))?)"
)
_WEAK = r"(?:consignes?|regles?|rules?|guidelines?|limites?|contraintes?|restrictions?|constraints?)"
_STRONG = r"(?:instructions?|directives?|prompts?|roles?|personnages?|programmation)"
_NOT_BUSINESS = r"(?!\s+(?:de|du|des|d|pour|sur|concernant|about|of|for)\b)"  # « les règles de calcul » : métier
_BEFORE = r"(?:precedent\w*|anterieur\w*|ci-dessus|above)"
_SOMEONE = r"(?:un|une|le|la|l|d|mon|ma|mes|notre)"
_REVEAL = (  # verbes qui demandent de montrer ou dire
    r"(?:revele|revelez|reveal|affiche|affichez|montre|montrez|show|repete|repetez|repeat|print|display"
    r"|dis|dites|donne|donnez|tell|give|ecris|ecrivez|write)"
)
_INJECTION = re.compile(
    "|".join(
        [
            # abandonner ses consignes : « ignore toutes tes instructions », « oublie ton rôle », « forget your rules »
            rf"{_VERB}{_MARK}\s+(?:\w+\s+){{0,2}}?(?:{_STRONG}|{_WEAK})\b{_NOT_BUSINESS}",
            rf"{_VERB}{_STRONG}\b{_NOT_BUSINESS}",  # « ignore les instructions et… »
            rf"{_VERB}(?:{_STRONG}|{_WEAK})(?:\s+\w+){{0,2}}?\s+{_BEFORE}\b",
            r"\b(?:ignore|disregard|forget)\s+(?:the\s+|all\s+)?(?:above|everything)\b",
            # changer de personnage : « tu es maintenant… », « tu n'es plus un employé », « agis comme… »
            rf"\b(?:tu|vous)\s+(?:n\s+(?:es|etes)\s+plus|(?:es|etes)\s+(?:maintenant|desormais|a\s+present|devenu\w*))"
            rf"\s+{_SOMEONE}\b",
            r"\byou\s+are\s+(?:now|no\s+longer)\b",
            r"\ba\s+partir\s+de\s+maintenant\W+(?:tu|vous|reponds|repondez|parle|parlez|agis|agissez|obeis|obeissez"
            r"|ignore|ignorez|oublie|oubliez)\b",
            r"\bfrom\s+now\s+on\W+(?:you|answer|reply|respond|act|ignore|forget)\b",
            r"\b(?:fais|faites)\s+comme\s+si\s+(?:tu|vous)\b",
            # impératif seulement : « tu agis comme un vrai chef » est un compliment
            r"(?<!\btu )(?<!\bvous )\b(?:agis|agissez|comporte|comportez|joue|jouez)\w*(?:-toi|-vous)?\s+comme\s+"
            r"(?:si|une?|l|le|la|mon|ma)\b",
            r"\b(?:parle|parlez|reponds|repondez)\w*(?:-moi)?\s+comme\s+(?:une?\s+)?"
            r"(?:ia|chatgpt|gpt|assistant|robot|chatbot|llm|machine)\b",
            r"\b(?:pretend|act\s+as|behave\s+as|role\s*play|fais\s+semblant|faites\s+semblant)\b",
            r"\b(?:joue|jouez|incarne|incarnez|adopte|adoptez)\s+(?:le|un|ton|ce|votre)\s+(?:role|personnage)\b",
            r"\b(?:sors|sortez|sortir|quitte|quittez)\s+(?:de\s+)?(?:ton|ta|votre|son)\s+(?:role|personnage|character)\b",
            r"\b(?:reponds|repondez|agis|agissez|parle|parlez)\w*\s+(?:\w+\s+){0,2}sans\s+(?:aucune?\s+)?"
            r"(?:limites?|restrictions?|regles?|filtres?|contraintes?|censure)\b",
            r"\bobei\w*\W+(?:\w+\W+){0,3}(?:mes|mon)\s+(?:ordres?|instructions?|commandes?|consignes?)\b",
            # révéler le prompt, la configuration, la solution
            r"\b(?:prompts?|jailbreak|chatgpt|openai|llm|chatbot)\b",
            r"\b(?:system|systeme)\s+message\b|\bmessage\s+systeme\b|\binstructions?\s+systeme\b",
            r"\bmode\s+(?:developpeur|dieu)\b|\bdeveloper\s+mode\b",
            rf"\b{_REVEAL}\b(?:-moi|\s+me)?(?:\s+\w+){{0,2}}?\s+(?:tes|ton|ta|vos|votre|your)\s+(?:\w+\s+)?"
            r"(?:instructions?|consignes?|regles?|directives?|programmation|rules?)\b",
            r"\b(?:solutions?\s+(?:complete|finale|du\s+jeu)|configuration\s+du\s+jeu|cheat\w*|triche\w*"
            r"|(?:reponses?|chiffres|valeurs|donnees|parametres|regles)\s+(?:cach\w+|secret\w*|internes?|confidentiel\w*)"
            r"|(?:rapporte|donne)\w*\s+le\s+plus\s+de\s+points)\b",
            r"\bnouvelles?\s+(?:instructions?|directives?)\b|\bnew\s+(?:instructions?|rules)\b",
            # faux en-têtes de rôle : « System: … », « [INST] », « <|im_start|> »
            r"^\W*(?:system|systeme|assistant|developer|developpeur)\s*[\]>*]*\s*:",
            r"<\|\w+\|>|\[/?inst\]|</?system>|###\s*(?:system|instruction)",
        ]
    ),
    re.MULTILINE,
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).lower()  # NFKD : les lettres pleine chasse deviennent ASCII
    text = "".join(c for c in text if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")
    return re.sub(r"['’`´]", " ", text)


def looks_like_injection(message: str) -> bool:
    """Vrai si le message tente de sortir l'agent de son rôle, de lui donner des consignes ou d'en extraire le
    prompt ou la solution. Pur et déterministe, sans modèle : appelé avant tout appel au LLM et sur les messages
    déjà mémorisés avant sa mise en place."""
    return _INJECTION.search(_normalize(message)) is not None


def should_remember(message: str, *, intent: str | None, injection: float | None) -> bool:
    """Vrai si le tour peut entrer dans npc_memories (donc être rejoué à tous les joueurs du lobby).
    Refusé : injection lexicale, injection selon tev1 (`injection` >= seuil de player.intent), hors-sujet.
    `injection` à None = tev1 n'a pas répondu : échec sûr, seul le pré-filtre lexical décide."""
    if looks_like_injection(message) or intent == "hors_sujet":
        return False
    return injection is None or injection < load_thresholds("player.intent")["injection"]


async def agent_reply(
    llm: LLMService,
    session: AsyncSession,
    *,
    spec: dict[str, Any],
    view: dict[str, Any],
    agent: dict[str, Any],
    message: str,
    speaker: str,
    memory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Réplique de l'agent : {reply, intent, sources, fallback, remember}. Modèle en panne, trop lent ou muet :
    `fallback_reply` et `fallback` vrai, jamais d'agent muet. `remember` faux = tour douteux (injection, hors-sujet) :
    la route ne l'enregistre pas dans npc_memories. Message d'injection lexicale : réponse sans appel au modèle."""
    if looks_like_injection(message):
        return {"reply": fallback_reply(agent, view), "intent": "injection", "sources": [], "fallback": False,
                "remember": False}  # fmt: skip
    loop = asyncio.get_running_loop()
    deadline = loop.time() + REPLY_TIMEOUT_S

    async def within(call: Awaitable[Any]) -> Any:
        # Un seul délai pour tous les appels au modèle. La recherche SQL du corpus reste hors délai : l'annuler en
        # vol laisserait la session de la route inutilisable.
        try:
            return await asyncio.wait_for(call, max(deadline - loop.time(), 0))
        except TimeoutError as exc:
            raise ModelUnavailable(f"pas de réponse du modèle en {REPLY_TIMEOUT_S} s") from exc

    intent, injection, reason = None, None, "réponse vide"  # injection : probabilité de tev1, None si absente

    def turn(reply: str, sources: list[dict[str, Any]], fallback: bool) -> dict[str, Any]:
        remember = should_remember(message, intent=intent, injection=injection)
        return {"reply": reply, "intent": intent, "sources": sources, "fallback": fallback, "remember": remember}

    try:
        verdict = await within(
            llm.decide("player.intent", f"Semaine {view['week']}\nJoueur : {message}", load_questions("player.intent"))
        )
        answers = verdict.get("answers") or {}
        intent = (answers.get("intent") or {}).get("choice")
        noul = (answers.get("injection") or {}).get("noul")
        injection = float(noul) if isinstance(noul, int | float) else None  # absente ou illisible : échec sûr
        if injection is not None and injection >= load_thresholds("player.intent")["injection"]:
            intent = "injection"
            return turn(INJECTION_REPLY, [], False)
        if intent == "hors_sujet":
            return turn(OFF_TOPIC_REPLY, [], False)

        context, sources = "", []
        if intent == "question_metier":  # le corpus seulement pour une question de fond : réponses courtes et rapides
            task, _ = await within(llm.resolve("npc.dialogue"))
            vector = await within(llm.embed_query(message))
            hits = await search(session, query_vector=vector, query_text=message, domain=DOMAIN, k=task.rag.top_k)
            context, sources = build_context(hits, task.rag.max_context_tokens)
        notions = [n for n in spec["notions"] if n["id"] in agent["notions"]]
        messages = load_prompt("npc.dialogue").render(
            npc_name=agent["name"],
            npc_job=agent["job"],
            company=spec["meta"]["company"],
            personality=agent["personality"]["traits"],
            style=agent["personality"]["style"],
            tasks="; ".join(agent["tasks"]),
            week=view["week"],
            weeks=view["weeks"],
            facts="\n".join(f"- {fact}" for fact in view["briefings"][agent["id"]]["facts"]) or "- rien de particulier",
            notions="\n".join(f"- {n['title']} : {n['text']}" for n in notions) or "- aucune",
            rag_context=context or "aucun",
            player_message=f"{speaker} : {message}",
        )
        history: list[dict[str, str]] = []
        # Défense en profondeur : un échange d'injection mémorisé avant ce filtre n'est jamais rejoué.
        for past in [t for t in memory if not looks_like_injection(t["message"])][-MEMORY_TURNS:]:
            history += [
                {"role": "user", "content": f"{past['speaker']} : {past['message']}"},
                {"role": "assistant", "content": past["reply"]},
            ]
        result = await within(llm.text("npc.dialogue", messages[:1] + history + messages[1:]))
        if reply := short_reply(result.content, agent["name"]):
            sources = [{"ref": s["ref"], "title": s["title"], "page": s["page"]} for s in sources]
            return turn(reply, sources, False)
    except MODEL_ERRORS as exc:
        reason = repr(exc)
    log.warning("agent %s : réplique de secours (%s)", agent["id"], reason)
    return turn(fallback_reply(agent, view), [], True)
