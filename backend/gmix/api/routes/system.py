from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from gmix.api.auth import Staff
from gmix.api.deps import producer_dependency
from gmix.health import full_health
from gmix.messaging.envelope import Envelope
from gmix.messaging.kafka import EventProducer
from gmix.messaging.topics import SYSTEM_PING

router = APIRouter(tags=["système"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """État de chaque dépendance (toujours 200 ; `status` vaut ok ou degraded)."""
    return await full_health(request.app.state.llm)


class PingRequest(BaseModel):
    message: str = Field(default="ping", max_length=200)


@router.post("/api/v1/system/ping", status_code=202)
async def ping_pipeline(
    body: PingRequest, user: Staff, producer: Annotated[EventProducer, Depends(producer_dependency)]
) -> dict[str, str]:
    """Teste toute la chaîne : API -> Kafka -> worker-system -> Ollama -> Kafka -> API -> WebSocket.
    Réservé au formateur et à l'admin (appels IA) ; system.pong revient sur leur WebSocket."""
    event = Envelope(type="system.ping", source="api", client_id=str(user.id), payload={"message": body.message})
    await producer.publish(SYSTEM_PING, event)
    return {"correlation_id": str(event.id)}
