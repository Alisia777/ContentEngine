from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_autopilot import ActionExecutor
from app.content_autopilot.errors import ContentAutopilotError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute one ContentEngine autopilot decision.")
    parser.add_argument("--decision-id", type=int, required=True)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--allow-publishing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ActionExecutor(db).execute(
                args.decision_id,
                allow_paid=args.allow_paid,
                allow_publishing=args.allow_publishing,
            )
    except ContentAutopilotError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine Autopilot Execute")
    print("=" * 40)
    print(f"Decision ID: {result.decision_id}")
    print(f"Action: {result.action}")
    print(f"Status: {result.status}")
    print(f"Executed: {result.executed}")
    print("Blockers: " + (", ".join(result.blockers) if result.blockers else "none"))
    print(f"Outputs: {result.outputs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
