from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_connectors import ConnectionRegistry, CSVMetricsImporter
from app.destination_connectors.errors import DestinationConnectorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import destination/post metrics from CSV.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--campaign-id", type=int, default=None)
    parser.add_argument("--connection-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        csv_path = Path(args.csv)
        text = csv_path.read_text(encoding="utf-8-sig")
        with SessionLocal() as db:
            connection = ConnectionRegistry(db).get(args.connection_id) if args.connection_id else None
            result = CSVMetricsImporter(db).import_csv_text(
                text,
                connection=connection,
                campaign_id=args.campaign_id,
                source_file=str(csv_path),
            )
    except (DestinationConnectorError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
