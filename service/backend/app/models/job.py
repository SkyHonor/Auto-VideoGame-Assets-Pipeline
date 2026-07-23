"""Generation job document — one prompt turned into a batch of images."""
from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from .common import GenerationParams
from .enums import JobStatus


class GenerationJob(Document):
    package_id: str
    owner_id: str

    prompt: str
    negative_prompt: str = ""
    llm_expand: bool = False
    expanded_prompt: str | None = None

    batch_size: int = 1
    params: GenerationParams = Field(default_factory=GenerationParams)

    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    image_ids: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    class Settings:
        name = "jobs"
        indexes = [
            pymongo.IndexModel([("package_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("status", pymongo.ASCENDING)]),
        ]
