from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import ProviderConfigurationError
from app.runway_recipes import ProductUGCRecipeRunner, RunwayRecipeError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one official Runway Product UGC recipe draft.")
    parser.add_argument("--draft-id", type=int, required=True)
    parser.add_argument("--real-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ProductUGCRecipeRunner(db).run(args.draft_id, real_run=args.real_run)
    except (ProviderConfigurationError, RunwayRecipeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine · Runway Product UGC Recipe")
    print("=" * 44)
    print(f"Draft ID: {result.draft_id}")
    print(f"Provider Task ID: {result.provider_task_id}")
    print(f"Provider Status: {result.provider_status}")
    print("Outputs: " + (", ".join(result.local_output_paths) if result.local_output_paths else "none"))
    print(f"Generation Report: {result.generation_report_path or 'none'}")
    print(f"Human Review: {result.human_review_status}")
    print(f"Publishing: {result.publishing_readiness}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
