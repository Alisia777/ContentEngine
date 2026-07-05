from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_factory import ContentPerformanceService
from app.database import SessionLocal, init_db


def main() -> int:
    init_db()
    with SessionLocal() as db:
        dashboard = ContentPerformanceService(db).dashboard()

    print("\nContentEngine AI content factory dashboard")
    print("=" * 48)
    print(f"Runs: {dashboard.total_runs}")
    print(f"Prompt-ready: {dashboard.prompt_ready_runs}")
    print(f"Real-smoke ready: {dashboard.real_smoke_ready_runs}")
    print(f"Human review queue: {dashboard.human_review_queue}")
    print(f"Performance rows: {dashboard.performance_metric_count}")
    if dashboard.top_blockers:
        print("Top blockers: " + ", ".join(f"{item['blocker']}={item['count']}" for item in dashboard.top_blockers))
    else:
        print("Top blockers: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
