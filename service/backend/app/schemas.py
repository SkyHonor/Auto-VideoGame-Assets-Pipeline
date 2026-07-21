"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models.common import GenerationParams
from .models.enums import JobStatus, PackageStatus, ReviewDecision, UserRole


# ------------------------- Auth -------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    username: str
    full_name: str = ""


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str = ""
    role: UserRole


# ------------------------- Packages -------------------------
class PackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class PackageOut(BaseModel):
    id: str
    name: str
    description: str = ""
    owner_username: str
    status: PackageStatus
    image_count: int = 0
    cover_image_id: str | None = None
    review_comment: str | None = None
    reviewed_by: str | None = None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None


# ------------------------- Generation -------------------------
class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    batch_size: int = Field(default=1, ge=1, le=16)
    llm_expand: bool = False
    params: GenerationParams = Field(default_factory=GenerationParams)


class JobOut(BaseModel):
    id: str
    package_id: str
    prompt: str
    expanded_prompt: str | None = None
    llm_expand: bool
    batch_size: int
    params: dict[str, Any]
    status: JobStatus
    error: str | None = None
    image_ids: list[str] = []
    created_at: datetime


# ------------------------- Images -------------------------
class ImageOut(BaseModel):
    id: str
    package_id: str
    job_id: str
    filename: str
    prompt: str
    expanded_prompt: str | None = None
    seed: int
    width: int
    height: int
    workflow_type: str
    created_at: datetime
    url: str


# ------------------------- Reviews -------------------------
class ReviewRequest(BaseModel):
    decision: ReviewDecision
    comment: str = ""


class ReviewOut(BaseModel):
    id: str
    package_id: str
    art_director_username: str
    decision: ReviewDecision
    comment: str = ""
    created_at: datetime


# ------------------------- Serialisers -------------------------
def user_out(u) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
    }


def package_out(p) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "owner_username": p.owner_username,
        "status": p.status,
        "image_count": p.image_count,
        "cover_image_id": p.cover_image_id,
        "review_comment": p.review_comment,
        "reviewed_by": p.reviewed_by,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "submitted_at": p.submitted_at,
        "reviewed_at": p.reviewed_at,
    }


def job_out(j) -> dict:
    params = j.params
    if hasattr(params, "model_dump"):
        params = params.model_dump()
    return {
        "id": str(j.id),
        "package_id": j.package_id,
        "prompt": j.prompt,
        "expanded_prompt": j.expanded_prompt,
        "llm_expand": j.llm_expand,
        "batch_size": j.batch_size,
        "params": params,
        "status": j.status,
        "error": j.error,
        "image_ids": j.image_ids,
        "created_at": j.created_at,
    }


def image_out(img, api_prefix: str = "/api/v1") -> dict:
    return {
        "id": str(img.id),
        "package_id": img.package_id,
        "job_id": img.job_id,
        "filename": img.filename,
        "prompt": img.prompt,
        "expanded_prompt": img.expanded_prompt,
        "seed": img.seed,
        "width": img.width,
        "height": img.height,
        "workflow_type": img.workflow_type,
        "created_at": img.created_at,
        "url": f"{api_prefix}/images/{str(img.id)}/file",
    }


def review_out(r) -> dict:
    return {
        "id": str(r.id),
        "package_id": r.package_id,
        "art_director_username": r.art_director_username,
        "decision": r.decision,
        "comment": r.comment,
        "created_at": r.created_at,
    }
