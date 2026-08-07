"""Background pipeline execution.

One PipelineRunner per process manages at most one live session at a time
(multi-classroom support = multiple backend containers, see README).

Responsibilities:
- read frames from a camera or file in a worker thread,
- drive the AttentionPipeline,
- batch-persist results (FrameAnalysis rows + ClassSnapshot timeline),
- keep the latest annotated JPEG + JSON payload for WebSocket consumers,
- finalize attendance and session status on stop/end/error.
"""
from __future__ import annotations

import base64
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import sessionmaker

from backend.app.core.config import AppConfig
from backend.app.core.logging import get_logger, log_event
from database import crud
from database.base import session_scope
from ml.types import FrameResult

log = get_logger("runner")

PipelineFactory = Callable[[AppConfig], "object"]  # returns AttentionPipeline-like


@dataclass
class LiveState:
    """Latest results, shared with WebSocket/API consumers under a lock."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    payload: Optional[dict] = None
    jpeg_b64: Optional[str] = None

    def set(self, payload: dict, jpeg_b64: str | None) -> None:
        with self.lock:
            self.payload = payload
            self.jpeg_b64 = jpeg_b64

    def get(self) -> tuple[Optional[dict], Optional[str]]:
        with self.lock:
            return self.payload, self.jpeg_b64


class PipelineRunner:
    def __init__(
        self,
        config: AppConfig,
        session_factory: sessionmaker,
        pipeline_factory: PipelineFactory | None = None,
    ) -> None:
        self.config = config
        self.session_factory = session_factory
        self._pipeline_factory = pipeline_factory
        self.live = LiveState()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._session_id: Optional[int] = None
        self._error: Optional[str] = None

    # ------------------------------------------------------------------ api
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def session_id(self) -> Optional[int]:
        return self._session_id if self.running else None

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    def start(self, source: int | str, session_name: str) -> int:
        """Create a DB session and launch the worker thread. Returns session id."""
        if self.running:
            raise RuntimeError("A session is already running; stop it first.")
        self._stop_event.clear()
        self._error = None

        with session_scope(self.session_factory) as db:
            source_label = (
                f"camera:{source}" if isinstance(source, int) else Path(str(source)).name
            )
            session = crud.create_session(db, name=session_name, source=source_label)
            session_id = session.id

        self._session_id = session_id
        self._thread = threading.Thread(
            target=self._run_safe, args=(source, session_id), daemon=True,
            name=f"pipeline-session-{session_id}",
        )
        self._thread.start()
        log_event(log, "session_started", session_id=session_id, source=str(source))
        return session_id

    def stop(self, timeout: float = 10.0) -> bool:
        """Request a graceful stop; returns True if the worker exited in time."""
        if not self.running:
            return True
        self._stop_event.set()
        assert self._thread is not None
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    # ------------------------------------------------------------- internals
    def _run_safe(self, source: int | str, session_id: int) -> None:
        status = "completed"
        try:
            self._run(source, session_id)
            if self._stop_event.is_set():
                status = "stopped"
        except Exception as exc:  # noqa: BLE001, worker must never crash silently
            self._error = str(exc)
            status = "failed"
            log.exception("Pipeline session %s failed", session_id)
        finally:
            self._finalize(session_id, status)

    def _run(self, source: int | str, session_id: int) -> None:
        import cv2

        from ml.annotate import annotate_frame
        from ml.pipeline import build_default_pipeline

        factory = self._pipeline_factory or build_default_pipeline
        pipeline = factory(self.config)

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source!r}")
        is_live = isinstance(source, int)
        if is_live:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.video.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.video.height)
        source_fps = cap.get(cv2.CAP_PROP_FPS) or self.config.video.target_fps

        every_n = self.config.video.process_every_n
        snapshot_interval = self.config.analytics.snapshot_interval_seconds
        batch_size = self.config.analytics.db_batch_size

        frame_index = 0
        processed = 0
        started_monotonic = time.monotonic()
        last_snapshot_ts = -snapshot_interval
        pending: list[FrameResult] = []
        student_cache: dict = {}

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    break  # end of file / camera lost
                frame_index += 1
                if (frame_index - 1) % every_n != 0:
                    continue

                timestamp = (
                    time.monotonic() - started_monotonic
                    if is_live
                    else frame_index / source_fps
                )
                result = pipeline.process_frame(frame, frame_index, timestamp)
                processed += 1

                annotated = annotate_frame(frame, result)
                ok_jpg, jpg = cv2.imencode(
                    ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 70]
                )
                self.live.set(
                    self._payload(session_id, result),
                    base64.b64encode(jpg.tobytes()).decode() if ok_jpg else None,
                )

                pending.append(result)
                if len(pending) >= max(1, batch_size // 10):
                    self._flush(session_id, pending, student_cache)
                    pending = []

                if timestamp - last_snapshot_ts >= snapshot_interval:
                    last_snapshot_ts = timestamp
                    with session_scope(self.session_factory) as db:
                        crud.store_snapshot(
                            db, session_id, result,
                            self.config.analytics.low_attention_alert,
                        )

                # Pace live capture; process files at full speed.
                if is_live:
                    budget = 1.0 / self.config.video.target_fps
                    elapsed = result.processing_ms / 1000.0
                    if elapsed < budget:
                        time.sleep(budget - elapsed)
        finally:
            cap.release()
            if pending:
                self._flush(session_id, pending, student_cache)
            elapsed_total = time.monotonic() - started_monotonic
            self._fps = processed / elapsed_total if elapsed_total > 0 else 0.0
            self._frames_processed = processed
            log_event(
                log, "session_capture_finished",
                session_id=session_id, frames=processed, fps=round(self._fps, 2),
            )

    def _flush(self, session_id: int, results: list[FrameResult], cache: dict) -> None:
        with session_scope(self.session_factory) as db:
            for result in results:
                crud.store_frame_result(db, session_id, result, cache)

    def _finalize(self, session_id: int, status: str) -> None:
        frames = getattr(self, "_frames_processed", 0)
        fps = getattr(self, "_fps", 0.0)
        try:
            with session_scope(self.session_factory) as db:
                crud.finalize_attendance(db, session_id, total_frames=frames)
                crud.end_session(
                    db, session_id, status=status, fps=round(fps, 2),
                    frames_processed=frames,
                )
        except Exception:  # noqa: BLE001
            log.exception("Failed to finalize session %s", session_id)
        log_event(log, "session_ended", session_id=session_id, status=status)

    @staticmethod
    def _payload(session_id: int, result: FrameResult) -> dict:
        return {
            "type": "frame",
            "session_id": session_id,
            "frame_index": result.frame_index,
            "timestamp": round(result.timestamp, 2),
            "class_average": result.class_average,
            "processing_ms": result.processing_ms,
            "students": [
                {
                    "track_id": s.track_id,
                    "label": s.label,
                    "bbox": [round(v, 1) for v in s.bbox],
                    "attention": s.score.smoothed,
                    "head_pose": s.head.label,
                    "gaze": s.gaze.label,
                    "eyes_closed": s.eyes.eyes_closed,
                    "phone_visible": s.phone.visible,
                    "hand_raised": s.hand.raised,
                    "score_components": s.score.components,
                }
                for s in result.students
            ],
        }
