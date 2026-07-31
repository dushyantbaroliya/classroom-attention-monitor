"""Unit tests for EAR computation and the blink/drowsiness state machine."""
from __future__ import annotations

import numpy as np
import pytest

from ml.attention.eye_aspect_ratio import (
    LEFT_EYE_INDICES,
    RIGHT_EYE_INDICES,
    BlinkTracker,
    average_ear,
    eye_aspect_ratio,
)


def eye_points(openness: float) -> np.ndarray:
    """Synthetic 6-point eye, 40px wide; `openness` scales lid distance."""
    return np.array(
        [
            [0, 0],                       # p1 outer corner
            [12, -6 * openness],          # p2 upper lid
            [28, -6 * openness],          # p3 upper lid
            [40, 0],                      # p4 inner corner
            [28, 6 * openness],           # p5 lower lid
            [12, 6 * openness],           # p6 lower lid
        ],
        dtype=np.float64,
    )


class TestEAR:
    def test_open_eye_has_high_ear(self):
        assert eye_aspect_ratio(eye_points(1.0)) == pytest.approx(0.3, abs=1e-9)

    def test_closed_eye_has_near_zero_ear(self):
        assert eye_aspect_ratio(eye_points(0.05)) < 0.05

    def test_ear_scales_with_openness(self):
        assert eye_aspect_ratio(eye_points(1.0)) > eye_aspect_ratio(eye_points(0.5))

    def test_degenerate_eye_returns_zero(self):
        pts = np.zeros((6, 2))
        assert eye_aspect_ratio(pts) == 0.0

    def test_average_ear_from_landmark_mapping(self):
        pts = eye_points(1.0)
        landmarks = {}
        for indices in (LEFT_EYE_INDICES, RIGHT_EYE_INDICES):
            for idx, p in zip(indices, pts):
                landmarks[idx] = tuple(p)
        assert average_ear(landmarks) == pytest.approx(0.3, abs=1e-9)

    def test_average_ear_missing_landmarks_returns_none(self):
        assert average_ear({1: (0, 0)}) is None


FPS = 10
DT = 1.0 / FPS


def run_sequence(tracker: BlinkTracker, ears: list[float], t0: float = 0.0):
    """Feed a sequence of EAR values at FPS; return list of EyeStates."""
    return [tracker.update(ear, t0 + i * DT) for i, ear in enumerate(ears)]


class TestBlinkTracker:
    def test_short_closure_counts_as_blink(self):
        tracker = BlinkTracker(ear_closed_threshold=0.21, blink_min_frames=2)
        states = run_sequence(tracker, [0.3, 0.3, 0.1, 0.1, 0.3, 0.3])
        assert states[-1].blink_total == 1

    def test_single_frame_dip_is_not_a_blink(self):
        tracker = BlinkTracker(blink_min_frames=2)
        states = run_sequence(tracker, [0.3, 0.1, 0.3, 0.3])
        assert states[-1].blink_total == 0

    def test_multiple_blinks_counted(self):
        tracker = BlinkTracker(blink_min_frames=2)
        seq = [0.3, 0.1, 0.1, 0.3, 0.3, 0.1, 0.1, 0.3]
        states = run_sequence(tracker, seq)
        assert states[-1].blink_total == 2

    def test_long_closure_reports_duration_not_blink(self):
        tracker = BlinkTracker(drowsy_after_seconds=2.0)
        # 30 closed frames at 10 FPS = 3 seconds closed.
        states = run_sequence(tracker, [0.3] + [0.1] * 30 + [0.3])
        closed_states = [s for s in states if s.eyes_closed]
        assert closed_states[-1].closed_duration == pytest.approx(2.9, abs=0.01)
        # Reopening after a drowsy episode must NOT count as a blink.
        assert states[-1].blink_total == 0

    def test_closed_duration_zero_when_open(self):
        tracker = BlinkTracker()
        state = tracker.update(0.35, 1.0)
        assert state.closed_duration == 0.0
        assert not state.eyes_closed

    def test_none_ear_reports_not_ok(self):
        tracker = BlinkTracker()
        state = tracker.update(None, 0.5)
        assert not state.ok

    def test_blink_rate_rolling_window(self):
        tracker = BlinkTracker(blink_min_frames=1)
        # one blink at ~t=0.2s
        run_sequence(tracker, [0.3, 0.1, 0.1, 0.3])
        state = tracker.update(0.3, 30.0)
        assert state.blink_rate == pytest.approx(2.0, abs=0.01)  # 1 blink / 30 s
