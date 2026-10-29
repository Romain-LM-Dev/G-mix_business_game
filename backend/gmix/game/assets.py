"""Recherche sémantique dans le catalogue d'assets (pgvector) : embedding d'un besoin comparé aux embeddings des
descriptions du catalogue, sans aucun token de génération. Sert à l'évaluation `python -m gmix.tools.assets
evaluate` et au choix d'assets pour de futurs gabarits."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gmix.db.models import Asset
from gmix.llm.service import LLMService


@dataclass(slots=True)
class AssetCandidate:
    id: str
    name: str
    category: str
    distance: float  # distance cosinus : plus petit = plus proche du besoin


async def candidate_assets(
    session: AsyncSession, llm: LLMService, need: str, *, k: int = 8, categories: list[str] | None = None
) -> list[AssetCandidate]:
    distance = Asset.embedding.cosine_distance(await llm.embed_query(need))
    query = select(Asset.id, Asset.name, Asset.category, distance.label("distance")).where(Asset.embedding.is_not(None))
    if categories:
        query = query.where(Asset.category.in_(categories))
    rows = await session.execute(query.order_by(distance).limit(k))
    return [AssetCandidate(row.id, row.name, row.category, float(row.distance)) for row in rows]
