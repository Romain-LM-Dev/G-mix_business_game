"""Ingestion d'un dossier de domaine (knowledge/<domaine>/), guidée par son SOURCES.md.

Règle : un fichier n'est ingéré que s'il figure dans SOURCES.md avec une licence ou un droit d'usage renseigné
(traçabilité des connaissances transmises aux joueurs). Les documents déjà ingérés (même sha256) sont ignorés.

Usage : python -m gmix.rag.ingest_dir supply-chain
"""

import argparse
import asyncio
from pathlib import Path

from gmix.db import get_engine, get_sessionmaker
from gmix.llm.service import LLMService
from gmix.logging_setup import setup_logging
from gmix.rag.ingest import ingest_bytes
from gmix.settings import REPO_ROOT, get_settings

SOURCES_FILE = "SOURCES.md"
SOURCES_COLUMNS = ["Fichier", "Titre", "Auteur / éditeur", "Date", "Licence ou droit d'usage", "Ingéré le"]
INGESTIBLE = {".pdf", ".md", ".txt"}


def knowledge_dir(domain: str) -> Path:
    return REPO_ROOT / "knowledge" / domain


def read_sources(text: str) -> dict[str, dict[str, str]]:
    """Table Markdown de SOURCES.md -> {fichier: {colonne: valeur}}."""
    rows = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(rows) < 2:
        return {}
    header = [cell.strip() for cell in rows[0].strip("|").split("|")]
    sources: dict[str, dict[str, str]] = {}
    for row in rows[2:]:  # rows[1] = ligne de séparation |---|
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        entry = dict(zip(header, cells, strict=False))
        if entry.get("Fichier"):
            sources[entry["Fichier"].strip("`")] = entry
    return sources


def source_row(values: list[str]) -> str:
    return "| " + " | ".join(value.replace("|", "/") for value in values) + " |"


def add_source_row(sources_path: Path, row: str) -> None:
    """Insère la ligne juste après la dernière ligne du tableau (le texte qui suit le tableau est préservé)."""
    lines = sources_path.read_text(encoding="utf-8").splitlines()
    last = max(i for i, line in enumerate(lines) if line.strip().startswith("|"))
    lines.insert(last + 1, row)
    sources_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def ingest_domain(domain: str) -> list[str]:
    folder = knowledge_dir(domain)
    sources_path = folder / SOURCES_FILE
    if not sources_path.exists():
        raise FileNotFoundError(f"{sources_path} absent : déclarez d'abord les sources et leurs licences")
    sources = read_sources(sources_path.read_text(encoding="utf-8"))
    report: list[str] = []
    llm = LLMService.from_settings(with_cache=False)
    try:
        for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in INGESTIBLE):
            if path.name in {SOURCES_FILE, "README.md"}:
                continue
            entry = sources.get(path.name)
            license_text = (entry or {}).get("Licence ou droit d'usage", "")
            if not license_text:
                report.append(f"IGNORÉ  {path.name} : absent de SOURCES.md ou licence vide")
                continue
            async with get_sessionmaker()() as session:
                result = await ingest_bytes(
                    session,
                    llm,
                    filename=path.name,
                    data=await asyncio.to_thread(path.read_bytes),
                    domain=domain,
                    title=entry.get("Titre") or path.stem,
                    license=license_text,
                )
                await session.commit()
            report.append(f"{result['status'].upper():8} {path.name} ({result.get('chunks', '-')} passages)")
    finally:
        await llm.aclose()
        await get_engine().dispose()
    return report


async def _main(domain: str) -> None:
    setup_logging(get_settings().log_level)
    for line in await ingest_domain(domain):
        print(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion d'un dossier knowledge/<domaine>")
    parser.add_argument("domain", help="slug de ai/domains.yaml")
    asyncio.run(_main(parser.parse_args().domain))
