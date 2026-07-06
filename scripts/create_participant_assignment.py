from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.participant_portal import AssignmentPortalService, ParticipantPortalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create participant assignment and brief card.")
    parser.add_argument("--participant-id", type=int, required=True)
    parser.add_argument("--assignment-type", default="create_video")
    parser.add_argument("--campaign-id", type=int)
    parser.add_argument("--product-id", type=int)
    parser.add_argument("--content-run-id", type=int)
    parser.add_argument("--creative-variant-id", type=int)
    parser.add_argument("--publishing-task-id", type=int)
    parser.add_argument("--payout-rule-id", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=args.participant_id,
                assignment_type=args.assignment_type,
                campaign_id=args.campaign_id,
                product_id=args.product_id,
                content_run_id=args.content_run_id,
                creative_variant_id=args.creative_variant_id,
                publishing_task_id=args.publishing_task_id,
                payout_rule_id=args.payout_rule_id,
            )
            payload = {"id": assignment.id, "participant_id": assignment.participant_id, "status": assignment.status, "brief": assignment.brief_json}
    except ParticipantPortalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
