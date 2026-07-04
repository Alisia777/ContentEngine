from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.intelligence.generation_runner import GeneratorRunService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a real data-driven product video workflow.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--llm-provider", default=None, help="openai or mock. Defaults to QVF_LLM_PROVIDER/mock.")
    parser.add_argument("--video-provider", default=None, help="runway, gemini, or mock. Defaults to QVF_VIDEO_PROVIDER/mock.")
    parser.add_argument("--build-prompts-only", action="store_true", help="Build intelligence, brief, script, and prompt pack only.")
    parser.add_argument("--real-run", action="store_true", help="Start provider generation after explicit spend gates pass.")
    parser.add_argument("--max-scenes", type=int, default=None, help="Maximum scenes for this real run. Defaults to the env cap.")
    parser.add_argument("--full-video", action="store_true", help="Allow a full-video real run within configured env caps.")
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
            runner = GeneratorRunService(db)
            if args.real_run:
                artifacts = runner.run_real(
                    product_id=args.product_id,
                    llm_provider=args.llm_provider,
                    video_provider=args.video_provider,
                    confirm_real_spend=True,
                    max_scenes=args.max_scenes,
                    full_video=args.full_video,
                )
            else:
                artifacts = runner.build_prompt_pack_only(
                    product_id=args.product_id,
                    llm_provider=args.llm_provider,
                    video_provider=args.video_provider,
                )
    except IntelligenceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine real generator flow")
    print("=" * 38)
    print(f"Product ID: {args.product_id}")
    print(f"Creative Intelligence Pack ID: {artifacts.pack.id}")
    print(f"Script Brief ID: {artifacts.brief.id}")
    print(f"Script Job ID: {artifacts.script_job.id} ({artifacts.script_job.llm_provider})")
    print(f"Script Variant ID: {artifacts.variant.id}")
    print(f"Prompt Pack ID: {artifacts.prompt_pack.id} ({artifacts.prompt_pack.prompt_pack_json.get('provider')})")
    if artifacts.video_job:
        print(f"Video Job ID: {artifacts.video_job.id} ({artifacts.video_job.provider}) / {artifacts.video_job.status}")
        print(
            "Provider Job IDs: "
            + ", ".join(clip.provider_job_id or "pending" for clip in artifacts.video_job.clips)
        )
        for path in artifacts.local_output_paths or []:
            print(f"Downloaded Output: {path}")
        if artifacts.video_job.output_video_path:
            print(f"Final Video: {artifacts.video_job.output_video_path}")
        if artifacts.report_path:
            print(f"Generation Report: {artifacts.report_path}")
    else:
        print("Video Job: skipped by prompt-only mode")
    print(f"Objective: {artifacts.pack.pack_json.get('recommended_objective')}")
    print(f"Angles: {', '.join(artifacts.pack.pack_json.get('recommended_creative_angles', []))}")
    if artifacts.pack.pack_json.get("missing_data"):
        print(f"Missing data: {', '.join(artifacts.pack.pack_json['missing_data'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
