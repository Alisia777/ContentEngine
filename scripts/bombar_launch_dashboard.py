from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import LaunchDashboardService
from app.bombar_launch.errors import BombarLaunchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a Bombar launch campaign dashboard.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            dashboard = LaunchDashboardService(db).dashboard(args.campaign_id)
    except BombarLaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign ID: {dashboard.campaign_id}")
    print(f"Linked Campaign ID: {dashboard.linked_campaign_id}")
    print(f"Status: {dashboard.campaign_status}")
    print(f"Ready SKU: {dashboard.ready_sku}")
    print(f"Blocked SKU: {dashboard.blocked_sku}")
    print(f"Needs reference: {dashboard.needs_reference}")
    print(f"Needs review: {dashboard.needs_review}")
    print(f"Publishing ready: {dashboard.ready_for_publishing}")
    print(f"Destination packs: {dashboard.destination_packs}")
    print(f"Publishing tasks: {dashboard.publishing_tasks}")
    print(f"Campaign state: {'present' if dashboard.campaign_state else 'missing'}")
    print(f"Campaign report: {'present' if dashboard.campaign_report else 'missing'}")
    for action in dashboard.next_actions:
        print(f"Next action: {action['action']} - {action['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
