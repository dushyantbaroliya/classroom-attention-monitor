"""Typed application configuration loaded from config.yaml.

Pydantic validates every value at startup so a bad config fails fast with a
readable error instead of surfacing as a runtime bug mid-session.
The config file path can be overridden with the CAM_CONFIG env var.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.yaml"


class VideoConfig(BaseModel):
    source: int | str = 0
    width: int = 1280
    height: int = 720
    target_fps: float = Field(20.0, gt=0)
    process_every_n: int = Field(1, ge=1)


class DetectionConfig(BaseModel):
    # backend: "mediapipe" (torch-free EfficientDet, default) or "yolo".
    backend: Literal["mediapipe", "yolo"] = "mediapipe"
    mediapipe_model_path: str = "models/efficientdet_lite2.tflite"
    model_path: str = "yolo_weights/yolov8n.pt"  # used when backend == "yolo"
    face_model_path: str | None = None
    device: str = "auto"
    confidence: float = Field(0.35, ge=0.0, le=1.0)
    iou: float = Field(0.45, ge=0.0, le=1.0)
    person_class_id: int = 0
    phone_class_id: int = 67
    max_detections: int = 60


class TrackingConfig(BaseModel):
    track_high_thresh: float = 0.50
    track_low_thresh: float = 0.10
    new_track_thresh: float = 0.60
    match_iou_thresh: float = 0.20
    max_lost_frames: int = 60
    min_hits: int = 3


class MediaPipeConfig(BaseModel):
    """MediaPipe Tasks model bundles (downloaded into models/, gitignored).

    The legacy `mp.solutions` API was removed in MediaPipe 0.10.x; the Tasks
    API loads these `.task` bundles instead.
    """

    face_landmarker_path: str = "models/face_landmarker.task"
    pose_landmarker_path: str = "models/pose_landmarker_lite.task"
    max_faces: int = Field(20, ge=1)
    enable_pose: bool = True  # hand-raise detection; disable to save CPU
    min_face_confidence: float = Field(0.4, ge=0.0, le=1.0)
    min_pose_confidence: float = Field(0.4, ge=0.0, le=1.0)
    crop_margin: float = Field(0.1, ge=0.0)


class HeadPoseConfig(BaseModel):
    yaw_left_deg: float = -20.0
    yaw_right_deg: float = 20.0
    pitch_up_deg: float = 15.0
    pitch_down_deg: float = -12.0


class EyesConfig(BaseModel):
    ear_closed_threshold: float = Field(0.21, gt=0)
    blink_min_frames: int = Field(2, ge=1)
    drowsy_after_seconds: float = Field(2.0, gt=0)


class GazeConfig(BaseModel):
    h_left_ratio: float = 0.40
    h_right_ratio: float = 0.60
    v_down_ratio: float = 0.62
    notebook_pitch_deg: float = -25.0


class HandsConfig(BaseModel):
    raise_margin: float = Field(0.05, ge=0)


class PhoneConfig(BaseModel):
    assoc_expand: float = 0.15
    looking_pitch_deg: float = -10.0


class ScoringConfig(BaseModel):
    smoothing_alpha: float = Field(0.35, gt=0, le=1)
    weights: dict[str, dict] = Field(default_factory=dict)


class AnalyticsConfig(BaseModel):
    snapshot_interval_seconds: float = Field(2.0, gt=0)
    db_batch_size: int = Field(50, ge=1)
    low_attention_alert: float = 40.0


class StorageConfig(BaseModel):
    database_url: str = "sqlite:///data/attention.db"
    upload_dir: str = "data/uploads"
    log_dir: str = "data/logs"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class AppConfig(BaseModel):
    video: VideoConfig = Field(default_factory=VideoConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    mediapipe: MediaPipeConfig = Field(default_factory=MediaPipeConfig)
    head_pose: HeadPoseConfig = Field(default_factory=HeadPoseConfig)
    eyes: EyesConfig = Field(default_factory=EyesConfig)
    gaze: GazeConfig = Field(default_factory=GazeConfig)
    hands: HandsConfig = Field(default_factory=HandsConfig)
    phone: PhoneConfig = Field(default_factory=PhoneConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def _absolutize_storage(config: AppConfig, base_dir: Path) -> None:
    """Resolve relative storage paths against the config file's directory,
    so the app behaves the same regardless of the process's working directory."""
    s = config.storage
    prefix = "sqlite:///"
    if s.database_url.startswith(prefix) and ":memory:" not in s.database_url:
        db_path = Path(s.database_url.removeprefix(prefix))
        if not db_path.is_absolute():
            s.database_url = prefix + str((base_dir / db_path).resolve())
    for attr in ("upload_dir", "log_dir"):
        value = Path(getattr(s, attr))
        if not value.is_absolute():
            setattr(s, attr, str((base_dir / value).resolve()))

    # MediaPipe model bundles: resolve relative paths against the config dir.
    mp_cfg = config.mediapipe
    for attr in ("face_landmarker_path", "pose_landmarker_path"):
        value = Path(getattr(mp_cfg, attr))
        if not value.is_absolute():
            setattr(mp_cfg, attr, str((base_dir / value).resolve()))

    det = config.detection
    mp_model = Path(det.mediapipe_model_path)
    if not mp_model.is_absolute():
        det.mediapipe_model_path = str((base_dir / mp_model).resolve())


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or os.environ.get("CAM_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        return AppConfig()  # all defaults — useful for tests
    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    config = AppConfig.model_validate(raw)
    _absolutize_storage(config, config_path.parent.resolve())
    return config


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()
