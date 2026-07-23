"""Synchronous ComfyUI REST client.

Implements the queue -> poll history -> download pattern validated in the
research notebook (nb_00). Used inside the Celery worker.
"""
from __future__ import annotations

import time
from typing import Any

import httpx


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = 600,
        poll_interval: float = 0.5,
        save_node_id: str = "46",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.save_node_id = save_node_id

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        try:
            resp = httpx.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            raise ComfyUIError(f"Failed to queue prompt: {exc}") from exc
        return resp.json()["prompt_id"]

    def _get_history(self, prompt_id: str) -> dict[str, Any]:
        resp = httpx.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _download(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        resp = httpx.get(
            f"{self.base_url}/view",
            params={
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.content

    def generate(self, workflow: dict[str, Any]) -> list[bytes]:
        """Queue a workflow, wait for completion and return all image bytes."""
        prompt_id = self.queue_prompt(workflow)
        deadline = time.time() + self.timeout

        while time.time() < deadline:
            try:
                history = self._get_history(prompt_id)
            except httpx.HTTPError:
                history = {}

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                node_output = outputs.get(self.save_node_id, {})
                images = node_output.get("images", [])
                if images:
                    return [
                        self._download(
                            img["filename"],
                            img.get("subfolder", ""),
                            img.get("type", "output"),
                        )
                        for img in images
                    ]
                # Completed but no images on the expected node.
                return []
            time.sleep(self.poll_interval)

        raise ComfyUIError(f"ComfyUI generation timed out after {self.timeout}s")

    def health(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/system_stats", timeout=5)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
