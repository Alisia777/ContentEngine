from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app import models
from app.database import SessionLocal, init_db
from app.engine import VideoFactoryEngine
from scripts.seed import seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Qharisma Video Factory mock demo pipeline.")
    parser.add_argument("--product-id", type=int, default=None, help="Product id to use. Defaults to first product.")
    parser.add_argument("--account-id", type=int, default=None, help="Publishing account id. Defaults to first owned account.")
    return parser.parse_args()


def ensure_seed_data() -> None:
    init_db()
    with SessionLocal() as db:
        has_product = db.scalar(select(models.Product.id).order_by(models.Product.id))
        has_account = db.scalar(select(models.PublishingAccount.id).order_by(models.PublishingAccount.id))
    if not has_product or not has_account:
        print("Seed data is missing; running scripts.seed.seed().")
        seed()


def first_product_id() -> int:
    with SessionLocal() as db:
        product_id = db.scalar(select(models.Product.id).order_by(models.Product.id))
    if not product_id:
        raise SystemExit("No products found. Run python scripts/seed.py and try again.")
    return product_id


def main() -> int:
    args = parse_args()
    ensure_seed_data()
    product_id = args.product_id or first_product_id()

    with SessionLocal() as db:
        result = VideoFactoryEngine(db).run_full_demo(product_id=product_id, account_id=args.account_id)

    print("\nQharisma Video Factory demo pipeline")
    print("=" * 42)
    print(f"Status: {result.status}")
    print(f"Product ID: {result.product_id}")
    print(f"Script Job ID: {result.script_job_id}")
    print(f"Script Variant ID: {result.script_variant_id}")
    print(f"Video Job ID: {result.video_job_id}")
    print(f"Publishing Package ID: {result.publishing_package_id}")
    print(f"Publishing Job ID: {result.publishing_job_id}")
    print(f"Analytics ID: {result.analytics_id}")
    print("\nSteps:")
    for step in result.steps:
        print(f"- {step.step_name}: {step.status} | {step.message}")
        if step.step_name == "run_upload" and step.data.get("provider_post_url"):
            print(f"  Post URL: {step.data['provider_post_url']}")
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"- {error}")
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

