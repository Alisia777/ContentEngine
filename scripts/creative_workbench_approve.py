from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_workbench import CreativeWorkbenchError, WorkbenchService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approve a creative workbench session for limited real smoke.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            approval = WorkbenchService(db).approve_for_smoke(
                args.session_id,
                reviewer_name=args.reviewer,
                notes=args.notes,
            )
    except CreativeWorkbenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative workbench approval")
    print("=" * 44)
    print(f"Session ID: {approval.session_id}")
    print(f"Approval ID: {approval.approval_id}")
    print(f"Reviewer: {approval.reviewer_name}")
    print(f"Status: {approval.status}")
    print(f"Approved At: {approval.approved_at or 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
