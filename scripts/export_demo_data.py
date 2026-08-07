"""Export a recorded session to static JSON for the GitHub Pages demo.

The demo build has no backend, so the dashboard reads pre-baked JSON files
instead of the REST API. These are produced by the *real* analytics
aggregators, so the payload shapes match the live API exactly, the frontend
only swaps its fetch layer, not its types or rendering.

    python scripts/export_demo_data.py [--session-id N]

Writes into frontend/public/demo-data/:
    health.json  sessions.json  analytics.json  statistics.json
    attendance.json  students.json  student-<id>-timeline.json  students.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import aggregator
from analytics.export import students_csv
from backend.app.core.config import load_config
from database import crud
from database.base import make_engine, make_session_factory, session_scope

OUT = Path(__file__).resolve().parents[1] / "frontend" / "public" / "demo-data"


def write(name: str, payload) -> None:
    dest = OUT / name
    if isinstance(payload, str):
        dest.write_text(payload, encoding="utf-8")
    else:
        dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"  {name}  ({dest.stat().st_size / 1024:.1f} KB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", type=int, default=None)
    args = ap.parse_args()

    config = load_config()
    engine = make_engine(config.storage.database_url)
    factory = make_session_factory(engine)
    OUT.mkdir(parents=True, exist_ok=True)

    with session_scope(factory) as db:
        if args.session_id is not None:
            sid = args.session_id
        else:
            latest = crud.latest_session(db)
            if latest is None:
                print("ERROR: no sessions in the database. Run scripts/seed_demo.py first.")
                return 1
            sid = latest.id

        summary = aggregator.session_summary(db, sid)
        if summary is None:
            print(f"ERROR: session {sid} not found.")
            return 1

        students = aggregator.per_student_stats(db, sid)
        print(f"Exporting session #{sid} ({summary['name']}, {len(students)} students):")

        # Mirrors GET /health on a backend with no active session.
        write("health.json", {
            "status": "ok",
            "version": "1.0.0-demo",
            "pipeline_available": False,
            "active_session_id": None,
        })
        write("sessions.json", [summary])
        write("analytics.json", {
            "session": summary,
            "timeline": aggregator.class_timeline(db, sid),
            "students": students,
        })
        write("statistics.json", aggregator.session_statistics(db, sid))
        write("attendance.json", {
            "session_id": sid,
            "attendance": aggregator.attendance_list(db, sid),
        })
        write("students.json", students)
        write("students.csv", students_csv(db, sid))

        for s in students:
            write(
                f"student-{s['student_id']}-timeline.json",
                aggregator.student_timeline(db, sid, s["student_id"]),
            )

    print(f"\nDemo data written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
