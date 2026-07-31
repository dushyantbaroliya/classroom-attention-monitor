"""Seed the database with a realistic synthetic session.

Lets you explore the dashboard without cameras, models or GPU:

    python scripts/seed_demo.py            # 8 students, 10 minutes of class
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.config import load_config
from database import crud
from database.base import Base, make_engine, make_session_factory, session_scope
from tests.conftest import make_frame
from ml.types import (
    EyeState,
    GazeEstimate,
    HandState,
    HeadPose,
    PhoneState,
    ScoreBreakdown,
    StudentFrameResult,
)

DURATION_S = 600.0
STEP_S = 2.0
N_STUDENTS = 8
SEED = 42


def synthetic_student(track_id: int, t: float, rng: random.Random) -> StudentFrameResult:
    """A student whose attention drifts over the lesson with personal bias."""
    personal_bias = 25 * math.sin(track_id * 1.7)          # some students focus more
    lesson_arc = 15 * math.sin(2 * math.pi * t / 600.0)    # class-wide ebb and flow
    noise = rng.gauss(0, 6)
    score = max(5.0, min(98.0, 65 + personal_bias + lesson_arc + noise))

    phone = score < 35 and rng.random() < 0.5
    eyes_closed = score < 25 and rng.random() < 0.4
    hand = score > 80 and rng.random() < 0.06
    head_label = "forward" if score > 55 else rng.choice(["left", "right", "down"])
    gaze_label = "screen" if score > 55 else rng.choice(["down", "left", "notebook"])

    x = 80 + (track_id - 1) % 4 * 300
    y = 100 + (track_id - 1) // 4 * 280
    return StudentFrameResult(
        track_id=track_id,
        label=f"Student {track_id}",
        bbox=(x, y, x + 200, y + 240),
        head=HeadPose(label=head_label, yaw=rng.gauss(0, 10), pitch=rng.gauss(0, 8), ok=True),
        eyes=EyeState(
            ear=0.12 if eyes_closed else 0.29,
            eyes_closed=eyes_closed,
            blink_total=int(t / 60 * 15),
            blink_rate=rng.gauss(15, 3),
            ok=True,
        ),
        gaze=GazeEstimate(label=gaze_label, ok=True),
        phone=PhoneState(visible=phone),
        hand=HandState(raised=hand),
        score=ScoreBreakdown(normalized=score, smoothed=round(score, 2)),
    )


def main() -> None:
    config = load_config()
    engine = make_engine(config.storage.database_url)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    rng = random.Random(SEED)

    with session_scope(factory) as db:
        session = crud.create_session(db, name="Demo lesson", source="synthetic")
        cache: dict = {}
        n_frames = 0
        t = 0.0
        while t <= DURATION_S:
            students = [
                synthetic_student(i + 1, t, rng)
                for i in range(N_STUDENTS)
                # Student 8 arrives 2 minutes late.
                if not (i == N_STUDENTS - 1 and t < 120)
            ]
            frame = make_frame(n_frames, t, students)
            crud.store_frame_result(db, session.id, frame, cache)
            crud.store_snapshot(
                db, session.id, frame, config.analytics.low_attention_alert
            )
            n_frames += 1
            t += STEP_S
        crud.finalize_attendance(db, session.id, total_frames=n_frames)
        crud.end_session(
            db, session.id, status="completed",
            fps=round(1 / STEP_S, 2), frames_processed=n_frames,
        )
        print(f"Seeded session #{session.id} with {N_STUDENTS} students, "
              f"{n_frames} frames -> {config.storage.database_url}")


if __name__ == "__main__":
    main()
