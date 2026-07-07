from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_workbench import CreativeWorkbenchError, WorkbenchService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a creative quality workbench session.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--ugc-script-id", type=int, default=None)
    parser.add_argument("--prompt-pack-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            service = WorkbenchService(db)
            session = service.build(
                args.product_id,
                platform=args.platform,
                ugc_script_id=args.ugc_script_id,
                prompt_pack_id=args.prompt_pack_id,
            )
            output = service.as_output(session)
    except CreativeWorkbenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative quality workbench")
    print("=" * 43)
    print(f"Workbench Session ID: {output.id}")
    print(f"Product: #{output.product_id} / {output.sku}")
    print(f"Status: {output.status}")
    print(f"Product Strategy Spec ID: {output.product_strategy_spec_id or 'missing'}")
    print(f"Offer Strategy ID: {output.offer_strategy_id or 'missing'}")
    print(f"Blogger Meaning Spec ID: {output.blogger_meaning_spec_id or 'missing'}")
    print(f"UGC Script ID: {output.ugc_script_id or 'missing'}")
    print(f"Creative Quality Score ID: {output.creative_quality_score_id or 'missing'}")
    print(f"Prompt Pack ID: {output.prompt_pack_id or 'missing'}")
    print(f"Real Smoke Allowed: {output.real_smoke_readiness.real_smoke_allowed}")
    print("Blockers: " + (", ".join(output.blockers) if output.blockers else "none"))
    print("Next Actions: " + (", ".join(output.next_actions) if output.next_actions else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
