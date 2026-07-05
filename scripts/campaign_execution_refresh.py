from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_execution import ActionQueueService, ExecutionStateService
from app.campaign_execution.errors import CampaignExecutionError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh a campaign execution snapshot and action queue.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            snapshot = ExecutionStateService(db).refresh_snapshot(args.campaign_id)
            actions = ActionQueueService(db).refresh_actions(args.campaign_id)
    except CampaignExecutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign ID: {snapshot.campaign_id}")
    print(f"Snapshot ID: {snapshot.snapshot_id}")
    print(f"Status: {snapshot.status}")
    print(f"Total SKU: {snapshot.total_sku}")
    print(f"Ready SKU: {snapshot.ready_sku}")
    print(f"Blocked SKU: {snapshot.blocked_sku}")
    print(f"Open actions: {len([item for item in actions if item.status == 'open'])}")
    print(f"Blocked actions: {len([item for item in actions if item.status == 'blocked'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
