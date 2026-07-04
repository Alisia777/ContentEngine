from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.publishing import PublishingDestinationService
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register an owned publishing destination.")
    parser.add_argument("--brand", default="Altea")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--handle")
    parser.add_argument("--url")
    parser.add_argument("--owner-name")
    parser.add_argument("--posting-mode", default="manual", choices=["manual", "api", "disabled"])
    parser.add_argument("--daily-limit", type=int, default=1)
    parser.add_argument("--weekly-limit", type=int, default=3)
    parser.add_argument("--notes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            destination = PublishingDestinationService(db).create(
                brand=args.brand,
                platform=args.platform,
                name=args.name,
                handle=args.handle,
                url=args.url,
                owner_name=args.owner_name,
                posting_mode=args.posting_mode,
                daily_limit=args.daily_limit,
                weekly_limit=args.weekly_limit,
                notes=args.notes,
            )
            print("\nContentEngine publishing destination")
            print("=" * 44)
            print(f"Destination ID: {destination.id}")
            print(f"Brand: {destination.brand}")
            print(f"Platform: {destination.platform}")
            print(f"Name: {destination.name}")
            print(f"Posting Mode: {destination.posting_mode}")
            print(f"Auth Status: {destination.auth_status}")
            print(f"Status: {destination.status}")
    except PublishingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
