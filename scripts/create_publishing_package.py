from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.publishing import PublishingPackageService
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a publishing package from a local video artifact.")
    parser.add_argument("--video-job-id", type=int, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--hashtag", action="append", dest="hashtags")
    parser.add_argument("--cta")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            package = PublishingPackageService(db).create_from_video(
                video_job_id=args.video_job_id,
                platform=args.platform,
                title=args.title,
                description=args.description,
                hashtags=args.hashtags,
                cta=args.cta,
            )
            print("\nContentEngine publishing package")
            print("=" * 42)
            print(f"Package ID: {package.id}")
            print(f"Video Job ID: {package.video_job_id}")
            print(f"Platform: {package.target_platform}")
            print(f"Status: {package.status}")
            print(f"Review Status: {package.review_status}")
            print(f"Video File: {package.video_file_path}")
    except PublishingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
