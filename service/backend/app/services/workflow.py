"""Build a ComfyUI API-format workflow from a template + user parameters.

Node IDs match the benchmarked templates (see backend/app/workflows/*.json and
the research notebooks): positive=67, negative=65, KSampler=66, latent=64,
SaveImage=46, style-LoRA=72.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..models.common import GenerationParams

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "workflows"

NODE_POSITIVE = "67"
NODE_NEGATIVE = "65"
NODE_KSAMPLER = "66"
NODE_LATENT = "64"
NODE_SAVE = "46"
NODE_STYLE_LORA = "72"

TRIGGERS = {"character": "@sltn", "props": "@spll_icn"}
TEMPLATES = {"character": "character.json", "props": "props.json"}

# --- Mandatory SFW guard (Anima Base / Cosmos 2, WD-14 Booru rating tags) ---
# These are always injected server-side and CANNOT be removed from the UI.
# `rating:safe` / `sfw` are the exact tags WD-14 uses to label the dataset, so
# Anima responds to them directly and biases sampling toward SFW output. The
# negative side hard-blocks explicit/questionable ratings and NSFW anatomy.
SFW_POSITIVE_ANCHOR = "rating:safe, sfw"
SFW_NEGATIVE_ANCHOR = (
    "rating:explicit, rating:questionable, nsfw, nude, nudity, naked, "
    "nipples, pussy, penis, sex, cum, cameltoe, cleavage, underwear, panties, "
    "lingerie, bikini, revealing clothes, suggestive, sexually suggestive, "
    "erotic, gore, blood"
)


def _merge_tags(*parts: str) -> str:
    """Join comma-separated tag strings, dropping blanks and case-insensitive dups."""
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for tag in (part or "").split(","):
            t = tag.strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
    return ", ".join(out)


_cache: dict[str, dict[str, Any]] = {}



def _load_template(workflow_type: str) -> dict[str, Any]:
    if workflow_type not in _cache:
        fname = TEMPLATES.get(workflow_type, TEMPLATES["character"])
        with open(WORKFLOW_DIR / fname, "r", encoding="utf-8") as fh:
            _cache[workflow_type] = json.load(fh)
    return _cache[workflow_type]


def build_workflow(
    prompt: str,
    params: GenerationParams,
    seed: int,
    filename_prefix: str = "AssetForge",
) -> dict[str, Any]:
    workflow_type = (
        params.workflow_type
        if isinstance(params.workflow_type, str)
        else params.workflow_type.value
    )
    wf = copy.deepcopy(_load_template(workflow_type))

    trigger = TRIGGERS.get(workflow_type, "")
    prefix = (params.positive_prefix or "").strip()
    final_prompt = f"{prefix}, {prompt}" if prefix else prompt
    if trigger and trigger not in final_prompt:
        final_prompt = f"{final_prompt}, {trigger}"

    # Enforce the mandatory SFW guard on top of whatever the user supplied.
    # These anchors are always present and cannot be stripped from the UI.
    final_prompt = _merge_tags(SFW_POSITIVE_ANCHOR, final_prompt)
    final_negative = _merge_tags(SFW_NEGATIVE_ANCHOR, params.negative_prompt)

    wf[NODE_POSITIVE]["inputs"]["text"] = final_prompt
    wf[NODE_NEGATIVE]["inputs"]["text"] = final_negative

    ks = wf[NODE_KSAMPLER]["inputs"]
    ks["seed"] = int(seed)
    ks["steps"] = int(params.steps)
    ks["cfg"] = float(params.cfg)
    ks["sampler_name"] = params.sampler_name
    ks["scheduler"] = params.scheduler
    ks["denoise"] = float(params.denoise)

    latent = wf[NODE_LATENT]["inputs"]
    latent["width"] = int(params.width)
    latent["height"] = int(params.height)
    latent["batch_size"] = 1

    if NODE_STYLE_LORA in wf:
        wf[NODE_STYLE_LORA]["inputs"]["strength_model"] = float(
            params.style_lora_strength
        )

    if NODE_SAVE in wf:
        wf[NODE_SAVE]["inputs"]["filename_prefix"] = filename_prefix

    return wf
