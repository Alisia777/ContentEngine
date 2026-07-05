from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_batch import BatchReporter
from app.campaign_batch.errors import CampaignBatchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a campaign batch report.")
    parser.add_argument("--batch-run-id", type=int, required=True)
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            report = BatchReporter(db).build_report(args.batch_run_id)
    except CampaignBatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.format == "csv":
        print(report.summary_csv)
    else:
        print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
