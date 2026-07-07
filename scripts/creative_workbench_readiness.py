from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_workbench import CreativeWorkbenchError, ReadinessService
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a creative workbench session readiness.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--provider", default="runway")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            readiness = ReadinessService(db).for_session(args.session_id, provider=args.provider)
    except CreativeWorkbenchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine creative workbench readiness")
    print("=" * 45)
    print(f"Product: #{readiness.product_id} / {readiness.sku}")
    print(f"Product Strategy Ready: {readiness.product_strategy_ready}")
    print(f"Offer Strategy Ready: {readiness.offer_strategy_ready}")
    print(f"Blogger Meaning Ready: {readiness.blogger_meaning_ready}")
    print(f"UGC Script Ready: {readiness.ugc_script_ready}")
    print(f"Creative Quality Passed: {readiness.creative_quality_passed}")
    print(f"Reference Policy Passed: {readiness.reference_policy_passed}")
    print(f"Prompt Pack Ready: {readiness.prompt_pack_ready}")
    print(f"Product Lock Mode: {readiness.product_lock_mode}")
    print(f"Real Smoke Allowed: {readiness.real_smoke_allowed}")
    print("Blockers: " + (", ".join(readiness.blockers) if readiness.blockers else "none"))
    print("Next Actions: " + (", ".join(readiness.next_actions) if readiness.next_actions else "none"))
    return 0 if readiness.real_smoke_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
