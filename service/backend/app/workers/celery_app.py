"""Celery application — the horizontally scalable generation worker pool.

Scale with:  docker compose up --scale worker=4
Every worker pulls jobs from the shared Redis broker and talks to ComfyUI.
"""
from __future__ import annotations

from celery import Celery

from ..core.config import settings

celery_app = Celery(
    "assetforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,  # fair dispatch for long GPU tasks
    task_acks_late=True,
    imports=("app.workers.tasks",),
)
