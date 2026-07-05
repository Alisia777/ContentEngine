from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_factory import ContentRunOrchestrator
from app.content_factory.errors import ContentFactoryError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run honest rules-based AI review for a content factory run.")
    parser.add_argument("--content-run-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).review(args.content_run_id)
    except ContentFactoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine content run review")
    print("=" * 38)
    print(f"Content Run ID: {result.id}")
    print(f"Status: {result.status}")
    print(f"AI Review ID: {result.ai_review_id}")
    print(f"Reference Readiness: {result.reference_readiness.get('status', 'unknown')}")
    print(f"Geometry Readiness: {result.geometry_readiness.get('status', 'unknown')}")
    print(f"Publishing Readiness: {result.publishing_readiness.get('status', 'unknown')}")
    print(f"Human Review Required: {result.human_review_required}")
    print("Blockers: " + (", ".join(result.blockers) if result.blockers else "none"))
    print("Next Actions: " + (", ".join(action.action for action in result.next_actions) if result.next_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
