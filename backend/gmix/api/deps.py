import asyncio
import contextlib
import logging

from fastapi import FastAPI, HTTPException, Request

from gmix.messaging.envelope import Envelope
from gmix.messaging.kafka import EventProducer
from gmix.messaging.topics import Topic

log = logging.getLogger("gmix.api")
_producer_lock = asyncio.Lock()


async def ensure_producer(app: FastAPI) -> EventProducer | None:
    """Producteur Kafka partagé, (re)créé à la demande si Kafka était indisponible."""
    if app.state.producer is not None:
        return app.state.producer
    async with _producer_lock:
        if app.state.producer is None:
            producer = EventProducer()
            try:
                await asyncio.wait_for(producer.start(), timeout=10)
            except Exception as exc:
                log.warning("Producteur Kafka indisponible : %s", exc)
                with contextlib.suppress(Exception):
                    await producer.stop()
                return None
            app.state.producer = producer
    return app.state.producer


async def producer_dependency(request: Request) -> EventProducer:
    producer = await ensure_producer(request.app)
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka indisponible (scripts\\infra.ps1 up)")
    return producer


async def publish(request: Request, topic: Topic, event: Envelope, *, required: bool = False) -> bool:
    """Publie sur Kafka. `required=False` (audit, diffusion d'état) : l'action déjà enregistrée en base
    n'échoue pas si Kafka est indisponible, l'incident est journalisé."""
    producer = await ensure_producer(request.app)
    if producer is None:
        if required:
            raise HTTPException(status_code=503, detail="Kafka indisponible (scripts\\infra.ps1 up)")
        log.warning("Événement %s non publié : Kafka indisponible", event.type)
        return False
    await producer.publish(topic, event)
    return True
