from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.blogger_brief import MeaningSpecBuilder
from app.blogger_brief.errors import BloggerBriefError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a blogger/UGC meaning spec for a product.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration-seconds", type=int, default=8)
    parser.add_argument("--demand-hypothesis-id", type=int, default=None)
    parser.add_argument("--creative-spec-id", type=int, default=None)
    parser.add_argument("--provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            spec = MeaningSpecBuilder(db).build(
                args.product_id,
                platform=args.platform,
                duration_seconds=args.duration_seconds,
                demand_hypothesis_id=args.demand_hypothesis_id,
                creative_spec_id=args.creative_spec_id,
                provider=args.provider,
            )
    except BloggerBriefError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine blogger meaning spec")
    print("=" * 39)
    print(f"Blogger Meaning Spec ID: {spec.id}")
    print(f"Product ID: {spec.product_id}")
    print(f"SKU: {spec.sku}")
    print(f"Persona: {spec.creator_persona_json.get('persona')}")
    print(f"Buyer Situation: {spec.buyer_context_json.get('buyer_situation')}")
    print(f"Proof Moment: {spec.proof_moment_json.get('proof_line')}")
    print(f"Product Lock Mode: {spec.product_lock_rules_json.get('product_lock_mode')}")
    print("Warnings: " + (", ".join(spec.warnings_json) if spec.warnings_json else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
