"""Immutable audit record of an art-director's decision on a package."""
from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from .enums import ReviewDecision


class Review(Document):
    package_id: str
    art_director_id: str
    art_director_username: str
    decision: ReviewDecision
    comment: str = ""
    # Snapshot of the package version this decision was made against, so the
    # rejection history reads as "v1 rejected -> v2 rejected -> v3 approved".
    package_version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "reviews"
        indexes = [
            pymongo.IndexModel([("package_id", pymongo.ASCENDING)]),
            pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
        ]
