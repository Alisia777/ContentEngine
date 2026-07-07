from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.output_acceptance import OutputAcceptanceError, RegenerationFeedbackBuilder
from app.video_generator.errors import VideoGeneratorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create regeneration feedback from an output acceptance review.")
    parser.add_argument("--acceptance-id", type=int, required=True)
    parser.add_argument("--reason", default=None)
    parser.add_argument("--scene-number", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            request = RegenerationFeedbackBuilder(db).request(
                args.acceptance_id,
                reason=args.reason,
                scene_number=args.scene_number,
            )
    except (OutputAcceptanceError, VideoGeneratorError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine output regeneration request")
    print("=" * 45)
    print(f"Regeneration Request ID: {request.id}")
    print(f"Acceptance ID: {args.acceptance_id}")
    print(f"Video Job ID: {request.video_job_id}")
    print(f"Scene Number: {request.scene_number}")
    print(f"Reason: {request.reason}")
    print(f"Status: {request.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
