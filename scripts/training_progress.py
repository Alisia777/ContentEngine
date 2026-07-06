from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.training_academy import CurriculumService, ProgressService, TrainingAcademyError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show participant training progress.")
    parser.add_argument("--participant-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            curriculum = CurriculumService(db)
            if not curriculum.list_courses():
                curriculum.seed_defaults()
            payload = ProgressService(db).progress(args.participant_id).model_dump(mode="json")
    except TrainingAcademyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
