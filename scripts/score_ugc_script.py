from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_quality import CreativeQualityDataError, UGCQualityScorer
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a UGC script with the creative quality rubric.")
    parser.add_argument("--ugc-script-id", type=int, required=True)
    parser.add_argument("--prompt-pack-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            score = UGCQualityScorer(db).score_script(args.ugc_script_id, prompt_pack_id=args.prompt_pack_id)
    except CreativeQualityDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative quality score")
    print("=" * 39)
    print(f"Quality Score ID: {score.id}")
    print(f"UGC Script ID: {score.ugc_script_id}")
    print(f"Product: #{score.product_id} / {score.sku}")
    print(f"Status: {score.status}")
    print(f"Total Score: {score.total_score}/100")
    print("Reasons: " + (", ".join(score.reasons_json) if score.reasons_json else "none"))
    print("Required Fixes: " + (" | ".join(score.required_fixes_json) if score.required_fixes_json else "none"))
    return 0 if score.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
