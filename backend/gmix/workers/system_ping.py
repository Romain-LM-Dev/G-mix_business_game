"""Worker de diagnostic : prouve la chaîne API -> Kafka -> worker -> Ollama (chat, embedding, décision)
-> Kafka -> API -> WebSocket -> Godot.

Lancement : scripts\\worker.ps1 system_ping   (ou python -m gmix.workers.system_ping)
Sert de modèle de référence pour écrire un worker : consommation, réponse corrélée (reply), DLQ.
"""

import logging
import time
from collections.abc import Awaitable
from typing import Any

from gmix.llm.service import LLMService
from gmix.messaging.envelope import Envelope
from gmix.messaging.kafka import EventProducer, consume
from gmix.messaging.topics import SYSTEM_PING, SYSTEM_PONG
from gmix.workers.runtime import run_worker

log = logging.getLogger("gmix.worker.system")
SOURCE = "worker-system"


async def _check(step: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        result = await step
        return {"ok": True, "ms": round((time.perf_counter() - start) * 1000), **result}
    except Exception as exc:
        return {
            "ok": False,
            "ms": round((time.perf_counter() - start) * 1000),
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


async def _chat(llm: LLMService) -> dict[str, Any]:
    result = await llm.text("system.ping", [{"role": "user", "content": "Réponds uniquement par le mot : pong"}])
    return {"model": result.usage.model, "answer": result.content.strip()[:60], "tokens": result.usage.total_tokens}


async def _embedding(llm: LLMService) -> dict[str, Any]:
    vector = await llm.embed_query("Comment réduire le besoin en fonds de roulement ?")
    return {"dims": len(vector)}


async def _decision(llm: LLMService) -> dict[str, Any]:
    data = await llm.decide(
        "system.ping.decision",
        "Joueur : « Combien nous coûterait l'affacturage de nos créances clients ? »",
        {
            "intent": {
                "type": "choice",
                "instructions": "Quelle est l'intention du joueur ?",
                "criteria": {
                    "question_metier": "Il pose une question sur un concept métier",
                    "decision": "Il annonce une décision de jeu",
                    "hors_sujet": "Message sans rapport avec la partie",
                },
            }
        },
    )
    answer = (data.get("answers") or {}).get("intent") or {}
    report: dict[str, Any] = {"answer": answer.get("choice"), "emulated": bool(data.get("emulated"))}
    if not data.get("emulated"):
        report["raw"] = data
    return report


async def main() -> None:
    llm = LLMService.from_settings()
    producer = EventProducer()
    await producer.start()

    async def handle(event: Envelope) -> None:
        checks = {
            "chat": await _check(_chat(llm)),
            "embedding": await _check(_embedding(llm)),
            "decision": await _check(_decision(llm)),
        }
        log.info("ping %s traité : %s", event.id, {name: c["ok"] for name, c in checks.items()})
        reply = event.reply("system.pong", SOURCE, {"echo": event.payload.get("message"), "checks": checks})
        await producer.publish(SYSTEM_PONG, reply)

    try:
        await consume([SYSTEM_PING], handle, group_id="worker-system", dlq=producer)
    finally:
        await producer.stop()
        await llm.aclose()


if __name__ == "__main__":
    run_worker(main)
