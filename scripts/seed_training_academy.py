from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.training_academy import CurriculumService, TrainingAcademyError


def main() -> int:
    init_db()
    try:
        with SessionLocal() as db:
            courses = CurriculumService(db).seed_defaults()
            payload = [
                {"id": course.id, "code": course.code, "title": course.title, "role": course.role}
                for course in courses
            ]
    except TrainingAcademyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"courses": payload}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
