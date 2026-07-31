"""Analytics aggregation over stored frame data.

All heavy lifting happens in SQL (works identically on SQLite and Postgres);
results come back as plain dicts ready for the API/JSON layer.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DbSession

from database.models import (
    AttendanceRecord,
    ClassSnapshot,
    FrameAnalysis,
    MonitoringSession,
    Student,
)


def session_summary(db: DbSession, session_id: int) -> dict[str, Any] | None:
    session = db.get(MonitoringSession, session_id)
    if session is None:
        return None
    return {
        "session_id": session.id,
        "name": session.name,
        "source": session.source,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "fps": session.fps,
        "frames_processed": session.frames_processed,
    }


def class_timeline(db: DbSession, session_id: int) -> list[dict[str, Any]]:
    """Class-average attention over time (one point per snapshot interval)."""
    rows = db.scalars(
        select(ClassSnapshot)
        .where(ClassSnapshot.session_id == session_id)
        .order_by(ClassSnapshot.timestamp)
    ).all()
    return [
        {
            "timestamp": round(r.timestamp, 2),
            "avg_attention": round(r.avg_attention, 2),
            "students_present": r.students_present,
            "phones_visible": r.phones_visible,
            "hands_raised": r.hands_raised,
            "alert": r.low_attention_alert,
        }
        for r in rows
    ]


def per_student_stats(db: DbSession, session_id: int) -> list[dict[str, Any]]:
    """Aggregate engagement metrics per student for the whole session."""
    f = FrameAnalysis
    rows = db.execute(
        select(
            Student.id,
            Student.label,
            Student.track_id,
            Student.first_seen_ts,
            Student.last_seen_ts,
            Student.frames_seen,
            func.avg(f.attention_score).label("avg_attention"),
            func.min(f.attention_score).label("min_attention"),
            func.max(f.attention_score).label("max_attention"),
            func.max(f.blink_total).label("blink_total"),
            func.avg(f.blink_rate).label("avg_blink_rate"),
            func.sum(case((f.phone_visible, 1), else_=0)).label("phone_frames"),
            func.sum(case((f.hand_raised, 1), else_=0)).label("hand_frames"),
            func.sum(case((f.eyes_closed, 1), else_=0)).label("eyes_closed_frames"),
            func.sum(case((f.head_pose == "forward", 1), else_=0)).label("forward_frames"),
            func.count(f.id).label("samples"),
        )
        .join(f, f.student_id == Student.id)
        .where(Student.session_id == session_id)
        .group_by(Student.id)
        .order_by(Student.track_id)
    ).all()

    result = []
    for r in rows:
        samples = r.samples or 1
        result.append(
            {
                "student_id": r.id,
                "track_id": r.track_id,
                "label": r.label,
                "first_seen": round(r.first_seen_ts, 2),
                "last_seen": round(r.last_seen_ts, 2),
                "frames_seen": r.frames_seen,
                "avg_attention": round(r.avg_attention or 0.0, 2),
                "min_attention": round(r.min_attention or 0.0, 2),
                "max_attention": round(r.max_attention or 0.0, 2),
                "blink_total": int(r.blink_total or 0),
                "avg_blink_rate": round(r.avg_blink_rate or 0.0, 2),
                "phone_usage_ratio": round((r.phone_frames or 0) / samples, 4),
                "hand_raised_ratio": round((r.hand_frames or 0) / samples, 4),
                "eyes_closed_ratio": round((r.eyes_closed_frames or 0) / samples, 4),
                "forward_ratio": round((r.forward_frames or 0) / samples, 4),
            }
        )
    return result


def student_timeline(
    db: DbSession, session_id: int, student_id: int, max_points: int = 500
) -> list[dict[str, Any]]:
    """Attention over time for one student, downsampled to max_points."""
    f = FrameAnalysis
    rows = db.execute(
        select(f.timestamp, f.attention_score, f.head_pose, f.gaze)
        .where(f.session_id == session_id, f.student_id == student_id)
        .order_by(f.timestamp)
    ).all()
    step = max(1, len(rows) // max_points)
    return [
        {
            "timestamp": round(r.timestamp, 2),
            "attention": round(r.attention_score, 2),
            "head_pose": r.head_pose,
            "gaze": r.gaze,
        }
        for r in rows[::step]
    ]


def session_statistics(db: DbSession, session_id: int) -> dict[str, Any]:
    """Headline numbers for the statistics endpoint / dashboard cards."""
    f = FrameAnalysis
    agg = db.execute(
        select(
            func.avg(f.attention_score),
            func.count(func.distinct(f.student_id)),
            func.count(f.id),
        ).where(f.session_id == session_id)
    ).one()
    avg_attention, student_count, sample_count = agg

    alerts = db.scalar(
        select(func.count(ClassSnapshot.id)).where(
            ClassSnapshot.session_id == session_id,
            ClassSnapshot.low_attention_alert.is_(True),
        )
    )
    students = per_student_stats(db, session_id)
    most_engaged = max(students, key=lambda s: s["avg_attention"], default=None)
    least_engaged = min(students, key=lambda s: s["avg_attention"], default=None)

    return {
        "session": session_summary(db, session_id),
        "class_average_attention": round(avg_attention or 0.0, 2),
        "students_detected": int(student_count or 0),
        "total_samples": int(sample_count or 0),
        "low_attention_alerts": int(alerts or 0),
        "most_engaged": most_engaged["label"] if most_engaged else None,
        "least_engaged": least_engaged["label"] if least_engaged else None,
        "total_hand_raises": sum(
            round(s["hand_raised_ratio"] * s["frames_seen"]) > 0 for s in students
        ),
        "phone_incidents": sum(s["phone_usage_ratio"] > 0 for s in students),
    }


def attendance_list(db: DbSession, session_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.label)
    ).all()
    if rows:
        return [
            {
                "label": r.label,
                "present": r.present,
                "first_seen": round(r.first_seen_ts, 2),
                "last_seen": round(r.last_seen_ts, 2),
                "presence_ratio": r.presence_ratio,
            }
            for r in rows
        ]
    # Session still running: derive live attendance from Student rows.
    students = db.scalars(
        select(Student).where(Student.session_id == session_id).order_by(Student.track_id)
    ).all()
    return [
        {
            "label": s.label,
            "present": True,
            "first_seen": round(s.first_seen_ts, 2),
            "last_seen": round(s.last_seen_ts, 2),
            "presence_ratio": None,
        }
        for s in students
    ]
