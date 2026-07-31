"""Shared fixtures: in-memory database and synthetic session data."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session as DbSession

from database import crud
from database.base import Base, make_engine, make_session_factory
from ml.types import (
    EyeState,
    FrameResult,
    GazeEstimate,
    HandState,
    HeadPose,
    PhoneState,
    ScoreBreakdown,
    StudentFrameResult,
)


@pytest.fixture()
def db() -> DbSession:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def student_result(
    track_id: int,
    score: float,
    *,
    phone: bool = False,
    hand: bool = False,
    eyes_closed: bool = False,
    head_label: str = "forward",
) -> StudentFrameResult:
    return StudentFrameResult(
        track_id=track_id,
        label=f"Student {track_id}",
        bbox=(10.0 * track_id, 20.0, 10.0 * track_id + 80, 220.0),
        head=HeadPose(label=head_label, ok=True),
        eyes=EyeState(ear=0.28, eyes_closed=eyes_closed, blink_total=track_id, ok=True),
        gaze=GazeEstimate(label="screen", ok=True),
        phone=PhoneState(visible=phone),
        hand=HandState(raised=hand),
        score=ScoreBreakdown(normalized=score, smoothed=score),
    )


def make_frame(
    frame_index: int, timestamp: float, students: list[StudentFrameResult]
) -> FrameResult:
    scores = [s.score.smoothed for s in students]
    return FrameResult(
        frame_index=frame_index,
        timestamp=timestamp,
        students=students,
        class_average=sum(scores) / len(scores) if scores else 0.0,
        phones_visible=sum(s.phone.visible for s in students),
        hands_raised=sum(s.hand.raised for s in students),
    )


@pytest.fixture()
def populated_session(db: DbSession) -> tuple[DbSession, int]:
    """A completed session: 2 students, 10 frames, snapshots + attendance."""
    session = crud.create_session(db, name="Test class", source="video.mp4")
    cache: dict = {}
    for i in range(10):
        ts = i * 0.5
        frame = make_frame(
            i,
            ts,
            [
                student_result(1, 80.0 + i, phone=False, hand=(i >= 5)),
                student_result(2, 40.0, phone=(i % 2 == 0), eyes_closed=True),
            ],
        )
        crud.store_frame_result(db, session.id, frame, cache)
        if i % 2 == 0:
            crud.store_snapshot(db, session.id, frame, low_attention_threshold=65.0)
    crud.finalize_attendance(db, session.id, total_frames=10)
    crud.end_session(db, session.id, status="completed", fps=12.5, frames_processed=10)
    db.commit()
    return db, session.id
