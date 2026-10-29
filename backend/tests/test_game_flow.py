"""Parcours complet d'une partie par l'API : génération par paramètres, import, lobby, code d'accès, rôle, actions
par module, semaines simulées, dialogues mémorisés avec un agent (tev1 + modèle de dialogue) et débrief.
Nécessite l'infra Docker et Ollama."""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import delete

from gmix.api.auth import create_access_token
from gmix.api.main import app
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import BusinessGame, Lobby, User, UserRole
from gmix.game.npc import MAX_CHARS
from gmix.game.spec import ActionField, Timeline
from gmix.tools.create_user import create_user

pytestmark = pytest.mark.integration


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


async def test_full_game_over_http() -> None:
    suffix = uuid.uuid4().hex[:8]
    trainer = await create_user(f"formateur-{suffix}", "mdp-formateur", UserRole.TRAINER)
    player = await create_user(f"joueur-{suffix}", "mdp-joueur-1", UserRole.PLAYER)
    as_trainer, as_player = _auth(trainer), _auth(player)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        ):
            assert (await client.get("/api/v1/games/options", headers=as_player)).status_code == 403
            options = (await client.get("/api/v1/games/options", headers=as_trainer)).json()
            assert "industrie" in {t["id"] for t in options["themes"]} and len(options["modules"]) == 7
            params = {"theme": "industrie", "modules": ["approvisionnement", "production", "qualite"],
                      "extra_agents": ["client"], "weeks": 4, "products": 2, "events": "aucun", "seed": 7}  # fmt: skip
            assert (await client.post("/api/v1/games", json=params, headers=as_player)).status_code == 403
            assert (
                await client.post("/api/v1/games", json=params | {"theme": "spatial"}, headers=as_trainer)
            ).status_code == 422
            game = (await client.post("/api/v1/games", json=params, headers=as_trainer)).json()
            assert game["status"] == "ready" and game["review"]["autopilot"]["weeks"] == 4
            spec = game["spec"]
            broken = spec | {"agents": [a | {"module_id": "finance"} for a in spec["agents"]]}
            assert (await client.post("/api/v1/games/import", json=broken, headers=as_trainer)).status_code == 422
            assert (await client.post("/api/v1/games/import", json=spec, headers=as_trainer)).status_code == 201

            body = {"name": "Groupe A", "business_game_id": game["id"]}
            lobby = (await client.post("/api/v1/lobbies", json=body, headers=as_trainer)).json()
            url = f"/api/v1/lobbies/{lobby['id']}"
            assert (await client.get(url, headers=as_player)).status_code == 404  # pas encore membre
            joined = await client.post(
                "/api/v1/lobbies/join", json={"code": lobby["join_code"].lower()}, headers=as_player
            )
            assert joined.status_code == 200 and joined.json()["join_code"] is None
            assert (await client.put(f"{url}/role", json={"game_role": "pirate"}, headers=as_player)).status_code == 422
            assert (
                await client.put(f"{url}/role", json={"game_role": "acheteur"}, headers=as_player)
            ).status_code == 200

            assert (await client.post(f"{url}/start", headers=as_player)).status_code == 403
            assert (await client.post(f"{url}/start", headers=as_trainer)).json()["state"]["status"] == "running"
            offer = next(o for o in spec["offers"] if o["profile"] == "standard")
            order = {
                "module": "approvisionnement",
                "action": "commander",
                "values": {"offer": offer["id"], "quantity": 500},
            }
            done = await client.post(f"{url}/actions", json=order, headers=as_player)
            assert done.status_code == 200 and done.json()["summary"].startswith("Commande de 500")
            too_small = order | {"values": {"offer": offer["id"], "quantity": 10}}
            assert (await client.post(f"{url}/actions", json=too_small, headers=as_player)).status_code == 409
            assert (await client.get(f"{url}/debrief", headers=as_player)).status_code == 409

            talk_url = f"{url}/npcs/agent_approvisionnement/talk"
            for message in ("Salut Noah, où en sont les commandes ?", "Et on recommande quand ?"):
                talk = await client.post(talk_url, json={"message": message}, headers=as_player)
                assert talk.status_code == 200, talk.text
                assert 0 < len(talk.json()["reply"]) <= MAX_CHARS
            memory = (await client.get(f"{url}/npcs/agent_approvisionnement/memory", headers=as_player)).json()
            assert [m["message"] for m in memory] == [
                "Salut Noah, où en sont les commandes ?",
                "Et on recommande quand ?",
            ]
            assert (
                await client.post(f"{url}/npcs/agent_inconnu/talk", json={"message": "?"}, headers=as_player)
            ).status_code == 404

            for _ in range(spec["meta"]["weeks"]):
                state = (await client.post(f"{url}/advance", headers=as_trainer)).json()["state"]
            assert state["status"] == "finished" and len(state["history"]) == 4
            report = (await client.get(f"{url}/debrief", headers=as_player)).json()
            assert report["kpis"] and report["lessons"] and report["log"][0]["name"] == player.display_name
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(Lobby).where(Lobby.trainer_id == trainer.id))
            await session.execute(delete(BusinessGame).where(BusinessGame.created_by == trainer.id))
            await session.execute(delete(User).where(User.username.like(f"%-{suffix}")))
            await session.commit()
        await get_engine().dispose()


