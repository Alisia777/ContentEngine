from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets.asset_storage import ProductAssetStorage
from app.assets.errors import AssetKitError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach a local or URL product reference asset.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--url", default=None)
    parser.add_argument("--asset-type", default="packshot")
    parser.add_argument("--manual-label", default=None)
    parser.add_argument("--primary", action="store_true")
    parser.add_argument("--review-status", default="approved")
    parser.add_argument("--variant-key", default=None, help="Exact product flavor/color/model variant for identity isolation.")
    parser.add_argument("--contract-type", default=None, help="Explicit Product Asset Contract type, for example cutaway_product.")
    parser.add_argument("--shared-non-identity", action="store_true", help="Mark style/lifestyle reference as reusable across variants.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if bool(args.file) == bool(args.url):
        print("Error: pass exactly one of --file or --url.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            if args.file:
                asset = storage.upload_file(
                    args.product_id,
                    filename=args.file.name,
                    content=args.file.read_bytes(),
                    asset_type=args.asset_type,
                    manual_label=args.manual_label,
                    is_primary_reference=args.primary,
                )
            else:
                asset = storage.attach_url(
                    args.product_id,
                    url=args.url,
                    asset_type=args.asset_type,
                    manual_label=args.manual_label,
                    is_primary_reference=args.primary,
                )
            asset = storage.update_asset(
                asset.id,
                review_status=args.review_status,
                is_primary_reference=args.primary,
                asset_type=args.asset_type,
                manual_label=args.manual_label,
                variant_key=args.variant_key,
                contract_type=args.contract_type,
                shared_non_identity=args.shared_non_identity,
            )
            summary = {
                "id": asset.id,
                "product_id": asset.product_id,
                "source_type": asset.source_type,
                "source_ref": asset.source_ref,
                "asset_type": asset.asset_type,
                "primary": asset.is_primary_reference,
                "review_status": asset.review_status,
                "checksum": asset.checksum,
                "variant_key": (asset.metadata_json or {}).get("variant_key"),
                "contract_type": (asset.metadata_json or {}).get("contract_type"),
            }
    except (AssetKitError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine product asset")
    print("=" * 31)
    print(f"Asset ID: {summary['id']}")
    print(f"Product ID: {summary['product_id']}")
    print(f"Source: {summary['source_type']} / {summary['source_ref']}")
    print(f"Asset Type: {summary['asset_type']}")
    print(f"Primary Reference: {summary['primary']}")
    print(f"Review Status: {summary['review_status']}")
    print(f"Variant Key: {summary['variant_key'] or 'unverified'}")
    print(f"Contract Type: {summary['contract_type'] or 'auto'}")
    if summary["checksum"]:
        print(f"Checksum: {summary['checksum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
