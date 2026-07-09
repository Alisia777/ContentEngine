from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.smoke_readiness import ReadinessReportService, RecoveryService, SmokeReadinessError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely rebuild/check one-video paid smoke readiness without provider calls.")
    parser.add_argument("--plan-id", type=int)
    parser.add_argument("--product-id", type=int)
    parser.add_argument("--sku")
    parser.add_argument("--platform", default="Instagram Reels")
    parser.add_argument("--video-provider", default="runway")
    parser.add_argument("--rebuild-plan", action="store_true")
    parser.add_argument("--seed-demo", action="store_true")
    parser.add_argument("--seed-demo-refs", action="store_true")
    parser.add_argument("--runway-credits-confirmed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def print_human(payload: dict) -> None:
    report = payload["report"]
    print("\nContentEngine smoke readiness recovery")
    print("=" * 45)
    print(f"Run ID: {payload['id']}")
    print(f"Decision: {report['final_decision']}")
    print(f"Product ID: {report.get('product_id') or 'none'}")
    print(f"SKU: {report.get('sku') or 'none'}")
    print(f"Requested plan exists: {report['requested_plan_exists']}")
    print(f"One-video plan ID: {report.get('one_video_render_plan_id') or 'none'}")
    print(f"Rebuilt plan ID: {report.get('rebuilt_plan_id') or 'none'}")
    print(f"Prompt Pack ID: {report.get('prompt_pack_id') or 'none'}")
    print(f"Prompt-only status: {report['prompt_only_status']}")
    print(f"Generation mode: {report['generation_mode']}")
    print(f"Spend gate: {report['spend_gate_status']['allow_real_spend']}")
    print(f"Runway key configured: {report['runway_key_configured']} ({report['runway_key_value']})")
    print(f"Runway credits confirmed: {report['runway_credits_confirmed']}")
    print(f"EngineAudit score: {report.get('engine_audit_latest_score')}")
    print(f"Control Room snapshot ID: {report.get('control_room_snapshot_id') or 'none'}")
    print("\nBlockers:")
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(f"- {blocker['blocker_type']} [{blocker['severity']}]: {blocker['message']}")
            print(f"  next: {blocker['recommended_action']}")
    else:
        print("- none recorded")
    print("\nNext actions:")
    for action in report["next_actions"] or ["No next action recorded."]:
        print(f"- {action}")
    print("\nVideo skipped. Provider not called.")


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            run = RecoveryService(db).recover(
                plan_id=args.plan_id,
                product_id=args.product_id,
                sku=args.sku,
                platform=args.platform,
                video_provider=args.video_provider,
                rebuild_plan=args.rebuild_plan,
                seed_demo=args.seed_demo,
                seed_demo_refs=args.seed_demo_refs,
                runway_credits_confirmed=args.runway_credits_confirmed,
            )
            payload = ReadinessReportService(db).output(run).model_dump(mode="json")
    except SmokeReadinessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
