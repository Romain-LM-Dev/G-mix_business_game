"""Production / consommation Kafka (aiokafka) et création des topics."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from gmix.messaging.envelope import Envelope
from gmix.messaging.topics import ALL_TOPICS, DLQ, Topic
from gmix.settings import get_settings

log = logging.getLogger(__name__)

Handler = Callable[[Envelope], Awaitable[None]]


class EventProducer:
    def __init__(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=get_settings().kafka_bootstrap,
            acks="all",
            enable_idempotence=True,
            linger_ms=5,
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, topic: Topic, event: Envelope, key: str | None = None) -> None:
        partition_key = key or str(event.lobby_id or event.correlation_id or event.id)
        await self._producer.send_and_wait(topic.name, event.to_bytes(), key=partition_key.encode())


async def consume(
    topics: Iterable[Topic],
    handler: Handler,
    *,
    group_id: str | None,
    dlq: EventProducer | None = None,
    from_latest: bool = False,
    max_poll_interval_ms: int = 300_000,
) -> None:
    """Boucle de consommation « au moins une fois ».

    group_id=None : chaque instance reçoit tout (relais WebSocket de l'API) et ne commite rien.
    Un message qui fait échouer le handler part en DLQ puis est commité (pas de blocage « poison pill »).
    `max_poll_interval_ms` : durée maximale d'un traitement ; au-delà, Kafka considère le consommateur mort.
    S'arrête par annulation de la tâche.
    """
    names = [t.name for t in topics]
    consumer = AIOKafkaConsumer(
        *names,
        bootstrap_servers=get_settings().kafka_bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="latest" if from_latest else "earliest",
        max_poll_interval_ms=max_poll_interval_ms,
    )
    await consumer.start()
    log.info("Consommation de %s (groupe=%s)", ", ".join(names), group_id)
    try:
        async for msg in consumer:
            try:
                await handler(Envelope.from_bytes(msg.value))
            except Exception as exc:
                log.exception("Échec du traitement %s[%s]@%s", msg.topic, msg.partition, msg.offset)
                if dlq is not None:
                    await dlq.publish(
                        DLQ,
                        Envelope(
                            type="dlq.message",
                            source=group_id or "consumer",
                            payload={
                                "topic": msg.topic,
                                "partition": msg.partition,
                                "offset": msg.offset,
                                "error": repr(exc)[:2000],
                                "raw": msg.value.decode(errors="replace")[:10_000],
                            },
                        ),
                    )
            if group_id is not None:
                await consumer.commit()
    finally:
        await consumer.stop()


async def ensure_topics() -> list[str]:
    """Crée les topics manquants de ALL_TOPICS. Idempotent. Retourne les noms créés."""
    admin = AIOKafkaAdminClient(bootstrap_servers=get_settings().kafka_bootstrap)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        missing = [
            NewTopic(
                name=t.name,
                num_partitions=t.partitions,
                replication_factor=1,
                topic_configs={"retention.ms": str(t.retention_ms)},
            )
            for t in ALL_TOPICS
            if t.name not in existing
        ]
        if missing:
            await admin.create_topics(missing)
        return [t.name for t in missing]
    finally:
        await admin.close()


async def list_topics(timeout_s: float = 5.0) -> set[str]:
    async def _list() -> set[str]:
        admin = AIOKafkaAdminClient(bootstrap_servers=get_settings().kafka_bootstrap, request_timeout_ms=4000)
        await admin.start()
        try:
            return set(await admin.list_topics())
        finally:
            await admin.close()

    return await asyncio.wait_for(_list(), timeout_s)
