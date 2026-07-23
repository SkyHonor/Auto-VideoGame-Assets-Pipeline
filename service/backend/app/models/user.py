"""User document."""
from __future__ import annotations

from datetime import datetime, timezone

import pymongo
from beanie import Document
from pydantic import Field

from .enums import UserRole


class User(Document):
    username: str
    full_name: str = ""
    hashed_password: str
    role: UserRole = UserRole.EXECUTOR
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = [
            pymongo.IndexModel([("username", pymongo.ASCENDING)], unique=True),
        ]
