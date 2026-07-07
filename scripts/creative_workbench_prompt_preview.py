from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_workbench import CreativeWorkbenchError, PromptPreviewService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show provider prompt preview for a workbench session.")
    parser.add_argument("--session-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            preview = PromptPreviewService(db).preview(args.session_id)
    except CreativeWorkbenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative workbench prompt preview")
    print("=" * 50)
    print(f"Session ID: {preview.session_id}")
    print(f"Prompt Pack ID: {preview.prompt_pack_id or 'missing'}")
    print(f"Product Lock Mode: {preview.product_lock_mode or 'missing'}")
    print(f"Reference Count: {preview.reference_count}")
    print(f"Negative Prompt: {preview.negative_prompt or 'missing'}")
    for scene in preview.scenes:
        print("-" * 50)
        print(f"Scene {scene.scene_number} / {scene.scene_role or 'unknown'}")
        print(f"Line: {scene.spoken_line or 'missing'}")
        print(f"Caption: {scene.caption or 'missing'}")
        print(f"Prompt: {scene.scene_prompt or 'missing'}")
    return 0 if preview.scenes else 1


if __name__ == "__main__":
    raise SystemExit(main())
