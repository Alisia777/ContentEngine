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
from app.video_generator.regeneration import VideoRegenerationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or run a scene regeneration from human feedback.")
    parser.add_argument("--regeneration-request-id", type=int, required=True)
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
            service = VideoRegenerationService(db)
            if args.build_prompts_only:
                request = service.build_prompt_pack(args.regeneration_request_id, provider=args.video_provider)
            else:
                request = service.run_real(
                    args.regeneration_request_id,
                    provider=args.video_provider,
                    explicit_real_run=True,
                    max_scenes=args.max_scenes,
                )
            print("\nContentEngine scene regeneration")
            print("=" * 36)
            print(f"Regeneration Request ID: {request.id}")
            print(f"Video Job ID: {request.video_job_id}")
            print(f"New Prompt Pack ID: {request.new_prompt_pack_id or 'not built'}")
            print(f"New Video Job ID: {request.new_video_job_id or 'not run'}")
            print(f"Status: {request.status}")
            print("Human review is still required before approval.")
    except (VideoGeneratorError, IntelligenceError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
