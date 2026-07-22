# ComfyUI inference server, built from the OFFICIAL upstream repository
# (https://github.com/comfyanonymous/ComfyUI) on top of the official PyTorch
# CUDA runtime image. Pinned to a specific release for reproducible builds so
# the image is identical on any machine.
#
# Version pinning is DELIBERATE and matches the environment on which the Anima /
# Qwen-image workflow was validated (ComfyUI 0.27.0 with a recent PyTorch):
#   * ComfyUI v0.27.0 loads the qwen_3_06b (0.6B, hidden 1024) text encoder
#     correctly with CLIPLoader type=stable_diffusion. Older cores mis-map it to
#     a 4096-hidden LLaMA -> "size mismatch" and zero images.
#   * PyTorch >= 2.6 is required by this ComfyUI core (it uses
#     scaled_dot_product_attention(enable_gqa=...), added in torch 2.5, plus
#     other newer ops). 2.8.0 is the closest widely-available official image to
#     the validated runtime.
FROM pytorch/pytorch:2.8.0-cuda12.6-cudnn9-runtime

# Pin to the exact upstream RELEASE TAG validated for this project. A floating
# `master` can introduce breaking changes at any rebuild; a tagged release keeps
# the build deterministic and guaranteed-compatible with the pinned PyTorch.
ARG COMFYUI_REF=v0.27.0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

# Clone the official ComfyUI repository.
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ComfyUI \
    && cd ComfyUI \
    && git checkout "${COMFYUI_REF}"

WORKDIR /opt/ComfyUI

# Install ComfyUI's own dependencies. Strip torch/torchvision/torchaudio from
# the requirements first so pip does NOT replace the CUDA-enabled build that
# ships in the base image with a (possibly CPU-only or mismatched) wheel.
RUN grep -ivE '^(torch|torchvision|torchaudio)([<>=!~ ]|$)' requirements.txt > /tmp/comfy-reqs.txt \
    && pip install --no-cache-dir -r /tmp/comfy-reqs.txt \
    && python -c "import torch; print('torch', torch.__version__, 'cuda_build', torch.version.cuda)"

# Models are provided at runtime via mounted volumes:
#   /opt/ComfyUI/models/checkpoints  <- Anima Base (UNet/CLIP/VAE)
#   /opt/ComfyUI/models/loras        <- turbo + style LoRAs
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --retries=10 --start-period=60s \
    CMD curl -f http://localhost:8188/ || exit 1

# --listen 0.0.0.0 so the backend/worker containers can reach the API.
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
