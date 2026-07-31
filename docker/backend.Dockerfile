# Backend + ML pipeline image.
# python:3.11-slim: newest Python fully supported by mediapipe.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libgl/glib: OpenCV + mediapipe native deps; ffmpeg: video decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Torch-free MediaPipe backend by default — small image, no CUDA needed.
# For the optional YOLO backend, also COPY + install requirements-yolo.txt.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend ./backend
COPY ml ./ml
COPY analytics ./analytics
COPY database ./database
COPY scripts ./scripts
COPY alembic.ini config.yaml ./

# Fetch MediaPipe model bundles at build time so first run is offline-ready.
RUN python scripts/download_models.py

RUN mkdir -p data/uploads data/logs yolo_weights

EXPOSE 8000
CMD ["uvicorn", "backend.app.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
