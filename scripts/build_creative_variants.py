from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.errors import VariantError
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build, score, and select creative variants from a creative spec.")
    parser.add_argument("--creative-spec-id", type=int, required=True)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--asset-kit-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            variant_set = CreativeVariantBuilder(db).build_set(
                args.creative_spec_id,
                count=args.count,
                asset_kit_id=args.asset_kit_id,
            )
            VariantScorer(db).score_set(variant_set.id)
            variant_set = VariantSelector(db).select_best(variant_set.id)
            variants = [
                {
                    "id": variant.id,
                    "number": variant.variant_number,
                    "status": variant.status,
                    "score": (variant.score_json or {}).get("score"),
                }
                for variant in sorted(variant_set.variants, key=lambda item: item.variant_number)
            ]
            summary = {
                "id": variant_set.id,
                "status": variant_set.status,
                "selected_variant_id": variant_set.selected_variant_id,
                "selection_reason": variant_set.selection_reason,
                "variants": variants,
            }
    except VariantError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative variants")
    print("=" * 36)
    print(f"Variant Set ID: {summary['id']}")
    print(f"Status: {summary['status']}")
    print(f"Selected Variant ID: {summary['selected_variant_id'] or 'needs review'}")
    print(f"Selection: {summary['selection_reason'] or 'none'}")
    for variant in summary["variants"]:
        print(f"Variant #{variant['number']} / id {variant['id']} / {variant['status']} / score {variant['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
