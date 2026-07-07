from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.blogger_brief import ProductReferencePolicyService
from app.blogger_brief.errors import BloggerBriefError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check strict product reference policy before mass UGC generation.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--provider", default="runway")
    parser.add_argument("--product-identity-strict", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            policy = ProductReferencePolicyService(db).check(
                args.product_id,
                provider=args.provider,
                product_identity_strict=args.product_identity_strict,
            )
    except BloggerBriefError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine product reference policy")
    print("=" * 44)
    print(f"Product ID: {policy.product_id}")
    print(f"SKU: {policy.sku}")
    print(f"Status: {policy.status}")
    print(f"Reference Count: {policy.approved_reference_count}/3")
    print(f"Product Lock Mode: {policy.product_lock_mode}")
    print(f"Strict Real Allowed: {policy.strict_real_generation_allowed}")
    print(f"Mass Safety: {policy.mass_generation_safety_status}")
    print("Missing Reference Types: " + (", ".join(policy.missing_reference_types) if policy.missing_reference_types else "none"))
    print("Blockers: " + (", ".join(policy.blockers) if policy.blockers else "none"))
    print("Next Actions: " + (", ".join(policy.next_actions) if policy.next_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
