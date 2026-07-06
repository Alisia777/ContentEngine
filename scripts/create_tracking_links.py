from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.metrics_intake import MetricsIntakeError, TrackingLinkService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create tracking links for campaign publishing tasks.")
    parser.add_argument("--campaign-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            links = TrackingLinkService(db).create_for_campaign(args.campaign_id)
            payload = [
                {
                    "id": link.id,
                    "slug": link.slug,
                    "redirect_url": f"https://our-domain.com/r/{link.slug}",
                    "target_url": link.target_url,
                    "publishing_task_id": link.publishing_task_id,
                    "sku": link.sku,
                }
                for link in links
            ]
    except MetricsIntakeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
