"""Connexion et gestion des comptes (ADR 0004 : l'admin crée les formateurs, les formateurs créent leurs joueurs)."""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from gmix.api.auth import (
    DUMMY_HASH,
    MIN_PASSWORD_LENGTH,
    USERNAME_PATTERN,
    CurrentUser,
    Session,
    Staff,
    create_access_token,
    hash_password,
    login_limiter,
    verify_password,
)
from gmix.api.deps import publish
from gmix.db.models import User, UserRole
from gmix.messaging.envelope import Actor, Envelope
from gmix.messaging.topics import AUDIT

router = APIRouter(prefix="/api/v1", tags=["comptes"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    role: UserRole
    must_change_password: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256, description="mot de passe provisoire")
    role: UserRole = UserRole.PLAYER
    email: str | None = Field(default=None, max_length=320)


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request, session: Session) -> TokenOut:
    key = f"{body.username.lower()}|{request.client.host if request.client else '?'}"
    login_limiter.check(key)
    user = await session.scalar(select(User).where(func.lower(User.username) == body.username.lower()))
    valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid or not user.is_active:
        login_limiter.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiant ou mot de passe incorrect")
    login_limiter.reset(key)
    return TokenOut(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/auth/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChange, user: CurrentUser, session: Session) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mot de passe actuel incorrect")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await session.commit()


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, actor: Staff, session: Session, request: Request) -> UserOut:
    if actor.role == UserRole.TRAINER and body.role != UserRole.PLAYER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Un formateur ne crée que des comptes joueurs")
    taken = await session.scalar(select(User.id).where(func.lower(User.username) == body.username.lower()))
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Identifiant déjà utilisé")
    user = User(
        username=body.username,
        display_name=body.display_name,
        email=body.email,
        role=body.role,
        password_hash=hash_password(body.password),
        must_change_password=True,
        created_by=actor.id,
    )
    session.add(user)
    await session.commit()
    await publish(
        request,
        AUDIT,
        Envelope(
            type="account.created",
            source="api",
            actor=Actor(user_id=actor.id, role=actor.role.value),
            payload={"user_id": str(user.id), "username": user.username, "role": user.role.value},
        ),
    )
    return UserOut.model_validate(user)


@router.get("/users")
async def list_users(actor: Staff, session: Session) -> list[UserOut]:
    query = select(User).order_by(User.role, User.username)
    if actor.role == UserRole.TRAINER:
        query = query.where(User.created_by == actor.id)
    return [UserOut.model_validate(u) for u in await session.scalars(query)]
