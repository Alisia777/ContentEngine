from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.participant_portal import (
    AssignmentPortalService,
    OnboardingService,
    ParticipantMetricsService,
    ParticipantPortalError,
    ParticipantService,
    PayoutService,
    RecommendationService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show participant dashboard.")
    parser.add_argument("--participant-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            participant = ParticipantService(db).get(args.participant_id)
            payouts = PayoutService(db).summary(args.participant_id)
            payload = {
                "participant": {"id": participant.id, "display_name": participant.display_name, "role": participant.role},
                "setup_steps": OnboardingService(db).setup_steps(args.participant_id),
                "destinations": [
                    {"destination_id": link.destination_id, "platform": link.destination.platform, "handle": link.destination.handle}
                    for link in OnboardingService(db).destinations(args.participant_id)
                ],
                "assignments": [
                    {"id": item.id, "status": item.status, "sku": item.sku, "assignment_type": item.assignment_type}
                    for item in AssignmentPortalService(db).list_assignments(args.participant_id)
                ],
                "stats": ParticipantMetricsService(db).dashboard_stats(args.participant_id),
                "payouts": {"total": payouts["total"], "totals": payouts["totals"]},
                "recommendations": RecommendationService(db).recommendations(args.participant_id),
            }
    except ParticipantPortalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
