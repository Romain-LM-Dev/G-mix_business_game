"""Stockage objet via l'API S3 (RustFS en dev). boto3 est synchrone : appels déportés dans un thread.

Buckets : gmix-assets (assets 3D .glb/.png), gmix-knowledge (documents sources du RAG),
gmix-games (exports de business games, rapports de débrief).
"""

import asyncio
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from gmix.settings import get_settings


@lru_cache
def s3_client(public: bool = False) -> Any:
    """public=True : client signé pour l'adresse vue par les joueurs (URL présignées en réseau ou à distance)."""
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=(s.s3_public_endpoint or s.s3_endpoint) if public else s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=3,
            read_timeout=30,
            # Les sommes de contrôle par défaut de boto3 >= 1.36 ne sont pas gérées par tous les S3 compatibles
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


async def list_buckets() -> set[str]:
    def _run() -> set[str]:
        return {b["Name"] for b in s3_client().list_buckets().get("Buckets", [])}

    return await asyncio.to_thread(_run)


async def ensure_buckets() -> list[str]:
    """Crée les buckets manquants. Idempotent. Retourne les noms créés."""
    existing = await list_buckets()
    missing = [b for b in get_settings().buckets if b not in existing]
    for name in missing:
        await asyncio.to_thread(s3_client().create_bucket, Bucket=name)
    return missing


async def put_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    await asyncio.to_thread(s3_client().put_object, Bucket=bucket, Key=key, Body=data, ContentType=content_type)


async def get_bytes(bucket: str, key: str) -> bytes:
    def _run() -> bytes:
        return s3_client().get_object(Bucket=bucket, Key=key)["Body"].read()

    return await asyncio.to_thread(_run)


async def presigned_get_url(bucket: str, key: str, expires_s: int = 3600) -> str:
    """URL temporaire de téléchargement direct (ex. Godot télécharge un .glb sans passer par l'API).
    Signée pour S3_PUBLIC_ENDPOINT : l'hôte signé doit être celui que le joueur contacte."""
    return await asyncio.to_thread(
        s3_client(public=True).generate_presigned_url,
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_s,
    )
