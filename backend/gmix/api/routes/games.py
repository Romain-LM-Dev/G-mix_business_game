"""Business games simulés : génération par paramètres (instantanée, sans modèle ni texte libre), relecture,
import et export de la spec (docs/decisions/0006). Un formateur ne voit que ses business games, l'admin les voit
tous (docs/roles.md)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select

from gmix.api.auth import Session, Staff
from gmix.api.deps import publish
from gmix.db.models import BusinessGame, GameStatus, User, UserRole
from gmix.game.generation import autopilot_check, generate
from gmix.game.spec import GameParams, SimSpec, load_pack
from gmix.messaging.envelope import Actor, Envelope
from gmix.messaging.topics import AUDIT
from gmix.settings import get_settings

router = APIRouter(prefix="/api/v1/games", tags=["business games"])
# [min, max, défaut], comme `limits` d'un pack ; ai/simulation.yaml n'en déclare pas
ATELIER_RANGES = {"weeks": [4, 12, 8], "products": [2, 4, 3]}
ATELIER_INFO = {  # ai/simulation.yaml n'a pas ces clés ; un pack de ai/packs/ les déclare lui-même
    "label": "Atelier de production",
    "description": "Simulation hebdomadaire de chaîne logistique : achats, lignes agrégées, qualité, ventes.",
    "domain": "supply-chain",
    "engine": "weekly",
}
SpecBody = Annotated[dict[str, Any], Body(description="spec complète (gmix.game.spec.SimSpec)")]


class GameSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    domain_slug: str
    status: GameStatus
    created_at: datetime


class GameDetail(GameSummary):
    brief: str
    params: dict[str, Any]
    review: dict[str, Any]
    spec_version: int
    spec: dict[str, Any] | None


async def owned_game(session: Session, game_id: uuid.UUID, user: User) -> BusinessGame:
    game = await session.get(BusinessGame, game_id)
    if game is None or (user.role != UserRole.ADMIN and game.created_by != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business game introuvable")
    return game


def _choices(pack: dict[str, Any]) -> dict[str, Any]:
    """Les choix d'un pack (secteurs, modules, agents, caractère, difficulté, aléas), tels que lus par le client."""
    return {
        "themes": [
            {"id": key, "label": t["label"], "description": t["description"],
             "products": [p["name"] for p in t["products"]]}
            for key, t in pack["themes"].items()
        ],
        "modules": [
            {"id": key, "title": m["title"], "description": m["description"]} for key, m in pack["modules"].items()
        ],
        "extra_agents": [
            {"id": key, "title": a["title"], "description": a["description"]}
            for key, a in pack["extra_agents"].items()
        ],
        "tones": [{"id": key, "label": t["label"]} for key, t in pack["agent_tones"].items()],
        "difficulties": [
            {"id": key, "label": d["label"], "detail": d["detail"]} for key, d in pack["difficulties"].items()
        ],
        "events": [{"id": key, "label": e["label"]} for key, e in pack["events_levels"].items()],
    }  # fmt: skip


def _pack_entry(pack_id: str) -> dict[str, Any]:
    pack = load_pack(pack_id)
    entry = ATELIER_INFO | {k: pack[k] for k in ATELIER_INFO if k in pack}
    return {"id": pack_id, **entry, "params": pack.get("params", []), **_choices(pack),
            "limits": pack.get("limits", ATELIER_RANGES)}  # fmt: skip


@router.get("/options")
async def generation_options(actor: Staff) -> dict[str, Any]:
    """Choix proposés au formateur pour générer un business game : clés de premier niveau = pack « atelier »
    (ai/simulation.yaml, inchangé) ; `packs` liste tous les packs (ai/packs/*.yaml), `limits` au format `ranges`."""
    packs = ["atelier", *sorted(p.stem for p in (get_settings().gmix_ai_dir / "packs").glob("*.yaml"))]
    return _choices(load_pack("atelier")) | {"ranges": ATELIER_RANGES, "packs": [_pack_entry(p) for p in packs]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_game(params: GameParams, actor: Staff, session: Session, request: Request) -> GameDetail:
    """Génère le business game à partir des seuls paramètres (pack et options compris), puis le vérifie par une
    partie en pilote automatique."""
    spec = generate(params)
    game = BusinessGame(domain_slug=spec["meta"]["domain"], created_by=actor.id)
    session.add(game)
    await _store(session, request, game, spec, actor, "game.generated")
    return await get_game(game.id, actor, session)


@router.get("")
async def list_games(actor: Staff, session: Session) -> list[GameSummary]:
    query = select(BusinessGame).where(BusinessGame.status != GameStatus.ARCHIVED)
    if actor.role != UserRole.ADMIN:
        query = query.where(BusinessGame.created_by == actor.id)
    return [
        GameSummary.model_validate(g) for g in await session.scalars(query.order_by(BusinessGame.created_at.desc()))
    ]


@router.get("/{game_id}")
async def get_game(game_id: uuid.UUID, actor: Staff, session: Session) -> GameDetail:
    return GameDetail.model_validate(await owned_game(session, game_id, actor))


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_game(actor: Staff, session: Session, request: Request, spec: SpecBody) -> GameDetail:
    """Crée un business game depuis une spec JSON (export d'un collègue, spec retouchée hors ligne)."""
    valid = _validated(spec)
    game = BusinessGame(domain_slug=valid["meta"]["domain"], created_by=actor.id)
    session.add(game)
    await _store(session, request, game, valid, actor, "game.imported")
    return await get_game(game.id, actor, session)


@router.put("/{game_id}/spec")
async def update_spec(
    game_id: uuid.UUID, actor: Staff, session: Session, request: Request, spec: SpecBody
) -> GameDetail:
    """Spec retouchée par le formateur (les lobbies déjà créés gardent leur copie)."""
    game = await owned_game(session, game_id, actor)
    await _store(session, request, game, _validated(spec), actor, "game.spec_saved")
    return await get_game(game_id, actor, session)


def _validated(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        return SimSpec.model_validate(spec).model_dump(mode="json")
    except ValidationError as exc:
        errors = [f"{'/'.join(map(str, e['loc']))} : {e['msg']}" for e in exc.errors()[:20]]
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, {"message": "Spec invalide", "errors": errors}
        ) from None


async def _store(
    session: Session, request: Request, game: BusinessGame, spec: dict[str, Any], actor: User, event_type: str
) -> None:
    meta = spec["meta"]
    modules = ", ".join(m["title"].lower() for m in spec["modules"])
    game.spec, game.title, game.status = spec, meta["title"][:200], GameStatus.READY
    game.brief = f"{meta['theme_label']} · {meta['difficulty_label']} · {meta['weeks']} semaines · {modules}"
    game.params = spec["params"]
    game.spec_version = (game.spec_version or 0) + 1  # None sur un objet pas encore inséré
    game.review = {"autopilot": autopilot_check(spec), "edited_by": str(actor.id)}
    await session.commit()
    payload = {"game_id": str(game.id), "spec_version": game.spec_version, "seed": spec["seed"]}
    actor_info = Actor(user_id=actor.id, role=actor.role.value)
    await publish(request, AUDIT, Envelope(type=event_type, source="api", actor=actor_info, payload=payload))
