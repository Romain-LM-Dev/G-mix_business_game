"""Catalogue des topics Kafka : source unique de vérité (créés par `python -m gmix.bootstrap`).

Convention : gmix.<contexte>.<commands|events|…>. Clé de partition = lobby_id (ou correlation_id)
pour garantir l'ordre des messages d'une même partie / d'une même génération.
Le temps réel 3D (positions des joueurs) ne passe PAS par Kafka : voir docs/architecture.md.
"""

from dataclasses import dataclass

HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS


@dataclass(frozen=True, slots=True)
class Topic:
    name: str
    partitions: int
    retention_ms: int
    doc: str


SYSTEM_PING = Topic("gmix.system.ping", 1, HOUR_MS, "Diagnostic : requête de test du pipeline (API -> worker)")
SYSTEM_PONG = Topic("gmix.system.pong", 1, HOUR_MS, "Diagnostic : réponse du worker (worker -> API -> WebSocket)")
GENERATION_COMMANDS = Topic(
    "gmix.generation.commands", 3, 7 * DAY_MS, "Demandes de génération / régénération de business game"
)
GENERATION_EVENTS = Topic(
    "gmix.generation.events", 3, 7 * DAY_MS, "Progression et résultat des générations (stage, completed, failed)"
)
GAME_EVENTS = Topic(
    "gmix.game.events", 3, 30 * DAY_MS, "Décisions des joueurs et événements de partie (scores, KPI, aléas)"
)
NPC_TRANSCRIPTS = Topic(
    "gmix.npc.transcripts", 3, 30 * DAY_MS, "Dialogues PNJ terminés (évaluation pédagogique, analytics)"
)
RAG_COMMANDS = Topic("gmix.rag.commands", 1, 7 * DAY_MS, "Ingestion / réindexation de documents de connaissance")
RAG_EVENTS = Topic("gmix.rag.events", 1, 7 * DAY_MS, "Résultats d'ingestion RAG")
AUDIT = Topic("gmix.audit", 1, 90 * DAY_MS, "Journal d'audit des actions formateur / admin")
DLQ = Topic("gmix.dlq", 1, 30 * DAY_MS, "Messages en échec (dead letter queue) avec l'erreur")

ALL_TOPICS: tuple[Topic, ...] = (
    SYSTEM_PING,
    SYSTEM_PONG,
    GENERATION_COMMANDS,
    GENERATION_EVENTS,
    GAME_EVENTS,
    NPC_TRANSCRIPTS,
    RAG_COMMANDS,
    RAG_EVENTS,
    AUDIT,
    DLQ,
)
