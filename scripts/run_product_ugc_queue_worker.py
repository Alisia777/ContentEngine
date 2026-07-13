from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings, validate_runtime_settings
from app.database import SessionLocal, engine, init_db
from app.migration_state import require_database_at_migration_head
from app.product_ugc_queue import ProductUGCGenerationQueueService, ProductUGCGenerationWorker


def _request_shutdown(_signum, _frame) -> None:
    raise KeyboardInterrupt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the durable paid Product UGC generation worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one ready job and exit.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--stale-after-seconds", type=int, default=300)
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Exit 0 when a supervised worker heartbeat is recent; never process a job.",
    )
    parser.add_argument("--healthy-within-seconds", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = validate_runtime_settings(get_settings())
    if settings.runtime_profile == "production":
        with engine.connect() as connection:
            require_database_at_migration_head(connection)
    if args.health_check:
        with SessionLocal() as db:
            health = ProductUGCGenerationQueueService(db).operational_health(
                healthy_within_seconds=max(30, args.healthy_within_seconds)
            )
        print(
            "Product UGC worker health: "
            f"readiness={health['readiness']}, worker_state={health['worker_state']}, "
            f"queue_lag_seconds={health['queue_lag_seconds']}, "
            f"ready_jobs={health['ready_jobs']}"
        )
        return 0 if health["worker_ready"] else 1

    if settings.auto_init_db:
        init_db()
    worker_id = ProductUGCGenerationWorker.default_worker_id()
    signal.signal(signal.SIGTERM, _request_shutdown)
    with SessionLocal() as db:
        ProductUGCGenerationWorker(
            db,
            worker_id=worker_id,
            lease_seconds=args.lease_seconds,
            supervised=True,
        ).heartbeat(state="starting")
        report = ProductUGCGenerationQueueService(db).reconcile_stale(
            stale_after_seconds=max(0, args.stale_after_seconds)
        )
        print(
            "Product UGC queue reconciled: "
            f"retry={report.released_for_retry}, terminal={report.terminal_failures}, "
            f"quarantine={report.quarantined}, recovered={report.recovered_drafts}"
        )

    try:
        while True:
            job = None
            with SessionLocal() as db:
                job = ProductUGCGenerationWorker(
                    db,
                    worker_id=worker_id,
                    lease_seconds=args.lease_seconds,
                    supervised=True,
                ).process_next()
                if job:
                    print(
                        f"job={job.id} draft={job.draft_id} status={job.status} "
                        f"attempt={job.attempt_count}/{job.max_attempts}"
                    )
            if args.once:
                with SessionLocal() as db:
                    ProductUGCGenerationWorker(
                        db,
                        worker_id=worker_id,
                        lease_seconds=args.lease_seconds,
                        supervised=True,
                    ).heartbeat(state="stopping")
                return 0
            if not job:
                time.sleep(max(0.2, args.poll_seconds))
    except KeyboardInterrupt:
        with SessionLocal() as db:
            ProductUGCGenerationWorker(
                db,
                worker_id=worker_id,
                lease_seconds=args.lease_seconds,
                supervised=True,
            ).heartbeat(state="stopping")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
