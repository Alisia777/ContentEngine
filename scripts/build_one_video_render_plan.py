from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.one_video_acceptance import BombbarOneVideoRenderPlanner, OneVideoAcceptanceError, OneVideoAcceptanceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one product-safe Bombbar render plan.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration-seconds", type=int, default=15)
    parser.add_argument("--video-provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            plan = OneVideoAcceptanceService(db).build_plan(
                args.product_id,
                platform=args.platform,
                duration_seconds=args.duration_seconds,
                provider=args.video_provider,
            )
            output = BombbarOneVideoRenderPlanner.as_output(plan)
    except (OneVideoAcceptanceError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine one-video render plan")
    print("=" * 42)
    print(f"Plan ID: {output.id}")
    print(f"Product ID: {output.product_id}")
    print(f"SKU: {output.sku}")
    print(f"Selected Variant ID: {output.creative_variant_id}")
    print(f"AI Production Brief ID: {output.ai_production_brief_id}")
    print(f"Director Prompt Pack ID: {output.director_prompt_pack_id}")
    print(f"Wrapper refs: {output.product_scene_policy.wrapper_reference_count}")
    print(f"Edible refs: {output.product_scene_policy.edible_reference_count}")
    print(f"Bite scene allowed: {output.product_scene_policy.bite_scene_allowed}")
    print(f"Packshot overlay required: {output.product_scene_policy.packshot_overlay_required}")
    print("Blocked scenes: " + (", ".join(output.product_scene_policy.blocked_scene_types) or "none"))
    print("Blockers: " + (", ".join(output.blockers) or "none"))
    print("Next actions: " + (", ".join(output.product_scene_policy.next_actions) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
