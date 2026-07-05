from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.factory_os import FactoryLaunchWorkflow
from app.factory_os.errors import FactoryOSError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Factory OS prompt-only launch workflow.")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--campaign-name", required=True)
    parser.add_argument("--target-videos", type=int, default=350)
    parser.add_argument("--target-destinations", type=int, default=120)
    parser.add_argument("--brand", default="Factory OS")
    parser.add_argument("--performance-csv", default="sample_data/campaign_performance.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = FactoryLaunchWorkflow(db).run_prompt_only_launch(
                args.matrix,
                args.campaign_name,
                args.target_videos,
                args.target_destinations,
                brand=args.brand,
                performance_csv_path=args.performance_csv or None,
            )
    except FactoryOSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
