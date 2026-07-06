from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_connectors import ConnectionRegistry
from app.destination_connectors.errors import DestinationConnectorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check destination connector credential/status readiness.")
    parser.add_argument("--connection-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ConnectionRegistry(db).check(args.connection_id)
    except DestinationConnectorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
