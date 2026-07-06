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
    parser = argparse.ArgumentParser(description="Create a destination connector connection.")
    parser.add_argument("--destination-id", type=int, required=True)
    parser.add_argument("--type", dest="connection_type", default="manual")
    parser.add_argument("--credential-ref", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            registry = ConnectionRegistry(db)
            connection = registry.create(args.destination_id, args.connection_type, credential_ref=args.credential_ref)
            payload = registry.view(connection).model_dump(mode="json")
    except DestinationConnectorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
