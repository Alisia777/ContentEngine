from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.training_academy.certification_service import CertificationService
from app.training_academy.errors import TrainingAcademyDataError
from app.training_academy.types import TrainingAttemptResult


class QuizService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, quiz_id: int) -> models.TrainingQuiz:
        quiz = self.db.get(models.TrainingQuiz, quiz_id)
        if not quiz:
            raise TrainingAcademyDataError(f"TrainingQuiz {quiz_id} not found.")
        return quiz

    def get_for_course_code(self, course_code: str) -> models.TrainingQuiz:
        quiz = self.db.scalar(
            select(models.TrainingQuiz)
            .join(models.TrainingCourse)
            .where(models.TrainingCourse.code == course_code)
            .order_by(models.TrainingQuiz.id)
        )
        if not quiz:
            raise TrainingAcademyDataError(f"Training quiz for {course_code} not found.")
        return quiz

    def submit(self, *, participant_id: int, quiz_id: int, answers: dict[str, Any]) -> TrainingAttemptResult:
        participant = self.db.get(models.ParticipantProfile, participant_id)
        if not participant:
            raise TrainingAcademyDataError(f"ParticipantProfile {participant_id} not found.")
        quiz = self.get(quiz_id)
        questions = quiz.questions_json or []
        correct_count = 0
        feedback: list[dict[str, Any]] = []
        for question in questions:
            question_id = str(question.get("id", ""))
            answer = answers.get(question_id)
            is_correct = self._answer_matches(answer, question.get("correct_answers", []))
            if is_correct:
                correct_count += 1
            feedback.append(
                {
                    "question_id": question_id,
                    "correct": is_correct,
                    "expected": question.get("correct_answers", []),
                    "explanation": question.get("explanation"),
                }
            )
        total_count = len(questions)
        score = (correct_count / total_count) if total_count else 0
        passed = score >= quiz.passing_score
        attempt = models.TrainingAttempt(
            participant_id=participant_id,
            course_id=quiz.course_id,
            quiz_id=quiz.id,
            status="passed" if passed else "failed",
            score=score,
            passed=passed,
            answers_json=answers,
            result_json={"feedback": feedback, "correct_count": correct_count, "total_count": total_count},
        )
        self.db.add(attempt)
        self.db.flush()
        certification_id = None
        if passed:
            certification = CertificationService(self.db).certify(participant_id=participant_id, course=quiz.course, attempt_id=attempt.id)
            certification_id = certification.id
        self.db.commit()
        self.db.refresh(attempt)
        return TrainingAttemptResult(
            attempt_id=attempt.id,
            participant_id=participant_id,
            course_id=quiz.course_id,
            quiz_id=quiz.id,
            score=score,
            passed=passed,
            status=attempt.status,
            correct_count=correct_count,
            total_count=total_count,
            certification_id=certification_id,
            feedback=feedback,
        )

    @staticmethod
    def _answer_matches(answer: Any, correct_answers: list[Any]) -> bool:
        if isinstance(answer, list):
            answer_values = {_normalize_answer(item) for item in answer}
        else:
            answer_values = {_normalize_answer(answer)}
        expected_values = {_normalize_answer(item) for item in correct_answers}
        return bool(answer_values & expected_values)


def _normalize_answer(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
