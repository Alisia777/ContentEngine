from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.destination_crm import DestinationReadinessService
from app.destination_crm.errors import DestinationCRMError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh destination readiness snapshot.")
    parser.add_argument("--destination-id", type=int, required=True)
    parser.add_argument("--campaign-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = DestinationReadinessService(db).refresh(args.destination_id, campaign_id=args.campaign_id)
    except DestinationCRMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
