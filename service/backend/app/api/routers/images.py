"""Image metadata + binary streaming from MinIO."""
from __future__ import annotations

import asyncio

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ...models import ImageAsset, User
from ...models.enums import UserRole
from ...schemas import ImageOut, image_out
from ...services.storage import get_storage
from ..deps import get_current_user

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
