"""Asset package document — the unit sent for art-direction review."""
from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from .enums import PackageStatus


class Package(Document):
    name: str
    description: str = ""
    owner_id: str
    owner_username: str
    status: PackageStatus = PackageStatus.DRAFT

    image_count: int = 0
    cover_image_id: str | None = None

    # Versioning: incremented every time the package is (re)submitted for
    # review. Combined with the immutable Review history this gives a full
    # audit trail of rejections up to final approval.
    version: int = 1

    # Review outcome (denormalised for quick listing)
    review_comment: str | None = None
    reviewed_by: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None

    class Settings:
        name = "packages"
        indexes = [
            pymongo.IndexModel([("owner_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("status", pymongo.ASCENDING)]),
            pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
        ]

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
