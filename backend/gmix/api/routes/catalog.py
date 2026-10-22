from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from gmix.api.auth import Session
from gmix.db.models import KnowledgeChunk
from gmix.domains import load_domains
from gmix.llm.catalog import load_catalog

router = APIRouter(prefix="/api/v1", tags=["catalogues"])


@router.get("/domains")
async def list_domains(session: Session) -> list[dict[str, Any]]:
    """Domaines d'expertise proposés au formateur, avec la taille de leur corpus RAG (0 : contenu non sourcé)."""
    rows = await session.execute(select(KnowledgeChunk.domain_slug, func.count()).group_by(KnowledgeChunk.domain_slug))
    chunks = dict(rows.tuples().all())
    return [
        d.model_dump(exclude={"active"}) | {"corpus_chunks": chunks.get(d.slug, 0)} for d in load_domains() if d.active
    ]


@router.get("/ai/tasks")
async def list_ai_tasks() -> dict[str, dict[str, Any]]:
    """Routage tâche IA -> modèle (lecture seule ; utile pour l'écran admin et le débogage)."""
    catalog = load_catalog()
    return {
        name: {
            "model": catalog.models[task.model].name,
            "fallback": catalog.models[task.fallback].name if task.fallback else None,
            "output": task.output,
            "description": task.description,
        }
        for name, task in catalog.tasks.items()
    }
