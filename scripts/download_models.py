"""Download the model bundles the pipeline needs (idempotent).

The MediaPipe backend needs three model files in `models/`:
  - face_landmarker.task        (478 face landmarks incl. iris)
  - pose_landmarker_lite.task   (hand-raise detection)
  - efficientdet_lite2.tflite   (person + phone detection)

They are gitignored (binary, freely downloadable). Run once after cloning:

    python scripts/download_models.py

The optional YOLO backend auto-downloads its own weights (yolov8n.pt) into
yolo_weights/ on first inference, nothing to do here.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODELS = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/latest/face_landmarker.task"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    ),
    "efficientdet_lite2.tflite": (
        "https://storage.googleapis.com/mediapipe-models/object_detector/"
        "efficientdet_lite2/float16/latest/efficientdet_lite2.tflite"
    ),
}


def main() -> int:
    models_dir = Path(__file__).resolve().parents[1] / "models"
    models_dir.mkdir(exist_ok=True)

    for name, url in MODELS.items():
        dest = models_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[skip] {name} ({dest.stat().st_size / 1e6:.1f} MB, exists)")
            continue
        print(f"[get ] {name} ...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"OK ({dest.stat().st_size / 1e6:.1f} MB)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: {exc}")
            return 1
    print(f"\nModels ready in {models_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
