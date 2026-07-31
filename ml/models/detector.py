"""Object detection wrappers.

Two interchangeable backends implement the same `Detector` protocol
(persons + phones), selected via `config.detection.backend`:

- YoloDetector (Ultralytics): needs torch; GPU-capable. COCO model detects
  persons + cell phones in one pass; a dedicated face model is also supported.
- MediaPipeObjectDetector: torch-free (EfficientDet-Lite via MediaPipe Tasks),
  so the whole pipeline can run on just `mediapipe` + `.task`/`.tflite`
  bundles — no torch/ultralytics install required.

Heavy imports happen inside __init__ so the rest of the codebase (and the
test suite) never needs torch or mediapipe installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from backend.app.core.logging import get_logger
from ml.types import Detection

log = get_logger("detector")


@dataclass(slots=True)
class DetectorOutput:
    persons: list[Detection] = field(default_factory=list)
    phones: list[Detection] = field(default_factory=list)


class Detector(Protocol):
    """Interface the pipeline depends on — swap in fakes for tests."""

    def detect(self, frame_bgr: np.ndarray) -> DetectorOutput: ...


def resolve_device(requested: str) -> str:
    """auto -> cuda if available else cpu; explicit values pass through."""
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class YoloDetector:
    """Ultralytics YOLO wrapper implementing the Detector protocol."""

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        confidence: float = 0.35,
        iou: float = 0.45,
        person_class_id: int = 0,
        phone_class_id: int = 67,
        max_detections: int = 60,
        face_model_path: str | None = None,
    ) -> None:
        from ultralytics import YOLO  # heavy import kept local

        self.device = resolve_device(device)
        self.confidence = confidence
        self.iou = iou
        self.person_class_id = person_class_id
        self.phone_class_id = phone_class_id
        self.max_detections = max_detections

        self.model = YOLO(model_path)
        self.face_model = YOLO(face_model_path) if face_model_path else None
        log.info(
            "YOLO detector ready (model=%s, face_model=%s, device=%s)",
            model_path,
            face_model_path,
            self.device,
        )

    def detect(self, frame_bgr: np.ndarray) -> DetectorOutput:
        results = self.model.predict(
            frame_bgr,
            conf=min(self.confidence, 0.15),  # keep low-conf dets for ByteTrack stage 2
            iou=self.iou,
            device=self.device,
            max_det=self.max_detections,
            classes=[self.person_class_id, self.phone_class_id],
            verbose=False,
        )[0]

        output = DetectorOutput()
        boxes = results.boxes
        if boxes is not None:
            for xyxy, conf, cls in zip(
                boxes.xyxy.cpu().numpy(),
                boxes.conf.cpu().numpy(),
                boxes.cls.cpu().numpy(),
            ):
                det = Detection(
                    bbox=tuple(float(v) for v in xyxy),
                    confidence=float(conf),
                    class_id=int(cls),
                )
                if det.class_id == self.person_class_id:
                    output.persons.append(det)
                elif det.class_id == self.phone_class_id and det.confidence >= self.confidence:
                    output.phones.append(det)

        if self.face_model is not None:
            face_results = self.face_model.predict(
                frame_bgr,
                conf=min(self.confidence, 0.15),
                iou=self.iou,
                device=self.device,
                max_det=self.max_detections,
                verbose=False,
            )[0]
            face_boxes = face_results.boxes
            if face_boxes is not None:
                # Face boxes replace person boxes as the tracked unit.
                output.persons = [
                    Detection(
                        bbox=tuple(float(v) for v in xyxy),
                        confidence=float(conf),
                        class_id=-1,
                    )
                    for xyxy, conf in zip(
                        face_boxes.xyxy.cpu().numpy(), face_boxes.conf.cpu().numpy()
                    )
                ]
        return output


class MediaPipeObjectDetector:
    """Torch-free person/phone detector (MediaPipe Tasks EfficientDet).

    Matches classes by COCO category name ("person", "cell phone") rather than
    index, so it is robust to label-map differences across EfficientDet
    variants. Implements the same Detector protocol as YoloDetector.
    """

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.35,
        max_detections: int = 60,
    ) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        self.confidence = confidence
        options = vision.ObjectDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            score_threshold=confidence,
            max_results=max_detections,
        )
        self.detector = vision.ObjectDetector.create_from_options(options)
        log.info("MediaPipe ObjectDetector ready (model=%s)", model_path)

    def detect(self, frame_bgr: np.ndarray) -> DetectorOutput:
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)
        )
        result = self.detector.detect(image)

        output = DetectorOutput()
        for det in result.detections:
            if not det.categories:
                continue
            cat = det.categories[0]
            name = (cat.category_name or "").lower()
            bb = det.bounding_box
            box = (
                float(bb.origin_x),
                float(bb.origin_y),
                float(bb.origin_x + bb.width),
                float(bb.origin_y + bb.height),
            )
            if name == "person":
                output.persons.append(
                    Detection(bbox=box, confidence=float(cat.score), class_id=0)
                )
            elif name in ("cell phone", "cell_phone", "cellphone", "mobile phone"):
                output.phones.append(
                    Detection(bbox=box, confidence=float(cat.score), class_id=67)
                )
        return output
