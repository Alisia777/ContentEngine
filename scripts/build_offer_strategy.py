from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.product_strategy import OfferStrategyBuilder, ProductStrategyDataError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offer strategy from a ProductStrategySpec.")
    parser.add_argument("--product-strategy-spec-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            offer = OfferStrategyBuilder(db).build(args.product_strategy_spec_id)
    except ProductStrategyDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine offer strategy")
    print("=" * 30)
    print(f"Offer Strategy ID: {offer.id}")
    print(f"Product Strategy Spec ID: {offer.product_strategy_spec_id}")
    print(f"Product: #{offer.product_id} / {offer.sku}")
    print(f"Status: {offer.status}")
    print(f"Offer Type: {offer.offer_type}")
    print(f"CTA Strategy: {offer.cta_strategy}")
    print(f"Stock Warning: {offer.stock_warning or 'none'}")
    print("Warnings: " + (", ".join(offer.warnings_json) if offer.warnings_json else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
