"""Verify the REAL MediaPipe stages against real footage (no YOLO needed).

This proves the parts of the pipeline that depend on facial/pose landmarks:
Face Mesh -> head pose (solvePnP), EAR/blinks, iris gaze, and Pose -> hand
raises. Person boxes come from MediaPipe's own face detections instead of
YOLO, so this runs without torch/ultralytics installed.

    python scripts/verify_mediapipe.py --source sample_videos/classroom.mp4
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from backend.app.core.config import load_config
from ml.attention.eye_aspect_ratio import BlinkTracker, average_ear
from ml.attention.gaze import GazeEstimator
from ml.attention.hand_raise import HandRaiseTracker, is_hand_raised
from ml.attention.head_pose import HeadPoseEstimator
from ml.attention.scoring import AttentionScorer, BehaviorSnapshot
from ml.models.face_analyzer import MediaPipeAnalyzer
from ml.tracking.byte_tracker import ByteTracker
from ml.types import Detection, PhoneState


def face_bbox(landmarks: dict, pad: float = 0.6) -> tuple[float, float, float, float]:
    """Bounding box around a face's landmarks, padded to approximate a torso."""
    xs = [p[0] for p in landmarks.values()]
    ys = [p[1] for p in landmarks.values()]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    w, h = x2 - x1, y2 - y1
    return (x1 - w * pad / 2, y1 - h * pad / 2, x2 + w * pad / 2, y2 + h * pad * 1.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--every", type=int, default=2, help="process every Nth frame")
    ap.add_argument("--save", default=None, help="save an annotated frame here")
    ap.add_argument("--pose", action="store_true", help="also run Pose (slow)")
    args = ap.parse_args()

    config = load_config()
    print("=" * 70)
    print("REAL MEDIAPIPE VERIFICATION  (Face Mesh + head pose + EAR + gaze)")
    print("=" * 70)
    import mediapipe

    print(f"python {sys.version.split()[0]} | mediapipe {mediapipe.__version__} | opencv {cv2.__version__}")

    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        print(f"ERROR: cannot open {args.source}")
        return 1
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"source: {args.source}  ({total} frames @ {cap.get(cv2.CAP_PROP_FPS):.0f} fps)")
    print("-" * 70)

    t0 = time.perf_counter()
    m = config.mediapipe
    analyzer = MediaPipeAnalyzer(
        face_landmarker_path=m.face_landmarker_path,
        pose_landmarker_path=m.pose_landmarker_path,
        max_faces=m.max_faces,
        crop_margin=m.crop_margin,
        min_face_confidence=m.min_face_confidence,
        min_pose_confidence=m.min_pose_confidence,
        enable_pose=args.pose,
    )
    print(f"MediaPipe models loaded in {time.perf_counter() - t0:.1f}s")

    hp = config.head_pose
    head_est = HeadPoseEstimator(
        yaw_left_deg=hp.yaw_left_deg, yaw_right_deg=hp.yaw_right_deg,
        pitch_up_deg=hp.pitch_up_deg, pitch_down_deg=hp.pitch_down_deg,
    )
    g = config.gaze
    gaze_est = GazeEstimator(
        h_left_ratio=g.h_left_ratio, h_right_ratio=g.h_right_ratio,
        v_down_ratio=g.v_down_ratio, notebook_pitch_deg=g.notebook_pitch_deg,
    )
    tracker = ByteTracker(min_hits=2, max_lost_frames=45)
    scorer = AttentionScorer(
        weights=config.scoring.weights or None,
        smoothing_alpha=config.scoring.smoothing_alpha,
    )
    blinks: dict[int, BlinkTracker] = {}
    hands: dict[int, HandRaiseTracker] = {}

    head_labels: Counter[str] = Counter()
    gaze_labels: Counter[str] = Counter()
    faces_per_frame: list[int] = []
    ears: list[float] = []
    yaws: list[float] = []
    durations: list[float] = []
    track_ids: set[int] = set()
    hand_events = 0
    processed = 0
    last = None

    idx = 0
    while processed < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        idx += 1
        if (idx - 1) % args.every:
            continue
        h, w = frame.shape[:2]
        ts = idx / 30.0

        started = time.perf_counter()
        faces = analyzer.detect_faces(frame)
        dets = [
            Detection(bbox=face_bbox(f), confidence=0.9, class_id=0) for f in faces
        ]
        tracks = tracker.update(dets)

        students = []
        for track in tracks:
            track_ids.add(track.track_id)
            # match the face whose nose sits inside this track box
            best = None
            for f in faces:
                nose = f.get(1)
                if nose and track.bbox[0] <= nose[0] <= track.bbox[2] and \
                   track.bbox[1] <= nose[1] <= track.bbox[3]:
                    best = f
                    break
            if best is None:
                continue

            head = head_est.estimate(best, (w, h))
            ear = average_ear(best)
            bt = blinks.setdefault(track.track_id, BlinkTracker(
                ear_closed_threshold=config.eyes.ear_closed_threshold,
                blink_min_frames=config.eyes.blink_min_frames,
                drowsy_after_seconds=config.eyes.drowsy_after_seconds,
            ))
            eyes = bt.update(ear, ts)
            gaze = gaze_est.estimate(best, head.pitch)

            hand_state = None
            if args.pose:
                pose_lm = analyzer.detect_pose(frame, track.bbox)
                raw = is_hand_raised(pose_lm, track.bbox[3] - track.bbox[1],
                                     config.hands.raise_margin) if pose_lm else False
                ht = hands.setdefault(track.track_id, HandRaiseTracker())
                hand_state = ht.update(raw, ts)
                if hand_state.changed:
                    hand_events += 1

            from ml.types import HandState
            score = scorer.score(track.track_id, BehaviorSnapshot(
                head=head, eyes=eyes, gaze=gaze, phone=PhoneState(),
                hand=hand_state or HandState(),
                drowsy_after_seconds=config.eyes.drowsy_after_seconds,
            ))

            if head.ok:
                head_labels[head.label] += 1
                yaws.append(head.yaw)
            if gaze.ok:
                gaze_labels[gaze.label] += 1
            if eyes.ok:
                ears.append(eyes.ear)
            students.append((track, head, eyes, gaze, score))

        durations.append(time.perf_counter() - started)
        faces_per_frame.append(len(faces))
        processed += 1
        last = (frame, students)

    cap.release()

    # ------------------------------------------------------------- report
    print("-" * 70)
    mean_ms = sum(durations) / len(durations) * 1000 if durations else 0
    print(f"frames processed      {processed}")
    print(f"mean latency          {mean_ms:.0f} ms/frame  ->  {1000/mean_ms:.1f} FPS (CPU)")
    print(f"faces detected        {sum(faces_per_frame)} total, "
          f"{np.mean(faces_per_frame):.2f} avg/frame, max {max(faces_per_frame or [0])}")
    print(f"unique tracks (students) {len(track_ids)}")
    print()
    print(f"head pose distribution   {dict(head_labels)}")
    if yaws:
        print(f"  yaw range             {min(yaws):+.1f}° .. {max(yaws):+.1f}°  (mean {np.mean(yaws):+.1f}°)")
    print(f"gaze distribution        {dict(gaze_labels)}")
    if ears:
        print(f"EAR                      mean {np.mean(ears):.3f}, min {min(ears):.3f}, max {max(ears):.3f}")
        closed = sum(1 for e in ears if e < config.eyes.ear_closed_threshold)
        print(f"  frames below closed-threshold ({config.eyes.ear_closed_threshold}): {closed}/{len(ears)}")
    if args.pose:
        print(f"hand-raise state changes {hand_events}")

    if last and last[1]:
        print("-" * 70)
        print("last processed frame, per student:")
        for track, head, eyes, gaze, score in last[1][:8]:
            print(f"  Student {track.track_id:<3} score={score.smoothed:5.1f}  "
                  f"head={head.label:<8}(yaw{head.yaw:+6.1f} pitch{head.pitch:+6.1f})  "
                  f"gaze={gaze.label:<8} ear={eyes.ear:.3f}")

    if args.save and last:
        frame, students = last
        out = frame.copy()
        for track, head, eyes, gaze, score in students:
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            color = (80, 200, 80) if score.smoothed >= 70 else (
                (60, 190, 255) if score.smoothed >= 40 else (70, 70, 230))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cv2.putText(out, f"S{track.track_id} {score.smoothed:.0f} {head.label}",
                        (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(args.save, out)
        print(f"\nannotated frame -> {args.save}")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
