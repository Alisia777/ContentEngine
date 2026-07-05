from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_factory import ContentRunOrchestrator
from app.content_factory.errors import ContentFactoryError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild a content factory prompt pack without video provider calls.")
    parser.add_argument("--content-run-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).run_prompt_only(args.content_run_id)
    except ContentFactoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine content prompt-only")
    print("=" * 39)
    print(f"Content Run ID: {result.id}")
    print(f"Status: {result.status}")
    print(f"Selected Variant ID: {result.selected_variant_id}")
    print(f"Generation Variant ID: {result.generation_variant_id}")
    print(f"Prompt Pack ID: {result.prompt_pack_id}")
    print("Video Job: skipped by prompt-only mode")
    print("Next Actions: " + (", ".join(action.action for action in result.next_actions) if result.next_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
