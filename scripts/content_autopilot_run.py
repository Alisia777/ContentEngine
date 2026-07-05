from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_autopilot import AutopilotQueueService
from app.content_autopilot.errors import ContentAutopilotError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ContentEngine autopilot decision loop.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--product-id", type=int)
    group.add_argument("--all-products", action="store_true")
    parser.add_argument("--execute-safe", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            product_ids = None if args.all_products else [args.product_id]
            result = AutopilotQueueService(db).run(product_ids=product_ids, execute_safe=args.execute_safe)
    except ContentAutopilotError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine Autopilot Run")
    print("=" * 36)
    print(f"Autopilot Run ID: {result.id}")
    print(f"Status: {result.status}")
    print(f"Scope: {result.scope_type}")
    print(f"Products checked: {result.total_checked}")
    print(f"Ready: {result.total_ready}")
    print(f"Blocked: {result.total_blocked}")
    print(f"Needs human review: {result.total_needs_human_review}")
    print(f"Actions executed: {result.total_actions_executed}")
    for item in result.summary.get("decisions", []):
        print(f"- {item['sku']}: {item['recommended_action']} / {item['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
