"""CSV export of session analytics."""
from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session as DbSession

from analytics.aggregator import per_student_stats

STUDENT_COLUMNS = [
    "label",
    "track_id",
    "first_seen",
    "last_seen",
    "frames_seen",
    "avg_attention",
    "min_attention",
    "max_attention",
    "blink_total",
    "avg_blink_rate",
    "phone_usage_ratio",
    "hand_raised_ratio",
    "eyes_closed_ratio",
    "forward_ratio",
]


def students_csv(db: DbSession, session_id: int) -> str:
    """Per-student engagement summary as CSV text."""
    rows = per_student_stats(db, session_id)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=STUDENT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()
