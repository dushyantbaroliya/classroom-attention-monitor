"""Heuristic eye-gaze estimation from MediaPipe iris landmarks.

How it works
------------
MediaPipe Face Mesh (with `refine_landmarks=True`) provides iris centres
(indices 468 and 473). We express each iris position as a ratio inside its
eye's bounding corners:

    h_ratio: 0 = iris at the outer/left corner, 1 = inner/right corner
    v_ratio: 0 = iris at the top lid, 1 = at the bottom lid

and threshold those ratios into coarse categories, combined with head pitch
to distinguish "notebook" (head down, gaze down, reading/writing) from
plain "down".

Documented limitations (see README "Gaze estimation limitations"):
- This is an appearance-based heuristic, NOT a calibrated gaze model.
- It cannot resolve where on a screen someone looks, only coarse direction.
- Accuracy degrades with strong head rotation, glasses, occlusion and
  low resolution (far-away students).
"""
from __future__ import annotations

from typing import Mapping, Sequence

from ml.types import GazeEstimate, GazeLabel

# Iris centres (refined landmarks).
LEFT_IRIS_CENTER = 473
RIGHT_IRIS_CENTER = 468

# Eye corner / lid landmarks used to normalize iris position.
LEFT_EYE = {"outer": 263, "inner": 362, "top": 386, "bottom": 374}
RIGHT_EYE = {"outer": 33, "inner": 133, "top": 159, "bottom": 145}


def _ratio(value: float, low: float, high: float) -> float:
    span = high - low
    if abs(span) < 1e-9:
        return 0.5
    r = (value - low) / span
    return min(1.0, max(0.0, r))


def iris_ratios(
    landmarks_px: Mapping[int, Sequence[float]],
) -> tuple[float, float] | None:
    """Average (h_ratio, v_ratio) of both irises, or None if landmarks missing."""
    try:
        ratios = []
        for iris_idx, eye in (
            (RIGHT_IRIS_CENTER, RIGHT_EYE),
            (LEFT_IRIS_CENTER, LEFT_EYE),
        ):
            ix, iy = landmarks_px[iris_idx][:2]
            x_a = landmarks_px[eye["outer"]][0]
            x_b = landmarks_px[eye["inner"]][0]
            y_top = landmarks_px[eye["top"]][1]
            y_bot = landmarks_px[eye["bottom"]][1]
            h = _ratio(ix, min(x_a, x_b), max(x_a, x_b))
            v = _ratio(iy, y_top, y_bot)
            ratios.append((h, v))
    except KeyError:
        return None
    h_avg = sum(r[0] for r in ratios) / len(ratios)
    v_avg = sum(r[1] for r in ratios) / len(ratios)
    return h_avg, v_avg


def classify_gaze(
    h_ratio: float,
    v_ratio: float,
    head_pitch_deg: float,
    *,
    h_left_ratio: float = 0.40,
    h_right_ratio: float = 0.60,
    v_down_ratio: float = 0.62,
    notebook_pitch_deg: float = -25.0,
) -> GazeLabel:
    """Threshold iris ratios (+ head pitch) into a coarse gaze category."""
    looking_down = v_ratio >= v_down_ratio or head_pitch_deg <= notebook_pitch_deg
    if looking_down:
        # Head bowed with gaze centred reads as working in a notebook;
        # gaze pushed sideways while down reads as generic "down" distraction.
        if h_left_ratio < h_ratio < h_right_ratio:
            return "notebook"
        return "down"
    if h_ratio <= h_left_ratio:
        return "left"
    if h_ratio >= h_right_ratio:
        return "right"
    return "screen"


class GazeEstimator:
    """Config-carrying wrapper around the pure helpers above."""

    def __init__(
        self,
        h_left_ratio: float = 0.40,
        h_right_ratio: float = 0.60,
        v_down_ratio: float = 0.62,
        notebook_pitch_deg: float = -25.0,
    ) -> None:
        self.h_left_ratio = h_left_ratio
        self.h_right_ratio = h_right_ratio
        self.v_down_ratio = v_down_ratio
        self.notebook_pitch_deg = notebook_pitch_deg

    def estimate(
        self,
        landmarks_px: Mapping[int, Sequence[float]],
        head_pitch_deg: float,
    ) -> GazeEstimate:
        ratios = iris_ratios(landmarks_px)
        if ratios is None:
            return GazeEstimate(ok=False)
        h, v = ratios
        label = classify_gaze(
            h,
            v,
            head_pitch_deg,
            h_left_ratio=self.h_left_ratio,
            h_right_ratio=self.h_right_ratio,
            v_down_ratio=self.v_down_ratio,
            notebook_pitch_deg=self.notebook_pitch_deg,
        )
        return GazeEstimate(label=label, h_ratio=h, v_ratio=v, ok=True)
