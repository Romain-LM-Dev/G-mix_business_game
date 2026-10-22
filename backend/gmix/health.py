"""Diagnostic des dépendances (base, Kafka, stockage, Ollama) : /health et `python -m gmix.tools.doctor`."""

import asyncio
import time
from collections.abc import Awaitable
from typing import Any

from sqlalchemy import text

from gmix import storage
from gmix.db import get_engine
from gmix.llm.service import LLMService
from gmix.messaging.kafka import list_topics
from gmix.messaging.topics import ALL_TOPICS
from gmix.settings import get_settings


async def _timed(name: str, check: Awaitable[dict[str, Any]], timeout_s: float = 6.0) -> tuple[str, dict[str, Any]]:
    start = time.perf_counter()
    try:
        detail = await asyncio.wait_for(check, timeout_s)
        ok = detail.pop("ok")
    except Exception as exc:
        ok, detail = False, {"error": f"{type(exc).__name__}: {exc}"[:300]}
    return name, {"ok": ok, "latency_ms": round((time.perf_counter() - start) * 1000), **detail}


async def _database() -> dict[str, Any]:
    async with get_engine().connect() as conn:
        pgvector = await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        has_alembic = await conn.scalar(text("SELECT to_regclass('alembic_version') IS NOT NULL"))
        revision = await conn.scalar(text("SELECT version_num FROM alembic_version")) if has_alembic else None
    return {"ok": bool(pgvector and revision), "pgvector": pgvector, "migration": revision}


async def _kafka() -> dict[str, Any]:
    topics = await list_topics()
    missing = [t.name for t in ALL_TOPICS if t.name not in topics]
    return {"ok": not missing, "topics": sum(1 for t in topics if t.startswith("gmix.")), "missing_topics": missing}


async def _storage() -> dict[str, Any]:
    buckets = await storage.list_buckets()
    missing = [b for b in get_settings().buckets if b not in buckets]
    return {"ok": not missing, "missing_buckets": missing}


async def _ollama(llm: LLMService) -> dict[str, Any]:
    version = await llm.client.version()
    installed = await llm.installed(refresh=True)
    missing = [tag for tag in llm.catalog.required_tags() if tag not in installed]
    optional = sorted({m.tag for m in llm.catalog.models.values() if not m.required and m.tag not in installed})
    return {"ok": not missing, "version": version, "missing_models": missing, "missing_optional_models": optional}


async def full_health(llm: LLMService) -> dict[str, Any]:
    results = dict(
        await asyncio.gather(
            _timed("database", _database()),
            _timed("kafka", _kafka()),
            _timed("storage", _storage()),
            _timed("ollama", _ollama(llm)),
        )
    )
    return {"status": "ok" if all(r["ok"] for r in results.values()) else "degraded", "services": results}
