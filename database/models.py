"""SQLAlchemy ORM models.

Schema
------
MonitoringSession  1 -- *  Student            (anonymous "Student N" labels)
MonitoringSession  1 -- *  FrameAnalysis      (per student per processed frame)
MonitoringSession  1 -- *  ClassSnapshot      (class-average timeline points)
MonitoringSession  1 -- *  AttendanceRecord   (presence summary per student)

Per-student attention timelines are derived on demand from FrameAnalysis
(see analytics.aggregator.student_timeline) rather than materialized into a
separate aggregate table — one source of truth, no write path to keep in sync.

No face embeddings or identity data are stored anywhere — students are
tracker ids only. A future opt-in face-recognition module could add a
`students.external_identity` column without touching the rest of the schema.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoringSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Session")
    source: Mapped[str] = mapped_column(String(500))  # "camera:0" or file name
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|completed|failed|stopped
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0)

    students: Mapped[list["Student"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    frames: Mapped[list["FrameAnalysis"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    snapshots: Mapped[list["ClassSnapshot"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Student(Base):
    """An anonymous tracked student within one session."""

    __tablename__ = "students"
    __table_args__ = (Index("ix_students_session_track", "session_id", "track_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    track_id: Mapped[int] = mapped_column(Integer)          # tracker-assigned id
    label: Mapped[str] = mapped_column(String(50))           # "Student 3"
    first_seen_ts: Mapped[float] = mapped_column(Float)      # session-relative seconds
    last_seen_ts: Mapped[float] = mapped_column(Float)
    frames_seen: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[MonitoringSession] = relationship(back_populates="students")
    frames: Mapped[list["FrameAnalysis"]] = relationship(back_populates="student")


class FrameAnalysis(Base):
    """One student's full behavioral readout for one processed frame."""

    __tablename__ = "frame_analysis"
    __table_args__ = (Index("ix_frames_session_ts", "session_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    frame_index: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[float] = mapped_column(Float)          # session-relative seconds

    bbox_x1: Mapped[float] = mapped_column(Float)
    bbox_y1: Mapped[float] = mapped_column(Float)
    bbox_x2: Mapped[float] = mapped_column(Float)
    bbox_y2: Mapped[float] = mapped_column(Float)

    head_pose: Mapped[str] = mapped_column(String(10), default="unknown")
    yaw: Mapped[float] = mapped_column(Float, default=0.0)
    pitch: Mapped[float] = mapped_column(Float, default=0.0)
    roll: Mapped[float] = mapped_column(Float, default=0.0)

    ear: Mapped[float] = mapped_column(Float, default=0.0)
    eyes_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    blink_total: Mapped[int] = mapped_column(Integer, default=0)
    blink_rate: Mapped[float] = mapped_column(Float, default=0.0)

    gaze: Mapped[str] = mapped_column(String(10), default="unknown")
    phone_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    looking_at_phone: Mapped[bool] = mapped_column(Boolean, default=False)
    hand_raised: Mapped[bool] = mapped_column(Boolean, default=False)

    attention_score: Mapped[float] = mapped_column(Float, default=0.0)  # smoothed 0..100

    session: Mapped[MonitoringSession] = relationship(back_populates="frames")
    student: Mapped[Student] = relationship(back_populates="frames")


class ClassSnapshot(Base):
    """Class-wide timeline point (average attention, counters, alert flag)."""

    __tablename__ = "class_snapshots"
    __table_args__ = (Index("ix_snapshots_session_ts", "session_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float)
    avg_attention: Mapped[float] = mapped_column(Float)
    students_present: Mapped[int] = mapped_column(Integer)
    phones_visible: Mapped[int] = mapped_column(Integer, default=0)
    hands_raised: Mapped[int] = mapped_column(Integer, default=0)
    low_attention_alert: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[MonitoringSession] = relationship(back_populates="snapshots")


class AttendanceRecord(Base):
    """Presence summary per student per session (no identity, tracker ids only)."""

    __tablename__ = "attendance"
    __table_args__ = (Index("ix_attendance_session", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    label: Mapped[str] = mapped_column(String(50))
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_ts: Mapped[float] = mapped_column(Float)
    last_seen_ts: Mapped[float] = mapped_column(Float)
    presence_ratio: Mapped[float] = mapped_column(Float, default=0.0)  # frames seen / session frames
