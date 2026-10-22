"""Enveloppe commune à tous les messages Kafka (relayée telle quelle au client Godot via WebSocket)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Actor(BaseModel):
    user_id: UUID | None = None
    role: str | None = None  # player | trainer | admin | system


class Envelope(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: str  # ex. "generation.stage_completed"
    version: int = 1
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str  # service émetteur : api, worker-system, worker-generation…
    correlation_id: UUID | None = None  # relie toute une chaîne de traitement
    causation_id: UUID | None = None  # id du message qui a provoqué celui-ci
    actor: Actor | None = None
    lobby_id: UUID | None = None
    client_id: str | None = None  # session WebSocket à notifier directement
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        return cls.model_validate_json(raw)

    def reply(self, event_type: str, source: str, payload: dict[str, Any]) -> "Envelope":
        """Message de réponse qui conserve la corrélation et la cible (lobby / client)."""
        return Envelope(
            type=event_type,
            source=source,
            correlation_id=self.correlation_id or self.id,
            causation_id=self.id,
            actor=self.actor,
            lobby_id=self.lobby_id,
            client_id=self.client_id,
            payload=payload,
        )

    def to_client(self) -> dict[str, Any]:
        """Format envoyé à Godot : {type, payload, meta}."""
        return {
            "type": self.type,
            "payload": self.payload,
            "meta": {
                "id": str(self.id),
                "correlation_id": str(self.correlation_id) if self.correlation_id else None,
                "lobby_id": str(self.lobby_id) if self.lobby_id else None,
                "occurred_at": self.occurred_at.isoformat(),
            },
        }
