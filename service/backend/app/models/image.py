"""Generated image asset document — metadata stored in Mongo, bytes in MinIO."""
from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field


class ImageAsset(Document):
    package_id: str
    job_id: str
    owner_id: str

    # MinIO object storage coordinates
    object_key: str
    bucket: str
    filename: str
    content_type: str = "image/png"
    size_bytes: int = 0

    # Reproducibility metadata (everything needed to regenerate the asset)
    prompt: str
    negative_prompt: str = ""
    expanded_prompt: str | None = None
    seed: int = 0
    width: int = 1024
    height: int = 1024
    workflow_type: str = "character"
    params: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "images"
        indexes = [
            pymongo.IndexModel([("package_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("job_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
        ]
