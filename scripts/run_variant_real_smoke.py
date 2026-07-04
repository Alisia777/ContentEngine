from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.video_generator.errors import VideoGeneratorError
from app.video_generator.real_smoke_runner import RealSmokeRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a spend-gated one-scene Runway smoke from a selected CreativeVariant.")
    parser.add_argument("--creative-variant-id", type=int, required=True)
    parser.add_argument("--video-provider", default="runway", help="Only runway is supported for Sprint 07 real smoke.")
    parser.add_argument("--real-run", action="store_true", help="Explicitly request a real provider run.")
    parser.add_argument("--max-scenes", type=int, default=1, help="Defaults to one scene.")
    parser.add_argument("--full-video", action="store_true", help="Explicitly allow full-video generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.real_run:
        print("Error: real smoke requires --real-run.", file=sys.stderr)
        return 2

    init_db()
    try:
        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(
                args.creative_variant_id,
                provider=args.video_provider,
                max_scenes=args.max_scenes,
                full_video=args.full_video,
                allow_real_spend=True,
            )
    except (VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine selected-variant real smoke")
    print("=" * 45)
    print(f"Product: #{output.product_id} / {output.sku}")
    print(f"Creative Spec ID: {output.creative_spec_id}")
    print(f"Creative Variant ID: {output.creative_variant_id}")
    print(f"Prompt Pack ID: {output.prompt_pack_id}")
    print(f"Reference Bundle ID: {output.reference_bundle_id or 'none'}")
    print(f"Video Job ID: {output.video_job_id}")
    print(f"Provider: {output.provider}")
    print("Provider Job IDs: " + (", ".join(output.provider_job_ids) if output.provider_job_ids else "none"))
    print(f"Provider Status: {output.status}")
    print("Downloaded Outputs: " + (", ".join(output.local_output_paths) if output.local_output_paths else "none"))
    print(f"Final Video: {output.final_video_path or 'pending'}")
    print(f"Generation Report: {output.generation_report_path or 'not written'}")
    print(f"Quality Review ID: {output.quality_review_id or 'none'}")
    print(f"Metadata Quality Score: {output.quality_score if output.quality_score is not None else 'pending'}")
    if output.warnings:
        print("Warnings: " + ", ".join(output.warnings))
    if output.errors:
        print("Errors: " + ", ".join(output.errors))
    print("Next: open the output video and generation report manually; status should remain Needs human review until approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
