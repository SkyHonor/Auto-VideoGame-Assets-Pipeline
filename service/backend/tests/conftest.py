"""Shared pytest fixtures.

The API is tested against an in-memory MongoDB (mongomock-motor) with Beanie,
an in-memory object store (FakeStorage) and a stubbed Celery ``.delay`` so the
whole HTTP surface can be exercised without external services.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.security import hash_password
from app.db import mongodb
from app.models import DOCUMENT_MODELS, ImageAsset, Package, User
from app.models.enums import UserRole

API = "/api/v1"


class FakeStorage:
    """In-memory stand-in for MinIO."""

    bucket = "assets"

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def ensure_bucket(self) -> None:  # noqa: D401
        pass

    def put_image(self, key: str, data: bytes, content_type: str = "image/png") -> int:
        self.data[key] = data
        return len(data)

    def get_image(self, key: str) -> bytes:
        return self.data[key]

    def remove_image(self, key: str) -> None:
        self.data.pop(key, None)


@pytest_asyncio.fixture
async def storage() -> FakeStorage:
    return FakeStorage()


@pytest_asyncio.fixture
async def client(monkeypatch, storage):
    mock_client = AsyncMongoMockClient()
    db = mock_client["assetforge_test"]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)
    mongodb._client = mock_client
    mongodb._database = db

    # Seed the two demo personas.
    await User(
        username="artist",
        full_name="Alex Artist",
        hashed_password=hash_password("artist123"),
        role=UserRole.EXECUTOR,
    ).insert()
    await User(
        username="director",
        full_name="Dana Director",
        hashed_password=hash_password("director123"),
        role=UserRole.ART_DIRECTOR,
    ).insert()

    # Route object storage to the in-memory fake.
    import app.api.routers.images as images_router
    import app.api.routers.packages as packages_router

    monkeypatch.setattr(packages_router, "get_storage", lambda: storage)
    monkeypatch.setattr(images_router, "get_storage", lambda: storage)

    # Neutralise the Celery dispatch (workers tested separately).
    from app.workers.tasks import generate_images_task

    monkeypatch.setattr(generate_images_task, "delay", lambda *a, **k: None)

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def auth_headers(client: AsyncClient, username: str, password: str) -> dict:
    resp = await client.post(
        f"{API}/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def simulate_generation(
    package_id: str, owner_id: str, storage: FakeStorage, n: int = 2
) -> list[str]:
    """Emulate a finished worker run: store bytes + ImageAsset docs + counts."""
    from app.services.mock import generate_placeholder

    ids = []
    pkg = await Package.get(package_id)
    for i in range(n):
        seed = 1000 + i
        key = f"{package_id}/job/{seed}.png"
        storage.put_image(key, generate_placeholder("test", 64, 64, seed))
        img = ImageAsset(
            package_id=package_id,
            job_id="job",
            owner_id=owner_id,
            object_key=key,
            bucket=storage.bucket,
            filename=f"{seed}.png",
            size_bytes=1,
            prompt="test",
            seed=seed,
            width=64,
            height=64,
        )
        await img.insert()
        ids.append(str(img.id))
    pkg.image_count += n
    pkg.cover_image_id = ids[0]
    await pkg.save()
    return ids
