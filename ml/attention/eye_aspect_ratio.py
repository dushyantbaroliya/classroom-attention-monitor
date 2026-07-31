"""Eye Aspect Ratio (EAR): blink, eyes-closed and drowsiness detection.

EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)   (Soukupova & Cech, 2016)

`BlinkTracker` is a small per-student state machine driven by timestamps
supplied by the caller, so it is fully deterministic in tests.
"""
from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence

import numpy as np

from ml.types import EyeState

# MediaPipe Face Mesh indices for the 6-point EAR polygon of each eye,
# ordered p1..p6 (outer corner, upper lids, inner corner, lower lids).
LEFT_EYE_INDICES: tuple[int, ...] = (362, 385, 387, 263, 373, 380)
RIGHT_EYE_INDICES: tuple[int, ...] = (33, 160, 158, 133, 153, 144)

BLINK_RATE_WINDOW_S = 60.0  # rolling window for blinks-per-minute


def eye_aspect_ratio(points: np.ndarray) -> float:
    """Compute EAR for one eye given its 6 points as an (6, 2) array."""
    p1, p2, p3, p4, p5, p6 = points
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal < 1e-9:
        return 0.0
    vertical = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
    return float(vertical / (2.0 * horizontal))


def average_ear(landmarks_px: Mapping[int, Sequence[float]]) -> float | None:
    """Average EAR over both eyes from a {landmark_index: (x, y)} mapping."""
    try:
        left = np.array([landmarks_px[i][:2] for i in LEFT_EYE_INDICES], dtype=np.float64)
        right = np.array([landmarks_px[i][:2] for i in RIGHT_EYE_INDICES], dtype=np.float64)
    except KeyError:
        return None
    return (eye_aspect_ratio(left) + eye_aspect_ratio(right)) / 2.0


class BlinkTracker:
    """Per-student blink/drowsiness state machine.

    Feed it (ear, timestamp) each processed frame; it tracks:
    - whether eyes are currently closed,
    - how long they have been continuously closed,
    - total blinks (short closures) and rolling blinks-per-minute.
    """

    def __init__(
        self,
        ear_closed_threshold: float = 0.21,
        blink_min_frames: int = 2,
        drowsy_after_seconds: float = 2.0,
    ) -> None:
        self.ear_closed_threshold = ear_closed_threshold
        self.blink_min_frames = blink_min_frames
        self.drowsy_after_seconds = drowsy_after_seconds

        self._closed_frames = 0
        self._closed_since: float | None = None
        self._blink_times: deque[float] = deque()
        self.blink_total = 0

    def update(self, ear: float | None, timestamp: float) -> EyeState:
        """Advance the state machine. `timestamp` is seconds (monotonic per session)."""
        if ear is None:
            # Face lost this frame: keep counters but report unknown.
            return EyeState(ok=False, blink_total=self.blink_total,
                            blink_rate=self._rate(timestamp))

        closed = ear < self.ear_closed_threshold
        if closed:
            self._closed_frames += 1
            if self._closed_since is None:
                self._closed_since = timestamp
        else:
            # Eye reopened: a short closure counts as a blink, a long one was
            # a drowsiness episode rather than a blink.
            if (
                self._closed_frames >= self.blink_min_frames
                and self._closed_since is not None
                and (timestamp - self._closed_since) < self.drowsy_after_seconds
            ):
                self.blink_total += 1
                self._blink_times.append(timestamp)
            self._closed_frames = 0
            self._closed_since = None

        closed_duration = (
            timestamp - self._closed_since if (closed and self._closed_since is not None) else 0.0
        )
        return EyeState(
            ear=float(ear),
            eyes_closed=closed,
            closed_duration=closed_duration,
            blink_total=self.blink_total,
            blink_rate=self._rate(timestamp),
            ok=True,
        )

    def _rate(self, now: float) -> float:
        while self._blink_times and now - self._blink_times[0] > BLINK_RATE_WINDOW_S:
            self._blink_times.popleft()
        window = min(BLINK_RATE_WINDOW_S, max(now, 1e-9))
        return len(self._blink_times) * (60.0 / window)
