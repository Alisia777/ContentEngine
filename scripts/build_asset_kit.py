from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.errors import AssetKitError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product asset kit from Product.images_json.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--override-required-assets", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(
                args.product_id,
                override_required_assets=args.override_required_assets,
            )
            summary = {
                "id": kit.id,
                "product_id": kit.product_id,
                "status": kit.status,
                "asset_count": len(kit.assets_json),
                "missing_assets": kit.missing_assets_json,
                "warnings": kit.warnings_json,
                "real_generation_allowed": kit.real_generation_allowed,
            }
    except AssetKitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine product asset kit")
    print("=" * 35)
    print(f"Asset Kit ID: {summary['id']}")
    print(f"Product ID: {summary['product_id']}")
    print(f"Status: {summary['status']}")
    print(f"Assets: {summary['asset_count']}")
    print(f"Real Provider Allowed: {summary['real_generation_allowed']}")
    print("Missing: " + (", ".join(summary["missing_assets"]) if summary["missing_assets"] else "none"))
    if summary["warnings"]:
        print("Warnings: " + ", ".join(summary["warnings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
