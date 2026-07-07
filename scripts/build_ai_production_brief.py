from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_brief_contract import AIBriefContractError, AIProductionBriefBuilder
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AI production brief contract.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--ugc-script-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            brief = AIProductionBriefBuilder(db).build(args.product_id, platform=args.platform, ugc_script_id=args.ugc_script_id)
    except AIBriefContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print("\nContentEngine AI production brief")
    print("=" * 41)
    print(f"AI Production Brief ID: {brief.id}")
    print(f"Product: #{brief.product_id} / {brief.sku}")
    print(f"Status: {brief.status}")
    print(f"Thesis: {brief.one_sentence_thesis}")
    print(f"Viewer Takeaway: {brief.viewer_takeaway}")
    print(f"Product Lock Mode: {brief.product_lock_mode}")
    print(f"CTA: {brief.cta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
