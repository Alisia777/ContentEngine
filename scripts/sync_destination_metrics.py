from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_connectors import DestinationConnectorSyncService
from app.destination_connectors.errors import DestinationConnectorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync metrics for a destination connector.")
    parser.add_argument("--connection-id", type=int, required=True)
    parser.add_argument("--period-start", type=date.fromisoformat, default=None)
    parser.add_argument("--period-end", type=date.fromisoformat, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = DestinationConnectorSyncService(db).sync(
                args.connection_id,
                period_start=args.period_start,
                period_end=args.period_end,
            )
    except DestinationConnectorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
