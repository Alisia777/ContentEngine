from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.launch_operations import LaunchReportService
from app.launch_operations.errors import LaunchOperationsError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export launch operations runbook for a campaign.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--reports-dir", default="reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = LaunchReportService(db, reports_dir=args.reports_dir).export_runbook(args.campaign_id)
    except LaunchOperationsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
