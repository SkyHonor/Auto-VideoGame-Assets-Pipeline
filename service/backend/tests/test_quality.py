"""Unit tests for the automatic QA gate (services/quality.py).

These run without the heavy ML stack installed: we verify the graceful
fallback path and, by stubbing the internals, the thresholding logic — so the
critical decision code is covered on any machine / in CI.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.quality import AssetQA, BatchQA, QualityAssessor



def _reset():
    QualityAssessor._load_failed = False
    QualityAssessor._torch = None
    QualityAssessor._clip_model = None
    QualityAssessor._lpips_model = None


def test_empty_batch_returns_empty():
    assert QualityAssessor.assess_batch([], "anything").results == []


def test_metrics_unavailable_marks_all_skipped(monkeypatch):
    """When torch/open_clip can't load, nothing is blocked: all -> skipped."""
    _reset()
    monkeypatch.setattr(QualityAssessor, "_ensure_loaded", classmethod(lambda cls: False))

    out = QualityAssessor.assess_batch([b"x", b"y", b"z"], "a prompt")
    assert len(out.results) == 3
    assert all(r.status == "skipped" for r in out.results)
    assert all(r.reason == "metrics unavailable" for r in out.results)
    # Distinct objects (no shared reference bug).
    assert out.results[0] is not out.results[1]


def test_batch_qa_passed_count():
    batch = BatchQA(
        results=[
            AssetQA(status="passed"),
            AssetQA(status="failed"),
            AssetQA(status="passed"),
        ]
    )
    assert batch.passed_count() == 2


def test_clip_threshold_and_lpips_thresholds(monkeypatch):
    """With loaders stubbed, verify pass/fail purely from the metric values."""
    _reset()
    monkeypatch.setattr(QualityAssessor, "_ensure_loaded", classmethod(lambda cls: True))
    # Skip real image decoding.
    monkeypatch.setattr(QualityAssessor, "_open", classmethod(lambda cls, b: b))

    # Batch big enough that LPIPS is evaluated.
    n = max(4, settings.qa_lpips_min_batch)
    below = settings.qa_min_clip_score - 0.05
    above = settings.qa_min_clip_score + 0.05
    low_div = settings.qa_min_lpips_diversity - 0.05
    ok_div = settings.qa_min_lpips_diversity + 0.05

    clip = [above, below] + [above] * (n - 2)
    div = [ok_div, ok_div, low_div] + [ok_div] * (n - 3)
    monkeypatch.setattr(
        QualityAssessor, "_clip_scores", classmethod(lambda cls, imgs, p: clip)
    )
    monkeypatch.setattr(
        QualityAssessor, "_lpips_diversity", classmethod(lambda cls, imgs: div)
    )

    out = QualityAssessor.assess_batch([b""] * n, "prompt")
    r = out.results
    assert r[0].status == "passed"                       # good clip + good div
    assert r[1].status == "failed" and "CLIP" in r[1].reason  # low clip
    assert r[2].status == "failed" and "LPIPS" in r[2].reason  # near-duplicate


def test_small_batch_skips_lpips(monkeypatch):
    """Batches smaller than the min size must not run the diversity check."""
    _reset()
    monkeypatch.setattr(QualityAssessor, "_ensure_loaded", classmethod(lambda cls: True))
    monkeypatch.setattr(QualityAssessor, "_open", classmethod(lambda cls, b: b))
    monkeypatch.setattr(
        QualityAssessor,
        "_clip_scores",
        classmethod(lambda cls, imgs, p: [settings.qa_min_clip_score + 0.1]),
    )

    called = {"lpips": False}

    def _fail_lpips(cls, imgs):  # pragma: no cover - must not be called
        called["lpips"] = True
        return [None]

    monkeypatch.setattr(QualityAssessor, "_lpips_diversity", classmethod(_fail_lpips))

    out = QualityAssessor.assess_batch([b""], "prompt")
    assert called["lpips"] is False
    assert out.results[0].status == "passed"
    assert out.results[0].lpips_diversity is None
