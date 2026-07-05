from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import DistributionAllocator
from app.bombar_launch.errors import BombarLaunchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Bombar campaign distribution plan.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            plan = DistributionAllocator(db).generate_plan(args.campaign_id)
    except BombarLaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Distribution plan ID: {plan.plan_id}")
    print(f"Status: {plan.status}")
    print(f"Tasks: {plan.total_tasks}")
    print("Blockers: " + (", ".join(plan.blockers) if plan.blockers else "none"))
    print("Warnings: " + (", ".join(plan.warnings) if plan.warnings else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
