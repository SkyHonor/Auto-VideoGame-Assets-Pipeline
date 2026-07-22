"""Download base diffusion model components from HuggingFace, sorting each file
into the ComfyUI model sub-folder that matches its type.

ComfyUI loads different model components from dedicated sub-directories:

    UNet / diffusion model   -> models/unet
    CLIP / text encoder      -> models/text_encoders
    VAE                      -> models/vae
    full checkpoint          -> models/checkpoints

So the downloader must place every file into the correct folder, otherwise the
UNETLoader / CLIPLoader / VAELoader nodes won't find it and ComfyUI rejects the
prompt with "Value not in list".

Configured entirely by environment variables so it can be re-run idempotently:

    BASE_MODELS   space separated list of "repo_id:filename:type" entries
                  type is one of: unet | text_encoder | vae | checkpoint
                  (type is optional; if omitted it is inferred from the filename
                  and finally defaults to "checkpoint")
    MODELS_DIR    root of the ComfyUI models tree (default: /models)
    HF_TOKEN      optional token for gated/private repositories

Example:
    BASE_MODELS="SkyHonor/Anima:anima-base-v1.0.safetensors:unet \
                 SkyHonor/Anima:qwen_3_06b_base.safetensors:text_encoder \
                 SkyHonor/Anima:qwen_image_vae.safetensors:vae"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

# Root of the ComfyUI models tree (mounted as a volume). Each model type goes
# into its own sub-directory, matching ComfyUI's loader conventions.
MODELS_ROOT = Path(os.getenv("MODELS_DIR", "/models"))

# Map a logical model type to the ComfyUI sub-folder it must live in.
TYPE_TO_SUBDIR = {
    "unet": "unet",
    "diffusion_model": "unet",
    "diffusion_models": "unet",
    "text_encoder": "text_encoders",
    "text_encoders": "text_encoders",
    "clip": "text_encoders",
    "vae": "vae",
    "checkpoint": "checkpoints",
    "checkpoints": "checkpoints",
}

DEFAULT_TYPE = "checkpoint"


def infer_type(filename: str) -> str:
    """Best-effort guess of the model type from its filename."""
    name = filename.lower()
    if "vae" in name:
        return "vae"
    if "text_encoder" in name or "text-encoder" in name or "clip" in name or "qwen_3" in name:
        return "text_encoder"
    if "unet" in name or "diffusion" in name or "base" in name:
        return "unet"
    return DEFAULT_TYPE


def resolve_subdir(model_type: str, filename: str) -> str:
    key = (model_type or "").strip().lower()
    if key in TYPE_TO_SUBDIR:
        return TYPE_TO_SUBDIR[key]
    # Unknown/empty type: infer from the filename.
    return TYPE_TO_SUBDIR[infer_type(filename)]


def main() -> int:
    spec = os.getenv("BASE_MODELS", "").strip()
    if not spec:
        print("[base-downloader] BASE_MODELS is empty, nothing to do.")
        return 0

    token = os.getenv("HF_TOKEN") or None

    for entry in spec.split():
        parts = entry.split(":")
        if len(parts) < 2:
            print(f"[base-downloader] skip malformed entry: {entry!r}")
            continue

        repo_id, filename = parts[0], parts[1]
        model_type = parts[2] if len(parts) >= 3 else ""
        subdir = resolve_subdir(model_type, filename)

        target_dir = MODELS_ROOT / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / filename

        if dest.exists():
            print(f"[base-downloader] already present: {dest}")
            continue

        print(f"[base-downloader] downloading {filename} from {repo_id} -> {subdir}/ ...")
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(target_dir),
            token=token,
        )
        print(f"[base-downloader] saved -> {path}")

    print("[base-downloader] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
