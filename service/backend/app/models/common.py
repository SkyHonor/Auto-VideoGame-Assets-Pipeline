"""Embedded value objects reused by documents and API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import WorkflowType


class GenerationParams(BaseModel):
    """Full set of inference parameters the executor controls from the UI.

    Defaults come straight from the benchmarked baselines (12 steps, CFG 2.0,
    euler / normal) so a bare request already produces on-style results.
    """

    workflow_type: WorkflowType = WorkflowType.CHARACTER
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    steps: int = Field(default=12, ge=1, le=100)
    cfg: float = Field(default=2.0, ge=0.0, le=30.0)
    sampler_name: str = "euler"
    scheduler: str = "simple"
    denoise: float = Field(default=1.0, ge=0.0, le=1.0)
    seed: int | None = Field(
        default=None,
        description="Fixed seed; when null each image in a batch gets a derived seed.",
    )
    style_lora_strength: float = Field(default=0.85, ge=0.0, le=2.0)

    # Optional automatic ML quality gate (like LLM expansion, toggled per job
    # from the UI). When on, CLIP Score is checked for every image and LPIPS
    # diversity for batches of >= qa_lpips_min_batch; failing assets are kept
    # but hidden from the default gallery.
    qa_check: bool = False


    # Quality-anchor prefix prepended to the user prompt. Anima Base (Cosmos 2)
    # was trained on WD-14 Booru-style tags, so we use plain quality tags here
    # (not Pony score_* tags). Kept separate from the user's creative text so it
    # is applied consistently. The mandatory SFW anchor is added server-side in
    # build_workflow() and cannot be removed from the UI.
    positive_prefix: str = "masterpiece, best quality, highly detailed"
    negative_prompt: str = (
        "worst quality, low quality, blurry, jpeg artifacts, lowres, "
        "bad anatomy, extra limbs, watermark, signature, text"
    )

    model_config = {"use_enum_values": True}
