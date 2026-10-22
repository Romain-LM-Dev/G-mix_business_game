"""Comptes locaux (ADR 0004) : hachage, jetons typés, limitation des tentatives, règles de rôle."""

import uuid

import httpx
import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from gmix.api import auth
from gmix.api.main import app
from gmix.api.routes import accounts
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import User, UserRole
from gmix.tools.create_user import create_user


def _user(role: UserRole) -> User:
    return User(id=uuid.uuid4(), username="u", display_name="U", role=role, password_hash="")


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch) -> None:
    monkeypatch.setattr(auth, "_secret", lambda: "s" * 32)


def test_password_hash_roundtrip_and_rejects() -> None:
    stored = auth.hash_password("cheval correct")
    assert stored.startswith("scrypt$") and "cheval correct" not in stored
    assert auth.verify_password("cheval correct", stored)
    assert not auth.verify_password("cheval", stored)
    assert not auth.verify_password("x", None) and not auth.verify_password("x", "bcrypt$abc")


def test_tokens_are_typed() -> None:
    user = _user(UserRole.TRAINER)
    claims = auth.decode_token(auth.create_access_token(user))
    assert claims["sub"] == str(user.id) and claims["role"] == "trainer"
    ticket = auth.create_presence_ticket(user, uuid.uuid4(), "daf")
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token(ticket)  # un ticket de présence n'ouvre pas l'API
    assert auth.decode_token(ticket, "presence")["role"] == "daf"


def test_login_limiter() -> None:
    limiter = auth.LoginLimiter(max_failures=2)
    limiter.fail("k")
    limiter.fail("k")
    with pytest.raises(HTTPException):
        limiter.check("k")
    limiter.reset("k")
    limiter.check("k")


async def test_role_rules() -> None:
    with pytest.raises(HTTPException) as exc:
        await auth.require_roles(UserRole.TRAINER, UserRole.ADMIN)(user=_user(UserRole.PLAYER))
    assert exc.value.status_code == 403
    body = accounts.UserCreate(username="chef", display_name="Chef", password="12345678", role=UserRole.ADMIN)
    with pytest.raises(HTTPException) as exc:
        await accounts.create_user(body, actor=_user(UserRole.TRAINER), session=None, request=None)
    assert exc.value.status_code == 403


@pytest.mark.integration
async def test_account_flow_over_http() -> None:
    suffix = uuid.uuid4().hex[:8]
    admin = await create_user(f"admin-{suffix}", "mdp-admin-1", UserRole.ADMIN)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        ):

            async def login(username: str, password: str) -> dict[str, str]:
                response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
                assert response.status_code == 200, response.text
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            as_admin = await login(admin.username.upper(), "mdp-admin-1")  # identifiant insensible à la casse
            assert (await client.get("/api/v1/auth/me", headers=as_admin)).json()["role"] == "admin"
            trainer = {
                "username": f"formateur-{suffix}",
                "display_name": "F",
                "password": "provisoire",
                "role": "trainer",
            }
            response = await client.post("/api/v1/users", json=trainer, headers=as_admin)
            assert response.status_code == 201 and response.json()["must_change_password"]

            as_trainer = await login(trainer["username"], "provisoire")
            forbidden = trainer | {"username": f"pirate-{suffix}", "role": "admin"}
            assert (await client.post("/api/v1/users", json=forbidden, headers=as_trainer)).status_code == 403
            player = {"username": f"joueur-{suffix}", "display_name": "J", "password": "provisoire"}
            assert (await client.post("/api/v1/users", json=player, headers=as_trainer)).status_code == 201
            assert (await client.post("/api/v1/users", json=player, headers=as_trainer)).status_code == 409
            listed = (await client.get("/api/v1/users", headers=as_trainer)).json()
            assert [u["username"] for u in listed] == [player["username"]]

            as_player = await login(player["username"], "provisoire")
            assert (await client.get("/api/v1/users", headers=as_player)).status_code == 403
            change = {"current_password": "mauvais", "new_password": "nouveau-mdp"}
            assert (await client.post("/api/v1/auth/password", json=change, headers=as_player)).status_code == 400
            change["current_password"] = "provisoire"
            assert (await client.post("/api/v1/auth/password", json=change, headers=as_player)).status_code == 204
            assert not (await client.get("/api/v1/auth/me", headers=as_player)).json()["must_change_password"]

            bad = {"username": player["username"], "password": "provisoire"}
            assert (await client.post("/api/v1/auth/login", json=bad)).status_code == 401
            assert (await client.get("/api/v1/auth/me")).status_code == 401
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(User).where(User.username.like(f"%-{suffix}")))
            await session.commit()
        await get_engine().dispose()
