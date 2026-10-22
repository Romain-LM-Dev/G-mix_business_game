"""Test de fumée de l'environnement complet.

Prérequis : scripts\\infra.ps1 up ; scripts\\api.ps1 ; scripts\\worker.ps1 system_ping
Usage     : python -m gmix.tools.smoke [--api http://127.0.0.1:8000] [--timeout 180] [--godot <godot_console.exe>]

Un compte admin jetable est créé pour le test puis supprimé.
1. /health : base, Kafka, stockage, Ollama
2. pipeline : POST /api/v1/system/ping -> Kafka -> worker -> Ollama -> Kafka -> WebSocket authentifié
3. RAG : ingestion d'une fiche, embeddings, recherche hybride (transaction annulée : rien n'est conservé)
4. (--godot) la même liaison depuis le client Godot headless
"""

import argparse
import asyncio
import contextlib
import json
import os
import secrets
import sys
import time
import uuid
from collections.abc import AsyncIterator

import httpx
import websockets
from sqlalchemy import delete

from gmix.api.auth import create_access_token
from gmix.db import get_engine, get_sessionmaker
from gmix.db.models import User, UserRole
from gmix.llm.service import LLMService
from gmix.rag.ingest import ingest_bytes
from gmix.rag.retrieval import build_context, search
from gmix.settings import get_settings
from gmix.tools.create_user import create_user

FIXTURE = """# Besoin en fonds de roulement (fiche de test)

Le besoin en fonds de roulement (BFR) d'exploitation mesure l'argent immobilisé par le cycle
d'exploitation : BFR = stocks + créances clients - dettes fournisseurs.

Le fonds de roulement (FR) correspond aux ressources stables restant après le financement des
immobilisations : FR = capitaux permanents - actif immobilisé. La trésorerie nette est égale à FR - BFR.

Une entreprise rentable peut manquer de trésorerie si son BFR augmente plus vite que son fonds de
roulement, par exemple quand ses clients paient plus tard. Pour 12 M€ de chiffre d'affaires annuel,
réduire de 10 jours le délai de paiement clients libère environ 12 000 k€ x 10 / 360, soit 333 k€.
"""


def _status(ok: bool) -> str:
    return "OK" if ok else "KO"


async def check_health(api: str) -> bool:
    async with httpx.AsyncClient(timeout=30) as http:
        report = (await http.get(f"{api}/health")).json()
    for name, result in report["services"].items():
        print(f"  [{_status(result['ok'])}] {name}: { ({k: v for k, v in result.items() if k != 'ok'}) }")
    return report["status"] == "ok"


@contextlib.asynccontextmanager
async def temporary_admin() -> AsyncIterator[str]:
    """Compte admin jetable le temps du test (le ping du pipeline et le WebSocket exigent une connexion)."""
    user = await create_user(f"smoke-{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(18), UserRole.ADMIN)
    try:
        yield create_access_token(user)
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()


async def check_pipeline(api: str, timeout_s: float, token: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    async with websockets.connect(f"{api.replace('http', 'ws', 1)}/ws", additional_headers=headers) as ws:
        json.loads(await ws.recv())  # session.welcome
        async with httpx.AsyncClient(timeout=15, headers=headers) as http:
            (await http.post(f"{api}/api/v1/system/ping", json={"message": "smoke"})).raise_for_status()
        start = time.perf_counter()
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout_s))
            if message["type"] == "system.pong":
                break
    print(f"  aller-retour complet : {time.perf_counter() - start:.1f} s")
    checks = message["payload"]["checks"]
    for name, check in checks.items():
        print(f"  [{_status(check['ok'])}] {name}: { ({k: v for k, v in check.items() if k != 'ok'}) }")
    return all(check["ok"] for check in checks.values())


async def check_rag() -> bool:
    llm = LLMService.from_settings(with_cache=False)
    try:
        async with get_sessionmaker()() as session:
            report = await ingest_bytes(
                session,
                llm,
                filename="fiche_test_bfr.md",
                data=FIXTURE.encode(),
                domain="finance-entreprise",
                title="Fiche test BFR",
                store_original=False,
            )
            query = "Comment calcule-t-on la trésorerie nette ?"
            hits = await search(
                session, query_vector=await llm.embed_query(query), query_text=query, domain="finance-entreprise", k=2
            )
            context, _ = build_context(hits, max_tokens=300)
            await session.rollback()
    finally:
        await llm.aclose()
        await get_engine().dispose()
    print(f"  ingestion : {report}")
    print(f"  meilleur passage : {context[:160]!r}…")
    return bool(hits)


async def check_godot(api: str, godot_exe: str, token: str) -> bool:
    """Même liaison vue depuis le client Godot headless, avec le jeton du compte jetable."""
    project = get_settings().gmix_ai_dir.parent / "godot"
    process = await asyncio.create_subprocess_exec(
        godot_exe, "--headless", "--path", str(project), "--", "--smoke", f"--api={api}",
        env=os.environ | {"GMIX_SMOKE_TOKEN": token},
    )  # fmt: skip
    return await process.wait() == 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=180.0, help="secondes (1er chargement des modèles en VRAM)")
    parser.add_argument("--godot", help="exécutable console de Godot : ajoute le test du client headless")
    args = parser.parse_args()
    results = {}
    try:
        async with temporary_admin() as token:
            steps = [
                ("health", check_health(args.api)),
                ("pipeline", check_pipeline(args.api, args.timeout, token)),
                ("rag", check_rag()),
            ]
            if args.godot:
                steps.append(("godot", check_godot(args.api, args.godot, token)))
            for name, step in steps:
                print(f"== {name}")
                try:
                    results[name] = await step
                except Exception as exc:
                    print(f"  ERREUR {type(exc).__name__}: {exc}")
                    results[name] = False
    finally:
        await get_engine().dispose()
    print("== résumé : " + ", ".join(f"{name} {_status(ok)}" for name, ok in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
