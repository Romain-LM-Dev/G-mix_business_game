"""Cohérence du catalogue d'assets 3D (ai/assets.yaml) avec les fichiers Godot et les business games."""

from gmix.assets_catalog import CATALOG_JSON, GODOT_ASSETS_DIR, SOURCES_DIR, load_assets_catalog
from gmix.game.assets import restrict_schema_to
from gmix.llm import schemas
from gmix.tools.assets import export_json


def test_catalog_is_valid() -> None:
    catalog = load_assets_catalog()  # le validateur lève si un id est en double ou un pack inconnu
    assert len(catalog.assets) >= 50
    assert {a.category for a in catalog.assets} >= {"building", "industrial", "vehicle", "character", "road"}


def test_godot_catalog_is_up_to_date() -> None:
    assert CATALOG_JSON.read_text(encoding="utf-8") == export_json(), (
        "godot/assets/catalog.json est périmé : .\\scripts\\assets.ps1 (ou python -m gmix.tools.assets export)"
    )


def test_every_asset_has_its_scene_and_licensed_source() -> None:
    missing = []
    for asset in load_assets_catalog().assets:
        if not (GODOT_ASSETS_DIR / asset.category / asset.id / f"{asset.id}.tscn").exists():
            missing.append(f"scène {asset.scene}")
        if not asset.procedural:
            pack_dir = SOURCES_DIR / asset.source.pack
            if not (pack_dir / asset.source.file).exists():  # type: ignore[operator]
                missing.append(f"modèle {asset.source.pack}/{asset.source.file}")
            if not (pack_dir / "License.txt").exists():
                missing.append(f"licence {asset.source.pack}")
    assert not missing, missing


def test_example_world_uses_only_catalog_assets(example_spec) -> None:
    known = set(load_assets_catalog().by_id())
    used = {asset_id for zone in example_spec["world"]["zones"] for asset_id in zone["asset_ids"]}
    assert used <= known, used - known


def test_asset_mapping_schema_can_be_restricted_to_candidates() -> None:
    schema = restrict_schema_to(schemas.resolve("asset_selection"), ["bld_warehouse", "prop_pallet_rack"])
    allowed = {"zones": [{"zone_id": "z_stock", "asset_ids": ["prop_pallet_rack"]}]}
    invented = {"zones": [{"zone_id": "z_stock", "asset_ids": ["prop_dragon"]}]}
    assert schemas.validation_errors(schema, allowed) == []
    assert schemas.validation_errors(schema, invented)
