"""Worker de génération des business games : consomme gmix.generation.commands, exécute gmix.game.generation et
publie la progression sur gmix.generation.events (relayée au formateur par WebSocket).

Lancement : scripts\\worker.ps1 generation   (ou python -m gmix.workers.generation)
Un job à la fois : le GPU n'héberge qu'un grand modèle (6 Go de VRAM).
"""

import logging
import uuid

from gmix.db import get_sessionmaker
from gmix.db.models import BusinessGame, GameStatus, GenerationJob, JobStatus
from gmix.domains import load_domains
from gmix.game.generation import GameRequest, GenerationFailed, GenerationRefused, Generator
from gmix.llm.service import LLMService
from gmix.messaging.envelope import Envelope
from gmix.messaging.kafka import EventProducer, consume
from gmix.messaging.topics import GENERATION_COMMANDS, GENERATION_EVENTS
from gmix.workers.runtime import run_worker

log = logging.getLogger("gmix.worker.generation")
SOURCE = "worker-generation"
MAX_JOB_MS = 45 * 60 * 1000  # au-delà, Kafka croit le worker mort et confie le job à un autre (en double)


async def run_job(llm: LLMService, producer: EventProducer, command: Envelope) -> None:
    sessions = get_sessionmaker()
    async with sessions() as session:
        job = await session.get(GenerationJob, uuid.UUID(command.payload["job_id"]))
        if job is None or job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            log.info("Commande %s ignorée : job absent ou déjà terminé", command.id)  # message relivré
            return
        game = await session.get(BusinessGame, job.business_game_id)
        job.status = JobStatus.RUNNING
        await session.commit()
        base = {"job_id": str(job.id), "game_id": str(game.id)}

        async def progress(stage: str, percent: int) -> None:
            job.stage, job.progress = stage, percent
            await session.commit()
            reply = command.reply("generation.progress", SOURCE, base | {"stage": stage, "progress": percent})
            await producer.publish(GENERATION_EVENTS, reply)

        generator = Generator(llm, sessions, progress)
        try:
            domain = {d.slug: d for d in load_domains()}[game.domain_slug]
            result = await generator.run(GameRequest(domain=domain, brief=game.brief, **game.params))
        except Exception as exc:
            if isinstance(exc, GenerationRefused | GenerationFailed):
                message = str(exc)
            else:
                log.exception("Génération %s en échec", job.id)
                message = f"Erreur interne ({type(exc).__name__}) : voir les journaux du worker"
            job.status, job.error, job.usage = JobStatus.FAILED, message, generator.usage
            game.status = GameStatus.FAILED
            game.review = {"warnings": [], "repairs": generator.repairs}
            await session.commit()
            reply = base | {"error": message, "refused": isinstance(exc, GenerationRefused)}
            await producer.publish(GENERATION_EVENTS, command.reply("generation.failed", SOURCE, reply))
            return
        game.spec, game.title, game.status = result.spec, result.spec["meta"]["title"][:200], GameStatus.READY
        game.spec_version += 1
        game.review = {"warnings": result.warnings, "repairs": result.repairs}
        job.status, job.stage, job.progress, job.usage = JobStatus.SUCCEEDED, "done", 100, result.usage
        await session.commit()
        payload = base | {"title": game.title, "warnings": len(result.warnings), "repairs": len(result.repairs)}
        await producer.publish(GENERATION_EVENTS, command.reply("generation.completed", SOURCE, payload))
        log.info("Génération %s terminée : %s (%d avertissements)", job.id, game.title, len(result.warnings))


async def main() -> None:
    llm = LLMService.from_settings()
    producer = EventProducer()
    await producer.start()

    async def handle(event: Envelope) -> None:
        if event.type == "generation.requested":
            await run_job(llm, producer, event)

    try:
        await consume(
            [GENERATION_COMMANDS], handle, group_id="worker-generation", dlq=producer, max_poll_interval_ms=MAX_JOB_MS
        )
    finally:
        await producer.stop()
        await llm.aclose()


if __name__ == "__main__":
    run_worker(main)
