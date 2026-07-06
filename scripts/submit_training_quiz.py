from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.training_academy import CurriculumService, QuizService, TrainingAcademyError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a training quiz for a participant.")
    parser.add_argument("--participant-id", type=int, required=True)
    parser.add_argument("--course-code", required=True)
    parser.add_argument("--answers", required=True, help="Path to JSON file with question_id -> answer.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    answers_path = Path(args.answers)
    try:
        answers = json.loads(answers_path.read_text(encoding="utf-8"))
        with SessionLocal() as db:
            curriculum = CurriculumService(db)
            if not curriculum.list_courses():
                curriculum.seed_defaults()
            quiz = QuizService(db).get_for_course_code(args.course_code)
            result = QuizService(db).submit(participant_id=args.participant_id, quiz_id=quiz.id, answers=answers)
    except (TrainingAcademyError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
