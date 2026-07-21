"""Beanie document models."""
from .common import GenerationParams
from .enums import (
    JobStatus,
    PackageStatus,
    ReviewDecision,
    UserRole,
    WorkflowType,
)
from .image import ImageAsset
from .job import GenerationJob
from .package import Package
from .review import Review
from .user import User

# Ordered list registered with Beanie on startup.
DOCUMENT_MODELS = [User, Package, GenerationJob, ImageAsset, Review]

__all__ = [
    "User",
    "Package",
    "GenerationJob",
    "ImageAsset",
    "Review",
    "GenerationParams",
    "UserRole",
    "PackageStatus",
    "JobStatus",
    "ReviewDecision",
    "WorkflowType",
    "DOCUMENT_MODELS",
]
