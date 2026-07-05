from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_factory import ContentStatsImporter
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import content factory performance statistics from CSV.")
    parser.add_argument("--csv", required=True, help="CSV file with content performance rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 2
    init_db()
    with SessionLocal() as db:
        result = ContentStatsImporter(db).import_csv_text(csv_path.read_text(encoding="utf-8-sig"))

    print("\nContentEngine content stats import")
    print("=" * 41)
    print(f"Imported: {result.imported_count}")
    print(f"Errors: {result.error_count}")
    for error in result.errors:
        print(f"- {error}")
    return 0 if result.error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
