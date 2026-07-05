from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.campaign_batch import BatchExecutor
from app.campaign_batch.errors import CampaignBatchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute safe campaign batch actions.")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--action-type", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = BatchExecutor(db).execute(args.campaign_id, action_type=args.action_type)
    except CampaignBatchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
