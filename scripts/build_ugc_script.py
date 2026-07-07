from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.blogger_brief import UGCAdScriptBuilder
from app.blogger_brief.errors import BloggerBriefError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a UGC ad script from a blogger meaning spec.")
    parser.add_argument("--blogger-meaning-spec-id", type=int, required=True)
    parser.add_argument("--creative-variant-id", type=int, default=None)
    parser.add_argument("--duration-seconds", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            script = UGCAdScriptBuilder(db).build(
                args.blogger_meaning_spec_id,
                creative_variant_id=args.creative_variant_id,
                duration_seconds=args.duration_seconds,
            )
    except BloggerBriefError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine UGC ad script")
    print("=" * 31)
    print(f"UGC Script ID: {script.id}")
    print(f"Blogger Meaning Spec ID: {script.blogger_meaning_spec_id}")
    print(f"Creative Variant ID: {script.creative_variant_id or 'none'}")
    print(f"Status: {script.status}")
    print(f"Duration: {script.duration_seconds}s")
    print("Scene Roles: " + ", ".join(scene.get("role", "") for scene in script.scene_script_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
