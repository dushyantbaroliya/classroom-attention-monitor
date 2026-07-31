"""CRUD helpers used by the pipeline runner and the API layer."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from database.models import (
    AttendanceRecord,
    ClassSnapshot,
    FrameAnalysis,
    MonitoringSession,
    Student,
    utcnow,
)
from ml.types import FrameResult, StudentFrameResult


def create_session(db: DbSession, name: str, source: str) -> MonitoringSession:
    session = MonitoringSession(name=name, source=source, status="running")
    db.add(session)
    db.flush()
    return session


def end_session(
    db: DbSession, session_id: int, status: str, fps: float, frames_processed: int
) -> None:
    session = db.get(MonitoringSession, session_id)
    if session is None:
        return
    session.status = status
    session.ended_at = utcnow()
    session.fps = fps
    session.frames_processed = frames_processed


def get_or_create_student(
    db: DbSession,
    session_id: int,
    track_id: int,
    label: str,
    timestamp: float,
    cache: dict[int, Student] | None = None,
) -> Student:
    """Fetch/create the Student row for a tracker id (optionally memoized)."""
    if cache is not None and track_id in cache:
        return cache[track_id]
    student = db.scalar(
        select(Student).where(
            Student.session_id == session_id, Student.track_id == track_id
        )
    )
    if student is None:
        student = Student(
            session_id=session_id,
            track_id=track_id,
            label=label,
            first_seen_ts=timestamp,
            last_seen_ts=timestamp,
        )
        db.add(student)
        db.flush()
    if cache is not None:
        cache[track_id] = student
    return student


def store_frame_result(
    db: DbSession,
    session_id: int,
    result: FrameResult,
    student_cache: dict[int, Student] | None = None,
) -> None:
    """Persist every student's readout for one processed frame."""
    for s in result.students:
        student = get_or_create_student(
            db, session_id, s.track_id, s.label, result.timestamp, student_cache
        )
        student.last_seen_ts = result.timestamp
        student.frames_seen += 1
        db.add(_frame_row(session_id, student.id, result, s))


def _frame_row(
    session_id: int, student_id: int, frame: FrameResult, s: StudentFrameResult
) -> FrameAnalysis:
    x1, y1, x2, y2 = s.bbox
    return FrameAnalysis(
        session_id=session_id,
        student_id=student_id,
        frame_index=frame.frame_index,
        timestamp=frame.timestamp,
        bbox_x1=x1,
        bbox_y1=y1,
        bbox_x2=x2,
        bbox_y2=y2,
        head_pose=s.head.label,
        yaw=s.head.yaw,
        pitch=s.head.pitch,
        roll=s.head.roll,
        ear=s.eyes.ear,
        eyes_closed=s.eyes.eyes_closed,
        blink_total=s.eyes.blink_total,
        blink_rate=s.eyes.blink_rate,
        gaze=s.gaze.label,
        phone_visible=s.phone.visible,
        looking_at_phone=s.phone.looking_at_phone,
        hand_raised=s.hand.raised,
        attention_score=s.score.smoothed,
    )


def store_snapshot(
    db: DbSession,
    session_id: int,
    result: FrameResult,
    low_attention_threshold: float,
) -> ClassSnapshot:
    snapshot = ClassSnapshot(
        session_id=session_id,
        timestamp=result.timestamp,
        avg_attention=result.class_average,
        students_present=len(result.students),
        phones_visible=result.phones_visible,
        hands_raised=result.hands_raised,
        low_attention_alert=(
            len(result.students) > 0 and result.class_average < low_attention_threshold
        ),
    )
    db.add(snapshot)
    return snapshot


def finalize_attendance(db: DbSession, session_id: int, total_frames: int) -> None:
    """Write attendance rows for every student seen during the session."""
    students = db.scalars(select(Student).where(Student.session_id == session_id)).all()
    for student in students:
        ratio = student.frames_seen / total_frames if total_frames > 0 else 0.0
        db.add(
            AttendanceRecord(
                session_id=session_id,
                student_id=student.id,
                label=student.label,
                present=True,
                first_seen_ts=student.first_seen_ts,
                last_seen_ts=student.last_seen_ts,
                presence_ratio=round(min(1.0, ratio), 4),
            )
        )


def latest_session(db: DbSession) -> MonitoringSession | None:
    return db.scalar(
        select(MonitoringSession).order_by(MonitoringSession.started_at.desc()).limit(1)
    )
