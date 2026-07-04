from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.publishing import PublishingDestinationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk import owned publishing destinations from CSV.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--default-brand", default="Altea")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    text = Path(args.file).read_text(encoding="utf-8-sig")
    with SessionLocal() as db:
        result = PublishingDestinationService(db).import_csv_text(text, default_brand=args.default_brand)
    print("\nContentEngine destination import")
    print("=" * 40)
    print(f"Created: {result['created_count']}")
    print(f"Errors: {result['error_count']}")
    print("Destination IDs: " + (", ".join(str(item) for item in result["destination_ids"]) or "none"))
    for error in result["errors"]:
        print(f"Row {error['row']}: {error['error']}", file=sys.stderr)
    return 2 if result["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
