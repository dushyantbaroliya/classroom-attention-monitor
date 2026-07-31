"""API endpoint tests using the app factory with an in-memory database."""
from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import AppConfig
from backend.app.main import create_app
from backend.app.services.pipeline_runner import PipelineRunner
from database import crud
from database.base import session_scope
from ml.pipeline import AttentionPipeline
from tests.conftest import make_frame, student_result
from tests.fakes import FakeAnalyzer, FakeDetector, FakeStudentScript


@pytest.fixture()
def app(tmp_path):
    config = AppConfig()
    config.storage.database_url = "sqlite:///:memory:"
    config.storage.upload_dir = str(tmp_path / "uploads")
    config.storage.log_dir = str(tmp_path / "logs")
    config.tracking.min_hits = 1
    application = create_app(config)

    # Inject a runner whose pipeline uses fakes (no YOLO/MediaPipe needed).
    def fake_pipeline_factory(cfg: AppConfig) -> AttentionPipeline:
        scripts = [FakeStudentScript(bbox=(100, 100, 300, 500))]
        return AttentionPipeline(
            config=cfg, detector=FakeDetector(scripts), analyzer=FakeAnalyzer(scripts)
        )

    application.state.runner = PipelineRunner(
        config, application.state.session_factory, pipeline_factory=fake_pipeline_factory
    )
    return application


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded(app):
    """Insert a completed session directly through the CRUD layer."""
    factory = app.state.session_factory
    with session_scope(factory) as db:
        session = crud.create_session(db, name="Seeded", source="video.mp4")
        cache: dict = {}
        for i in range(6):
            frame = make_frame(
                i, i * 1.0,
                [student_result(1, 90.0), student_result(2, 30.0, phone=True)],
            )
            crud.store_frame_result(db, session.id, frame, cache)
            crud.store_snapshot(db, session.id, frame, low_attention_threshold=40.0)
        crud.finalize_attendance(db, session.id, total_frames=6)
        crud.end_session(db, session.id, "completed", fps=10.0, frames_processed=6)
        sid = session.id
    return sid


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["active_session_id"] is None
        assert body["pipeline_available"] is False  # heavy deps absent in tests


class TestAnalyticsEndpoints:
    def test_analytics_returns_timeline_and_students(self, client, seeded):
        r = client.get("/analytics", params={"session_id": seeded})
        assert r.status_code == 200
        body = r.json()
        assert body["session"]["status"] == "completed"
        assert len(body["timeline"]) == 6
        assert len(body["students"]) == 2

    def test_analytics_defaults_to_latest_session(self, client, seeded):
        r = client.get("/analytics")
        assert r.status_code == 200
        assert r.json()["session"]["session_id"] == seeded

    def test_analytics_no_sessions_404(self, client):
        assert client.get("/analytics").status_code == 404

    def test_students_endpoint(self, client, seeded):
        r = client.get("/students", params={"session_id": seeded})
        assert r.status_code == 200
        students = r.json()
        assert [s["label"] for s in students] == ["Student 1", "Student 2"]
        assert students[0]["avg_attention"] == 90.0

    def test_attendance_endpoint(self, client, seeded):
        r = client.get("/attendance", params={"session_id": seeded})
        assert r.status_code == 200
        entries = r.json()["attendance"]
        assert len(entries) == 2
        assert all(e["present"] for e in entries)

    def test_statistics_endpoint(self, client, seeded):
        r = client.get("/statistics", params={"session_id": seeded})
        assert r.status_code == 200
        body = r.json()
        assert body["students_detected"] == 2
        assert body["most_engaged"] == "Student 1"
        assert body["phone_incidents"] == 1

    def test_csv_export(self, client, seeded):
        r = client.get("/analytics/export.csv", params={"session_id": seeded})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("label,track_id")
        assert len(lines) == 3

    def test_sessions_list(self, client, seeded):
        r = client.get("/sessions")
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestUploadValidation:
    def test_rejects_non_video_files(self, client):
        r = client.post(
            "/video/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400
        assert "Unsupported video type" in r.json()["detail"]


class TestStreamLifecycle:
    def test_stop_without_session_is_ok(self, client):
        r = client.post("/stream/stop")
        assert r.status_code == 200
        assert "No active session" in r.json()["message"]

    def test_start_process_stop_with_synthetic_video(self, client, app, tmp_path):
        cv2 = pytest.importorskip("cv2")
        video_path = tmp_path / "class.avi"
        writer = cv2.VideoWriter(
            str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (640, 480)
        )
        for _ in range(20):
            writer.write(np.zeros((480, 640, 3), dtype=np.uint8))
        writer.release()

        r = client.post(
            "/stream/start",
            json={"source": str(video_path), "session_name": "Synthetic"},
        )
        assert r.status_code == 200
        session_id = r.json()["session_id"]

        # Wait for the worker to finish the 20-frame file.
        runner = app.state.runner
        for _ in range(100):
            if not runner.running:
                break
            time.sleep(0.05)
        assert not runner.running

        stats = client.get("/statistics", params={"session_id": session_id}).json()
        assert stats["session"]["status"] == "completed"
        assert stats["students_detected"] == 1
        assert stats["total_samples"] > 0

        attendance = client.get("/attendance", params={"session_id": session_id}).json()
        assert attendance["attendance"][0]["label"] == "Student 1"

    def test_double_start_conflicts(self, client, app, tmp_path):
        cv2 = pytest.importorskip("cv2")
        video_path = tmp_path / "long.avi"
        writer = cv2.VideoWriter(
            str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (640, 480)
        )
        for _ in range(300):
            writer.write(np.zeros((480, 640, 3), dtype=np.uint8))
        writer.release()

        first = client.post("/stream/start", json={"source": str(video_path)})
        assert first.status_code == 200
        second = client.post("/stream/start", json={"source": str(video_path)})
        assert second.status_code == 409

        stop = client.post("/stream/stop")
        assert stop.status_code == 200
