"""Real-model smoke test: prove the CV pipeline actually runs.

Unlike the pytest suite (which injects scripted fakes), this loads the REAL
YOLO and MediaPipe models and pushes frames through the full pipeline,
reporting what each stage produced and the achieved FPS.

    python scripts/verify_pipeline.py                 # synthetic frames
    python scripts/verify_pipeline.py --source path/to/video.mp4
    python scripts/verify_pipeline.py --source 0      # webcam
    python scripts/verify_pipeline.py --frames 60 --save-annotated out.jpg
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from backend.app.core.config import load_config
from backend.app.core.logging import setup_logging


def synthetic_frame(width: int, height: int, i: int) -> np.ndarray:
    """A moving gradient + shapes. Exercises the code path, not accuracy."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.linspace(20, 90, width, dtype=np.uint8)[None, :]
    frame[:, :, 1] = np.linspace(30, 70, height, dtype=np.uint8)[:, None]
    import cv2

    cx = int(width * 0.5 + 60 * np.sin(i / 8))
    cv2.circle(frame, (cx, height // 2), 70, (180, 170, 160), -1)
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=None, help="video path or camera index")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--save-annotated", default=None)
    args = parser.parse_args()

    config = load_config()
    setup_logging(config.storage.log_dir)

    print("=" * 68)
    print("REAL MODEL VERIFICATION")
    print("=" * 68)

    # --- dependency + device report -------------------------------------
    import cv2
    import mediapipe

    print(f"python       {sys.version.split()[0]}")
    print(f"detector     backend={config.detection.backend}")
    print(f"mediapipe    {mediapipe.__version__}")
    print(f"opencv       {cv2.__version__}")
    try:
        import torch

        print(f"torch        {torch.__version__}  (cuda: {torch.cuda.is_available()})")
    except ImportError:
        print("torch        not installed (fine for the mediapipe backend)")
    print("-" * 68)

    # --- build the real pipeline ----------------------------------------
    from ml.annotate import annotate_frame
    from ml.pipeline import build_default_pipeline

    t0 = time.perf_counter()
    pipeline = build_default_pipeline(config)
    model_ref = (
        config.detection.mediapipe_model_path
        if config.detection.backend == "mediapipe"
        else config.detection.model_path
    )
    print(f"models loaded in {time.perf_counter() - t0:.1f}s ({model_ref})")
    print("-" * 68)

    # --- frame source ----------------------------------------------------
    cap = None
    if args.source is not None:
        source: int | str = int(args.source) if str(args.source).isdigit() else args.source
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"ERROR: could not open source {source!r}")
            return 1
        print(f"source: {source!r}")
    else:
        print("source: synthetic frames (no real faces expected)")

    width, height = config.video.width, config.video.height
    durations: list[float] = []
    totals = {
        "frames": 0,
        "students": 0,
        "faces_ok": 0,
        "head_ok": 0,
        "eyes_ok": 0,
        "gaze_ok": 0,
        "phones": 0,
        "hands": 0,
    }
    last_frame = None
    last_result = None

    for i in range(args.frames):
        if cap is not None:
            ok, frame = cap.read()
            if not ok:
                print(f"(source ended after {i} frames)")
                break
        else:
            frame = synthetic_frame(width, height, i)

        started = time.perf_counter()
        result = pipeline.process_frame(frame, i + 1, i / 20.0)
        durations.append(time.perf_counter() - started)

        totals["frames"] += 1
        totals["students"] += len(result.students)
        totals["phones"] += result.phones_visible
        totals["hands"] += result.hands_raised
        for s in result.students:
            totals["head_ok"] += int(s.head.ok)
            totals["eyes_ok"] += int(s.eyes.ok)
            totals["gaze_ok"] += int(s.gaze.ok)
            totals["faces_ok"] += int(s.head.ok or s.eyes.ok)
        last_frame, last_result = frame, result

    if cap is not None:
        cap.release()

    # --- report ----------------------------------------------------------
    print("-" * 68)
    n = max(1, totals["frames"])
    mean_ms = sum(durations) / len(durations) * 1000 if durations else 0.0
    fps = 1000 / mean_ms if mean_ms else 0.0
    print(f"frames processed     {totals['frames']}")
    print(f"mean latency         {mean_ms:.1f} ms/frame")
    print(f"throughput           {fps:.1f} FPS  (CPU, backend={config.detection.backend})")
    print(f"students detected    {totals['students']} total, "
          f"{totals['students'] / n:.2f} avg/frame")
    print(f"face landmarks ok    {totals['faces_ok']}")
    print(f"  head pose ok       {totals['head_ok']}")
    print(f"  eye/EAR ok         {totals['eyes_ok']}")
    print(f"  gaze ok            {totals['gaze_ok']}")
    print(f"phone detections     {totals['phones']}")
    print(f"hand raises          {totals['hands']}")

    if last_result and last_result.students:
        print("-" * 68)
        print("last frame, per student:")
        for s in last_result.students:
            print(
                f"  {s.label:<10} score={s.score.smoothed:5.1f}  "
                f"head={s.head.label:<8} (yaw={s.head.yaw:6.1f} pitch={s.head.pitch:6.1f})  "
                f"gaze={s.gaze.label:<8} ear={s.eyes.ear:.3f}  "
                f"phone={s.phone.visible}  hand={s.hand.raised}"
            )
            print(f"             components: {s.score.components}")

    if args.save_annotated and last_frame is not None and last_result is not None:
        out = Path(args.save_annotated)
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), annotate_frame(last_frame, last_result))
        print(f"\nannotated frame saved -> {out}")

    print("=" * 68)
    detected = totals["students"] > 0
    print("RESULT: models loaded and inference ran end-to-end.")
    if not detected:
        print("NOTE:   no people detected, expected with synthetic frames.")
        print("        Re-run with --source <video|0> for real detections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
