from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models
from app.database import SessionLocal, init_db
from app.publishing import PublishingPackageService
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approve a publishing package for scheduling.")
    parser.add_argument("--package-id", type=int, required=True)
    parser.add_argument("--reviewer-name", default="operator")
    parser.add_argument("--manual-override", action="store_true")
    parser.add_argument("--notes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            package = db.get(models.PublishingPackage, args.package_id)
            if not package:
                raise PublishingError("Publishing package not found.")
            package = PublishingPackageService(db).approve(
                package,
                reviewer_name=args.reviewer_name,
                manual_override=args.manual_override,
                notes=args.notes,
            )
            print("\nContentEngine package approval")
            print("=" * 38)
            print(f"Package ID: {package.id}")
            print(f"Status: {package.status}")
            print(f"Review Status: {package.review_status}")
            print(f"Manual Override: {args.manual_override}")
    except PublishingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
