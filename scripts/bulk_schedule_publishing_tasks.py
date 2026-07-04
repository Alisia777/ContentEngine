from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.publishing import PublishingScheduler
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk schedule approved publishing packages across owned destinations.")
    parser.add_argument("--package-id", action="append", type=int, dest="package_ids")
    parser.add_argument("--package-ids", dest="package_ids_csv", help="Comma-separated package ids.")
    parser.add_argument("--destination-id", action="append", type=int, dest="destination_ids")
    parser.add_argument("--destination-ids", dest="destination_ids_csv", help="Comma-separated destination ids.")
    parser.add_argument("--start-at", required=True)
    parser.add_argument("--interval-minutes", type=int, default=60)
    parser.add_argument("--operator-name", default="operator")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_ids = (args.package_ids or []) + _parse_ids(args.package_ids_csv)
    destination_ids = (args.destination_ids or []) + _parse_ids(args.destination_ids_csv)
    init_db()
    try:
        with SessionLocal() as db:
            result = PublishingScheduler(db).bulk_schedule(
                package_ids=package_ids,
                destination_ids=destination_ids,
                start_at=datetime.fromisoformat(args.start_at),
                interval_minutes=args.interval_minutes,
                operator_name=args.operator_name,
                dry_run=args.dry_run,
            )
    except (PublishingError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print("\nContentEngine bulk publishing schedule")
    print("=" * 44)
    print(f"Dry Run: {result['dry_run']}")
    print(f"Planned: {result['planned_count']}")
    print(f"Created: {result['created_count']}")
    print(f"Errors: {result['error_count']}")
    print("Task IDs: " + (", ".join(str(item) for item in result["task_ids"]) or "none"))
    for error in result["errors"]:
        print(
            f"Package {error['package_id']} -> destination {error['destination_id']}: {error['error']}",
            file=sys.stderr,
        )
    return 2 if result["error_count"] else 0


def _parse_ids(value: str | None) -> list[int]:
    if not value:
        return []
    normalized = value.replace(";", ",").replace(" ", ",")
    return [int(item) for item in normalized.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
