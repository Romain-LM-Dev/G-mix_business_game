"""Chaîne des assets 3D (catalogue ai/assets.yaml).

  python -m gmix.tools.assets import <dossier>  copie les GLB du catalogue (+ textures et licence de chaque pack)
                                                 depuis les zips extraits (<dossier>/<download_dir>/x/...)
                                                 vers godot/assets/_sources/<pack>/
  python -m gmix.tools.assets export            écrit godot/assets/catalog.json (lu par Godot)
  python -m gmix.tools.assets sync-db           met à jour la table assets + embeddings (choix sémantique par l'IA)
  python -m gmix.tools.assets search "besoin"   présélection sémantique (ce que verra la tâche game.asset_mapping)

Les scènes Godot sont ensuite construites par : Godot --headless --path godot --script res://tools/build_asset_scenes.gd
"""

import argparse
import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from gmix.assets_catalog import CATALOG_JSON, GODOT_ASSETS_DIR, SOURCES_DIR, load_assets_catalog
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import Asset
from gmix.game.assets import candidate_assets
from gmix.llm.service import LLMService
from gmix.logging_setup import setup_logging
from gmix.settings import get_settings


def export_json() -> str:
    return json.dumps(load_assets_catalog().to_godot(), ensure_ascii=False, indent=2) + "\n"


def export_credits() -> str:
    catalog = load_assets_catalog()
    used: dict[str, list[str]] = defaultdict(list)
    for asset in catalog.assets:
        used[asset.source.pack].append(asset.id)
    lines = [
        "# Crédits des assets 3D",
        "",
        "Généré depuis ai/assets.yaml (`python -m gmix.tools.assets export`). Les packs CC0 n'exigent pas",
        "d'attribution : elle est donnée par courtoisie et pour la traçabilité.",
        "",
        "| Pack | Licence | Source | Assets |",
        "|---|---|---|---|",
    ]
    for pack_id, ids in sorted(used.items()):
        pack = catalog.packs[pack_id]
        lines.append(f"| {pack.title} | {pack.license} | {pack.url} | {len(ids)} |")
    return "\n".join(lines) + "\n"


async def evaluate(ks: tuple[int, ...] = (4, 8, 15)) -> list[str]:
    """Rappel@k de la présélection sémantique sur ai/evals/assets.retrieval.jsonl."""
    path = get_settings().gmix_ai_dir / "evals" / "assets.retrieval.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    llm = LLMService.from_settings(with_cache=False)
    hits = dict.fromkeys(ks, 0)
    report = []
    try:
        async with get_sessionmaker()() as session:
            for case in cases:
                ranked = [c.id for c in await candidate_assets(session, llm, case["need"], k=max(ks))]
                rank = next((i + 1 for i, asset_id in enumerate(ranked) if asset_id in case["expected"]), None)
                for k in ks:
                    hits[k] += rank is not None and rank <= k
                report.append(f"rang {rank or '-':>2}  {case['need']}")
    finally:
        await llm.aclose()
        await get_engine().dispose()
    report.append("  ".join(f"rappel@{k} : {hits[k]}/{len(cases)}" for k in ks))
    return report


async def search(need: str, category: str | None) -> list[str]:
    llm = LLMService.from_settings(with_cache=False)
    try:
        async with get_sessionmaker()() as session:
            found = await candidate_assets(session, llm, need, categories=[category] if category else None)
    finally:
        await llm.aclose()
        await get_engine().dispose()
    return [f"{c.distance:.3f}  {c.id:<30} {c.name} ({c.category})" for c in found]


def import_sources(downloads: Path) -> list[str]:
    catalog = load_assets_catalog()
    files_by_pack: dict[str, set[str]] = defaultdict(set)
    for asset in catalog.assets:
        if not asset.procedural:
            files_by_pack[asset.source.pack].add(asset.source.file)  # type: ignore[arg-type]
    report = []
    for pack_id, files in sorted(files_by_pack.items()):
        pack = catalog.packs[pack_id]
        extracted = downloads / pack.download_dir / "x"  # type: ignore[operator]
        models = extracted / pack.models_dir  # type: ignore[operator]
        target = SOURCES_DIR / pack_id
        target.mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            shutil.copy2(models / name, target / name)
        if (models / "Textures").is_dir():
            shutil.copytree(models / "Textures", target / "Textures", dirs_exist_ok=True)
        licence = next((p for p in extracted.iterdir() if p.name.lower().startswith("licen")), None)
        if licence is None:
            raise FileNotFoundError(f"{pack_id} : licence introuvable dans {extracted}")
        shutil.copy2(licence, target / "License.txt")
        report.append(f"{pack_id:<28} {len(files):>3} modèles  ({pack.license})")
    return report


async def sync_db() -> int:
    catalog = load_assets_catalog()
    llm = LLMService.from_settings(with_cache=False)
    try:
        vectors = await llm.embed_documents(
            [a.embedding_text() for a in catalog.assets], titles=[a.name for a in catalog.assets]
        )
        async with get_sessionmaker()() as session:
            for asset, vector in zip(catalog.assets, vectors, strict=True):
                values = {
                    "id": asset.id,
                    "name": asset.name,
                    "category": asset.category,
                    "tags": asset.tags,
                    "description": asset.description,
                    "godot_scene": asset.scene,
                    "storage_key": None,
                    "footprint": asset.footprint.model_dump() | {"fit": asset.fit, "variants": asset.variants},
                    "license": catalog.packs[asset.source.pack].license,
                    "source_url": catalog.packs[asset.source.pack].url,
                    "embedding": vector,
                }
                stmt = insert(Asset).values(**values)
                await session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[Asset.id], set_={k: stmt.excluded[k] for k in values if k != "id"}
                    )
                )
            await session.commit()
    finally:
        await llm.aclose()
        await get_engine().dispose()
    return len(catalog.assets)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chaîne des assets 3D G-mix")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export")
    sub.add_parser("sync-db")
    importer = sub.add_parser("import")
    importer.add_argument("downloads", type=Path, help="dossier contenant <download_dir>/x/ pour chaque pack")
    searcher = sub.add_parser("search")
    searcher.add_argument("need", help="besoin en langage naturel, ex. « zone de stockage des palettes »")
    searcher.add_argument("--category")
    sub.add_parser("evaluate")
    args = parser.parse_args()
    setup_logging(get_settings().log_level)
    if args.command == "import":
        for line in import_sources(args.downloads):
            print(line)
    elif args.command == "export":
        CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
        CATALOG_JSON.write_text(export_json(), encoding="utf-8")
        (GODOT_ASSETS_DIR / "CREDITS.md").write_text(export_credits(), encoding="utf-8")
        print(f"{CATALOG_JSON} : {len(load_assets_catalog().assets)} assets (+ CREDITS.md)")
    elif args.command == "search":
        for line in asyncio.run(search(args.need, args.category)):
            print(line)
    elif args.command == "evaluate":
        for line in asyncio.run(evaluate()):
            print(line)
    else:
        print(f"Table assets synchronisée : {asyncio.run(sync_db())} assets (avec embeddings)")


if __name__ == "__main__":
    main()
