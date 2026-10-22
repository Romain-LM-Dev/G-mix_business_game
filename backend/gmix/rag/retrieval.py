"""Recherche hybride : similarité vectorielle (pgvector, HNSW cosinus) + plein texte français,
fusionnées par Reciprocal Rank Fusion. Le contexte renvoyé est numéroté [S1], [S2]… pour que
les agents citent leurs sources (traçabilité des connaissances transmises aux joueurs)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gmix.db.models import KnowledgeChunk, KnowledgeDocument
from gmix.llm.tokens import estimate_tokens, truncate_to_tokens

RRF_K = 60


@dataclass(slots=True)
class Hit:
    chunk_id: int
    document_id: str
    title: str
    content: str
    meta: dict[str, Any]
    score: float


async def search(
    session: AsyncSession,
    *,
    query_vector: list[float],
    query_text: str,
    domain: str | None,
    k: int = 4,
    hybrid: bool = True,
    candidates: int = 20,
) -> list[Hit]:
    # pgvector >= 0.8 : poursuit le parcours HNSW tant que le filtre (domaine) n'a pas donné assez de lignes
    await session.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
    base = select(
        KnowledgeChunk.id,
        KnowledgeChunk.document_id,
        KnowledgeDocument.title,
        KnowledgeChunk.content,
        KnowledgeChunk.meta,
    ).join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
    if domain:
        base = base.where(KnowledgeChunk.domain_slug == domain)

    ranked: dict[int, list[Any]] = {}
    vector_rows = await session.execute(
        base.order_by(KnowledgeChunk.embedding.cosine_distance(query_vector)).limit(candidates)
    )
    for rank, row in enumerate(vector_rows):
        ranked[row.id] = [row, 1 / (RRF_K + rank + 1)]

    if hybrid and query_text.strip():
        tsquery = func.websearch_to_tsquery("french", query_text)
        text_rows = await session.execute(
            base.where(KnowledgeChunk.tsv.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(KnowledgeChunk.tsv, tsquery).desc())
            .limit(candidates)
        )
        for rank, row in enumerate(text_rows):
            ranked.setdefault(row.id, [row, 0.0])[1] += 1 / (RRF_K + rank + 1)

    best = sorted(ranked.values(), key=lambda entry: entry[1], reverse=True)[:k]
    return [
        Hit(
            chunk_id=row.id,
            document_id=str(row.document_id),
            title=row.title,
            content=row.content,
            meta=row.meta or {},
            score=score,
        )
        for row, score in best
    ]


def build_context(hits: list[Hit], max_tokens: int) -> tuple[str, list[dict[str, Any]]]:
    """Contexte numéroté [S1]… tenant dans le budget, et la liste des sources à citer."""
    blocks: list[str] = []
    sources: list[dict[str, Any]] = []
    used = 0
    for i, hit in enumerate(hits, start=1):
        page = hit.meta.get("page")
        block = f"[S{i}] {hit.title}{f', p. {page}' if page else ''}\n{hit.content}"
        cost = estimate_tokens(block)
        if used + cost > max_tokens:
            if blocks:
                break
            block = truncate_to_tokens(block, max_tokens)
            cost = max_tokens
        blocks.append(block)
        sources.append(
            {"ref": f"S{i}", "chunk_id": hit.chunk_id, "document_id": hit.document_id, "title": hit.title, "page": page}
        )
        used += cost
    return "\n\n".join(blocks), sources
