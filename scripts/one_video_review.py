from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.one_video_acceptance import OneVideoAcceptanceError, OneVideoAcceptanceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record human review for a one-video render result.")
    parser.add_argument("--result-id", type=int, required=True)
    parser.add_argument("--status", required=True, choices=["needs_human_review", "needs_regeneration", "approved", "rejected"])
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = OneVideoAcceptanceService(db).review(
                args.result_id,
                status=args.status,
                notes=args.notes or None,
            )
            output = OneVideoAcceptanceService.as_result_output(result)
    except OneVideoAcceptanceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine one-video human review")
    print("=" * 43)
    print(f"Result ID: {output.id}")
    print(f"Plan ID: {output.plan_id}")
    print(f"Video Job ID: {output.video_job_id or 'none'}")
    print(f"Output Acceptance ID: {output.output_acceptance_id or 'none'}")
    print(f"Human Review: {output.human_review_status}")
    print(f"Notes: {output.human_review_notes or 'none'}")
    print("Publishing remains blocked unless the review is explicitly approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
