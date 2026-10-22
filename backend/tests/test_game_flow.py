"""Parcours complet d'une partie par l'API : import de la spec d'exemple, lobby, code d'accès, rôle, décisions,
PNJ (tev1 + RAG + modèle de dialogue), fin de partie et débrief. Nécessite l'infra Docker et Ollama."""

import json
import uuid

import httpx
import pytest
from sqlalchemy import delete

from gmix.api.auth import create_access_token
from gmix.api.main import app
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import BusinessGame, Lobby, User, UserRole
from gmix.tools.create_user import create_user

pytestmark = pytest.mark.integration


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


async def test_full_game_over_http(example_spec) -> None:
    suffix = uuid.uuid4().hex[:8]
    trainer = await create_user(f"formateur-{suffix}", "mdp-formateur", UserRole.TRAINER)
    player = await create_user(f"joueur-{suffix}", "mdp-joueur-1", UserRole.PLAYER)
    as_trainer, as_player = _auth(trainer), _auth(player)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        ):
            assert (await client.post("/api/v1/games/import", json=example_spec, headers=as_player)).status_code == 403
            game = (await client.post("/api/v1/games/import", json=example_spec, headers=as_trainer)).json()
            assert game["status"] == "ready" and game["review"]["warnings"] == []
            body = {"name": "Groupe A", "business_game_id": game["id"]}
            lobby = (await client.post("/api/v1/lobbies", json=body, headers=as_trainer)).json()
            url = f"/api/v1/lobbies/{lobby['id']}"
            assert (await client.get(url, headers=as_player)).status_code == 404  # pas encore membre

            joined = await client.post(
                "/api/v1/lobbies/join", json={"code": lobby["join_code"].lower()}, headers=as_player
            )
            view = joined.json()
            assert joined.status_code == 200 and view["join_code"] is None
            assert '"effects"' not in json.dumps(view["spec"]) and "debrief" not in view["spec"]
            assert view["world_template"]["zones"]
            assert (await client.put(f"{url}/role", json={"game_role": "pirate"}, headers=as_player)).status_code == 422
            assert (await client.put(f"{url}/role", json={"game_role": "daf"}, headers=as_player)).status_code == 200

            assert (await client.post(f"{url}/start", headers=as_player)).status_code == 403
            assert (await client.post(f"{url}/start", headers=as_trainer)).json()["state"]["status"] == "running"
            decision = {"decision_id": "d_priorite", "option_id": "o_clients"}
            state = (await client.post(f"{url}/decisions", json=decision, headers=as_player)).json()["state"]
            assert state["kpis"]["frais_financiers"] == 70
            assert (await client.post(f"{url}/decisions", json=decision, headers=as_player)).status_code == 409
            assert (await client.get(f"{url}/debrief", headers=as_player)).status_code == 409

            talk = await client.post(
                f"{url}/npcs/npc_banquiere/talk", json={"message": "Combien coûte l'affacturage ?"}, headers=as_player
            )
            assert talk.status_code == 200, talk.text
            assert talk.json()["reply"] and talk.json()["intent"] == "question_metier"

            for _ in example_spec["phases"]:
                state = (await client.post(f"{url}/advance", headers=as_trainer)).json()["state"]
            assert state["status"] == "finished"
            report = (await client.get(f"{url}/debrief", headers=as_player)).json()
            assert report["decisions"][0]["chosen"] == "o_clients" and report["sources"]
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(Lobby).where(Lobby.trainer_id == trainer.id))
            await session.execute(delete(BusinessGame).where(BusinessGame.created_by == trainer.id))
            await session.execute(delete(User).where(User.username.like(f"%-{suffix}")))
            await session.commit()
        await get_engine().dispose()
