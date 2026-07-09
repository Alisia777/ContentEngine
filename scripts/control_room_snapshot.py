from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.control_room import ControlRoomSnapshotService
from app.database import SessionLocal, init_db


def main() -> int:
    init_db()
    with SessionLocal() as db:
        service = ControlRoomSnapshotService(db)
        snapshot = service.refresh(role="owner")
        output = service.output(snapshot)
    print(f"Control Room Snapshot: {output.id}")
    print(f"Role: {output.role}")
    print(f"Engine score: {output.summary.get('engine_audit_total_score')}/10")
    print(f"Ready: {len(output.ready_items)}")
    print(f"Blocked: {len(output.blocked_items)}")
    print(f"Review queue: {len(output.review_queue)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
