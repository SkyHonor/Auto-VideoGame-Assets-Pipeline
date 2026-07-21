"""MongoDB / Beanie initialisation."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from beanie import init_beanie

from ..core.config import settings
from ..models import DOCUMENT_MODELS

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def init_db(
    uri: str | None = None,
    db_name: str | None = None,
    client: AsyncIOMotorClient | None = None,
) -> AsyncIOMotorDatabase:
    """Connect to MongoDB and register all Beanie document models.

    A pre-built ``client`` can be injected (used by the test-suite with an
    in-memory mongomock client).
    """
    global _client, _database
    _client = client or AsyncIOMotorClient(uri or settings.mongo_uri)
    _database = _client[db_name or settings.mongo_db]
    await init_beanie(database=_database, document_models=DOCUMENT_MODELS)
    return _database


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")
    return _database


async def close_db() -> None:
    global _client, _database
    if _client is not None:
        _client.close()
    _client = None
    _database = None
