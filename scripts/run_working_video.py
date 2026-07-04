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
from app.video_generator.errors import VideoGeneratorError
from app.workflows.working_video_generator import WorkingVideoGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the prepared working video path.")
    parser.add_argument("--selected-variant-id", type=int, required=True)
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
    if not args.build_prompts_only and not args.real_run:
        print("Error: choose --build-prompts-only or --real-run.", file=sys.stderr)
        return 2

    init_db()
    try:
        with SessionLocal() as db:
            runner = WorkingVideoGenerator(db)
            if args.build_prompts_only:
                result = runner.run_prompt_only(args.selected_variant_id, provider=args.video_provider)
                print("\nContentEngine working video prompt-only")
                print("=" * 46)
                print(f"Selected Variant ID: {result.selected_variant_id}")
                print(f"Buyer Need: {result.buyer_need}")
                print(f"Selected Hook: {result.selected_hook}")
                print(f"Prompt Pack ID: {result.prompt_pack_id}")
                print(f"Generation Variant ID: {result.generation_variant_id}")
                print(f"Reference Readiness: {result.reference_readiness.get('status')}")
                print(f"Real Smoke Eligible: {result.real_smoke_eligible}")
            else:
                output = runner.run_real_smoke(
                    args.selected_variant_id,
                    provider=args.video_provider,
                    allow_real_spend=True,
                    max_scenes=args.max_scenes,
                )
                print("\nContentEngine working video real smoke")
                print("=" * 47)
                print(f"Selected Variant ID: {args.selected_variant_id}")
                print(f"Video Job ID: {output.video_job_id}")
                print("Provider Job IDs: " + (", ".join(output.provider_job_ids) if output.provider_job_ids else "none"))
                print(f"Status: {output.status}")
                print("Downloaded Outputs: " + (", ".join(output.local_output_paths) if output.local_output_paths else "none"))
                print(f"Final Video: {output.final_video_path or 'pending'}")
                print(f"Generation Report: {output.generation_report_path or 'not written'}")
                print(f"Quality Review ID: {output.quality_review_id or 'none'}")
                print("Manual review required.")
    except (DemandError, IntelligenceError, VideoGeneratorError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
