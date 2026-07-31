"""Structured (JSON-lines) logging for the whole application.

Every record carries a timestamp, level, logger name and message plus any
extra fields passed via `logger.info("msg", extra={"extra_fields": {...}})`.
Console output stays human-readable; the rotating file sink is JSON for
machine consumption.
"""
from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOGGER = "cam"  # classroom attention monitor


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def setup_logging(log_dir: str | Path, level: int = logging.INFO) -> logging.Logger:
    """Configure the app logger once; safe to call repeatedly."""
    logger = logging.getLogger(APP_LOGGER)
    if logger.handlers:  # already configured
        return logger
    logger.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    logger.addHandler(console)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path / "app.jsonl", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    return logger


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{APP_LOGGER}.{component}")


def log_event(logger: logging.Logger, message: str, **fields) -> None:
    """Structured event helper: log_event(log, "session_started", session_id=3)."""
    logger.info(message, extra={"extra_fields": fields})
