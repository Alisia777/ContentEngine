from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models
from app.database import SessionLocal, init_db
from app.publishing import ManualUploadProvider
from app.publishing.errors import PublishingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store the final URL after an operator manually uploads a post.")
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--operator-name", default="operator")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            task = db.get(models.PublishingTask, args.task_id)
            if not task:
                raise PublishingError("Publishing task not found.")
            task = ManualUploadProvider(db).mark_published(task, args.url, args.operator_name)
            print("\nContentEngine manual publish")
            print("=" * 36)
            print(f"Task ID: {task.id}")
            print(f"Status: {task.status}")
            print(f"Final URL: {task.final_url}")
            print(f"Operator: {task.operator_name}")
    except PublishingError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
