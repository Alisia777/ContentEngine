from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.product_strategy import ProductStrategyBuilder, ProductStrategyDataError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product strategy spec for a SKU.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--demand-hypothesis-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            spec = ProductStrategyBuilder(db).build(
                args.product_id,
                platform=args.platform,
                demand_hypothesis_id=args.demand_hypothesis_id,
            )
    except ProductStrategyDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine product strategy spec")
    print("=" * 39)
    print(f"Product Strategy Spec ID: {spec.id}")
    print(f"Product: #{spec.product_id} / {spec.sku}")
    print(f"Status: {spec.status}")
    print(f"Buyer Situation: {(spec.buyer_situation_json or {}).get('situation')}")
    print(f"Main Objection: {spec.main_objection}")
    print(f"Offer Type: {(spec.offer_strategy_json or {}).get('offer_type')}")
    print(f"Platform: {(spec.platform_strategy_json or {}).get('primary_platform')}")
    print("Warnings: " + (", ".join(spec.warnings_json) if spec.warnings_json else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
