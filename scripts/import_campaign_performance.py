from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_performance import CampaignMetricsImporter
from app.campaign_performance.errors import CampaignPerformanceError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import campaign performance metrics from CSV.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--csv", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    csv_path = Path(args.csv)
    try:
        with SessionLocal() as db:
            result = CampaignMetricsImporter(db).import_csv_text(
                args.campaign_id,
                csv_path.read_text(encoding="utf-8-sig"),
                source_file=str(csv_path),
            )
    except (CampaignPerformanceError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
