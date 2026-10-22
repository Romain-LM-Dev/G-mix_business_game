"""Client Ollama minimal (httpx) : chat, chat en streaming, embeddings et modèles de décision (tev1).

On appelle l'API REST directement : la bibliothèque `ollama` ne gère pas l'endpoint /v1/systemone
des modèles de décision, et l'accès brut donne les compteurs de tokens exacts.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


@dataclass(slots=True)
class Usage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float = 0.0
    load_ms: float = 0.0  # > 0 : le modèle a été (re)chargé en VRAM pour cet appel

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def from_ollama(cls, data: dict[str, Any]) -> "Usage":
        return cls(
            model=data.get("model", ""),
            prompt_tokens=data.get("prompt_eval_count") or 0,
            completion_tokens=data.get("eval_count") or 0,
            duration_ms=(data.get("total_duration") or 0) / 1e6,
            load_ms=(data.get("load_duration") or 0) / 1e6,
        )


@dataclass(slots=True)
class ChatResult:
    content: str
    usage: Usage
    thinking: str | None = None
    done_reason: str | None = None  # "length" : num_predict atteint, sortie tronquée
    cached: bool = False


class OllamaClient:
    def __init__(self, base_url: str, timeout_s: float = 300.0, api_key: str = "") -> None:
        # api_key : Ollama n'a pas d'authentification ; sur un serveur distant il est placé derrière un reverse
        # proxy qui exige un jeton Bearer. Vide en local.
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_s, connect=5.0), headers=headers
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def version(self) -> str:
        return (await self._get("/api/version"))["version"]

    async def installed_models(self) -> set[str]:
        return {m["name"] for m in (await self._get("/api/tags")).get("models", [])}

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: dict[str, Any] | None = None,
        fmt: str | dict[str, Any] | None = None,
        think: bool | None = None,
        keep_alive: str | None = None,
    ) -> ChatResult:
        body = _chat_body(model, messages, options, fmt, think, keep_alive, stream=False)
        data = await self._post("/api/chat", body)
        message = data.get("message") or {}
        return ChatResult(
            content=message.get("content", ""),
            thinking=message.get("thinking"),
            usage=Usage.from_ollama(data),
            done_reason=data.get("done_reason"),
        )

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
        keep_alive: str | None = None,
    ) -> AsyncIterator[str | Usage]:
        """Rend les fragments de texte au fil de l'eau, puis un `Usage` final."""
        body = _chat_body(model, messages, options, None, think, keep_alive, stream=True)
        async with self._http.stream("POST", "/api/chat", json=body) as response:
            if response.status_code >= 400:
                raise OllamaError(f"/api/chat -> HTTP {response.status_code}: {(await response.aread())[:500]!r}")
            async for line in response.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise OllamaError(data["error"])
                chunk = (data.get("message") or {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    yield Usage.from_ollama(data)

    async def embed(
        self, model: str, inputs: list[str], *, keep_alive: str | None = None
    ) -> tuple[list[list[float]], Usage]:
        body: dict[str, Any] = {"model": model, "input": inputs}
        if keep_alive:
            body["keep_alive"] = keep_alive
        data = await self._post("/api/embed", body)
        return data["embeddings"], Usage.from_ollama(data)

    async def decide(
        self,
        model: str,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
        *,
        keep_alive: str | None = None,
    ) -> dict[str, Any]:
        """Modèle de décision (tev1, API compatible Jev / SystemOne).

        questions : {nom: {"type": "choice"|"noul"|"score", "instructions": str, "criteria": ...}}
        1 à 64 questions par appel ; contexte effectif ~2 000 tokens ; corps <= 64 Kio.
        """
        body: dict[str, Any] = {"model": model, "state": state, "questions": questions}
        if keep_alive:
            body["keep_alive"] = keep_alive
        return await self._post("/v1/systemone", body)

    async def _get(self, path: str) -> dict[str, Any]:
        response = await self._http.get(path)
        if response.status_code >= 400:
            raise OllamaError(f"{path} -> HTTP {response.status_code}: {response.text[:500]}")
        return response.json()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._http.post(path, json=body)
        if response.status_code >= 400:
            raise OllamaError(f"{path} -> HTTP {response.status_code}: {response.text[:500]}")
        return response.json()


def _chat_body(
    model: str,
    messages: list[dict[str, str]],
    options: dict[str, Any] | None,
    fmt: str | dict[str, Any] | None,
    think: bool | None,
    keep_alive: str | None,
    *,
    stream: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream, "options": options or {}}
    if fmt is not None:
        body["format"] = fmt  # "json" ou schéma JSON (sorties structurées, décodage contraint)
    if think is not None:
        body["think"] = think
    if keep_alive:
        body["keep_alive"] = keep_alive
    return body
