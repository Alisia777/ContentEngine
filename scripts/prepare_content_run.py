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
    parser = argparse.ArgumentParser(description="Prepare an AI content factory run without paid provider calls.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--variant-count", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(
                args.product_id,
                args.platform,
                args.duration,
                args.variant_count,
            )
    except ContentFactoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine AI content run")
    print("=" * 36)
    print(f"Content Run ID: {result.id}")
    print(f"Product: #{result.product_id} / {result.sku}")
    print(f"Status: {result.status}")
    print(f"Demand Hypothesis ID: {result.demand_hypothesis_id}")
    print(f"Creative Spec ID: {result.creative_spec_id}")
    print(f"Selected Variant ID: {result.selected_variant_id}")
    print(f"Prompt Pack ID: {result.prompt_pack_id}")
    print(f"AI Review ID: {result.ai_review_id}")
    print("Blockers: " + (", ".join(result.blockers) if result.blockers else "none"))
    print("Next Actions: " + (", ".join(action.action for action in result.next_actions) if result.next_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
