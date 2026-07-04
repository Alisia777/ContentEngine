from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.assets.errors import AssetKitError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check product reference readiness and build a provider bundle.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            bundle = ProviderReferenceBundleBuilder(db).build(args.product_id, provider=args.provider)
            summary = {
                "bundle_id": bundle.id,
                "status": bundle.status,
                "provider": bundle.provider,
                "primary": bundle.primary_image_asset_id,
                "references": bundle.reference_asset_ids_json,
                "blockers": bundle.blockers_json,
                "warnings": bundle.warnings_json,
            }
    except AssetKitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine product references")
    print("=" * 36)
    print(f"Reference Bundle ID: {summary['bundle_id']}")
    print(f"Provider: {summary['provider']}")
    print(f"Status: {summary['status']}")
    print(f"Primary Reference Asset ID: {summary['primary'] or 'none'}")
    print("Reference Asset IDs: " + (", ".join(str(item) for item in summary["references"]) if summary["references"] else "none"))
    print("Blockers: " + (", ".join(summary["blockers"]) if summary["blockers"] else "none"))
    print("Warnings: " + (", ".join(summary["warnings"]) if summary["warnings"] else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