@asynccontextmanager
async def _trainer_client() -> AsyncIterator[tuple[httpx.AsyncClient, dict[str, str]]]:
    """Client HTTP et en-têtes d'un formateur jetable ; ses lobbies, jeux et compte sont supprimés à la sortie."""
    suffix = uuid.uuid4().hex[:8]
    trainer = await create_user(f"formateur-{suffix}", "mdp-formateur", UserRole.TRAINER)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        ):
            yield client, _auth(trainer)
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(Lobby).where(Lobby.trainer_id == trainer.id))
            await session.execute(delete(BusinessGame).where(BusinessGame.created_by == trainer.id))
            await session.execute(delete(User).where(User.username.like(f"%-{suffix}")))
            await session.commit()
        await get_engine().dispose()


USINE = {"pack": "usine", "theme": "industrie", "modules": ["pilotage", "production", "maintenance"], "products": 1,
         "weeks": 6, "events": "aucun", "options": {"lines": 3}, "seed": 5}  # fmt: skip


async def test_pack_options_and_validation() -> None:
    async with _trainer_client() as (client, headers):
        options = (await client.get("/api/v1/games/options", headers=headers)).json()
        packs = {p["id"]: p for p in options["packs"]}
        assert {"atelier", "usine"} <= packs.keys()
        for pack in packs.values():  # contrat de l'annexe 0007 §4 ; limites au format [min, max, défaut] de `ranges`
            assert {
                "id",
                "label",
                "description",
                "domain",
                "engine",
                "params",
                "themes",
                "modules",
                "limits",
            } <= pack.keys()
            assert pack["limits"].keys() == {"weeks", "products"}
            assert all(low <= default <= high for low, high, default in pack["limits"].values())
            assert all(ActionField.model_validate(p) for p in pack["params"])
        atelier, usine = packs["atelier"], packs["usine"]
        assert atelier["limits"] == options["ranges"] and atelier["params"] == [] and atelier["engine"] == "weekly"
        assert [t["id"] for t in atelier["themes"]] == [t["id"] for t in options["themes"]]  # clés d'origine = atelier
        assert [m["id"] for m in atelier["modules"]] == [m["id"] for m in options["modules"]]
        assert usine["engine"] == "factory" and [p["id"] for p in usine["params"]] == ["lines"]
        assert usine["limits"]["products"][:2] == [1, 1] and {m["id"] for m in usine["modules"]} >= {"pilotage"}

        atelier_params = USINE | {"pack": "atelier", "modules": ["production"], "products": 2, "options": {}}
        for bad in (
            USINE | {"pack": "inconnu"}, USINE | {"options": {"lines": 9}}, USINE | {"options": {"voies": 1}},
            USINE | {"products": 2}, USINE | {"modules": ["approvisionnement"]},  # hors limites ou hors pack
            atelier_params | {"options": {"lines": 2}},  # l'atelier n'a pas d'option
        ):  # fmt: skip
            answer = await client.post("/api/v1/games", json=bad, headers=headers)
            assert answer.status_code == 422, (bad, answer.text[:200])
        game = (await client.post("/api/v1/games", json=atelier_params, headers=headers)).json()
        assert game["domain_slug"] == "supply-chain" and game["spec"]["meta"]["pack"] == "atelier"


async def test_factory_game_within_budget() -> None:
    """Pack usine de bout en bout : génération sous 1 s (3 lignes, pilote automatique compris), un tour joué, état
    public < 64 Ko, chronologie servie < 200 Ko. Attend le moteur d'usine (étape 6 de l'ADR 0007)."""
    pytest.importorskip("gmix.game.factory")
    async with _trainer_client() as (client, headers):
        params = USINE | {"weeks": 12, "difficulty": "expert", "events": "frequents"}
        started = time.perf_counter()
        created = await client.post("/api/v1/games", json=params, headers=headers)
        elapsed = time.perf_counter() - started
        assert created.status_code == 201, created.text[:300]
        assert elapsed < 1.0, f"POST /games : {elapsed:.2f} s"
        game = created.json()
        assert game["domain_slug"] == "supply-chain" and game["spec"]["meta"]["pack"] == "usine"
        assert game["spec"]["factory"] and game["review"]["autopilot"]

        body = {"name": "Usine", "business_game_id": game["id"]}
        lobby = (await client.post("/api/v1/lobbies", json=body, headers=headers)).json()
        url = f"/api/v1/lobbies/{lobby['id']}"
        assert (await client.post(f"{url}/start", headers=headers)).status_code == 200
        advanced = await client.post(f"{url}/advance", headers=headers)
        assert advanced.status_code == 200 and "timeline" not in advanced.json()["state"]["last"]
        assert len(advanced.content) < 64_000
        served = await client.get(f"{url}/weeks/1/timeline", headers=headers)
        assert served.status_code == 200 and len(served.content) < 200_000
        assert Timeline.model_validate(served.json()).week == 1
