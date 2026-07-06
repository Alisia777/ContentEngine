from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.participant_portal import ParticipantPortalError, ParticipantService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create participant portal profile.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", default="creator")
    parser.add_argument("--email")
    parser.add_argument("--telegram-handle")
    parser.add_argument("--platforms", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            participant = ParticipantService(db).create(
                display_name=args.name,
                role=args.role,
                email=args.email,
                telegram_handle=args.telegram_handle,
                platforms=[item.strip() for item in args.platforms.split(",") if item.strip()],
            )
            payload = {"id": participant.id, "display_name": participant.display_name, "role": participant.role, "platforms": participant.platforms_json}
    except ParticipantPortalError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
