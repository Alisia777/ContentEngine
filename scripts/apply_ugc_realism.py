from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError, ProviderConfigurationError
from app.ugc.realism_service import UGCRealismService
from app.video_generator.errors import VideoGeneratorError
from app.workflows.working_video_generator import WorkingVideoGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply realistic UGC constraints to a selected variant.")
    parser.add_argument("--selected-variant-id", type=int, required=True)
    parser.add_argument("--duration-seconds", type=int, default=8)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--video-provider", default="runway")
    parser.add_argument("--build-prompts-only", action="store_true")
    parser.add_argument("--real-run", action="store_true")
    parser.add_argument("--max-scenes", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.build_prompts_only and args.real_run:
        print("Error: choose either --build-prompts-only or --real-run, not both.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            variant = UGCRealismService(db).apply_to_variant(
                args.selected_variant_id,
                duration_seconds=args.duration_seconds,
                platform=args.platform,
            )
            print("\nContentEngine UGC realism contract")
            print("=" * 42)
            print(f"Selected Variant ID: {variant.id}")
            print(f"Creative Spec ID: {variant.creative_spec_id}")
            print(f"Duration: {args.duration_seconds}s")
            print(f"Hook: {variant.hook_text}")
            print("Presenter: sporty female, 25-30")
            print("Continuity: one smooth take")
            print("Guards: no wrapper bite, no generated text, edible piece only")
            if args.build_prompts_only:
                result = WorkingVideoGenerator(db).run_prompt_only(variant.id, provider=args.video_provider)
                print(f"Prompt Pack ID: {result.prompt_pack_id}")
                print(f"Generation Variant ID: {result.generation_variant_id}")
                print(f"Reference Readiness: {result.reference_readiness.get('status')}")
                print(f"Real Smoke Eligible: {result.real_smoke_eligible}")
                print("Real Smoke Blockers: " + (", ".join(result.real_smoke_blockers) if result.real_smoke_blockers else "none"))
            elif args.real_run:
                output = WorkingVideoGenerator(db).run_real_smoke(
                    variant.id,
                    provider=args.video_provider,
                    allow_real_spend=True,
                    max_scenes=args.max_scenes,
                )
                print(f"Video Job ID: {output.video_job_id}")
                print("Provider Job IDs: " + (", ".join(output.provider_job_ids) if output.provider_job_ids else "none"))
                print(f"Status: {output.status}")
                print("Downloaded Outputs: " + (", ".join(output.local_output_paths) if output.local_output_paths else "none"))
                print(f"Final Video: {output.final_video_path or 'pending'}")
                print(f"Generation Report: {output.generation_report_path or 'not written'}")
                print(f"Quality Review ID: {output.quality_review_id or 'none'}")
                print("Manual review required.")
            else:
                print("Video Job: skipped. Add --build-prompts-only or --real-run.")
    except (ProviderConfigurationError, VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
