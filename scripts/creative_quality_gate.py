from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_quality import CreativeQualityDataError, CreativeQualityGateService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check creative quality gate before real smoke.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--ugc-script-id", type=int, default=None)
    parser.add_argument("--creative-variant-id", type=int, default=None)
    parser.add_argument("--prompt-pack-id", type=int, default=None)
    parser.add_argument("--provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            gate = CreativeQualityGateService(db).gate(
                args.product_id,
                ugc_script_id=args.ugc_script_id,
                creative_variant_id=args.creative_variant_id,
                prompt_pack_id=args.prompt_pack_id,
                provider=args.provider,
            )
    except CreativeQualityDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative quality gate")
    print("=" * 39)
    print(f"Product: #{gate.product_id} / {gate.sku}")
    print(f"UGC Script ID: {gate.ugc_script_id or 'none'}")
    print(f"Quality Score ID: {gate.quality_score_id or 'none'}")
    print(f"Status: {gate.status}")
    print(f"Real Smoke Allowed: {gate.real_smoke_allowed}")
    print(f"Next Action: {gate.next_action}")
    print("Blockers: " + (", ".join(gate.blockers) if gate.blockers else "none"))
    print("Warnings: " + (", ".join(gate.warnings) if gate.warnings else "none"))
    return 0 if gate.real_smoke_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
