from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.engine_audit import EngineAuditError, EngineAuditReportService, EngineAuditScorecardService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ContentEngine quality scorecard audit.")
    parser.add_argument("--scope-type", default="global")
    parser.add_argument("--scope-id", type=int, default=None)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--output-dir", default="reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            service = EngineAuditScorecardService(db)
            report = service.run(scope_type=args.scope_type, scope_id=args.scope_id)
            report_path = None
            if args.write_report:
                report_path = EngineAuditReportService(db).write(report.id, output_dir=args.output_dir)
                db.refresh(report)
            output = service.output(report)
    except EngineAuditError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine engine audit")
    print("=" * 34)
    print(f"Audit Report ID: {output.id}")
    print(f"Status: {output.status}")
    print(f"Overall Score: {output.overall_score:.1f}/10")
    print(f"Dimensions: {len(output.dimensions)}")
    for dimension in output.dimensions:
        reasons = ", ".join(dimension.reasons) if dimension.reasons else "none"
        fixes = " | ".join(dimension.required_fixes) if dimension.required_fixes else "none"
        print(f"- {dimension.label}: {dimension.score:.1f}/10 [{dimension.status}]")
        print(f"  reasons: {reasons}")
        print(f"  required fixes: {fixes}")
        print(f"  next action: {dimension.next_action}")
    print("\nRoad to 10/10:")
    for index, step in enumerate(output.road_to_10, start=1):
        print(f"{index}. {step['label']} -> {step['next_action']} ({step['current_score']}/10)")
    print(f"\nReport Path: {report_path or output.report_path or 'not written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
