from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.product_asset_contract import ProductAssetContractError, ProductAssetTierService, ReferenceRequirementService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the hard Product Asset Contract for one exact SKU/variant.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--purpose", default="final_ad")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            tier_service = ProductAssetTierService(db)
            tier = tier_service.output(tier_service.evaluate(args.product_id))
            requirement_service = ReferenceRequirementService(db)
            requirement = requirement_service.output(
                requirement_service.evaluate(tier, purpose=args.purpose),
                permission=tier.permissions.model_dump(mode="json"),
            )
            payload = {
                "product_id": tier.product_id,
                "sku": tier.sku,
                "variant_key": tier.variant_key,
                "product_profile": tier.product_profile,
                "current_tier": tier.current_tier,
                "required_tier": requirement.required_tier,
                "purpose": requirement.purpose,
                "status": requirement.status,
                "missing_assets": requirement.missing_asset_types,
                "variant_mismatch_asset_ids": tier.variant_mismatch_asset_ids,
                "allowed_scenes": tier.allowed_scenes,
                "blocked_scenes": tier.blocked_scenes,
                "permissions": tier.permissions.model_dump(mode="json"),
                "interaction_mode": tier.permissions.interaction_mode,
                "interaction_scene_allowed": tier.permissions.interaction_scene_allowed,
                "human_review_required": True,
            }
    except ProductAssetContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("\nContentEngine Product Asset Contract")
    print("=" * 39)
    print(f"Product: {payload['product_id']} / {payload['sku']}")
    print(f"Variant: {payload['variant_key'] or 'product-id boundary'}")
    print(f"Profile: {payload['product_profile']}")
    print(f"Interaction: {payload['interaction_mode']} ({'allowed' if payload['interaction_scene_allowed'] else 'blocked'})")
    print(f"Current Tier: {payload['current_tier']}")
    print(f"Required Tier: {payload['required_tier']} ({payload['purpose']})")
    print(f"Status: {payload['status']}")
    print("Missing Assets: " + (", ".join(payload["missing_assets"]) if payload["missing_assets"] else "none"))
    print("Variant Mismatch Assets: " + (", ".join(map(str, payload["variant_mismatch_asset_ids"])) if payload["variant_mismatch_asset_ids"] else "none"))
    print("Allowed Scenes: " + (", ".join(payload["allowed_scenes"]) if payload["allowed_scenes"] else "none"))
    print("Blocked Scenes: " + (", ".join(payload["blocked_scenes"]) if payload["blocked_scenes"] else "none"))
    print("Human Review Required: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
