"""Frame annotation: bounding boxes, labels and per-student status overlays."""
from __future__ import annotations

import numpy as np

from ml.types import FrameResult, StudentFrameResult

# BGR colors keyed by attention band.
COLOR_HIGH = (80, 200, 80)     # green  >= 70
COLOR_MID = (60, 190, 255)     # amber  40..70
COLOR_LOW = (70, 70, 230)      # red    < 40
COLOR_PHONE = (200, 90, 250)


def _color_for(score: float) -> tuple[int, int, int]:
    if score >= 70:
        return COLOR_HIGH
    if score >= 40:
        return COLOR_MID
    return COLOR_LOW


def annotate_frame(frame_bgr: np.ndarray, result: FrameResult) -> np.ndarray:
    """Draw overlays on a copy of the frame and return it."""
    import cv2

    out = frame_bgr.copy()
    for s in result.students:
        _draw_student(cv2, out, s)

    banner = (
        f"class avg {result.class_average:.0f}  |  "
        f"students {len(result.students)}  |  "
        f"phones {result.phones_visible}  |  hands {result.hands_raised}"
    )
    cv2.rectangle(out, (0, 0), (out.shape[1], 28), (30, 30, 30), -1)
    cv2.putText(
        out, banner, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1
    )
    return out


def _draw_student(cv2, out: np.ndarray, s: StudentFrameResult) -> None:
    x1, y1, x2, y2 = (int(v) for v in s.bbox)
    color = _color_for(s.score.smoothed)
    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

    tags = [f"{s.label}  {s.score.smoothed:.0f}"]
    detail = f"{s.head.label}/{s.gaze.label}"
    if s.hand.raised:
        detail += " HAND"
    if s.eyes.eyes_closed:
        detail += " zzz" if s.eyes.closed_duration >= 1.0 else " blink"
    tags.append(detail)

    y_text = max(18, y1 - 24)
    for i, text in enumerate(tags):
        cv2.putText(
            out,
            text,
            (x1, y_text + i * 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    if s.phone.visible and s.phone.bbox is not None:
        px1, py1, px2, py2 = (int(v) for v in s.phone.bbox)
        cv2.rectangle(out, (px1, py1), (px2, py2), COLOR_PHONE, 2)
        cv2.putText(
            out, "PHONE", (px1, max(12, py1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_PHONE, 1, cv2.LINE_AA,
        )
