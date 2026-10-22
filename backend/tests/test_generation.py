"""Pipeline de génération sans modèle : un faux LLM rejoue les morceaux de la spec d'exemple. On vérifie
l'assemblage, les schémas restreints envoyés au modèle et les réparations déterministes."""

import copy
from types import SimpleNamespace

import pytest

from gmix.domains import load_domains
from gmix.game import generation
from gmix.game.generation import GameRequest, GenerationRefused, Generator
from gmix.game.world import template_zones
from gmix.llm import schemas
from gmix.llm.ollama import ChatResult, Usage


class FakeLLM:
    def __init__(self, spec: dict, verdict: dict | None = None, review_says: str = "non_dit") -> None:
        self.spec = spec
        self.verdict = verdict or {"usable": 0.9, "in_domain": 0.9, "injection": 0.01}
        self.review_says = review_says  # ce que la revue « lit » dans chaque explication
        self.calls: list[tuple[str, dict | None]] = []
        self.reviews = 0

    async def decide(self, task, state, questions):
        if task == "game.coherence_review":
            self.reviews += 1
            answer = {"choice": self.review_says, "probabilities": {self.review_says: 0.9}}
            return {"model": "fake", "answers": dict.fromkeys(questions, answer)}
        return {"model": "fake", "answers": {name: {"noul": self.verdict.get(name, 0.9)} for name in questions}}

    async def resolve(self, task):
        return SimpleNamespace(rag=SimpleNamespace(top_k=2, max_context_tokens=500)), None

    async def embed_query(self, text):
        return [0.0] * 768

    def schema(self, task: str, index: int = -1) -> dict:
        return [schema for name, schema in self.calls if name == task][index]

    async def json(self, task, messages, *, schema=None):
        self.calls.append((task, schema))
        spec = copy.deepcopy(self.spec)
        if task == "game.outline":
            data = {key: spec[key] for key in ("meta", "learning_objectives", "context", "roles", "kpis")}
            data["phases"] = [{k: p[k] for k in ("id", "title", "duration_minutes", "goal")} for p in spec["phases"]]
        elif task == "game.npcs":
            data = {"npcs": spec["npcs"]}
        elif task == "game.phase_detail":
            content = messages[-1]["content"]
            phase = next(p for p in spec["phases"] if f"Phase à détailler : {p['title']}" in content)
            for option in (o for d in phase["decisions"] for o in d["options"]):
                option.pop("source_refs", None)  # pas de corpus dans ce test
            for item in [o for d in phase["decisions"] for o in d["options"]] + phase["events"]:
                item["effects"] = [  # le modèle donne un sens et une ampleur, pas de montant
                    {"kpi": e["kpi"], "sens": "hausse" if e["value"] > 0 else "baisse", "ampleur": _strength(e)}
                    | ({"delay_phases": e["delay_phases"]} if e.get("delay_phases") else {})
                    for e in item["effects"]
                ]
            if phase["id"] == "p2_plan":
                if "Interdit" not in content:  # premier essai : rejoue la décision de la phase 1
                    phase["decisions"][0] = copy.deepcopy(spec["phases"][0]["decisions"][0])
                phase["decisions"][0]["id"] = "d_priorite"  # même id qu'en phase 1 : doit être renommé
            data = {"decisions": phase["decisions"], "events": phase["events"]}
        elif task == "game.asset_mapping":
            data = {"zones": [{"zone_id": "z_banque", "asset_ids": ["prop_desk_computer"]}]}
        else:
            data = spec["debrief"]
        return data, ChatResult(content="", usage=Usage(model="fake", prompt_tokens=10, completion_tokens=5))


def _strength(effect: dict) -> str:
    """Ampleur qu'aurait choisie le modèle pour un effet de l'exemple (options graduées : 60 ou 90 jours)."""
    size = abs(effect["value"])
    return "faible" if size < 20 else "moyenne" if size < 300 else "forte"


class _NoDatabase:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def no_retrieval(monkeypatch) -> None:
    async def nothing(*args, **kwargs):
        return []

    monkeypatch.setattr(generation, "search", nothing)
    monkeypatch.setattr(generation, "candidate_assets", nothing)


def _request(**overrides) -> GameRequest:
    domain = next(d for d in load_domains() if d.slug == "finance-entreprise")
    return GameRequest(domain=domain, brief="Trésorerie d'une PME industrielle", **overrides)


async def _progress(stage: str, percent: int) -> None:
    pass


