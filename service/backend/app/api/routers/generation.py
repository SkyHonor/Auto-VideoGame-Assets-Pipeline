"""Generation endpoints: enqueue a job (1 or batch) and poll its status."""
from __future__ import annotations

from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from ...models import GenerationJob, Package, User
from ...models.enums import PackageStatus
from ...schemas import GenerateRequest, JobOut, job_out
from ..deps import get_current_user, require_executor

router = APIRouter(tags=["generation"])


@router.post("/packages/{package_id}/generate", response_model=JobOut, status_code=202)
async def generate(
    package_id: str,
    payload: GenerateRequest,
    user: User = Depends(require_executor),
):
    try:
        pkg = await Package.get(PydanticObjectId(package_id))
    except Exception:
        pkg = None
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if pkg.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your package")
    if pkg.status in (PackageStatus.PENDING_REVIEW, PackageStatus.APPROVED):
        raise HTTPException(
            status_code=409,
            detail="Package is locked for review; create a new one to generate.",
        )

    # The QA toggle lives on the request; persist it into the params so the
    # worker (which only reads job.params) can honour it, and so a regenerate
    # reproducing these params keeps the same behaviour.
    params = payload.params
    params.qa_check = payload.qa_check

    job = GenerationJob(
        package_id=package_id,
        owner_id=str(user.id),
        prompt=payload.prompt,
        negative_prompt=params.negative_prompt,
        llm_expand=payload.llm_expand,
        batch_size=payload.batch_size,
        params=params,
    )

    await job.insert()

    pkg.status = PackageStatus.GENERATING
    pkg.touch()
    await pkg.save()

    # Enqueue on the Celery worker pool (imported lazily to avoid a hard
    # broker dependency during unit tests).
    from ...workers.tasks import generate_images_task

    generate_images_task.delay(str(job.id))
    return job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: User = Depends(get_current_user)):
    try:
        job = await GenerationJob.get(PydanticObjectId(job_id))
    except Exception:
        job = None
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_out(job)
