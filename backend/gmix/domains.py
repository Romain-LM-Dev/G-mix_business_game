"""Domaines d'expertise sélectionnables par le formateur (ai/domains.yaml)."""

from functools import lru_cache

import yaml
from pydantic import BaseModel, Field

from gmix.settings import get_settings


class DomainSpec(BaseModel):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    name: str
    description: str
    competencies: list[str] = Field(min_length=3)
    kpis: list[str] = Field(min_length=3)
    references: list[str] = Field(min_length=2)
    roles: list[str] = Field(min_length=2)
    active: bool = True


@lru_cache
def load_domains() -> list[DomainSpec]:
    raw = yaml.safe_load((get_settings().gmix_ai_dir / "domains.yaml").read_text(encoding="utf-8"))
    domains = [DomainSpec.model_validate(d) for d in raw["domains"]]
    slugs = [d.slug for d in domains]
    if len(slugs) != len(set(slugs)):
        raise ValueError("ai/domains.yaml : slugs en double")
    return domains
