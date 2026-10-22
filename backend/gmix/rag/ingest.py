"""Ingestion d'un document de connaissance dans le RAG.

Usage : python -m gmix.rag.ingest <fichier.pdf|.md|.txt> --domain finance-entreprise [--title T] [--license L]

Extraction (PDF page par page) -> découpage -> embeddings (tâche rag.embed) -> pgvector + plein texte,
l'original est archivé dans le bucket gmix-knowledge. Un document déjà ingéré (même sha256) est ignoré.
"""

import argparse
import asyncio
import hashlib
import io
import mimetypes
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gmix import storage
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import DocStatus, KnowledgeChunk, KnowledgeDocument
from gmix.llm.service import LLMService
from gmix.llm.tokens import estimate_tokens
from gmix.logging_setup import setup_logging
from gmix.rag.chunking import split_into_chunks
from gmix.settings import get_settings

EMBED_BATCH = 16


def extract_pages(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
    if suffix in {".md", ".txt"}:
        return [(None, data.decode("utf-8"))]
    raise ValueError(f"Format non géré : {suffix} (pdf, md, txt)")


async def ingest_bytes(
    session: AsyncSession,
    llm: LLMService,
    *,
    filename: str,
    data: bytes,
    domain: str,
    title: str | None = None,
    license: str | None = None,
    store_original: bool = True,
) -> dict[str, Any]:
    """Ajoute le document à la session (flush, sans commit : l'appelant décide)."""
    checksum = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.checksum == checksum))
    if existing:
        return {"status": "skipped", "document_id": str(existing)}

    title = title or Path(filename).stem
    chunks = [(page, chunk) for page, content in extract_pages(filename, data) for chunk in split_into_chunks(content)]
    if not chunks:
        raise ValueError(f"Aucun texte extrait de {filename} (PDF scanné ? OCR nécessaire)")

    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = [content for _, content in chunks[start : start + EMBED_BATCH]]
        vectors.extend(await llm.embed_documents(batch, title=title))

    source_uri = f"{domain}/{checksum[:12]}-{Path(filename).name}"
    if store_original:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        await storage.put_bytes(get_settings().s3_bucket_knowledge, source_uri, data, content_type)

    document = KnowledgeDocument(
        domain_slug=domain,
        title=title,
        source_type=Path(filename).suffix.lstrip(".").lower(),
        source_uri=source_uri,
        license=license,
        checksum=checksum,
        status=DocStatus.INGESTED,
        meta={"chunks": len(chunks), "embed_model": llm.catalog.embedding_model().name},
    )
    session.add(document)
    await session.flush()
    session.add_all(
        KnowledgeChunk(
            document_id=document.id,
            domain_slug=domain,
            ordinal=i,
            content=content,
            token_count=estimate_tokens(content),
            meta={"page": page} if page else {},
            embedding=vector,
        )
        for i, ((page, content), vector) in enumerate(zip(chunks, vectors, strict=True))
    )
    await session.flush()
    return {"status": "ingested", "document_id": str(document.id), "chunks": len(chunks)}


async def _main(args: argparse.Namespace) -> None:
    setup_logging(get_settings().log_level)
    llm = LLMService.from_settings(with_cache=False)
    path = Path(args.file)
    try:
        async with get_sessionmaker()() as session:
            report = await ingest_bytes(
                session,
                llm,
                filename=path.name,
                data=await asyncio.to_thread(path.read_bytes),
                domain=args.domain,
                title=args.title,
                license=args.license,
            )
            await session.commit()
        print(report)
    finally:
        await llm.aclose()
        await get_engine().dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion d'un document dans le RAG G-mix")
    parser.add_argument("file")
    parser.add_argument("--domain", required=True, help="slug de ai/domains.yaml")
    parser.add_argument("--title")
    parser.add_argument("--license", help="droits d'usage (ex. 'CC BY 4.0', 'support fourni par le formateur')")
    asyncio.run(_main(parser.parse_args()))
