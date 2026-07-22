"""Worker task tests (mock generation mode, in-memory Mongo + storage)."""
from __future__ import annotations

import mongomock

import app.workers.tasks as tasks_mod
from app.core.config import settings


class _FakeStorage:
    bucket = "assets"

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def ensure_bucket(self) -> None:
        pass

    def put_image(self, key: str, data: bytes, content_type: str = "image/png") -> int:
        self.store[key] = data
        return len(data)


def _params(seed: int = 123) -> dict:
    return {
        "workflow_type": "character",
        "width": 256,
        "height": 256,

        "steps": 12,
        "cfg": 2.0,
        "sampler_name": "euler",
        "scheduler": "simple",
        "denoise": 1.0,
        "seed": seed,
        "style_lora_strength": 0.85,
        "negative_prompt": "",
    }


def test_worker_generates_batch_in_mock_mode(monkeypatch):
    db = mongomock.MongoClient()["assetforge_worker_test"]
    fake = _FakeStorage()

    monkeypatch.setattr(tasks_mod, "_db", lambda: db)
    monkeypatch.setattr(tasks_mod, "StorageService", lambda: fake)
    monkeypatch.setattr(settings, "comfyui_mock", True)

    pkg_id = db["packages"].insert_one(
        {"status": "generating", "image_count": 0, "cover_image_id": None}
    ).inserted_id
    job_id = db["jobs"].insert_one(
        {
            "package_id": str(pkg_id),
            "owner_id": "u1",
            "prompt": "a dragon",
            "negative_prompt": "",
            "llm_expand": False,
            "batch_size": 3,
            "params": _params(),
        }
    ).inserted_id

    result = tasks_mod.generate_images_task(str(job_id))

    # QA is off for this job, so every rendered image is visible.
    assert result == {"status": "completed", "images": 3, "visible": 3}
    job = db["jobs"].find_one({"_id": job_id})
    assert job["status"] == "completed"
    assert len(job["image_ids"]) == 3
    assert db["images"].count_documents({}) == 3
    assert len(fake.store) == 3
    # Without the QA gate assets are persisted as "skipped" (never blocked).
    assert all(img["qa_status"] == "skipped" for img in db["images"].find({}))


    pkg = db["packages"].find_one({"_id": pkg_id})
    assert pkg["image_count"] == 3
    assert pkg["status"] == "draft"  # reset from 'generating' after completion
    assert pkg["cover_image_id"] is not None


def test_worker_missing_job_is_noop(monkeypatch):
    db = mongomock.MongoClient()["assetforge_worker_empty"]
    monkeypatch.setattr(tasks_mod, "_db", lambda: db)
    from bson import ObjectId

    result = tasks_mod.generate_images_task(str(ObjectId()))
    assert result == {"status": "missing"}
