"""Automatic ML quality-assurance gate for generated assets.

Implements the two online-capable metrics promised in the business plan:

  * **CLIP Score** — prompt<->image alignment, computed per image. Assets whose
    score falls below ``qa_min_clip_score`` are rejected (they don't follow the
    brief well enough).
  * **LPIPS diversity** — perceptual distance between images of the same batch,
    used to drop near-duplicates. Only meaningful when a batch has at least
    ``qa_lpips_min_batch`` images (per the product requirement), so smaller
    batches skip this check.

KID is intentionally NOT implemented here: it is only defined on distributions
against a reference dataset and is handled offline in the research pipeline.

The heavy ML libraries (torch / open_clip / lpips) are imported lazily so the
API process and the unit tests never pay for them. If they are missing or fail
to load, the gate degrades gracefully: every asset is marked ``skipped`` and
generation is never blocked.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Sequence

from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AssetQA:
    """Per-asset QA outcome written onto the ImageAsset document."""

    status: str = "skipped"  # QAStatus value
    reason: str | None = None
    clip_score: float | None = None
    lpips_diversity: float | None = None


@dataclass
class BatchQA:
    """QA results for a whole generated batch, indexed like the input list."""

    results: list[AssetQA] = field(default_factory=list)

    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")


class QualityAssessor:
    """Lazily-loaded CLIP + LPIPS scorer with graceful degradation."""

    _clip_model = None
    _clip_preprocess = None
    _clip_tokenizer = None
    _lpips_model = None
    _torch = None
    _load_failed = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        """Load torch/open_clip/lpips once. Return False if unavailable."""
        if cls._load_failed:
            return False
        if cls._torch is not None and cls._clip_model is not None:
            return True
        try:
            import open_clip  # type: ignore
            import torch  # type: ignore

            cls._torch = torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                settings.qa_clip_model, pretrained=settings.qa_clip_pretrained
            )
            model = model.to(device).eval()
            cls._clip_model = model
            cls._clip_preprocess = preprocess
            cls._clip_tokenizer = open_clip.get_tokenizer(settings.qa_clip_model)
            cls._clip_device = device

            # LPIPS is optional; diversity check is skipped if it can't load.
            try:
                import lpips  # type: ignore

                cls._lpips_model = lpips.LPIPS(net="alex").to(device).eval()
            except Exception as exc:  # noqa: BLE001
                logger.warning("LPIPS unavailable, diversity check disabled: %s", exc)
                cls._lpips_model = None
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("QA metrics unavailable, gate disabled: %s", exc)
            cls._load_failed = True
            return False

    # --- image helpers -------------------------------------------------
    @classmethod
    def _open(cls, data: bytes):
        from PIL import Image  # Pillow is already a dependency (mock generator)

        return Image.open(io.BytesIO(data)).convert("RGB")

    @classmethod
    def _clip_scores(cls, images, prompt: str) -> list[float]:
        torch = cls._torch
        device = cls._clip_device
        with torch.no_grad():
            text = cls._clip_tokenizer([prompt]).to(device)
            text_feat = cls._clip_model.encode_text(text)
            text_feat = text_feat / text_feat.norm(dim=-1, keepdim=True)

            scores: list[float] = []
            for img in images:
                tensor = cls._clip_preprocess(img).unsqueeze(0).to(device)
                img_feat = cls._clip_model.encode_image(tensor)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                # Cosine similarity in [-1, 1]; typical good alignment ~0.25-0.35.
                sim = float((img_feat @ text_feat.T).squeeze().item())
                scores.append(sim)
        return scores

    @classmethod
    def _lpips_diversity(cls, images) -> list[float]:
        """Mean LPIPS distance of each image to the rest of the batch."""
        torch = cls._torch
        device = cls._clip_device
        n = len(images)
        if cls._lpips_model is None or n < 2:
            return [None] * n  # type: ignore[list-item]

        def to_tensor(img):
            import numpy as np

            arr = np.asarray(img.resize((256, 256)), dtype="float32") / 255.0
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            return (t * 2 - 1).to(device)  # LPIPS expects [-1, 1]

        tensors = [to_tensor(im) for im in images]
        with torch.no_grad():
            div: list[float] = []
            for i in range(n):
                dists = []
                for j in range(n):
                    if i == j:
                        continue
                    d = float(cls._lpips_model(tensors[i], tensors[j]).item())
                    dists.append(d)
                div.append(sum(dists) / len(dists) if dists else None)
        return div

    # --- public API ----------------------------------------------------
    @classmethod
    def assess_batch(cls, image_bytes: Sequence[bytes], prompt: str) -> BatchQA:
        """Score a batch generated from a single prompt.

        Returns a :class:`BatchQA` with one :class:`AssetQA` per input image.
        Never raises: any failure results in every asset marked ``skipped``.
        """
        n = len(image_bytes)
        if n == 0:
            return BatchQA(results=[])
        if not cls._ensure_loaded():
            return BatchQA(
                results=[AssetQA(reason="metrics unavailable") for _ in range(n)]
            )


        try:
            images = [cls._open(b) for b in image_bytes]
        except Exception as exc:  # noqa: BLE001
            logger.warning("QA could not decode images: %s", exc)
            return BatchQA(results=[AssetQA(reason="decode error") for _ in range(n)])

        # CLIP always; LPIPS only for sufficiently large batches.
        clip_scores = cls._clip_scores(images, prompt)
        run_lpips = n >= settings.qa_lpips_min_batch
        lpips_div = cls._lpips_diversity(images) if run_lpips else [None] * n

        results: list[AssetQA] = []
        for i in range(n):
            reasons: list[str] = []
            cs = clip_scores[i]
            if cs is not None and cs < settings.qa_min_clip_score:
                reasons.append(
                    f"CLIP {cs:.3f} < {settings.qa_min_clip_score:.3f}"
                )
            dv = lpips_div[i]
            if dv is not None and dv < settings.qa_min_lpips_diversity:
                reasons.append(
                    f"LPIPS {dv:.3f} < {settings.qa_min_lpips_diversity:.3f} "
                    "(near-duplicate)"
                )
            results.append(
                AssetQA(
                    status="failed" if reasons else "passed",
                    reason="; ".join(reasons) if reasons else None,
                    clip_score=cs,
                    lpips_diversity=dv,
                )
            )
        return BatchQA(results=results)
