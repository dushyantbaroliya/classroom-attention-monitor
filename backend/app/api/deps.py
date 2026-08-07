"""FastAPI dependency injection: config, database sessions, runner.

The app stores its singletons on `app.state`; these dependencies pull from
there, which makes tests trivial, build an app with a test config and an
in-memory database, no monkeypatching.
"""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from backend.app.core.config import AppConfig
from backend.app.services.pipeline_runner import PipelineRunner
from database import crud


def get_app_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_db(request: Request) -> Iterator[DbSession]:
    factory = request.app.state.session_factory
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_runner(request: Request) -> PipelineRunner:
    return request.app.state.runner


def resolve_session_id(
    request: Request, db: DbSession, session_id: int | None
) -> int:
    """Default to the active session, else the most recent one."""
    if session_id is not None:
        return session_id
    runner: PipelineRunner = request.app.state.runner
    if runner.session_id is not None:
        return runner.session_id
    latest = crud.latest_session(db)
    if latest is None:
        raise HTTPException(status_code=404, detail="No sessions recorded yet")
    return latest.id
