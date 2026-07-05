from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_execution import ActionQueueService
from app.campaign_execution.errors import CampaignExecutionError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print campaign execution action queue items.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--include-done", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            actions = ActionQueueService(db).list_actions(args.campaign_id, include_done=args.include_done)
    except CampaignExecutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign ID: {args.campaign_id}")
    print(f"Actions: {len(actions)}")
    for item in actions:
        sku = item.sku or "campaign"
        blockers = ",".join(item.blockers)
        print(
            f"#{item.action_id} priority={item.priority} sku={sku} content_run={item.content_run_id or '-'} action={item.action_type} "
            f"status={item.status} safe={item.safe_to_execute} human={item.requires_human} blockers={blockers}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
