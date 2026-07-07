from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.output_acceptance import FrameExtractor, OutputAcceptanceError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract keyframes and contact sheet for video output acceptance.")
    parser.add_argument("--video-job-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = FrameExtractor(db).extract(args.video_job_id)
    except OutputAcceptanceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine output frame extraction")
    print("=" * 43)
    print(f"Frame Extraction ID: {result.id}")
    print(f"Video Job ID: {result.video_job_id}")
    print(f"Status: {result.status}")
    print(f"Frames: {len(result.frame_paths_json or [])}")
    print(f"Contact Sheet: {result.contact_sheet_path}")
    print("Warnings: " + (", ".join(result.warnings_json or []) if result.warnings_json else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
