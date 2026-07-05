from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_autopilot import CampaignRunner
from app.campaign_autopilot.errors import CampaignAutopilotError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run safe prompt-only actions for a campaign.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = CampaignRunner(db).run_prompt_only_for_ready_items(args.campaign_id)
    except CampaignAutopilotError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign Run ID: {result.campaign_run_id}")
    print(f"Status: {result.status}")
    print(f"Prompt ready: {result.total_prompt_ready}")
    print(f"Blockers: {', '.join(result.blockers) if result.blockers else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
