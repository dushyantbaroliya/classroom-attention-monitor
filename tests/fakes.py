"""Fake detector/analyzer implementations for pipeline and API tests.

They satisfy the same Protocols as the YOLO/MediaPipe wrappers, so the
pipeline runs end-to-end with zero heavy dependencies: a scripted classroom
of synthetic students.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ml.attention.eye_aspect_ratio import LEFT_EYE_INDICES, RIGHT_EYE_INDICES
from ml.attention.gaze import LEFT_EYE, LEFT_IRIS_CENTER, RIGHT_EYE, RIGHT_IRIS_CENTER
from ml.attention.hand_raise import (
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)
from ml.attention.head_pose import PNP_LANDMARK_INDICES
from ml.models.detector import DetectorOutput
from ml.types import BBox, Detection


@dataclass
class FakeStudentScript:
    """Where a synthetic student is and what they are doing."""

    bbox: BBox
    attentive: bool = True       # forward-facing, eyes open
    hand_raised: bool = False
    has_phone: bool = False


def face_landmarks_for(bbox: BBox, attentive: bool = True) -> dict:
    """Generate a plausible frontal face landmark set inside the bbox top half.

    When `attentive=False` the eye landmarks collapse (eyes closed) and the
    PnP points shift to simulate a turned head.
    """
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    cx = x1 + w / 2
    top = y1 + 0.05 * (y2 - y1)
    fw = w * 0.5                       # face width
    fx = cx - fw / 2                   # face left
    turn = 0.0 if attentive else fw * 0.35  # lateral shift of nose/chin when turned

    landmarks: dict[int, tuple[float, float]] = {}

    # PnP correspondences: nose, chin, eye corners, mouth corners.
    nose = (fx + fw / 2 + turn, top + fw * 0.55)
    chin = (fx + fw / 2 + turn * 1.4, top + fw * 1.05)
    left_eye_outer = (fx + fw * 0.15, top + fw * 0.40)
    right_eye_outer = (fx + fw * 0.85, top + fw * 0.40)
    mouth_l = (fx + fw * 0.32 + turn, top + fw * 0.85)
    mouth_r = (fx + fw * 0.68 + turn, top + fw * 0.85)
    for idx, pt in zip(
        PNP_LANDMARK_INDICES, (nose, chin, right_eye_outer, left_eye_outer, mouth_r, mouth_l)
    ):
        landmarks[idx] = pt

    # Eyes for EAR: open (tall) when attentive, nearly flat otherwise.
    openness = 6.0 if attentive else 0.5
    for indices, eye_cx in ((LEFT_EYE_INDICES, fx + fw * 0.7), (RIGHT_EYE_INDICES, fx + fw * 0.3)):
        ey = top + fw * 0.40
        p = [
            (eye_cx - 12, ey),
            (eye_cx - 5, ey - openness),
            (eye_cx + 5, ey - openness),
            (eye_cx + 12, ey),
            (eye_cx + 5, ey + openness),
            (eye_cx - 5, ey + openness),
        ]
        for idx, pt in zip(indices, p):
            landmarks[idx] = pt

    # Iris + corners for gaze: centered iris => "screen".
    for iris_idx, eye in ((RIGHT_IRIS_CENTER, RIGHT_EYE), (LEFT_IRIS_CENTER, LEFT_EYE)):
        eye_cx = fx + fw * (0.3 if iris_idx == RIGHT_IRIS_CENTER else 0.7)
        ey = top + fw * 0.40
        landmarks.setdefault(eye["outer"], (eye_cx - 12, ey))
        landmarks.setdefault(eye["inner"], (eye_cx + 12, ey))
        landmarks[eye["top"]] = (eye_cx, ey - 6)
        landmarks[eye["bottom"]] = (eye_cx, ey + 6)
        landmarks[iris_idx] = (eye_cx, ey)
    return landmarks


@dataclass
class FakeDetector:
    """Scripted detector: emits person + phone boxes from the scripts."""

    scripts: list[FakeStudentScript] = field(default_factory=list)

    def detect(self, frame_bgr: np.ndarray) -> DetectorOutput:
        out = DetectorOutput()
        for s in self.scripts:
            out.persons.append(Detection(bbox=s.bbox, confidence=0.92, class_id=0))
            if s.has_phone:
                x1, y1, x2, y2 = s.bbox
                cx, py = (x1 + x2) / 2, y2 - 20
                out.phones.append(
                    Detection(bbox=(cx - 15, py - 15, cx + 15, py + 15),
                              confidence=0.8, class_id=67)
                )
        return out


@dataclass
class FakeAnalyzer:
    """Scripted face/pose analyzer matching the FaceAnalyzer protocol."""

    scripts: list[FakeStudentScript] = field(default_factory=list)

    def detect_faces(
        self, frame_bgr: np.ndarray, regions: list | None = None
    ) -> list[dict]:
        # `regions` (person boxes) is honored by the real analyzer; the fake
        # returns its scripted faces regardless.
        return [face_landmarks_for(s.bbox, s.attentive) for s in self.scripts]

    def detect_pose(self, frame_bgr: np.ndarray, bbox: BBox) -> dict | None:
        script = next((s for s in self.scripts if s.bbox == bbox), None)
        if script is None:  # tracker box drifted slightly: match by center
            cx = (bbox[0] + bbox[2]) / 2
            script = min(
                self.scripts,
                key=lambda s: abs((s.bbox[0] + s.bbox[2]) / 2 - cx),
                default=None,
            )
        if script is None:
            return None
        x1, y1, x2, y2 = bbox
        shoulder_y = y1 + (y2 - y1) * 0.35
        wrist_y = y1 - 10 if script.hand_raised else y2 - 10
        return {
            LEFT_SHOULDER: (x1 + 10, shoulder_y, 0.95),
            RIGHT_SHOULDER: (x2 - 10, shoulder_y, 0.95),
            LEFT_WRIST: (x1 + 5, wrist_y, 0.95),
            RIGHT_WRIST: (x2 - 5, y2 - 10, 0.95),
        }
