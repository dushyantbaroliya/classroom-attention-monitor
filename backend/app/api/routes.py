"""REST + WebSocket API routes."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from analytics import aggregator
from analytics.export import students_csv
from backend.app import schemas
from backend.app.api.deps import (
    get_app_config,
    get_db,
    get_runner,
    resolve_session_id,
)
from backend.app.core.config import AppConfig
from backend.app.core.logging import get_logger, log_event
from backend.app.services.pipeline_runner import PipelineRunner
from database.models import MonitoringSession

log = get_logger("api")
router = APIRouter()

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
API_VERSION = "1.0.0"


# --------------------------------------------------------------------- health
@router.get("/health", response_model=schemas.HealthResponse, tags=["system"])
def health(request: Request, runner: PipelineRunner = Depends(get_runner)):
    try:
        import ultralytics  # noqa: F401
        import mediapipe  # noqa: F401

        pipeline_available = True
    except ImportError:
        pipeline_available = False
    return schemas.HealthResponse(
        status="ok",
        version=API_VERSION,
        pipeline_available=pipeline_available,
        active_session_id=runner.session_id,
    )


# --------------------------------------------------------------------- video
@router.post("/video/upload", response_model=schemas.UploadResponse, tags=["video"])
async def upload_video(
    file: UploadFile,
    session_name: str = "Uploaded video",
    config: AppConfig = Depends(get_app_config),
    runner: PipelineRunner = Depends(get_runner),
):
    """Save an uploaded video and start analyzing it as a new session."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video type '{suffix}'. Allowed: {sorted(ALLOWED_VIDEO_SUFFIXES)}",
        )
    if runner.running:
        raise HTTPException(status_code=409, detail="A session is already running")

    upload_dir = Path(config.storage.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / Path(file.filename).name
    with target.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    log_event(log, "video_uploaded", filename=target.name, bytes=target.stat().st_size)

    try:
        session_id = runner.start(source=str(target), session_name=session_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return schemas.UploadResponse(
        ok=True,
        message="Upload accepted; analysis started.",
        session_id=session_id,
        filename=target.name,
    )


# -------------------------------------------------------------------- stream
@router.post("/stream/start", response_model=schemas.StreamActionResponse, tags=["stream"])
def stream_start(
    body: schemas.StreamStartRequest,
    config: AppConfig = Depends(get_app_config),
    runner: PipelineRunner = Depends(get_runner),
):
    source = body.source if body.source is not None else config.video.source
    try:
        session_id = runner.start(source=source, session_name=body.session_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return schemas.StreamActionResponse(
        ok=True, message=f"Stream started from source {source!r}", session_id=session_id
    )


@router.post("/stream/stop", response_model=schemas.StreamActionResponse, tags=["stream"])
def stream_stop(runner: PipelineRunner = Depends(get_runner)):
    if not runner.running:
        return schemas.StreamActionResponse(ok=True, message="No active session")
    session_id = runner.session_id
    stopped = runner.stop()
    if not stopped:
        raise HTTPException(status_code=500, detail="Worker did not stop in time")
    return schemas.StreamActionResponse(
        ok=True, message="Session stopped", session_id=session_id
    )


# ------------------------------------------------------------------ sessions
@router.get("/sessions", response_model=list[schemas.SessionInfo], tags=["analytics"])
def list_sessions(db: DbSession = Depends(get_db)):
    rows = db.scalars(
        select(MonitoringSession).order_by(MonitoringSession.started_at.desc()).limit(50)
    ).all()
    return [aggregator.session_summary(db, r.id) for r in rows]


# ------------------------------------------------------------------ students
@router.get("/students", response_model=list[schemas.StudentStats], tags=["analytics"])
def students(
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    return aggregator.per_student_stats(db, sid)


@router.get("/students/{student_id}/timeline", tags=["analytics"])
def student_timeline(
    student_id: int,
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    return aggregator.student_timeline(db, sid, student_id)


# ----------------------------------------------------------------- analytics
@router.get("/analytics", response_model=schemas.AnalyticsResponse, tags=["analytics"])
def analytics(
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    summary = aggregator.session_summary(db, sid)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Session {sid} not found")
    return schemas.AnalyticsResponse(
        session=summary,
        timeline=aggregator.class_timeline(db, sid),
        students=aggregator.per_student_stats(db, sid),
    )


@router.get("/analytics/export.csv", tags=["analytics"])
def analytics_csv(
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    csv_text = students_csv(db, sid)
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="session_{sid}_students.csv"'
        },
    )


@router.get("/attendance", response_model=schemas.AttendanceResponse, tags=["analytics"])
def attendance(
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    return schemas.AttendanceResponse(
        session_id=sid, attendance=aggregator.attendance_list(db, sid)
    )


@router.get("/statistics", response_model=schemas.StatisticsResponse, tags=["analytics"])
def statistics(
    request: Request,
    session_id: Optional[int] = None,
    db: DbSession = Depends(get_db),
):
    sid = resolve_session_id(request, db, session_id)
    return aggregator.session_statistics(db, sid)


# ----------------------------------------------------------------- live feed
@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket):
    """Push the latest annotated frame + analytics ~10x/second."""
    await websocket.accept()
    runner: PipelineRunner = websocket.app.state.runner
    last_frame_index = -1
    try:
        while True:
            payload, jpeg_b64 = runner.live.get()
            if payload is not None and payload["frame_index"] != last_frame_index:
                last_frame_index = payload["frame_index"]
                await websocket.send_json({**payload, "jpeg_b64": jpeg_b64})
            elif not runner.running:
                await websocket.send_json({"type": "idle"})
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
