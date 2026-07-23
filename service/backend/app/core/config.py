"""Centralised application configuration.

All settings are environment-driven so the exact same image can run locally,
in CI and in the on-premise docker-compose stack without code changes.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    app_name: str = "AssetForge"
    api_v1_prefix: str = "/api/v1"
    environment: str = "local"
    cors_origins: str = "*"

    # --- MongoDB (domain model + image metadata) ---
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "assetforge"

    # --- MinIO / S3 (image binaries) ---
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "assets"
    minio_secure: bool = False

    # --- Redis / Celery (async generation workers) ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- ComfyUI (GPU inference backend) ---
    comfyui_url: str = "http://localhost:8188"
    comfyui_timeout: int = 600
    # When True the worker generates deterministic placeholder images without a
    # GPU/ComfyUI (mirrors the DRY_RUN mode used in the research notebooks).
    comfyui_mock: bool = False

    # --- Ollama (local LLM prompt expansion) ---
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout: int = 120

    # --- Automatic quality assurance (optional per-request gate) ---
    # CLIP Score checks prompt<->image alignment for every image; LPIPS checks
    # in-batch diversity (only meaningful for batches of >= qa_lpips_min_batch).
    # Thresholds are derived from the research phase (see baseline/README.md).
    # When the metric libraries are unavailable the worker degrades gracefully
    # and marks assets as `skipped` instead of blocking generation.
    qa_clip_model: str = "ViT-B-32"
    qa_clip_pretrained: str = "openai"
    qa_min_clip_score: float = 0.22
    qa_min_lpips_diversity: float = 0.10
    qa_lpips_min_batch: int = 4


    # --- Auth / JWT ---
    jwt_secret: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # --- Bootstrap ---
    # Seed two demo accounts (executor / art-director) on first boot so the
    # product is instantly demoable.
    seed_default_users: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
