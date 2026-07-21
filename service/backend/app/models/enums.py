"""Domain enumerations shared across the service."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """Two product personas described in the business plan."""

    EXECUTOR = "executor"          # 2D artist / prompt engineer — generates assets
    ART_DIRECTOR = "art_director"  # reviews & approves asset packages


class PackageStatus(str, Enum):
    """Lifecycle of an asset package (the unit of art-direction review)."""

    DRAFT = "draft"                    # being filled with generations by executor
    GENERATING = "generating"          # at least one job is queued/running
    PENDING_REVIEW = "pending_review"  # submitted to art-director
    APPROVED = "approved"              # accepted -> ready for production download
    REJECTED = "rejected"              # sent back to the executor


class JobStatus(str, Enum):
    """Lifecycle of a single generation job (1 prompt -> N images)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class WorkflowType(str, Enum):
    """Which LoRA / brandbook pipeline to run in ComfyUI.

    Mirrors the two trained adapters from the research phase:
      * character  -> @sltn  (Booru tags, LLM expansion HURTS quality)
      * props      -> @spll_icn (hybrid tags+NLP, LLM expansion HELPS quality)
    """

    CHARACTER = "character"
    PROPS = "props"
