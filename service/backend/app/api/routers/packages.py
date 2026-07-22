"""Package lifecycle: create, list, submit, review and production download."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ...models import ImageAsset, Package, Review, User
from ...models.enums import PackageStatus, UserRole
from ...schemas import (
    ImageOut,
    PackageCreate,
    PackageOut,
    ReviewOut,
    ReviewRequest,
    image_out,
    package_out,
    review_out,
)
from ...services import package_flow
from ...services.storage import get_storage
from ..deps import get_current_user, require_art_director, require_executor

router = APIRouter(tags=["packages"])


async def _get_package_or_404(package_id: str) -> Package:
    try:
        pkg = await Package.get(PydanticObjectId(package_id))
    except Exception:
        pkg = None
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg


def _assert_owner(pkg: Package, user: User) -> None:
    if pkg.owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Not your package")


@router.post("/packages", response_model=PackageOut, status_code=201)
async def create_package(
    payload: PackageCreate, user: User = Depends(require_executor)
):
    pkg = Package(
        name=payload.name,
        description=payload.description,
        owner_id=str(user.id),
        owner_username=user.username,
    )
    await pkg.insert()
    return package_out(pkg)


@router.get("/packages", response_model=list[PackageOut])
async def list_packages(
    user: User = Depends(get_current_user),
    status_filter: PackageStatus | None = Query(default=None, alias="status"),
):
    query: dict = {}
    if user.role == UserRole.EXECUTOR:
        query["owner_id"] = str(user.id)
    else:  # art-director sees everything that left DRAFT
        query["status"] = {"$ne": PackageStatus.DRAFT.value}
    if status_filter is not None:
        query["status"] = status_filter.value

    packages = await Package.find(query).sort("-created_at").to_list()
    return [package_out(p) for p in packages]


@router.get("/packages/{package_id}", response_model=PackageOut)
async def get_package(package_id: str, user: User = Depends(get_current_user)):
    pkg = await _get_package_or_404(package_id)
    if user.role == UserRole.EXECUTOR:
        _assert_owner(pkg, user)
    return package_out(pkg)


@router.get("/packages/{package_id}/images", response_model=list[ImageOut])
async def list_package_images(
    package_id: str, user: User = Depends(get_current_user)
):
    pkg = await _get_package_or_404(package_id)
    if user.role == UserRole.EXECUTOR:
        _assert_owner(pkg, user)
    images = (
        await ImageAsset.find(ImageAsset.package_id == package_id)
        .sort("-created_at")
        .to_list()
    )
    return [image_out(img) for img in images]


@router.post("/packages/{package_id}/submit", response_model=PackageOut)
async def submit_package(package_id: str, user: User = Depends(require_executor)):
    pkg = await _get_package_or_404(package_id)
    _assert_owner(pkg, user)
    try:
        package_flow.validate_submit(pkg.status, pkg.image_count)
    except package_flow.FlowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # A resubmission after a rejection opens a new review version. The first
    # submission stays at version 1.
    if pkg.status == PackageStatus.REJECTED:
        pkg.version += 1
    pkg.status = PackageStatus.PENDING_REVIEW
    pkg.submitted_at = datetime.now(timezone.utc)
    pkg.review_comment = None
    pkg.touch()
    await pkg.save()
    return package_out(pkg)


@router.post("/packages/{package_id}/review", response_model=PackageOut)
async def review_package(
    package_id: str,
    payload: ReviewRequest,
    user: User = Depends(require_art_director),
):
    pkg = await _get_package_or_404(package_id)
    try:
        package_flow.validate_review(pkg.status)
    except package_flow.FlowError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    new_status = package_flow.resolve_review(payload.decision)
    pkg.status = new_status
    pkg.review_comment = payload.comment
    pkg.reviewed_by = user.username
    pkg.reviewed_at = datetime.now(timezone.utc)
    pkg.touch()
    await pkg.save()

    await Review(
        package_id=package_id,
        art_director_id=str(user.id),
        art_director_username=user.username,
        decision=payload.decision,
        comment=payload.comment,
        package_version=pkg.version,
    ).insert()
    return package_out(pkg)


@router.delete("/packages/{package_id}", status_code=204)
async def delete_package(package_id: str, user: User = Depends(require_executor)):
    """Delete a whole package: its images (bytes + metadata) and review history.

    Only the owner may delete, and never while it is awaiting review.
    """
    pkg = await _get_package_or_404(package_id)
    _assert_owner(pkg, user)
    if pkg.status == PackageStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail="Package is awaiting review; it cannot be deleted right now.",
        )

    images = await ImageAsset.find(ImageAsset.package_id == package_id).to_list()
    storage = get_storage()
    for img in images:
        await asyncio.to_thread(storage.remove_image, img.object_key)
        await img.delete()
    await Review.find(Review.package_id == package_id).delete()
    await pkg.delete()
    return None


@router.get("/packages/{package_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(package_id: str, user: User = Depends(get_current_user)):
    pkg = await _get_package_or_404(package_id)
    if user.role == UserRole.EXECUTOR:
        _assert_owner(pkg, user)
    reviews = (
        await Review.find(Review.package_id == package_id)
        .sort("-created_at")
        .to_list()
    )
    return [review_out(r) for r in reviews]


@router.get("/packages/{package_id}/download")
async def download_package(package_id: str, user: User = Depends(get_current_user)):
    pkg = await _get_package_or_404(package_id)
    if user.role == UserRole.EXECUTOR:
        _assert_owner(pkg, user)
    if not package_flow.can_download(pkg.status):
        raise HTTPException(
            status_code=409, detail="Only APPROVED packages can be downloaded"
        )

    images = await ImageAsset.find(ImageAsset.package_id == package_id).to_list()
    storage = get_storage()

    def _build_zip() -> bytes:
        buf = io.BytesIO()
        manifest = []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img in images:
                data = storage.get_image(img.object_key)
                zf.writestr(f"images/{img.filename}", data)
                manifest.append(
                    {
                        "filename": img.filename,
                        "prompt": img.prompt,
                        "expanded_prompt": img.expanded_prompt,
                        "seed": img.seed,
                        "width": img.width,
                        "height": img.height,
                        "workflow_type": img.workflow_type,
                        "params": img.params,
                    }
                )
            zf.writestr(
                "metadata.json",
                json.dumps(
                    {"package": pkg.name, "assets": manifest}, indent=2
                ),
            )
        return buf.getvalue()

    payload = await asyncio.to_thread(_build_zip)
    safe = pkg.name.replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )
