from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_crm import DestinationHealthService
from app.destination_crm.errors import DestinationCRMError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh destination health for a campaign.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = DestinationHealthService(db).refresh_campaign(args.campaign_id)
    except DestinationCRMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps([item.model_dump(mode="json") for item in result], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
