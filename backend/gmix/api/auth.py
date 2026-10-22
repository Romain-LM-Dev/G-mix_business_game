"""Authentification par comptes locaux (ADR 0004) : mots de passe scrypt, jetons JWT HS256, contrôle des rôles."""

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from gmix.db import session_dependency
from gmix.db.models import User, UserRole
from gmix.settings import get_settings

SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}  # recommandation OWASP pour scrypt (16 Mio de mémoire)
# shortcut: pas de jeton de rafraîchissement, une séance tient dans 8 h ; à ajouter avant le jeu à distance
ACCESS_TOKEN_HOURS = 8
PRESENCE_TICKET_SECONDS = 60
MIN_PASSWORD_LENGTH = 8
USERNAME_PATTERN = r"^[A-Za-z0-9._-]{3,64}$"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT_PARAMS)
    return "scrypt${n}${r}${p}${salt}${digest}".format(**SCRYPT_PARAMS, salt=_b64(salt), digest=_b64(digest))


def verify_password(password: str, stored: str | None) -> bool:
    try:
        scheme, n, r, p, salt, digest = (stored or "").split("$")
        expected = base64.b64decode(digest)
        candidate = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except ValueError:
        return False
    return scheme == "scrypt" and hmac.compare_digest(candidate, expected)


# Hachage factice : une connexion avec un identifiant inconnu prend le même temps qu'un mauvais mot de passe.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _secret() -> str:
    secret = get_settings().jwt_secret
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET doit faire au moins 32 caractères (.env) : relancer .\\scripts\\setup.ps1")
    return secret


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "role": user.role.value, "name": user.display_name, "typ": "access"}
    return jwt.encode(claims | {"iat": now, "exp": now + timedelta(hours=ACCESS_TOKEN_HOURS)}, _secret(), "HS256")


def create_presence_ticket(user: User, lobby_id: uuid.UUID, game_role: str | None) -> str:
    """Ticket court pour le serveur de partie Godot (ADR 0005) : il le vérifie avec le même secret."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "name": user.display_name,
        "lobby": str(lobby_id),
        "role": game_role or "",
        "typ": "presence",
    }
    return jwt.encode(
        claims | {"iat": now, "exp": now + timedelta(seconds=PRESENCE_TICKET_SECONDS)}, _secret(), "HS256"
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    claims = jwt.decode(token, _secret(), algorithms=["HS256"])
    if claims.get("typ") != expected_type:
        raise jwt.InvalidTokenError("type de jeton inattendu")
    return claims


class LoginLimiter:
    """Bloque un couple identifiant + adresse après 5 échecs en 5 minutes.
    shortcut: compteur en mémoire d'une seule instance d'API ; à mettre en base si plusieurs instances."""

    def __init__(self, max_failures: int = 5, window_s: float = 300.0) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        failures = self._failures[key]
        while failures and failures[0] < time.monotonic() - self.window_s:
            failures.popleft()
        if len(failures) >= self.max_failures:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives : réessayez dans quelques minutes"
            )

    def fail(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_limiter = LoginLimiter()
_bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Connexion requise ou expirée", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_token(credentials.credentials)
        user = await session.get(User, uuid.UUID(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: UserRole):
    async def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Action réservée à un autre rôle")
        return user

    return dependency


CurrentUser = Annotated[User, Depends(current_user)]
Staff = Annotated[User, Depends(require_roles(UserRole.TRAINER, UserRole.ADMIN))]
Session = Annotated[AsyncSession, Depends(session_dependency)]
