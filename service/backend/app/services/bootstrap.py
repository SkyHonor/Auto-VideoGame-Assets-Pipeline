"""First-boot seeding of demo accounts so the product is instantly demoable."""
from __future__ import annotations

from ..core.security import hash_password
from ..models import User
from ..models.enums import UserRole

DEFAULT_USERS = [
    ("artist", "artist123", "Alex Artist", UserRole.EXECUTOR),
    ("director", "director123", "Dana Director", UserRole.ART_DIRECTOR),
]


async def seed_default_users() -> None:
    for username, password, full_name, role in DEFAULT_USERS:
        existing = await User.find_one(User.username == username)
        if existing is None:
            await User(
                username=username,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=role,
            ).insert()
