from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_brief_contract import AIBriefContractError, SceneBlueprintBuilder
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build scene blueprint rows for an AI production brief.")
    parser.add_argument("--ai-production-brief-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            scenes = SceneBlueprintBuilder(db).build(args.ai_production_brief_id)
    except AIBriefContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print("\nContentEngine scene blueprint")
    print("=" * 35)
    print(f"AI Production Brief ID: {args.ai_production_brief_id}")
    print(f"Scene Count: {len(scenes)}")
    for scene in scenes:
        print(f"{scene.scene_order}. {scene.start_second:g}-{scene.end_second:g}s / {scene.scene_role} / {scene.product_visibility}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
