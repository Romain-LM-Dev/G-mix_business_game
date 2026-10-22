"""Catalogue des assets 3D (ai/assets.yaml) : chargement validé et export JSON pour Godot."""

from functools import lru_cache
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from gmix.settings import REPO_ROOT, get_settings

GODOT_ASSETS_DIR = REPO_ROOT / "godot" / "assets"
SOURCES_DIR = GODOT_ASSETS_DIR / "_sources"
CATALOG_JSON = GODOT_ASSETS_DIR / "catalog.json"
PROCEDURAL_PACK = "gmix"

Category = Literal["building", "industrial", "interactive", "furniture", "vehicle", "character", "nature", "road"]


class PackSpec(BaseModel):
    title: str
    url: str
    license: str
    download_dir: str | None = None  # dossier du zip extrait (sous le dossier de téléchargement)
    models_dir: str | None = None  # dossier des GLB dans le zip


class Footprint(BaseModel):
    w: float = Field(gt=0)
    d: float = Field(gt=0)
    h: float = Field(gt=0)


class AssetSource(BaseModel):
    pack: str
    file: str | None = None  # None : scène procédurale écrite à la main


class AssetSpec(BaseModel):
    id: str = Field(pattern=r"^(bld|prop|veh|furn|char|nat|road)_[a-z0-9_]+$")
    name: str
    category: Category
    tags: list[str] = Field(min_length=1)
    description: str = Field(min_length=5)
    footprint: Footprint
    fit: Literal["h", "w", "d", "max"] = "max"
    variants: list[str] = Field(default_factory=list)
    source: AssetSource
    status: Literal["a_sourcer", "importe", "publie"] = "importe"

    @property
    def procedural(self) -> bool:
        return self.source.file is None

    @property
    def scene(self) -> str:
        return f"res://assets/{self.category}/{self.id}/{self.id}.tscn"

    @property
    def source_path(self) -> str | None:
        return None if self.procedural else f"res://assets/_sources/{self.source.pack}/{self.source.file}"

    def embedding_text(self) -> str:
        return f"{self.name}. {self.description} Mots-clés : {', '.join(self.tags)}."


class AssetCatalog(BaseModel):
    version: int
    packs: dict[str, PackSpec]
    assets: list[AssetSpec]

    @model_validator(mode="after")
    def _check(self) -> "AssetCatalog":
        errors: list[str] = []
        ids = [a.id for a in self.assets]
        errors += [f"id en double : {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
        for asset in self.assets:
            pack = self.packs.get(asset.source.pack)
            if pack is None:
                errors.append(f"{asset.id} : pack inconnu '{asset.source.pack}'")
            elif asset.procedural != (asset.source.pack == PROCEDURAL_PACK):
                errors.append(f"{asset.id} : seul le pack '{PROCEDURAL_PACK}' est procédural (sans fichier)")
            elif not asset.procedural and not (pack.download_dir and pack.models_dir):
                errors.append(f"{asset.id} : le pack '{asset.source.pack}' n'indique pas où trouver ses modèles")
        if errors:
            raise ValueError("ai/assets.yaml invalide :\n- " + "\n- ".join(errors))
        return self

    def by_id(self) -> dict[str, AssetSpec]:
        return {a.id: a for a in self.assets}

    def to_godot(self) -> dict[str, Any]:
        """Données utiles au jeu et au constructeur de scènes (godot/assets/catalog.json)."""
        return {
            "version": self.version,
            "generated_from": "ai/assets.yaml (python -m gmix.tools.assets export)",
            "assets": [
                {
                    "id": a.id,
                    "name": a.name,
                    "category": a.category,
                    "tags": a.tags,
                    "footprint": a.footprint.model_dump(),
                    "fit": a.fit,
                    "variants": a.variants,
                    "scene": a.scene,
                    "source_path": a.source_path,
                    "sign": "enseigne" in a.variants,
                    "license": self.packs[a.source.pack].license,
                }
                for a in self.assets
            ],
        }


@lru_cache
def load_assets_catalog() -> AssetCatalog:
    path = get_settings().gmix_ai_dir / "assets.yaml"
    return AssetCatalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
