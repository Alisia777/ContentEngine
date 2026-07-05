from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import LaunchPlanner
from app.bombar_launch.errors import BombarLaunchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare prompt-only content runs for a Bombar campaign.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--variant-count", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = LaunchPlanner(db).prepare_content(
                args.campaign_id,
                platform=args.platform,
                duration_seconds=args.duration,
                variant_count=args.variant_count,
            )
    except BombarLaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign ID: {result['campaign_id']}")
    print(f"Prepared runs: {result['prepared_count']}")
    print("Blockers: " + (", ".join(result["blockers"]) if result["blockers"] else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
