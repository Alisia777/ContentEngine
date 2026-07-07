from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_workbench import CreativeWorkbenchError, RewriteWorkflowService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create and build a creative workbench rewrite.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--feedback", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = RewriteWorkflowService(db).rewrite(args.session_id, feedback=args.feedback)
    except CreativeWorkbenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative workbench rewrite")
    print("=" * 43)
    print(f"Session ID: {result.session_id}")
    print(f"Rewrite Request ID: {result.rewrite_request_id}")
    print(f"Source UGC Script ID: {result.source_ugc_script_id}")
    print(f"New UGC Script ID: {result.new_ugc_script_id}")
    print(f"Status: {result.status}")
    print(f"Previous Score: {(result.previous_score or {}).get('total_score', 'missing')}")
    print(f"New Score: {(result.new_score or {}).get('total_score', 'missing')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
