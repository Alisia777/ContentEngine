from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_brief_contract import AIBriefContractError, BriefQualityChecker
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run quality checks for an AI production brief.")
    parser.add_argument("--ai-production-brief-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            check = BriefQualityChecker(db).check(args.ai_production_brief_id)
    except AIBriefContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print("\nContentEngine AI brief quality check")
    print("=" * 43)
    print(f"Brief Quality Check ID: {check.id}")
    print(f"Status: {check.status}")
    print(f"Score: {check.score}")
    print("Missing: " + (", ".join(check.missing_fields_json) if check.missing_fields_json else "none"))
    print("Risks: " + (", ".join(check.failure_risks_json) if check.failure_risks_json else "none"))
    return 0 if check.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
