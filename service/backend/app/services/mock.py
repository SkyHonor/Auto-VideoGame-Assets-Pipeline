"""Deterministic placeholder image generator (no-GPU demo / test mode).

Mirrors the DRY_RUN behaviour of the research notebooks so the whole pipeline
(queue -> store -> review -> download) can be demonstrated without ComfyUI.
"""
from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageDraw


def _color_from_seed(seed: int, salt: str = "") -> tuple[int, int, int]:
    digest = hashlib.md5(f"{seed}-{salt}".encode()).digest()
    return digest[0], digest[1], digest[2]


def generate_placeholder(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    workflow_type: str = "character",
) -> bytes:
    top = _color_from_seed(seed, "top")
    bottom = _color_from_seed(seed, workflow_type)

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)),
        )

    label = (prompt[:60] + "…") if len(prompt) > 60 else prompt
    draw.text((16, 16), f"AssetForge · {workflow_type}", fill=(255, 255, 255))
    draw.text((16, 36), f"seed={seed}", fill=(255, 255, 255))
    draw.text((16, height - 28), label, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
