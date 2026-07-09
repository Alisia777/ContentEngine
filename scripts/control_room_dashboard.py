from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.control_room import ControlRoomSnapshotService
from app.database import SessionLocal, init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a role-based Control Room dashboard.")
    parser.add_argument("--role", default="owner")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        service = ControlRoomSnapshotService(db)
        snapshot = service.refresh(role=args.role)
        output = service.output(snapshot)

    print(f"Unified Control Room: {output.role}")
    print(f"Engine score: {output.summary.get('engine_audit_total_score')}/10 ({output.overall_status})")
    print("Ready:")
    for item in output.ready_items:
        print(f"- {item.label} -> {item.target_url}")
    print("Blocked:")
    for item in output.blocked_items:
        print(f"- {item.label} -> {item.target_url}")
    print("Next actions:")
    for item in output.next_actions[:5]:
        print(f"- {item.action_type} -> {item.target_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
