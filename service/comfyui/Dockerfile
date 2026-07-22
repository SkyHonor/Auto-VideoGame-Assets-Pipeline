# ComfyUI inference server, built from the OFFICIAL upstream repository
# (https://github.com/comfyanonymous/ComfyUI) on top of the official PyTorch
# CUDA runtime image. Pinned to a specific commit for reproducible builds so the
# image is identical on any machine.
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

# Pin to a concrete upstream commit for reproducibility.
ARG COMFYUI_REF=master

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

# Install ComfyUI's own dependencies (torch is already present in the base image).
RUN pip install --no-cache-dir -r requirements.txt

# Models are provided at runtime via mounted volumes:
#   /opt/ComfyUI/models/checkpoints  <- Anima Base (UNet/CLIP/VAE)
#   /opt/ComfyUI/models/loras        <- turbo + style LoRAs
EXPOSE 8188

HEALTHCHECK --interval=30s --timeout=5s --retries=10 --start-period=60s \
    CMD curl -f http://localhost:8188/ || exit 1

# --listen 0.0.0.0 so the backend/worker containers can reach the API.
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
