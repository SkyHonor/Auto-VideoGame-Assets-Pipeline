"""Generation task executed on the worker pool.

Uses synchronous PyMongo (Celery workers are not async) but writes documents
whose shape matches the Beanie models so the API reads them transparently.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

from ..core.config import settings
from ..models.common import GenerationParams
from ..services.comfy_client import ComfyUIClient
from ..services.llm import LLMExpander
from ..services.mock import generate_placeholder
from ..services.storage import StorageService
from ..services.workflow import build_workflow
from .celery_app import celery_app

_client: MongoClient | None = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri)
    return _client[settings.mongo_db]


def _now():
    return datetime.now(timezone.utc)


@celery_app.task(name="generate_images", bind=True, max_retries=0)
def generate_images_task(self, job_id: str) -> dict:
    db = _db()
    jobs, images, packages = db["jobs"], db["images"], db["packages"]
    oid = ObjectId(job_id)
    job = jobs.find_one({"_id": oid})
    if job is None:
        return {"status": "missing"}

    jobs.update_one(
        {"_id": oid}, {"$set": {"status": "running", "started_at": _now()}}
    )
    package_oid = ObjectId(job["package_id"])

    try:
        params = GenerationParams(**job.get("params", {}))
        workflow_type = (
            params.workflow_type
            if isinstance(params.workflow_type, str)
            else params.workflow_type.value
        )

        prompt = job["prompt"]
        if job.get("llm_expand"):
            expanded = LLMExpander().expand(prompt, workflow_type)
            jobs.update_one({"_id": oid}, {"$set": {"expanded_prompt": expanded}})
            effective_prompt = expanded
        else:
            effective_prompt = prompt

        storage = StorageService()
        storage.ensure_bucket()
        comfy = ComfyUIClient(
            settings.comfyui_url,
            timeout=settings.comfyui_timeout,
            save_node_id="46",
        )

        base_seed = (
            params.seed if params.seed is not None else random.randint(1, 2**31 - 1)
        )
        image_ids: list[str] = []

        for i in range(int(job.get("batch_size", 1))):
            seed = base_seed + i * 7919
            if settings.comfyui_mock:
                rendered = [
                    generate_placeholder(
                        effective_prompt,
                        params.width,
                        params.height,
                        seed,
                        workflow_type,
                    )
                ]
            else:
                workflow = build_workflow(effective_prompt, params, seed)
                rendered = comfy.generate(workflow)

            for k, data in enumerate(rendered):
                filename = f"{seed}_{k}.png"
                object_key = f"{job['package_id']}/{job_id}/{filename}"
                size = storage.put_image(object_key, data)
                doc = {
                    "package_id": job["package_id"],
                    "job_id": job_id,
                    "owner_id": job["owner_id"],
                    "object_key": object_key,
                    "bucket": storage.bucket,
                    "filename": filename,
                    "content_type": "image/png",
                    "size_bytes": size,
                    "prompt": prompt,
                    "negative_prompt": job.get("negative_prompt", ""),
                    "expanded_prompt": job.get("expanded_prompt"),
                    "seed": seed,
                    "width": params.width,
                    "height": params.height,
                    "workflow_type": workflow_type,
                    "params": params.model_dump(),
                    "created_at": _now(),
                }
                image_ids.append(str(images.insert_one(doc).inserted_id))

        jobs.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": "completed",
                    "finished_at": _now(),
                    "image_ids": image_ids,
                }
            },
        )

        set_ops = {"updated_at": _now()}
        pkg = packages.find_one({"_id": package_oid})
        if pkg is not None:
            if not pkg.get("cover_image_id") and image_ids:
                set_ops["cover_image_id"] = image_ids[0]
            if pkg.get("status") == "generating":
                set_ops["status"] = "draft"
        packages.update_one(
            {"_id": package_oid},
            {"$set": set_ops, "$inc": {"image_count": len(image_ids)}},
        )
        return {"status": "completed", "images": len(image_ids)}

    except Exception as exc:  # noqa: BLE001 - report failure back to the DB
        jobs.update_one(
            {"_id": oid},
            {"$set": {"status": "failed", "error": str(exc), "finished_at": _now()}},
        )
        pkg = packages.find_one({"_id": package_oid})
        if pkg is not None and pkg.get("status") == "generating":
            packages.update_one(
                {"_id": package_oid}, {"$set": {"status": "draft"}}
            )
        raise
