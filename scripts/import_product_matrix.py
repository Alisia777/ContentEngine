from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_autopilot import ProductMatrixImporter
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a campaign product matrix CSV.")
    parser.add_argument("--csv", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    with SessionLocal() as db:
        result = ProductMatrixImporter(db).import_path(args.csv)
    print(f"Import ID: {result.import_id}")
    print(f"Status: {result.status}")
    print(f"Imported count: {result.imported_count}")
    print(f"Warnings: {', '.join(result.warnings) if result.warnings else 'none'}")
    print(f"Errors: {', '.join(result.errors) if result.errors else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
