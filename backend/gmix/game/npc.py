"""Réplique d'un PNJ expert (flux 2 de docs/architecture.md) : filtre player.intent, RAG du domaine, npc.dialogue.

Les messages hors sujet ou les tentatives d'injection reçoivent une réponse fixe : aucun token de génération.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from gmix.game import engine
from gmix.llm.prompts import load_prompt, load_questions, load_thresholds
from gmix.llm.service import LLMService
from gmix.rag.retrieval import build_context, search

HISTORY_TURNS = 6  # au-delà, docs/ai-runtime.md prévoit un résumé (à faire)
OFF_TOPIC_REPLY = "Restons sur l'entreprise, le temps presse. Qu'est-ce qui vous inquiète dans la situation actuelle ?"
INJECTION_REPLY = "Je ne peux vous aider que sur l'entreprise et vos décisions. Quelle est votre question ?"


def game_summary(spec: dict[str, Any], state: dict[str, Any]) -> str:
    phase = spec["phases"][state["phase_index"]]
    values = engine.kpi_values(spec, state)
    kpis = ", ".join(
        f"{k['name']} {values.get(k['id'], k['initial']):g} {k['unit']} (cible {k['target']:g})" for k in spec["kpis"]
    )
    return f"Phase « {phase['title']} » : {phase['goal']} Indicateurs : {kpis}."


async def npc_reply(
    llm: LLMService,
    session: AsyncSession,
    *,
    spec: dict[str, Any],
    state: dict[str, Any],
    domain: str,
    npc: dict[str, Any],
    message: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    phase_title = spec["phases"][state["phase_index"]]["title"]
    questions = load_questions("player.intent")
    verdict = await llm.decide("player.intent", f"Phase : {phase_title}\nJoueur : {message}", questions)
    answers = verdict.get("answers") or {}
    intent = (answers.get("intent") or {}).get("choice")
    if float((answers.get("injection") or {}).get("noul") or 0) >= load_thresholds("player.intent")["injection"]:
        return {"reply": INJECTION_REPLY, "intent": "injection", "sources": []}
    if intent == "hors_sujet":
        return {"reply": OFF_TOPIC_REPLY, "intent": intent, "sources": []}

    task, _ = await llm.resolve("npc.dialogue")
    vector = await llm.embed_query(message)
    hits = await search(session, query_vector=vector, query_text=message, domain=domain, k=task.rag.top_k)
    context, sources = build_context(hits, task.rag.max_context_tokens)
    messages = load_prompt("npc.dialogue").render(
        npc_name=npc["name"],
        npc_job=npc["job"],
        npc_personality=npc["personality"],
        npc_expertise=", ".join(npc["expertise"]),
        npc_goals="; ".join(npc["dialogue_goals"]),
        company_name=spec["context"]["company"]["name"],
        game_state=game_summary(spec, state),
        rag_context=context or "(aucun extrait : reste général et dis que tu dois vérifier)",
        player_message=message,
    )
    messages = messages[:1] + history[-HISTORY_TURNS:] + messages[1:]
    result = await llm.text("npc.dialogue", messages)
    return {
        "reply": result.content.strip(),
        "intent": intent,
        "sources": [{"ref": s["ref"], "title": s["title"], "page": s["page"]} for s in sources],
    }
