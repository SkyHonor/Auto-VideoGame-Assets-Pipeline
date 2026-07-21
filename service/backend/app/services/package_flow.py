"""Pure domain logic for the package review state machine.

Kept free of I/O so it can be unit-tested exhaustively (critical part).
"""
from __future__ import annotations

from ..models.enums import PackageStatus, ReviewDecision


class FlowError(ValueError):
    """Raised on an illegal package state transition."""


def can_submit(status: PackageStatus, image_count: int) -> bool:
    return status in (PackageStatus.DRAFT, PackageStatus.REJECTED) and image_count > 0


def validate_submit(status: PackageStatus, image_count: int) -> None:
    if image_count <= 0:
        raise FlowError("Cannot submit an empty package for review.")
    if status not in (PackageStatus.DRAFT, PackageStatus.REJECTED):
        raise FlowError(
            f"Package in status '{status.value}' cannot be submitted for review."
        )


def validate_review(status: PackageStatus) -> None:
    if status != PackageStatus.PENDING_REVIEW:
        raise FlowError(
            f"Package in status '{status.value}' is not awaiting review."
        )


def resolve_review(decision: ReviewDecision) -> PackageStatus:
    return (
        PackageStatus.APPROVED
        if decision == ReviewDecision.APPROVE
        else PackageStatus.REJECTED
    )


def can_download(status: PackageStatus) -> bool:
    return status == PackageStatus.APPROVED
