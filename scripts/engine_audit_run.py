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
    parser = argparse.ArgumentParser(description="Run the ContentEngine quality scorecard.")
    parser.add_argument("--scope-type", default="global")
    parser.add_argument("--scope-id", type=int, default=None)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        service = EngineAuditScorecardService(db)
        run = service.run(scope_type=args.scope_type, scope_id=args.scope_id)
        output = service.output(run)
        report_path = None
        if args.write_report:
            report_path = EngineAuditReportService(db).write(run.id, output_dir=args.output_dir)

    print(f"Audit Run ID: {output.id}")
    print(f"Overall Score: {output.overall_score}/10")
    print(f"Status: {output.status}")
    print("Scores:")
    for dimension in output.dimensions:
        print(f"- {dimension.label}: {dimension.score}/10 ({dimension.status})")
    print("Road to 10/10:")
    for item in output.road_to_10[:5]:
        print(f"- {item['label']}: {item['next_action']}")
    if report_path:
        print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
