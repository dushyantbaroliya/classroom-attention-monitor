"""Shared datatypes flowing between ML pipeline stages.

Every stage consumes/produces these plain dataclasses so stages stay
independently testable and replaceable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

HeadPoseLabel = Literal["forward", "left", "right", "up", "down", "unknown"]
GazeLabel = Literal["screen", "notebook", "left", "right", "down", "unknown"]

BBox = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


@dataclass(slots=True)
class Detection:
    """A single raw detector output."""

    bbox: BBox
    confidence: float
    class_id: int

    @property
    def xyxy(self) -> np.ndarray:
        return np.asarray(self.bbox, dtype=np.float32)

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)


@dataclass(slots=True)
class Track:
    """A tracked student (output of the tracker stage)."""

    track_id: int
    bbox: BBox
    confidence: float
    hits: int = 0
    age: int = 0
    time_since_update: int = 0


@dataclass(slots=True)
class HeadPose:
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    label: HeadPoseLabel = "unknown"
    ok: bool = False


@dataclass(slots=True)
class EyeState:
    ear: float = 0.0
    eyes_closed: bool = False
    closed_duration: float = 0.0   # seconds eyes have been continuously closed
    blink_total: int = 0           # blinks since the student appeared
    blink_rate: float = 0.0        # blinks per minute (rolling)
    ok: bool = False


@dataclass(slots=True)
class GazeEstimate:
    label: GazeLabel = "unknown"
    h_ratio: float = 0.5           # 0 = far left, 1 = far right (iris position)
    v_ratio: float = 0.5           # 0 = top, 1 = bottom
    ok: bool = False


@dataclass(slots=True)
class PhoneState:
    visible: bool = False
    looking_at_phone: bool = False
    bbox: Optional[BBox] = None


@dataclass(slots=True)
class HandState:
    raised: bool = False
    changed: bool = False          # True on the frame the state flipped


@dataclass(slots=True)
class ScoreBreakdown:
    """Explainable score: every applied component and its contribution."""

    components: dict[str, float] = field(default_factory=dict)
    raw: float = 0.0
    normalized: float = 0.0        # 0..100, before temporal smoothing
    smoothed: float = 0.0          # 0..100, exponentially smoothed


@dataclass(slots=True)
class StudentFrameResult:
    """Everything the system knows about one student in one frame."""

    track_id: int
    label: str                     # "Student 3" (anonymous by design)
    bbox: BBox
    head: HeadPose = field(default_factory=HeadPose)
    eyes: EyeState = field(default_factory=EyeState)
    gaze: GazeEstimate = field(default_factory=GazeEstimate)
    phone: PhoneState = field(default_factory=PhoneState)
    hand: HandState = field(default_factory=HandState)
    score: ScoreBreakdown = field(default_factory=ScoreBreakdown)


@dataclass(slots=True)
class FrameResult:
    """Output of the pipeline for one processed frame."""

    frame_index: int
    timestamp: float               # seconds since session start
    students: list[StudentFrameResult] = field(default_factory=list)
    class_average: float = 0.0
    phones_visible: int = 0
    hands_raised: int = 0
    processing_ms: float = 0.0
