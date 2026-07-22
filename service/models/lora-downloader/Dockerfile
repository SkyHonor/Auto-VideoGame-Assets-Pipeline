# One-shot job that pulls LoRA weights from HuggingFace into a shared volume
# consumed by the ComfyUI service. Keeps large model weights out of git and out
# of the application images.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY download_loras.py .

CMD ["python", "download_loras.py"]
