"""Choix des assets d'une zone de lobby (étape 5 du pipeline de génération, docs/ai-runtime.md).

1. `candidate_assets` : présélection sémantique dans pgvector (embedding du besoin vs embeddings des
   descriptions du catalogue) : aucun token de génération.
2. `restrict_schema_to` : le schéma de sortie de la tâche game.asset_mapping n'accepte plus que ces ids
   (décodage contraint par `enum`) : le modèle ne peut pas inventer un asset.
"""

import copy
from dataclasses import dataclass
from typing import Any

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


def restrict_schema_to(schema: dict[str, Any], allowed_ids: list[str]) -> dict[str, Any]:
    """Copie du schéma asset_selection où `asset_ids` n'accepte que les ids candidats."""
    restricted = copy.deepcopy(schema)
    restricted["properties"]["zones"]["items"]["properties"]["asset_ids"]["items"] = {"enum": list(allowed_ids)}
    return restricted
