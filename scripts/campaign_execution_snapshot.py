from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_execution import ExecutionStateService
from app.campaign_execution.errors import CampaignExecutionError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a campaign execution snapshot.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            snapshot = ExecutionStateService(db).latest_snapshot(args.campaign_id)
    except CampaignExecutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
