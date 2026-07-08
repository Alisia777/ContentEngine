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
from app.video_generator.errors import VideoGeneratorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one-video prompt pack without calling a paid provider.")
    parser.add_argument("--plan-id", type=int, required=True)
    parser.add_argument("--video-provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            plan = OneVideoAcceptanceService(db).prompt_only(args.plan_id, provider=args.video_provider)
            output = BombbarOneVideoRenderPlanner.as_output(plan)
    except (OneVideoAcceptanceError, VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine one-video prompt-only")
    print("=" * 41)
    print(f"Plan ID: {output.id}")
    print(f"Selected Variant ID: {output.creative_variant_id}")
    print(f"Prompt Pack ID: {output.prompt_pack_id}")
    print(f"Generation Variant ID: {output.video_generation_variant_id}")
    print(f"Bite scene allowed: {output.product_scene_policy.bite_scene_allowed}")
    print(f"Negative prompt contains muesli/granola guards: {'muesli' in (output.negative_prompt or '') and 'granola' in (output.negative_prompt or '')}")
    if output.product_scene_policy.asset_audit:
        print(f"Asset audit decision: {output.product_scene_policy.asset_audit.decision}")
    if output.mvp_scorecard:
        print(f"MVP scorecard: {output.mvp_scorecard.total_score}/{output.mvp_scorecard.max_score} ({output.mvp_scorecard.verdict})")
    print("Video skipped. Provider not called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
