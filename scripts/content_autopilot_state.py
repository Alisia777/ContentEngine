from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_autopilot import AutopilotQueueService
from app.content_autopilot.errors import ContentAutopilotError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect one SKU state for ContentEngine autopilot.")
    parser.add_argument("--product-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            state = AutopilotQueueService(db).state(args.product_id)
    except ContentAutopilotError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine Autopilot State")
    print("=" * 38)
    print(f"Product: #{state.product_id} / {state.sku}")
    print(f"Content Run ID: {state.content_run_id or 'none'}")
    print(f"Demand: {state.has_demand}")
    print(f"Creative Spec: {state.has_creative_spec}")
    print(f"Selected Variant: {state.has_selected_variant}")
    print(f"Prompt Pack: {state.has_prompt_pack}")
    print(f"Reference Readiness: {state.reference_readiness.get('status', 'unknown')}")
    print(f"Geometry Readiness: {state.geometry_readiness.get('status', 'unknown')}")
    print(f"Generation Report Exists: {state.generation_report_exists}")
    print(f"Video Review: {state.video_review_status or 'none'}")
    print(f"Publishing Readiness: {state.publishing_readiness.get('status', 'unknown')}")
    print(f"Performance: {state.performance_data_status} / {state.performance_strength}")
    print("Blockers: " + (", ".join(state.blockers) if state.blockers else "none"))
    print("Available Actions: " + (", ".join(state.available_actions) if state.available_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
