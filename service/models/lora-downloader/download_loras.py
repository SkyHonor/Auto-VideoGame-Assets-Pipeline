"""Download LoRA weights from HuggingFace into the shared volume.

Configured entirely by environment variables so it can be re-run idempotently:

    LORA_MODELS   space separated list of "repo_id:filename" entries
    HF_TOKEN      optional token for gated/private repositories

Example:
    LORA_MODELS="SkyHonor/Acceleration_Lora:anima-turbo-lora-v0.2.safetensors SkyHonor/Prototype:SlyToon-Anima-v1.safetensors"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

TARGET_DIR = Path(os.getenv("LORAS_DIR", "/models/loras"))


def main() -> int:
    spec = os.getenv("LORA_MODELS", "").strip()
    if not spec:
        print("[lora-downloader] LORA_MODELS is empty, nothing to do.")
        return 0

    token = os.getenv("HF_TOKEN") or None
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    for entry in spec.split():
        if ":" not in entry:
            print(f"[lora-downloader] skip malformed entry: {entry!r}")
            continue
        repo_id, filename = entry.split(":", 1)
        dest = TARGET_DIR / filename
        if dest.exists():
            print(f"[lora-downloader] already present: {dest}")
            continue
        print(f"[lora-downloader] downloading {filename} from {repo_id} ...")
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(TARGET_DIR),
            token=token,
        )
        print(f"[lora-downloader] saved -> {path}")

    print("[lora-downloader] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
