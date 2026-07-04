from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a hook-driven VideoCreativeSpec.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            record = CreativeSpecBuilder(db).build_for_product(
                args.product_id,
                platform=args.platform,
                duration_seconds=args.duration,
            )
    except IntelligenceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative spec")
    print("=" * 34)
    print(f"Creative Spec ID: {record.id}")
    print(f"Product ID: {record.product_id}")
    print(f"Platform: {record.platform}")
    print(f"Duration: {record.duration_seconds}")
    print(f"Status: {record.status}")
    print(f"Selected Hook: {record.spec_json.get('hook_type')} / {record.spec_json.get('hook_text')}")
    print(f"First Frame: {record.spec_json.get('first_frame_spec', {}).get('text_overlay')}")
    print(f"Scenes: {len(record.spec_json.get('scene_plan', []))}")
    if record.warnings_json:
        print(f"Warnings: {', '.join(record.warnings_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
