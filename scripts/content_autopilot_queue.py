from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content_autopilot import AutopilotQueueService
from app.database import SessionLocal, init_db


def main() -> int:
    init_db()
    with SessionLocal() as db:
        dashboard = AutopilotQueueService(db).dashboard()

    print("\nContentEngine Autopilot Queue")
    print("=" * 38)
    print(f"Products checked: {dashboard.products_checked}")
    print(f"Ready: {dashboard.ready}")
    print(f"Blocked: {dashboard.blocked}")
    print(f"Needs human review: {dashboard.needs_human_review}")
    print(f"Publishing-ready: {dashboard.publishing_ready}")
    if dashboard.top_blockers:
        print("Top blockers: " + ", ".join(f"{item['blocker']}={item['count']}" for item in dashboard.top_blockers))
    else:
        print("Top blockers: none")
    if dashboard.queue:
        print("Queue:")
        for item in dashboard.queue:
            blockers = ", ".join(item["blockers"]) if item["blockers"] else "none"
            print(f"- #{item['id']} {item['sku']} -> {item['recommended_action']} ({item['queue_type']}); blockers: {blockers}")
    else:
        print("Queue: empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
