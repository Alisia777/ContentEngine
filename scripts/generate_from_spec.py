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
from app.video_generator.generator import VideoGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate provider prompts or video from a VideoCreativeSpec.")
    parser.add_argument("--creative-spec-id", type=int, required=True)
    parser.add_argument("--video-provider", default=None, help="mock, runway, or gemini. Defaults to QVF_VIDEO_PROVIDER/mock.")
    parser.add_argument("--build-prompts-only", action="store_true")
    parser.add_argument("--real-run", action="store_true")
    parser.add_argument("--max-scenes", type=int, default=None)
    parser.add_argument("--full-video", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.build_prompts_only and args.real_run:
        print("Error: choose either --build-prompts-only or --real-run, not both.", file=sys.stderr)
        return 2
    if args.full_video and not args.real_run:
        print("Error: --full-video requires --real-run.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            generator = VideoGenerator(db)
            variant = generator.build_prompt_pack_from_spec(args.creative_spec_id, provider=args.video_provider)
            review = None
            if args.real_run:
                variant = generator.start_generation(
                    variant.id,
                    provider=args.video_provider,
                    confirm_real_spend=True,
                    max_scenes=args.max_scenes,
                    full_video=args.full_video,
                )
                generator.poll(variant.id)
                variant = generator.download(variant.id)
                variant = generator.assemble(variant.id)
                review = generator.score(variant.id)
            video_job = variant.video_job
            summary = {
                "generation_variant_id": variant.id,
                "prompt_pack_id": variant.prompt_pack_id,
                "provider": variant.provider,
                "status": variant.status,
                "video_job_id": video_job.id if video_job else None,
                "provider_job_ids": [clip.provider_job_id or "pending" for clip in video_job.clips] if video_job else [],
                "local_output_paths": list(variant.local_output_paths_json or []),
                "final_video_path": variant.final_video_path,
                "quality_score": review.score if review else None,
            }
    except (VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine spec-driven video generator")
    print("=" * 44)
    print(f"Creative Spec ID: {args.creative_spec_id}")
    print(f"Generation Variant ID: {summary['generation_variant_id']}")
    print(f"Prompt Pack ID: {summary['prompt_pack_id']}")
    print(f"Provider: {summary['provider']}")
    print(f"Status: {summary['status']}")
    if summary["video_job_id"]:
        print(f"Video Job ID: {summary['video_job_id']}")
        print("Provider Job IDs: " + ", ".join(summary["provider_job_ids"]))
    if summary["local_output_paths"]:
        for path in summary["local_output_paths"]:
            print(f"Downloaded Output: {path}")
    if summary["final_video_path"]:
        print(f"Final Video: {summary['final_video_path']}")
    if summary["quality_score"] is not None:
        print(f"Quality Score: {summary['quality_score']}")
    if not args.real_run:
        print("Video Job: skipped by prompt-only mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
