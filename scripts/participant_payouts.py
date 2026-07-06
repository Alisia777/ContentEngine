from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.participant_portal import ParticipantPortalError, PayoutService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show participant payout ledger.")
    parser.add_argument("--participant-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            summary = PayoutService(db).summary(args.participant_id)
            payload = {
                "total": summary["total"],
                "totals": summary["totals"],
                "entries": [
                    {"id": entry.id, "amount": entry.amount, "currency": entry.currency, "status": entry.status, "reason": entry.reason}
                    for entry in summary["entries"]
                ],
            }
    except ParticipantPortalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
