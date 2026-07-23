"""Liveness / readiness probe with downstream dependency checks."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from ...core.config import settings
from ...services.comfy_client import ComfyUIClient
from ...services.llm import LLMExpander
from ...services.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    async def _mongo() -> bool:
        try:
            from ...db import get_database

            await get_database().command("ping")
            return True
        except Exception:
            return False

    def _minio() -> bool:
        try:
            return get_storage().client.bucket_exists(settings.minio_bucket)
        except Exception:
            return False

    mongo_ok, minio_ok, comfy_ok, ollama_ok = await asyncio.gather(
        _mongo(),
        asyncio.to_thread(_minio),
        asyncio.to_thread(
            ComfyUIClient(settings.comfyui_url, timeout=5).health
        ),
        asyncio.to_thread(LLMExpander().health),
    )
    ok = mongo_ok and minio_ok
    return {
        "status": "ok" if ok else "degraded",
        "app": settings.app_name,
        "dependencies": {
            "mongodb": mongo_ok,
            "minio": minio_ok,
            "comfyui": comfy_ok,
            "ollama": ollama_ok,
        },
    }