async def test_pipeline_assembles_a_valid_coherent_spec(example_spec, no_retrieval) -> None:
    llm = FakeLLM(example_spec)
    request = _request(duration_minutes=60, players_min=2, players_max=4, level="intermediaire")
    result = await Generator(llm, _NoDatabase, _progress).run(request)

    spec = result.spec
    assert len(result.warnings) == 1 and "non sourcé" in result.warnings[0]  # aucun corpus dans ce test
    assert spec["meta"]["players"] == {"min": 2, "max": 4} and spec["meta"]["duration_minutes"] == 60
    assert sum(p["duration_minutes"] for p in spec["phases"]) <= 50  # 10 min de débrief
    assert any("durée des phases" in r for r in result.repairs)
    assert spec["phases"][1]["decisions"][0]["id"] == "d_priorite_2"
    assert result.usage["phase_detail"]["calls"] == len(spec["phases"]) + 1  # phase 2 répétée : un second essai
    options = [o for p in spec["phases"] for d in p["decisions"] for o in d["options"]]
    assert llm.reviews == sum(1 for o in options if o["effects"])
    dso = spec["phases"][0]["decisions"][0]["options"][0]["effects"][0]
    assert dso == {"kpi": "dso", "operation": "add", "value": -2.2, "delay_phases": 1}  # faible : 15 % de 75 -> 60

    first, second = llm.schema("game.phase_detail", 0)["$defs"], llm.schema("game.phase_detail", 1)["$defs"]
    assert first["decision"]["properties"]["role"]["enum"] == ["daf", "resp_achats", "resp_supply"]
    assert second["decision"]["properties"]["role"]["enum"] == ["resp_achats", "resp_supply"]  # rôles sans décision
    assert "bfr_jours" not in first["effect"]["properties"]["kpi"]["enum"]  # KPI dérivé
    assert llm.schema("game.npcs")["$defs"]["npc"]["properties"]["zone"]["enum"] == list(template_zones())
    pristine = schemas.resolve("business_game#/$defs/phase_detail")["$defs"]["decision"]["properties"]["role"]
    assert pristine == {"$ref": "#/$defs/id"}  # le schéma en cache n'est jamais modifié

    zones = {z["id"]: z["asset_ids"] for z in spec["world"]["zones"]}
    assert zones["z_siege"][:2] == ["bld_office_hq", "prop_kpi_screen"]
    assert zones["z_banque"][0] == "bld_bank_branch" and "prop_desk_computer" in zones["z_banque"]


def test_outline_repair_keeps_stated_values_when_formulas_are_circular(example_spec) -> None:
    outline = {key: copy.deepcopy(example_spec[key]) for key in ("meta", "learning_objectives", "kpis")}
    outline["phases"] = copy.deepcopy(example_spec["phases"])
    outline["kpis"] += [
        {"id": "service", "initial": 85, "formula": "1 - rupture"},  # mesuré sur qwen2.5:7b, en %
        {"id": "rupture", "initial": 15, "formula": "1 - service"},
    ]
    outline["kpis"][4]["initial"] = 88  # bfr_jours = dso + dio - dpo = 90 : petite erreur, corrigée
    generator = Generator(None, None, _progress)
    generator._repair_outline(outline, _request(duration_minutes=90, players_min=3, players_max=6))
    kpis = {k["id"]: k for k in outline["kpis"]}
    assert kpis["bfr_jours"]["initial"] == 90 and kpis["bfr_jours"]["formula"]
    assert kpis["service"]["initial"] == 85 and "formula" not in kpis["service"]
    assert kpis["rupture"]["initial"] == 15 and "formula" not in kpis["rupture"]


async def test_review_flips_effects_that_contradict_the_explanation(example_spec, no_retrieval) -> None:
    llm = FakeLLM(example_spec, review_says="hausse")  # chaque explication « dit » que l'indicateur monte
    result = await Generator(llm, _NoDatabase, _progress).run(_request())
    effects = [e for p in result.spec["phases"] for d in p["decisions"] for o in d["options"] for e in o["effects"]]
    assert effects and all(e["value"] > 0 for e in effects)
    assert any("inversé (baisse -> hausse)" in repair for repair in result.repairs)


async def test_unusable_brief_is_refused_before_any_generation(example_spec, no_retrieval) -> None:
    llm = FakeLLM(example_spec, verdict={"usable": 0.05, "in_domain": 0.9, "injection": 0.0})
    with pytest.raises(GenerationRefused):
        await Generator(llm, _NoDatabase, _progress).run(_request())
    assert llm.calls == []
