from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_production import BombarProductionDryRunService
from app.bombar_production.errors import BombarProductionError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bombar production dry run without paid provider calls.")
    parser.add_argument("--matrix", required=True, help="Path to Bombar CSV/XLSX product matrix.")
    parser.add_argument("--target-videos", type=int, default=350)
    parser.add_argument("--target-destinations", type=int, default=120)
    parser.add_argument("--campaign-name", default="Bombar Production Dry Run")
    parser.add_argument("--reports-dir", default="reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = BombarProductionDryRunService(db, reports_dir=args.reports_dir).run(
                args.matrix,
                target_videos=args.target_videos,
                target_destinations=args.target_destinations,
                campaign_name=args.campaign_name,
            )
    except BombarProductionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
