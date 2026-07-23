"""Unit tests for the critical, I/O-free domain logic."""
from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.common import GenerationParams
from app.models.enums import PackageStatus, ReviewDecision, WorkflowType
from app.services import package_flow
from app.services.mock import generate_placeholder
from app.services.workflow import (
    SFW_NEGATIVE_ANCHOR,
    SFW_POSITIVE_ANCHOR,
    build_workflow,
)



# ------------------------- Package state machine -------------------------
@pytest.mark.parametrize(
    "status,count,expected",
    [
        (PackageStatus.DRAFT, 3, True),
        (PackageStatus.REJECTED, 1, True),
        (PackageStatus.DRAFT, 0, False),
        (PackageStatus.PENDING_REVIEW, 3, False),
        (PackageStatus.APPROVED, 3, False),
    ],
)
def test_can_submit(status, count, expected):
    assert package_flow.can_submit(status, count) is expected


def test_validate_submit_empty_raises():
    with pytest.raises(package_flow.FlowError):
        package_flow.validate_submit(PackageStatus.DRAFT, 0)


def test_validate_submit_wrong_status_raises():
    with pytest.raises(package_flow.FlowError):
        package_flow.validate_submit(PackageStatus.APPROVED, 5)


def test_validate_review_requires_pending():
    package_flow.validate_review(PackageStatus.PENDING_REVIEW)  # ok
    with pytest.raises(package_flow.FlowError):
        package_flow.validate_review(PackageStatus.DRAFT)


def test_resolve_review():
    assert package_flow.resolve_review(ReviewDecision.APPROVE) == PackageStatus.APPROVED
    assert package_flow.resolve_review(ReviewDecision.REJECT) == PackageStatus.REJECTED


def test_can_download_only_approved():
    assert package_flow.can_download(PackageStatus.APPROVED)
    assert not package_flow.can_download(PackageStatus.PENDING_REVIEW)


# ------------------------- Security -------------------------
def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("artist", "executor")
    payload = decode_access_token(token)
    assert payload["sub"] == "artist"
    assert payload["role"] == "executor"


def test_jwt_invalid_returns_none():
    assert decode_access_token("garbage.token.value") is None


# ------------------------- Workflow builder -------------------------
def test_build_workflow_character_injects_trigger_and_params():
    params = GenerationParams(
        workflow_type=WorkflowType.CHARACTER, steps=20, cfg=3.5, width=768, height=512
    )
    wf = build_workflow("a knight", params, seed=42)
    assert "@sltn" in wf["67"]["inputs"]["text"]
    assert wf["66"]["inputs"]["seed"] == 42
    assert wf["66"]["inputs"]["steps"] == 20
    assert wf["66"]["inputs"]["cfg"] == 3.5
    assert wf["64"]["inputs"]["width"] == 768
    assert wf["64"]["inputs"]["height"] == 512


def test_build_workflow_props_uses_props_trigger_and_lora():
    params = GenerationParams(workflow_type=WorkflowType.PROPS)
    wf = build_workflow("fire sword", params, seed=7)
    assert "@spll_icn" in wf["67"]["inputs"]["text"]
    assert "SpellIcons" in wf["72"]["inputs"]["lora_name"]


# ------------------------- Mandatory SFW guard -------------------------
def test_sfw_anchor_always_injected():
    params = GenerationParams()
    wf = build_workflow("a hero", params, seed=1)
    positive = wf["67"]["inputs"]["text"]
    negative = wf["65"]["inputs"]["text"]
    for tag in SFW_POSITIVE_ANCHOR.split(","):
        assert tag.strip() in positive
    for tag in SFW_NEGATIVE_ANCHOR.split(","):
        assert tag.strip() in negative


def test_sfw_anchor_cannot_be_removed_by_user_input():
    # Even if the user empties/overrides prompts, the SFW guard is enforced.
    params = GenerationParams(positive_prefix="", negative_prompt="")
    wf = build_workflow("nsfw, nude woman", params, seed=1)
    positive = wf["67"]["inputs"]["text"]
    negative = wf["65"]["inputs"]["text"]
    assert "rating:safe" in positive and "sfw" in positive
    assert "nsfw" in negative and "nude" in negative


def test_sfw_anchor_deduplicates_tags():
    # A user repeating a guard tag must not produce duplicates.
    params = GenerationParams(negative_prompt="nsfw, blurry")
    wf = build_workflow("a hero", params, seed=1)
    negative = wf["65"]["inputs"]["text"].lower()
    assert negative.count("nsfw") == 1



# ------------------------- Mock generator -------------------------
def test_mock_generation_is_png_and_deterministic():
    a = generate_placeholder("x", 32, 32, seed=5)
    b = generate_placeholder("x", 32, 32, seed=5)
    assert a[:8] == b"\x89PNG\r\n\x1a\n"
    assert a == b  # deterministic for a fixed seed
