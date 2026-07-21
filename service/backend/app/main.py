"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .core.config import settings
from .db import close_db, init_db
from .services.bootstrap import seed_default_users
from .services.storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.seed_default_users:
        await seed_default_users()
    try:
        get_storage().ensure_bucket()
    except Exception:
        # MinIO may not be reachable yet during cold-start; health endpoint reports it.
        pass
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AssetForge API",
        version=__version__,
        description="On-premise game-asset generation service (ComfyUI + LoRA).",
        lifespan=lifespan,
    )

    wildcard = settings.cors_origin_list == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .api.routers import auth, generation, health, images, packages

    prefix = settings.api_v1_prefix
    for module in (health, auth, packages, generation, images):
        app.include_router(module.router, prefix=prefix)

    @app.get("/")
    async def root():
        return {"service": settings.app_name, "version": __version__, "docs": "/docs"}

    return app


app = create_app()
