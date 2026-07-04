from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models
from app.database import SessionLocal, init_db
from app.publishing import PublishingScheduler
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Schedule an approved publishing package to an owned destination.")
    parser.add_argument("--package-id", type=int, required=True)
    parser.add_argument("--destination-id", type=int, required=True)
    parser.add_argument("--scheduled-at", required=True)
    parser.add_argument("--operator-name", default="operator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            package = db.get(models.PublishingPackage, args.package_id)
            destination = db.get(models.PublishingDestination, args.destination_id)
            if not package:
                raise PublishingError("Publishing package not found.")
            if not destination:
                raise PublishingError("Publishing destination not found.")
            task = PublishingScheduler(db).schedule(
                package=package,
                destination=destination,
                scheduled_at=datetime.fromisoformat(args.scheduled_at),
                operator_name=args.operator_name,
            )
            print("\nContentEngine publishing task")
            print("=" * 39)
            print(f"Task ID: {task.id}")
            print(f"Package ID: {task.publishing_package_id}")
            print(f"Destination ID: {task.destination_id}")
            print(f"Status: {task.status}")
            print(f"Scheduled At: {task.scheduled_at}")
    except (PublishingError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
