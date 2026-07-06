from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_control_tower import DestinationControlReportService, DestinationControlTowerError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export destination control tower report.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--markdown", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            report = DestinationControlReportService(db).build(args.campaign_id)
    except DestinationControlTowerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.markdown:
        print(report.markdown)
    else:
        print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
