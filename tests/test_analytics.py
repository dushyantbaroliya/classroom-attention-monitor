"""Unit tests for CRUD persistence and analytics aggregation."""
from __future__ import annotations

import csv
import io

import pytest

from analytics import aggregator
from analytics.export import students_csv
from database import crud
from database.models import FrameAnalysis, Student


class TestCrud:
    def test_students_created_once_per_track_id(self, populated_session):
        db, session_id = populated_session
        students = db.query(Student).filter_by(session_id=session_id).all()
        assert len(students) == 2
        assert {s.label for s in students} == {"Student 1", "Student 2"}

    def test_frames_persisted_with_scores(self, populated_session):
        db, session_id = populated_session
        frames = db.query(FrameAnalysis).filter_by(session_id=session_id).all()
        assert len(frames) == 20  # 2 students x 10 frames
        assert all(0 <= f.attention_score <= 100 for f in frames)

    def test_student_frames_seen_counter(self, populated_session):
        db, session_id = populated_session
        student = db.query(Student).filter_by(session_id=session_id, track_id=1).one()
        assert student.frames_seen == 10
        assert student.last_seen_ts == pytest.approx(4.5)

    def test_session_lifecycle(self, populated_session):
        db, session_id = populated_session
        summary = aggregator.session_summary(db, session_id)
        assert summary["status"] == "completed"
        assert summary["frames_processed"] == 10
        assert summary["fps"] == 12.5

    def test_missing_session_returns_none(self, db):
        assert aggregator.session_summary(db, 999) is None


class TestAggregation:
    def test_per_student_stats(self, populated_session):
        db, session_id = populated_session
        stats = {s["label"]: s for s in aggregator.per_student_stats(db, session_id)}
        s1, s2 = stats["Student 1"], stats["Student 2"]

        # Student 1 scores were 80..89 -> avg 84.5.
        assert s1["avg_attention"] == pytest.approx(84.5)
        assert s1["min_attention"] == 80.0
        assert s1["max_attention"] == 89.0
        # Hand raised in frames 5..9 = half the samples.
        assert s1["hand_raised_ratio"] == pytest.approx(0.5)
        assert s1["phone_usage_ratio"] == 0.0

        # Student 2: phone in even frames (5 of 10), always eyes closed.
        assert s2["phone_usage_ratio"] == pytest.approx(0.5)
        assert s2["eyes_closed_ratio"] == 1.0
        assert s2["avg_attention"] == 40.0

    def test_class_timeline_points_and_alerts(self, populated_session):
        db, session_id = populated_session
        timeline = aggregator.class_timeline(db, session_id)
        assert len(timeline) == 5  # snapshot every other frame
        assert timeline[0]["students_present"] == 2
        # Class averages start at (80+40)/2 = 60 < 65 -> alert fires.
        assert timeline[0]["alert"] is True
        assert timeline[-1]["avg_attention"] == pytest.approx((88 + 40) / 2)

    def test_student_timeline_ordered_and_bounded(self, populated_session):
        db, session_id = populated_session
        student = db.query(Student).filter_by(session_id=session_id, track_id=1).one()
        points = aggregator.student_timeline(db, session_id, student.id)
        assert len(points) == 10
        timestamps = [p["timestamp"] for p in points]
        assert timestamps == sorted(timestamps)
        assert points[0]["attention"] == 80.0

    def test_statistics_headline_numbers(self, populated_session):
        db, session_id = populated_session
        stats = aggregator.session_statistics(db, session_id)
        assert stats["students_detected"] == 2
        assert stats["total_samples"] == 20
        assert stats["most_engaged"] == "Student 1"
        assert stats["least_engaged"] == "Student 2"
        assert stats["low_attention_alerts"] == 5
        assert stats["phone_incidents"] == 1

    def test_attendance_after_finalize(self, populated_session):
        db, session_id = populated_session
        attendance = aggregator.attendance_list(db, session_id)
        assert len(attendance) == 2
        assert all(a["present"] for a in attendance)
        assert attendance[0]["presence_ratio"] == 1.0

    def test_attendance_live_fallback(self, db):
        """A running session (no finalized rows) derives attendance live."""
        from tests.conftest import make_frame, student_result

        session = crud.create_session(db, name="live", source="camera:0")
        crud.store_frame_result(db, session.id, make_frame(0, 0.0, [student_result(1, 75.0)]))
        db.commit()
        attendance = aggregator.attendance_list(db, session.id)
        assert len(attendance) == 1
        assert attendance[0]["presence_ratio"] is None


class TestCsvExport:
    def test_csv_has_header_and_all_students(self, populated_session):
        db, session_id = populated_session
        text = students_csv(db, session_id)
        rows = list(csv.DictReader(io.StringIO(text)))
        assert len(rows) == 2
        assert rows[0]["label"] == "Student 1"
        assert float(rows[0]["avg_attention"]) == 84.5

    def test_csv_empty_session(self, db):
        session = crud.create_session(db, name="empty", source="camera:0")
        db.commit()
        text = students_csv(db, session.id)
        rows = list(csv.DictReader(io.StringIO(text)))
        assert rows == []
