"""Cohérence du catalogue d'assets 3D (ai/assets.yaml) avec les fichiers Godot et les business games."""

import re

from gmix.assets_catalog import CATALOG_JSON, GODOT_ASSETS_DIR, SOURCES_DIR, load_assets_catalog
from gmix.tools.assets import export_json

# ADR 0007, annexe §5 : les 14 assets du monde usine, référencés par id par le pack `usine` et la génération.
FACTORY_ASSETS = (
    "prop_machine", "prop_buffer_table", "prop_dock_door", "prop_floor_zone", "veh_pallet_jack",
    "prop_inspection_table", "prop_scrap_bin", "prop_packing_table", "prop_pallet_wrapper", "prop_workbench",
    "prop_wall_board", "prop_part_token", "prop_bin_shelf", "prop_safety_cabinet",
)  # fmt: skip


def test_catalog_is_valid() -> None:
    catalog = load_assets_catalog()  # le validateur lève si un id est en double ou un pack inconnu
    assert len(catalog.assets) >= 50
    assert {a.category for a in catalog.assets} >= {"building", "industrial", "vehicle", "character", "road"}


def test_factory_assets_are_declared_and_unbuilt_ones_stay_out_of_godot() -> None:
    catalog = load_assets_catalog()
    assert set(FACTORY_ASSETS) <= catalog.by_id().keys()
    exported = {a["id"] for a in catalog.to_godot()["assets"]}
    for asset in catalog.assets:  # a_sourcer = ni scène ni entrée dans catalog.json
        assert (asset.status == "a_sourcer") != (asset.id in exported), asset.id


def test_factory_slice_one_scenes_are_clean_and_have_their_own_collision() -> None:
    """Tranche 1 (étape 5b) : fabriquée, sans dérivation du jeu de référence, collision propre, source CC0 créditée."""
    catalog = load_assets_catalog()
    credited = {a.source.pack for a in catalog.shipped()}  # packs listés dans CREDITS.md
    for asset_id in FACTORY_ASSETS[:11]:
        asset = catalog.by_id()[asset_id]
        assert asset.status == "importe" and asset.procedural, asset_id
        scene = (GODOT_ASSETS_DIR / asset.category / asset_id / f"{asset_id}.tscn").read_text(encoding="utf-8")
        script_path = re.search(r'path="res://(assets/procedural/\w+\.gd)"', scene)
        assert script_path, f"{asset_id} : script introuvable dans la scène"
        code = (GODOT_ASSETS_DIR.parent / script_path.group(1)).read_text(encoding="utf-8")
        assert "production_line" not in code and "site_office" not in code, f"{asset_id} dérive du jeu de référence"
        # prop_floor_zone : marquage plat, jamais un obstacle ; tous les autres ont un StaticBody3D « Collision »
        assert ("Mesher.collider" in code) == (asset_id != "prop_floor_zone"), asset_id
        for pack, name in re.findall(r"res://assets/_sources/([\w-]+)/([\w.-]+)", code):  # modèle libre embarqué
            assert pack in credited and catalog.packs[pack].license.startswith("CC0"), (
                f"{asset_id} : {pack} non crédité"
            )
            assert (SOURCES_DIR / pack / name).exists() and (SOURCES_DIR / pack / "License.txt").exists(), asset_id


def test_godot_catalog_is_up_to_date() -> None:
    assert CATALOG_JSON.read_text(encoding="utf-8") == export_json(), (
        "godot/assets/catalog.json est périmé : .\\scripts\\assets.ps1 (ou python -m gmix.tools.assets export)"
    )


def test_every_asset_has_its_scene_and_licensed_source() -> None:
    missing = []
    for asset in load_assets_catalog().shipped():  # les a_sourcer sont déclarés, pas encore fabriqués
        if not (GODOT_ASSETS_DIR / asset.category / asset.id / f"{asset.id}.tscn").exists():
            missing.append(f"scène {asset.scene}")
        if not asset.procedural:
            pack_dir = SOURCES_DIR / asset.source.pack
            if not (pack_dir / asset.source.file).exists():  # type: ignore[operator]
                missing.append(f"modèle {asset.source.pack}/{asset.source.file}")
            if not (pack_dir / "License.txt").exists():
                missing.append(f"licence {asset.source.pack}")
    assert not missing, missing
