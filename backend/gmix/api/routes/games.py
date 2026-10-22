"""Business games : demande de génération (asynchrone, Kafka), suivi, relecture et modification de la spec.

Un formateur ne voit que ses business games, l'admin les voit tous (docs/roles.md).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from gmix.api.auth import Session, Staff
from gmix.api.deps import publish
from gmix.db.models import Asset, BusinessGame, Domain, GameStatus, GenerationJob, JobStatus, User, UserRole
from gmix.game.coherence import check_spec
from gmix.game.world import load_world_templates
from gmix.llm import schemas
from gmix.messaging.envelope import Actor, Envelope
from gmix.messaging.topics import AUDIT, GENERATION_COMMANDS

router = APIRouter(prefix="/api/v1/games", tags=["business games"])
SpecBody = Annotated[dict[str, Any], Body(description="spec complète (ai/schemas/business_game.schema.json)")]


class GameRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=64)
    brief: str = Field(min_length=20, max_length=2000, description="besoin du formateur, en langage libre")
    level: Literal["debutant", "intermediaire", "avance"] = "intermediaire"
    duration_minutes: int = Field(default=90, ge=30, le=240)
    players_min: int = Field(default=2, ge=1, le=60)
    players_max: int = Field(default=6, ge=1, le=60)
    competencies: list[str] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _players(self) -> "GameRequest":
        if self.players_min > self.players_max:
            raise ValueError("players_min doit être inférieur ou égal à players_max")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: JobStatus
    stage: str | None
    progress: int
    error: str | None


class GameSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    domain_slug: str
    status: GameStatus
    created_at: datetime
    job: JobOut | None = None


class GameDetail(GameSummary):
    brief: str
    params: dict[str, Any]
    review: dict[str, Any]
    spec_version: int
    spec: dict[str, Any] | None


def _actor(user: User) -> Actor:
    return Actor(user_id=user.id, role=user.role.value)


async def owned_game(session: Session, game_id: uuid.UUID, user: User) -> BusinessGame:
    game = await session.get(BusinessGame, game_id)
    if game is None or (user.role != UserRole.ADMIN and game.created_by != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business game introuvable")
    return game


async def _latest_jobs(session: Session, game_ids: list[uuid.UUID]) -> dict[uuid.UUID, GenerationJob]:
    query = (
        select(GenerationJob)
        .where(GenerationJob.business_game_id.in_(game_ids))
        .order_by(GenerationJob.business_game_id, GenerationJob.created_at.desc())
        .ext(distinct_on(GenerationJob.business_game_id))
    )
    return {job.business_game_id: job for job in await session.scalars(query)}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def request_game(body: GameRequest, actor: Staff, session: Session, request: Request) -> GameSummary:
    """Crée le business game et publie la demande ; la progression arrive par WebSocket (generation.*)."""
    domain = await session.get(Domain, body.domain)
    if domain is None or not domain.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Domaine inconnu ou inactif")
    game = BusinessGame(
        domain_slug=domain.slug,
        title=f"{domain.name} : génération en cours",
        brief=body.brief,
        status=GameStatus.GENERATING,
        params=body.model_dump(exclude={"brief", "domain"}),
        created_by=actor.id,
    )
    session.add(game)
    await session.flush()
    job = GenerationJob(business_game_id=game.id, kind="generate_game", requested_by=actor.id)
    session.add(job)
    await session.commit()
    command = Envelope(
        type="generation.requested",
        source="api",
        correlation_id=job.id,
        actor=_actor(actor),
        client_id=str(actor.id),  # la progression est envoyée à la session WebSocket du formateur
        payload={"job_id": str(job.id), "game_id": str(game.id)},
    )
    try:
        await publish(request, GENERATION_COMMANDS, command, required=True)
    except Exception:
        game.status, job.status, job.error = GameStatus.FAILED, JobStatus.FAILED, "Kafka indisponible"
        await session.commit()
        raise
    return GameSummary.model_validate(game).model_copy(update={"job": JobOut.model_validate(job)})


@router.get("")
async def list_games(actor: Staff, session: Session) -> list[GameSummary]:
    query = select(BusinessGame).where(BusinessGame.status != GameStatus.ARCHIVED)
    if actor.role != UserRole.ADMIN:
        query = query.where(BusinessGame.created_by == actor.id)
    games = list(await session.scalars(query.order_by(BusinessGame.created_at.desc())))
    jobs = await _latest_jobs(session, [g.id for g in games])
    return [
        GameSummary.model_validate(g).model_copy(
            update={"job": JobOut.model_validate(jobs[g.id]) if g.id in jobs else None}
        )
        for g in games
    ]


@router.get("/{game_id}")
async def get_game(game_id: uuid.UUID, actor: Staff, session: Session) -> GameDetail:
    game = await owned_game(session, game_id, actor)
    job = (await _latest_jobs(session, [game.id])).get(game.id)
    return GameDetail.model_validate(game).model_copy(update={"job": JobOut.model_validate(job) if job else None})


async def _store_spec(
    session: Session, request: Request, game: BusinessGame, spec: dict[str, Any], actor: User
) -> None:
    """Spec écrite par un humain : refusée si le schéma n'est pas respecté ; les incohérences métier restent
    des avertissements (review.warnings) que le formateur arbitre."""
    if errors := schemas.validation_errors(schemas.resolve("business_game"), spec):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"message": "Spec invalide", "errors": errors[:20]})
    asset_ids = {a for zone in spec["world"]["zones"] for a in zone["asset_ids"]}
    known = set(await session.scalars(select(Asset.id).where(Asset.id.in_(asset_ids))))
    warnings = check_spec(spec) + [f"asset inconnu du catalogue : {a}" for a in sorted(asset_ids - known)]
    template = load_world_templates().get(spec["world"]["template"])
    if template is None:
        warnings.append(f"gabarit de carte inconnu « {spec['world']['template']} » : monde 3D vide")
    else:
        slots = {z["id"] for z in template["zones"]}
        warnings += [
            f"zone {z['id']} absente du gabarit : non affichée" for z in spec["world"]["zones"] if z["id"] not in slots
        ]
    game.spec, game.title, game.status = spec, spec["meta"]["title"][:200], GameStatus.READY
    game.spec_version = (game.spec_version or 0) + 1  # None sur un objet pas encore inséré
    game.review = {"warnings": warnings, "repairs": [], "edited_by": str(actor.id)}
    await session.commit()
    payload = {"game_id": str(game.id), "spec_version": game.spec_version, "warnings": len(warnings)}
    await publish(request, AUDIT, Envelope(type="game.spec_saved", source="api", actor=_actor(actor), payload=payload))


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_game(actor: Staff, session: Session, request: Request, spec: SpecBody) -> GameDetail:
    """Crée un business game prêt à jouer depuis une spec JSON (export d'un collègue, exemple, édition hors ligne)."""
    domain_slug = str((spec.get("meta") or {}).get("domain", ""))
    domain = await session.get(Domain, domain_slug) if domain_slug else None
    if domain is None or not domain.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "meta.domain : domaine inconnu ou inactif")
    game = BusinessGame(domain_slug=domain.slug, title="Import", brief="Import d'une spec JSON", created_by=actor.id)
    session.add(game)
    await _store_spec(session, request, game, spec, actor)
    return await get_game(game.id, actor, session)


@router.put("/{game_id}/spec")
async def update_spec(
    game_id: uuid.UUID, actor: Staff, session: Session, request: Request, spec: SpecBody
) -> GameDetail:
    """Spec relue ou modifiée par le formateur (les lobbies déjà créés gardent leur copie)."""
    game = await owned_game(session, game_id, actor)
    if game.status == GameStatus.GENERATING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Génération en cours : attendre sa fin")
    await _store_spec(session, request, game, spec, actor)
    return await get_game(game_id, actor, session)
