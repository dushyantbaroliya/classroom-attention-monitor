"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.core.config import AppConfig, load_config
from backend.app.core.logging import get_logger, log_event, setup_logging
from backend.app.services.pipeline_runner import PipelineRunner
from database.base import Base, make_engine, make_session_factory


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or load_config()
    setup_logging(config.storage.log_dir)
    log = get_logger("app")

    engine = make_engine(config.storage.database_url)
    Base.metadata.create_all(engine)  # dev convenience; Alembic owns migrations
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(log, "app_started", database=config.storage.database_url)
        yield
        app.state.runner.stop()
        engine.dispose()
        log_event(log, "app_stopped")

    app = FastAPI(
        title="Classroom Attention Monitoring System",
        description=(
            "Estimates observable engagement behaviors (head pose, gaze, "
            "blinks, phone use, hand raises) for anonymous tracked students. "
            "See README ethics section: this is decision support, not "
            "surveillance or grading."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.runner = PipelineRunner(config, session_factory)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        response = await call_next(request)
        log_event(
            get_logger("http"),
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    app.include_router(router)
    return app
