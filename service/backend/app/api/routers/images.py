"""Image metadata + binary streaming from MinIO, plus per-asset edit actions."""
from __future__ import annotations

import asyncio

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ...models import GenerationJob, ImageAsset, Package, User
from ...models.common import GenerationParams
from ...models.enums import PackageStatus, UserRole
from ...schemas import ImageOut, JobOut, image_out, job_out
from ...services.storage import get_storage
from ..deps import get_current_user, require_executor

router = APIRouter(tags=["images"])


async def _get_image_or_404(image_id: str) -> ImageAsset:
    try:
        img = await ImageAsset.get(PydanticObjectId(image_id))
    except Exception:
        img = None
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return img


def _authorise(img: ImageAsset, user: User) -> None:
    if user.role == UserRole.EXECUTOR and img.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your image")


async def _assert_package_editable(package_id: str) -> Package:
    """A package can only be edited while the executor still owns the workflow
    (draft / rejected / generating). Once it is pending review or approved it is
    frozen so the art-director always sees a stable snapshot."""
    pkg = await Package.get(PydanticObjectId(package_id))
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if pkg.status in (PackageStatus.PENDING_REVIEW, PackageStatus.APPROVED):
        raise HTTPException(
            status_code=409,
            detail="Package is locked for review; unlock it before editing.",
        )
    return pkg


@router.get("/images/{image_id}", response_model=ImageOut)
async def get_image_meta(image_id: str, user: User = Depends(get_current_user)):
    img = await _get_image_or_404(image_id)
    _authorise(img, user)
    return image_out(img)


@router.get("/images/{image_id}/file")
async def get_image_file(image_id: str, user: User = Depends(get_current_user)):
    img = await _get_image_or_404(image_id)
    _authorise(img, user)
    data = await asyncio.to_thread(get_storage().get_image, img.object_key)
    return Response(content=data, media_type=img.content_type)


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(image_id: str, user: User = Depends(require_executor)):
    """Delete a single asset from a package (bytes in MinIO + metadata in Mongo)."""
    img = await _get_image_or_404(image_id)
    _authorise(img, user)
    pkg = await _assert_package_editable(img.package_id)

    was_visible = img.qa_status != "failed"
    await asyncio.to_thread(get_storage().remove_image, img.object_key)
    await img.delete()

    # Keep the denormalised counters / cover consistent. QA-failed assets were
    # never counted in image_count, so only decrement for visible ones.
    if was_visible:
        pkg.image_count = max(0, pkg.image_count - 1)
    if pkg.cover_image_id == image_id:

        nxt = await ImageAsset.find(
            ImageAsset.package_id == img.package_id
        ).first_or_none()
        pkg.cover_image_id = str(nxt.id) if nxt else None
    pkg.touch()
    await pkg.save()
    return None


@router.post("/images/{image_id}/restore", response_model=ImageOut)
async def restore_image(image_id: str, user: User = Depends(require_executor)):
    """Manually add a QA-rejected asset back into the package.

    The executor reviews assets that the automatic QA gate marked ``failed``
    (via ``GET /packages/{id}/images?include_failed=true``) and can decide to
    keep one anyway. Restoring flips it to ``passed`` and bumps the package's
    visible image counter so it behaves like any accepted asset from then on.
    """
    img = await _get_image_or_404(image_id)
    _authorise(img, user)
    pkg = await _assert_package_editable(img.package_id)

    if img.qa_status != "failed":
        # Already visible — nothing to do, just return current state.
        return image_out(img)

    img.qa_status = "passed"
    img.qa_reason = None
    await img.save()

    pkg.image_count += 1
    if not pkg.cover_image_id:
        pkg.cover_image_id = str(img.id)
    pkg.touch()
    await pkg.save()
    return image_out(img)


@router.post("/images/{image_id}/regenerate", response_model=JobOut, status_code=202)

async def regenerate_image(
    image_id: str, user: User = Depends(require_executor)
):
    """Re-roll a single asset: queue a fresh 1-image job reusing the original
    asset's prompt and parameters but a new random seed. The old asset is
    removed so the package keeps its size."""
    img = await _get_image_or_404(image_id)
    _authorise(img, user)
    pkg = await _assert_package_editable(img.package_id)

    params = GenerationParams(**(img.params or {}))
    params.seed = None  # force a fresh seed for a genuinely different result

    job = GenerationJob(
        package_id=img.package_id,
        owner_id=str(user.id),
        prompt=img.prompt,
        negative_prompt=params.negative_prompt,
        llm_expand=False,
        batch_size=1,
        params=params,
    )
    await job.insert()

    # Drop the asset being replaced.
    await asyncio.to_thread(get_storage().remove_image, img.object_key)
    await img.delete()
    pkg.image_count = max(0, pkg.image_count - 1)
    pkg.status = PackageStatus.GENERATING
    pkg.touch()
    await pkg.save()

    from ...workers.tasks import generate_images_task

    generate_images_task.delay(str(job.id))
    return job_out(job)
