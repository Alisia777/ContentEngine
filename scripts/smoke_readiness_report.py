from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.smoke_readiness import ReadinessReportService, SmokeReadinessError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print the latest one-video smoke readiness report.")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def print_human(payload: dict) -> None:
    report = payload["report"]
    print("\nContentEngine smoke readiness report")
    print("=" * 41)
    print(f"Run ID: {payload['id']}")
    print(f"Decision: {report['final_decision']}")
    print(f"Plan: {report.get('one_video_render_plan_id') or 'none'}")
    print(f"Prompt-only: {report['prompt_only_status']}")
    print(f"Generation mode: {report['generation_mode']}")
    print(f"Spend gate: {report['spend_gate_status']['allow_real_spend']}")
    print(f"Runway key configured: {report['runway_key_configured']} ({report['runway_key_value']})")
    print(f"Runway credits confirmed: {report['runway_credits_confirmed']}")
    print(f"EngineAudit score: {report.get('engine_audit_latest_score')}")
    print("Blockers: " + (", ".join(item["blocker_type"] for item in report["blockers"]) or "none"))


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            service = ReadinessReportService(db)
            run = service.get(args.run_id) if args.run_id else service.latest()
            if not run:
                print("No smoke readiness run found.", file=sys.stderr)
                return 2
            payload = service.output(run).model_dump(mode="json")
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
