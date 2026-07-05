from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.video_generator.errors import VideoGeneratorError
from app.video_generator.regeneration_requests import ALLOWED_REGENERATION_REASONS, RegenerationRequestService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request a prompt-only scene regeneration from human feedback.")
    parser.add_argument("--video-job-id", type=int, required=True)
    parser.add_argument("--scene-number", type=int, required=True)
    parser.add_argument("--reason", required=True, choices=sorted(ALLOWED_REGENERATION_REASONS))
    parser.add_argument("--feedback", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            request = RegenerationRequestService(db).create(
                video_job_id=args.video_job_id,
                scene_number=args.scene_number,
                reason=args.reason,
                feedback=args.feedback,
            )
            summary = {
                "id": request.id,
                "video_job_id": request.video_job_id,
                "generation_variant_id": request.video_generation_variant_id,
                "scene_number": request.scene_number,
                "reason": request.reason,
                "status": request.status,
            }
    except VideoGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine regeneration request")
    print("=" * 36)
    print(f"Regeneration Request ID: {summary['id']}")
    print(f"Video Job ID: {summary['video_job_id']}")
    print(f"Generation Variant ID: {summary['generation_variant_id']}")
    print(f"Scene Number: {summary['scene_number']}")
    print(f"Reason: {summary['reason']}")
    print(f"Status: {summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
