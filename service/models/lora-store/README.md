# LoRA store

This directory is mounted into ComfyUI at `models/loras`. Drop the project's
trained style LoRA files here so the generation workflows can reference them.

Expected files (referenced by `backend/app/workflows/*.json`):

| File                       | Used by workflow | Trigger word |
|----------------------------|------------------|--------------|
| `CharacterStyle.safetensors` | `character.json` | `@sltn`      |
| `SpellIcons.safetensors`     | `props.json`     | `@spll_icn`  |

> Weights are intentionally **not** committed to git (see `.gitignore`).
> Place them here manually or provision them via your model registry / DVC.
