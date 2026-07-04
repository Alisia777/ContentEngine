from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.demand.errors import DemandError
from app.intelligence.errors import IntelligenceError
from app.variants.errors import VariantError
from app.video_generator.errors import VideoGeneratorError
from app.workflows.working_video_generator import WorkingVideoGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare demand-driven selected video variant without paid provider calls.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--variant-count", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = WorkingVideoGenerator(db).prepare(
                args.product_id,
                args.platform,
                args.duration,
                args.variant_count,
            )
    except (DemandError, IntelligenceError, VariantError, VideoGeneratorError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine working video prepare")
    print("=" * 43)
    print(f"Product: #{result.product_id} / {result.sku}")
    print(f"Demand Hypothesis ID: {result.demand_hypothesis_id}")
    print(f"Buyer Need: {result.buyer_need}")
    print(f"Trigger: {result.trigger_situation}")
    print(f"Objection: {result.objection}")
    print(f"Safe Promise: {result.safe_promise}")
    print("Source Refs: " + (", ".join(result.source_refs) if result.source_refs else "none"))
    print("Missing Data: " + (", ".join(result.missing_data) if result.missing_data else "none"))
    print(f"Creative Spec ID: {result.creative_spec_id}")
    print(f"Selected Hook: {result.selected_hook}")
    print(f"Selected Variant ID: {result.selected_variant_id}")
    print(f"Prompt Pack ID: {result.prompt_pack_id}")
    print(f"Generation Variant ID: {result.generation_variant_id}")
    print(f"Reference Readiness: {result.reference_readiness.get('status')}")
    print(f"Real Smoke Eligible: {result.real_smoke_eligible}")
    print("Real Smoke Blockers: " + (", ".join(result.real_smoke_blockers) if result.real_smoke_blockers else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
