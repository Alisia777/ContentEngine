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
    parser = argparse.ArgumentParser(description="Create a human-review regeneration request for a video scene.")
    parser.add_argument("--video-job-id", type=int, required=True)
    parser.add_argument("--scene-number", type=int, default=1)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--feedback", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            request = VideoRegenerationService(db).request(
                video_job_id=args.video_job_id,
                scene_number=args.scene_number,
                reason=args.reason,
                human_feedback=args.feedback,
            )
            print("\nContentEngine regeneration request")
            print("=" * 42)
            print(f"Regeneration Request ID: {request.id}")
            print(f"Video Job ID: {request.video_job_id}")
            print(f"Creative Variant ID: {request.creative_variant_id or 'none'}")
            print(f"Scene Number: {request.scene_number}")
            print(f"Reason: {request.reason}")
            print(f"Status: {request.status}")
            print("Identity Flags: " + ", ".join(request.identity_corrections_json.get("identity_mismatch_flags", [])))
    except (VideoGeneratorError, IntelligenceError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
