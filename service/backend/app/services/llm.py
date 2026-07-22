"""Local Ollama prompt-expansion service.

Insights from the ablation study (see baseline/README.md) are baked in:
  * CHARACTER pipeline -> keep short Booru-style tags (LLM expansion hurts KID)
  * PROPS pipeline     -> rich NLP description synergises with the hybrid LoRA
The expander therefore uses a workflow-aware instruction. On any failure it
degrades gracefully by returning the original prompt (never blocks generation).
"""
from __future__ import annotations

import httpx

from ..core.config import settings

# Every expansion must stay strictly safe-for-work so the LLM never introduces
# NSFW/suggestive tags (the diffusion side also has a hard SFW guard).
SFW_RULE = (
    "The output MUST be strictly safe-for-work: absolutely no nudity, "
    "sexual, suggestive, fetish, or gore content."
)
CHARACTER_INSTRUCTION = (
    "You expand Stable Diffusion prompts for a 2.5D anime game-asset model. "
    "Keep the Booru comma-separated TAG style (no prose sentences). Add a few "
    "relevant appearance/composition tags. " + SFW_RULE + " "
    "Return ONLY the tags, no preamble."
)
PROPS_INSTRUCTION = (
    "You expand Stable Diffusion prompts for glowing magical game props/VFX. "
    "Produce one rich English sentence describing shapes, glow, volumetric "
    "lighting and misty gradients. Do NOT mention art style. " + SFW_RULE + " "
    "Return ONLY the description, no preamble."
)


class LLMExpander:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.url = (url or settings.ollama_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout

    def _instruction(self, workflow_type: str) -> str:
        return PROPS_INSTRUCTION if workflow_type == "props" else CHARACTER_INSTRUCTION

    def expand(self, prompt: str, workflow_type: str = "character") -> str:
        """Return an expanded prompt, or the original prompt on any error."""
        instruction = self._instruction(workflow_type)
        try:
            resp = httpx.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{instruction}\n\nPrompt: {prompt}",
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            expanded = resp.json().get("response", "").strip()
        except (httpx.HTTPError, KeyError, ValueError):
            return prompt

        expanded = expanded.replace("\n", ", ").strip(" ,")
        return expanded or prompt

    def health(self) -> bool:
        try:
            return httpx.get(f"{self.url}/api/tags", timeout=5).status_code == 200
        except httpx.HTTPError:
            return False
