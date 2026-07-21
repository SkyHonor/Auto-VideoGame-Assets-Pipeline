"""Download base diffusion checkpoints from HuggingFace into the shared volume.

Configured entirely by environment variables so it can be re-run idempotently:

    BASE_MODELS   space separated list of "repo_id:filename" entries
    HF_TOKEN      optional token for gated/private repositories

Example:
    BASE_MODELS="stabilityai/stable-diffusion-xl-base-1.0:sd_xl_base_1.0.safetensors"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

TARGET_DIR = Path(os.getenv("CHECKPOINTS_DIR", "/models/checkpoints"))


def main() -> int:
    spec = os.getenv("BASE_MODELS", "").strip()
    if not spec:
        print("[base-downloader] BASE_MODELS is empty, nothing to do.")
        return 0

    token = os.getenv("HF_TOKEN") or None
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    for entry in spec.split():
        if ":" not in entry:
            print(f"[base-downloader] skip malformed entry: {entry!r}")
            continue
        repo_id, filename = entry.split(":", 1)
        dest = TARGET_DIR / filename
        if dest.exists():
            print(f"[base-downloader] already present: {dest}")
            continue
        print(f"[base-downloader] downloading {filename} from {repo_id} ...")
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(TARGET_DIR),
            token=token,
        )
        print(f"[base-downloader] saved -> {path}")

    print("[base-downloader] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
