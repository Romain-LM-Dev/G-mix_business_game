"""Initialise l'infrastructure applicative, de façon idempotente :
topics Kafka, buckets S3, migrations Alembic, synchronisation des domaines (ai/domains.yaml -> table domains).

Usage : python -m gmix.bootstrap   (appelé par scripts\\infra.ps1 up)
"""

import asyncio
import logging

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects.postgresql import insert

from gmix import storage
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import Domain
from gmix.domains import load_domains
from gmix.logging_setup import setup_logging
from gmix.messaging.kafka import ensure_topics
from gmix.settings import BACKEND_DIR, get_settings

log = logging.getLogger("gmix.bootstrap")


def migrate() -> None:
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")


async def sync_domains() -> int:
    domains = load_domains()
    async with get_sessionmaker()() as session:
        for order, domain in enumerate(domains):
            values = {
                "slug": domain.slug,
                "name": domain.name,
                "description": domain.description,
                "is_active": domain.active,
                "sort_order": order,
                "meta": domain.model_dump(include={"competencies", "kpis", "references", "roles"}),
            }
            stmt = insert(Domain).values(**values)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[Domain.slug],
                    set_={key: stmt.excluded[key] for key in values if key != "slug"},
                )
            )
        await session.commit()
    return len(domains)


async def main() -> None:
    setup_logging(get_settings().log_level)
    log.info("Topics Kafka créés : %s", await ensure_topics() or "aucun (déjà présents)")
    log.info("Buckets S3 créés : %s", await storage.ensure_buckets() or "aucun (déjà présents)")
    await asyncio.to_thread(migrate)
    log.info("Migrations Alembic appliquées (head)")
    log.info("Domaines synchronisés : %d", await sync_domains())
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
