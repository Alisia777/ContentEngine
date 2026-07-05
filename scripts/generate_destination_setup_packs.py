from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bombar_launch import DestinationSetupPlanner
from app.bombar_launch.errors import BombarLaunchError
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate internal destination setup packs for a Bombar campaign.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            packs = DestinationSetupPlanner(db).generate(args.campaign_id)
    except BombarLaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Destination setup packs: {len(packs)}")
    for pack in packs[:5]:
        print(f"#{pack.pack_id}: {pack.platform} / {pack.suggested_handle} / {pack.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
