# One-shot job that pulls base checkpoints from HuggingFace into a shared volume
# consumed by the ComfyUI service. Keeps large model weights out of git and out
# of the application images.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY download_models.py .

CMD ["python", "download_models.py"]
