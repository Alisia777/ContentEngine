from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.training_academy.errors import TrainingAcademyDataError


class LessonService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_course(self, course_id: int) -> list[models.TrainingLesson]:
        return self.db.scalars(
            select(models.TrainingLesson)
            .where(models.TrainingLesson.course_id == course_id)
            .order_by(models.TrainingLesson.sort_order, models.TrainingLesson.id)
        ).all()

    def get(self, lesson_id: int) -> models.TrainingLesson:
        lesson = self.db.get(models.TrainingLesson, lesson_id)
        if not lesson:
            raise TrainingAcademyDataError(f"TrainingLesson {lesson_id} not found.")
        return lesson
