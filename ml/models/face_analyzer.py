"""MediaPipe wrappers (Tasks API).

MediaPipe 0.10.x removed the legacy `mp.solutions.*` graphs, so this module
uses the current Tasks API (`mediapipe.tasks.python.vision`) with downloaded
`.task` model bundles (see `config.mediapipe`, files live in `models/`).

- FaceLandmarker runs ONCE per frame (multi-face) and emits 478 landmarks
  per face, including the iris points (468–477) that the gaze heuristic needs.
  Faces are matched to tracked students by their nose landmark falling inside
  the student's box — far cheaper than a model per student.
- PoseLandmarker is single-pose here, so it runs per-student on crops for
  hand-raise detection; it can be disabled via `config.mediapipe.enable_pose`.

Heavy imports stay inside methods/__init__ so the rest of the codebase (and
the fake-injected test suite) never needs MediaPipe installed.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

from backend.app.core.logging import get_logger
from ml.types import BBox

log = get_logger("face_analyzer")

FaceLandmarks = dict[int, tuple[float, float]]          # index -> (x_px, y_px)
PoseLandmarks = dict[int, tuple[float, float, float]]   # index -> (x_px, y_px, visibility)


class FaceAnalyzer(Protocol):
    def detect_faces(
        self, frame_bgr: np.ndarray, regions: list[BBox] | None = None
    ) -> list[FaceLandmarks]: ...
    def detect_pose(self, frame_bgr: np.ndarray, bbox: BBox) -> PoseLandmarks | None: ...


def _landmark_span(landmarks) -> float:
    """Bounding-box area of a MediaPipe landmark list (normalized units)."""
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def match_face_to_bbox(faces: list[FaceLandmarks], bbox: BBox) -> FaceLandmarks | None:
    """Pick the face whose nose tip (landmark 1) lies inside `bbox`."""
    x1, y1, x2, y2 = bbox
    best: FaceLandmarks | None = None
    best_dist = float("inf")
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    for face in faces:
        nose = face.get(1)
        if nose is None:
            continue
        if x1 <= nose[0] <= x2 and y1 <= nose[1] <= y2:
            dist = (nose[0] - cx) ** 2 + (nose[1] - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best = face
    return best


class MediaPipeAnalyzer:
    """Real implementation backed by the MediaPipe Tasks API."""

    def __init__(
        self,
        face_landmarker_path: str,
        pose_landmarker_path: str | None = None,
        max_faces: int = 20,
        crop_margin: float = 0.1,
        min_face_confidence: float = 0.4,
        min_pose_confidence: float = 0.4,
        enable_pose: bool = True,
    ) -> None:
        import mediapipe as mp  # heavy import kept local
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        self.crop_margin = crop_margin
        self._face_target_px = 320  # upscale target for per-region face crops

        face_options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=face_landmarker_path),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
            min_face_detection_confidence=min_face_confidence,
            min_face_presence_confidence=min_face_confidence,
            min_tracking_confidence=min_face_confidence,
        )
        self.face_landmarker = vision.FaceLandmarker.create_from_options(face_options)

        self.pose_landmarker = None
        if enable_pose and pose_landmarker_path:
            pose_options = vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=pose_landmarker_path),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=min_pose_confidence,
                min_pose_presence_confidence=min_pose_confidence,
                min_tracking_confidence=min_pose_confidence,
            )
            self.pose_landmarker = vision.PoseLandmarker.create_from_options(pose_options)

        log.info(
            "MediaPipe Tasks analyzers ready (max_faces=%d, pose=%s)",
            max_faces,
            self.pose_landmarker is not None,
        )

    def _mp_image(self, rgb: np.ndarray):
        return self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

    def detect_faces(
        self, frame_bgr: np.ndarray, regions: list[BBox] | None = None
    ) -> list[FaceLandmarks]:
        """Detect faces + 478 landmarks (full-frame pixel coords).

        With `regions` (e.g. person boxes from the detector), each region is
        cropped and upscaled before landmarking. This is what makes small,
        distant classroom faces detectable — MediaPipe's built-in face
        detector is short-range and misses faces that occupy little of the
        full frame. Without regions, a single full-frame pass is used (fine
        for close-up / few faces, and for tests).
        """
        import cv2

        h, w = frame_bgr.shape[:2]
        if not regions:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result = self.face_landmarker.detect(self._mp_image(rgb))
            return [
                {i: (lm.x * w, lm.y * h) for i, lm in enumerate(fl)}
                for fl in result.face_landmarks
            ]

        faces: list[FaceLandmarks] = []
        for (x1, y1, x2, y2) in regions:
            rw, rh = x2 - x1, y2 - y1
            cx1 = max(0, int(x1 - rw * self.crop_margin))
            cy1 = max(0, int(y1 - rh * self.crop_margin))
            cx2 = min(w, int(x2 + rw * self.crop_margin))
            cy2 = min(h, int(y2 + rh * self.crop_margin))
            if cx2 - cx1 < 10 or cy2 - cy1 < 10:
                continue

            crop = frame_bgr[cy1:cy2, cx1:cx2]
            ch, cw = crop.shape[:2]
            # Upscale small crops so the short-range face detector can fire.
            scale = max(1.0, self._face_target_px / min(cw, ch))
            if scale > 1.0:
                crop = cv2.resize(
                    crop, (int(cw * scale), int(ch * scale)),
                    interpolation=cv2.INTER_CUBIC,
                )
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            result = self.face_landmarker.detect(self._mp_image(np.ascontiguousarray(rgb)))
            if not result.face_landmarks:
                continue
            # Largest face in the crop (guards against a neighbour's partial face).
            best = max(result.face_landmarks, key=_landmark_span)
            faces.append(
                {
                    i: (cx1 + lm.x * (cx2 - cx1), cy1 + lm.y * (cy2 - cy1))
                    for i, lm in enumerate(best)
                }
            )
        return faces

    def detect_pose(self, frame_bgr: np.ndarray, bbox: BBox) -> PoseLandmarks | None:
        if self.pose_landmarker is None:
            return None
        import cv2

        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = bbox
        mx = (x2 - x1) * self.crop_margin
        my = (y2 - y1) * self.crop_margin
        cx1, cy1 = max(0, int(x1 - mx)), max(0, int(y1 - my))
        cx2, cy2 = min(w, int(x2 + mx)), min(h, int(y2 + my))
        if cx2 - cx1 < 10 or cy2 - cy1 < 10:
            return None

        crop = frame_bgr[cy1:cy2, cx1:cx2]
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        result = self.pose_landmarker.detect(self._mp_image(np.ascontiguousarray(rgb)))
        if not result.pose_landmarks:
            return None
        landmarks = result.pose_landmarks[0]  # num_poses=1
        ch, cw = crop.shape[:2]
        return {
            i: (cx1 + lm.x * cw, cy1 + lm.y * ch, lm.visibility)
            for i, lm in enumerate(landmarks)
        }

    def close(self) -> None:
        self.face_landmarker.close()
        if self.pose_landmarker is not None:
            self.pose_landmarker.close()
