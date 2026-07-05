from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import LaunchPlanner
from app.bombar_launch.errors import BombarLaunchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Bombar launch campaign from an imported matrix.")
    parser.add_argument("--import-id", type=int, required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--brand", default="Bombar")
    parser.add_argument("--target-videos", type=int, default=350)
    parser.add_argument("--target-destinations", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = LaunchPlanner(db).create_campaign(
                args.import_id,
                name=args.name,
                brand=args.brand,
                target_video_count=args.target_videos,
                target_destination_count=args.target_destinations,
            )
    except BombarLaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Campaign ID: {result.campaign_id}")
    print(f"Name: {result.name}")
    print(f"Products: {len(result.product_ids)}")
    print(f"Targets: {result.target_video_count} videos / {result.target_destination_count} destinations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
