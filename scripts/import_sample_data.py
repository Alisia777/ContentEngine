from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.csv_imports import import_csv_path
from scripts.seed import seed


SAMPLE_FILES = {
    "product_metrics": ROOT / "sample_data" / "product_metric_snapshots.csv",
    "creative_performance": ROOT / "sample_data" / "creative_performance_snapshots.csv",
    "review_insights": ROOT / "sample_data" / "product_review_insights.csv",
    "market_signals": ROOT / "sample_data" / "market_signals.csv",
}


def main() -> int:
    init_db()
    seed()
    with SessionLocal() as db:
        for kind, path in SAMPLE_FILES.items():
            count = import_csv_path(db, kind, path)
            print(f"Imported {count} rows from {path.name} as {kind}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

