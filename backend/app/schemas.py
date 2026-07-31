"""Pydantic response/request schemas for the REST API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    pipeline_available: bool
    active_session_id: Optional[int] = None


class SessionInfo(BaseModel):
    session_id: int
    name: str
    source: str
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    fps: float = 0.0
    frames_processed: int = 0


class StudentStats(BaseModel):
    student_id: int
    track_id: int
    label: str
    first_seen: float
    last_seen: float
    frames_seen: int
    avg_attention: float
    min_attention: float
    max_attention: float
    blink_total: int
    avg_blink_rate: float
    phone_usage_ratio: float
    hand_raised_ratio: float
    eyes_closed_ratio: float
    forward_ratio: float


class TimelinePoint(BaseModel):
    timestamp: float
    avg_attention: float
    students_present: int
    phones_visible: int
    hands_raised: int
    alert: bool


class AnalyticsResponse(BaseModel):
    session: Optional[SessionInfo]
    timeline: list[TimelinePoint]
    students: list[StudentStats]


class AttendanceEntry(BaseModel):
    label: str
    present: bool
    first_seen: float
    last_seen: float
    presence_ratio: Optional[float] = None


class AttendanceResponse(BaseModel):
    session_id: int
    attendance: list[AttendanceEntry]


class StatisticsResponse(BaseModel):
    session: Optional[SessionInfo]
    class_average_attention: float
    students_detected: int
    total_samples: int
    low_attention_alerts: int
    most_engaged: Optional[str]
    least_engaged: Optional[str]
    total_hand_raises: int
    phone_incidents: int


class StreamStartRequest(BaseModel):
    source: Optional[int | str] = None   # camera index / video path; config default if omitted
    session_name: str = "Live session"


class StreamActionResponse(BaseModel):
    ok: bool
    message: str
    session_id: Optional[int] = None


class UploadResponse(BaseModel):
    ok: bool
    message: str
    session_id: Optional[int] = None
    filename: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str


class LiveStudent(BaseModel):
    """Per-student payload pushed over the live WebSocket."""

    track_id: int
    label: str
    bbox: list[float]
    attention: float
    head_pose: str
    gaze: str
    eyes_closed: bool
    phone_visible: bool
    hand_raised: bool
    score_components: dict[str, float]


class LiveFramePayload(BaseModel):
    type: str = "frame"
    session_id: int
    frame_index: int
    timestamp: float
    class_average: float
    students: list[LiveStudent]
    jpeg_b64: Optional[str] = None
    processing_ms: float = 0.0
    extras: dict[str, Any] = {}
