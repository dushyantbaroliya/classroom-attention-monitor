"""Hand-raise detection from MediaPipe Pose landmarks.

A hand counts as raised when either wrist is clearly above its shoulder
(image y grows downward, so "above" means smaller y). A small margin,
a fraction of the person's bounding-box height, filters out hands resting
on a desk near shoulder height.

`HandRaiseTracker` debounces the signal and records rise/lower timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ml.types import HandState

# MediaPipe Pose landmark indices.
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_WRIST, RIGHT_WRIST = 15, 16
MIN_VISIBILITY = 0.5


def is_hand_raised(
    pose_landmarks: Mapping[int, Sequence[float]],
    bbox_height: float,
    raise_margin: float = 0.05,
) -> bool:
    """Pure check: wrist above shoulder by `raise_margin * bbox_height` pixels.

    `pose_landmarks` maps index -> (x_px, y_px, visibility).
    """
    margin_px = raise_margin * max(bbox_height, 1.0)
    for wrist_i, shoulder_i in ((LEFT_WRIST, LEFT_SHOULDER), (RIGHT_WRIST, RIGHT_SHOULDER)):
        wrist = pose_landmarks.get(wrist_i)
        shoulder = pose_landmarks.get(shoulder_i)
        if wrist is None or shoulder is None:
            continue
        w_vis = wrist[2] if len(wrist) > 2 else 1.0
        s_vis = shoulder[2] if len(shoulder) > 2 else 1.0
        if w_vis < MIN_VISIBILITY or s_vis < MIN_VISIBILITY:
            continue
        if wrist[1] < shoulder[1] - margin_px:
            return True
    return False


@dataclass(slots=True)
class HandRaiseEvent:
    timestamp: float
    raised: bool  # True = hand went up, False = hand came down


@dataclass
class HandRaiseTracker:
    """Debounced per-student hand state with an event log.

    The raw signal must persist for `debounce_frames` consecutive frames
    before the public state flips, suppressing single-frame pose glitches.
    """

    debounce_frames: int = 3
    raised: bool = False
    events: list[HandRaiseEvent] = field(default_factory=list)
    _streak: int = 0
    _candidate: bool = False

    def update(self, raw_raised: bool, timestamp: float) -> HandState:
        if raw_raised == self.raised:
            self._streak = 0
            self._candidate = self.raised
            return HandState(raised=self.raised, changed=False)

        if raw_raised != self._candidate:
            self._candidate = raw_raised
            self._streak = 1
        else:
            self._streak += 1

        if self._streak >= self.debounce_frames:
            self.raised = raw_raised
            self._streak = 0
            self.events.append(HandRaiseEvent(timestamp=timestamp, raised=raw_raised))
            return HandState(raised=self.raised, changed=True)
        return HandState(raised=self.raised, changed=False)

    @property
    def raise_count(self) -> int:
        return sum(1 for e in self.events if e.raised)
