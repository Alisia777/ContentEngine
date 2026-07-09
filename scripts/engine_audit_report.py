from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.engine_audit import EngineAuditReportService, EngineAuditScorecardService


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the latest ContentEngine quality scorecard report.")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        service = EngineAuditScorecardService(db)
        run = service.get(args.run_id) if args.run_id else service.latest()
        if not run:
            run = service.run()
        path = EngineAuditReportService(db).write(run.id, output_dir=args.output_dir)

    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
