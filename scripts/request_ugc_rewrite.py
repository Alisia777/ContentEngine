from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_quality import CreativeQualityDataError, ScriptRewriter
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a creative rewrite request for a low-scoring UGC script.")
    parser.add_argument("--quality-score-id", type=int, required=True)
    parser.add_argument("--feedback", default=None)
    parser.add_argument("--reason", default="quality_score_below_threshold")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            request = ScriptRewriter(db).create_request(args.quality_score_id, feedback=args.feedback, reason=args.reason)
    except CreativeQualityDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine UGC rewrite request")
    print("=" * 37)
    print(f"Rewrite Request ID: {request.id}")
    print(f"Quality Score ID: {request.creative_quality_score_id}")
    print(f"UGC Script ID: {request.ugc_script_id}")
    print(f"Status: {request.status}")
    print(f"Reason: {request.reason}")
    print("Required Fixes: " + (" | ".join(request.required_fixes_json) if request.required_fixes_json else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
