"""Schéma v0 de la base : source de vérité pour `alembic revision --autogenerate`.

Conventions : UUID en clé primaire, horodatages UTC, JSONB pour les specs générées par l'IA
(toujours validées contre ai/schemas/*.schema.json avant écriture).
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Doit être égal à `dims` du modèle d'embedding dans ai/models.yaml (testé). Changer => migration + réindexation.
EMBED_DIM = 768


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB}


def _pg_enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _empty_json() -> Mapped[dict[str, Any]]:
    return mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserRole(enum.StrEnum):
    PLAYER = "player"
    TRAINER = "trainer"
    ADMIN = "admin"


class GameStatus(enum.StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class LobbyStatus(enum.StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    RUNNING = "running"
    CLOSED = "closed"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DocStatus(enum.StrEnum):
    PENDING = "pending"
    INGESTED = "ingested"
    FAILED = "failed"


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True)  # identifiant de connexion (ADR 0004)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(_pg_enum(UserRole, "user_role"), server_default=UserRole.PLAYER.value)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)


class Domain(Base):
    """Domaine d'expertise sélectionnable (contenu maintenu dans ai/domains.yaml, synchronisé par bootstrap)."""

    __tablename__ = "domains"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    meta: Mapped[dict[str, Any]] = _empty_json()


class BusinessGame(Timestamped, Base):
    __tablename__ = "business_games"

    id: Mapped[uuid.UUID] = _uuid_pk()
    domain_slug: Mapped[str] = mapped_column(ForeignKey("domains.slug"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    brief: Mapped[str] = mapped_column(Text)  # demande initiale du formateur
    status: Mapped[GameStatus] = mapped_column(
        _pg_enum(GameStatus, "game_status"), server_default=GameStatus.DRAFT.value
    )
    spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # ai/schemas/business_game.schema.json
    spec_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    params: Mapped[dict[str, Any]] = _empty_json()  # demande du formateur : niveau, durée, joueurs, compétences
    review: Mapped[dict[str, Any]] = _empty_json()  # contrôles : {"warnings": [...], "repairs": [...]}
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Lobby(Timestamped, Base):
    __tablename__ = "lobbies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120))
    join_code: Mapped[str] = mapped_column(String(8), unique=True)
    trainer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    business_game_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_games.id", ondelete="SET NULL"))
    status: Mapped[LobbyStatus] = mapped_column(
        _pg_enum(LobbyStatus, "lobby_status"), server_default=LobbyStatus.DRAFT.value
    )
    settings: Mapped[dict[str, Any]] = _empty_json()  # joueurs max, durée, difficulté, équipes…
    world_layout: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # placements d'assets (ids catalogue)
    spec: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB
    )  # copie figée de la spec : la modifier n'affecte pas la partie
    state: Mapped[dict[str, Any]] = _empty_json()  # état de partie (gmix.game.engine) : phase, KPI, décisions


class LobbyMember(Base):
    __tablename__ = "lobby_members"

    lobby_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lobbies.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    team: Mapped[str | None] = mapped_column(String(64))
    game_role: Mapped[str | None] = mapped_column(String(64))  # rôle métier dans le business game
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Asset(Timestamped, Base):
    """Asset 3D prédéfini. L'IA choisit des assets par id (jamais de géométrie générée)."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # ex. bld_office_small_01
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default="{}")
    description: Mapped[str] = mapped_column(Text, server_default="")  # texte embarqué pour le choix sémantique
    godot_scene: Mapped[str | None] = mapped_column(String(255))  # res://assets/…tscn
    storage_key: Mapped[str | None] = mapped_column(String(255))  # clé S3 du .glb (bucket gmix-assets)
    footprint: Mapped[dict[str, Any]] = _empty_json()  # emprise au sol, hauteur, points d'ancrage
    license: Mapped[str] = mapped_column(String(64), server_default="CC0")
    source_url: Mapped[str | None] = mapped_column(String(500))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class KnowledgeDocument(Timestamped, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    domain_slug: Mapped[str] = mapped_column(ForeignKey("domains.slug"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(16))  # pdf | md | txt | url
    source_uri: Mapped[str] = mapped_column(String(500))  # clé S3 (bucket gmix-knowledge) ou URL
    license: Mapped[str | None] = mapped_column(String(120))  # droits d'usage du document source
    checksum: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 : évite les doublons
    status: Mapped[DocStatus] = mapped_column(_pg_enum(DocStatus, "doc_status"), server_default=DocStatus.PENDING.value)
    meta: Mapped[dict[str, Any]] = _empty_json()


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    domain_slug: Mapped[str] = mapped_column(String(64), index=True)  # dénormalisé pour filtrer vite
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    meta: Mapped[dict[str, Any]] = _empty_json()  # page, section…
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('french', content)", persisted=True))


class GenerationJob(Timestamped, Base):
    """Suivi d'une génération IA, avec la consommation de tokens par étape (usage)."""

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_game_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("business_games.id", ondelete="CASCADE"), index=True
    )
    lobby_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lobbies.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40))  # generate_game | regenerate_section | ingest_document…
    status: Mapped[JobStatus] = mapped_column(_pg_enum(JobStatus, "job_status"), server_default=JobStatus.QUEUED.value)
    stage: Mapped[str | None] = mapped_column(String(60))
    progress: Mapped[int] = mapped_column(Integer, server_default=text("0"))  # 0..100
    usage: Mapped[dict[str, Any]] = _empty_json()  # {étape: {model, prompt_tokens, completion_tokens, ms}}
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class LLMCache(Base):
    """Cache exact des appels déterministes (temperature 0) : évite de repayer les mêmes tokens."""

    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(tâche, modèle, messages, options)
    task: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(80))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    hits: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
