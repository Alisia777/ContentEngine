from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import BombarMatrixImporter
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a Bombar product matrix from CSV or XLSX.")
    parser.add_argument("--file", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    with SessionLocal() as db:
        result = BombarMatrixImporter(db).import_path(args.file)
    print(f"Bombar import ID: {result.import_id}")
    print(f"Status: {result.status}")
    print(f"Imported rows: {result.imported_count}")
    print("Warnings: " + (", ".join(result.warnings) if result.warnings else "none"))
    print("Errors: " + (", ".join(result.errors) if result.errors else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
