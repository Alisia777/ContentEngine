from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.participant_portal import OnboardingService, ParticipantPortalError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Link participant to owned destination.")
    parser.add_argument("--participant-id", type=int, required=True)
    parser.add_argument("--destination-id", type=int, required=True)
    parser.add_argument("--relationship", default="creator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            link = OnboardingService(db).link_destination(args.participant_id, args.destination_id, relationship_type=args.relationship)
            payload = {"id": link.id, "participant_id": link.participant_id, "destination_id": link.destination_id, "relationship_type": link.relationship_type, "status": link.status}
    except ParticipantPortalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
