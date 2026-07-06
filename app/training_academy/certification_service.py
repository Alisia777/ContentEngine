from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.training_academy.errors import TrainingAcademyDataError


GATE_COURSE_BY_ACTION = {
    "publishing": "publisher_basics",
    "metrics_submission": "metrics_basics",
    "reviewer_approval": "reviewer_basics",
}


class CertificationService:
    def __init__(self, db: Session):
        self.db = db

    def certify(self, *, participant_id: int, course: models.TrainingCourse, attempt_id: int | None = None) -> models.ParticipantCertification:
        certification = self.db.scalar(
            select(models.ParticipantCertification).where(
                models.ParticipantCertification.participant_id == participant_id,
                models.ParticipantCertification.course_id == course.id,
                models.ParticipantCertification.status == "certified",
            )
        )
        if not certification:
            certification = models.ParticipantCertification(
                participant_id=participant_id,
                course_id=course.id,
                course_code=course.code,
                status="certified",
            )
            self.db.add(certification)
        certification.attempt_id = attempt_id
        certification.course_code = course.code
        self.db.flush()
        return certification

    def list_certifications(self, participant_id: int) -> list[models.ParticipantCertification]:
        return self.db.scalars(
            select(models.ParticipantCertification)
            .where(models.ParticipantCertification.participant_id == participant_id)
            .order_by(models.ParticipantCertification.issued_at.desc(), models.ParticipantCertification.id.desc())
        ).all()

    def has_certification(self, participant_id: int, course_code: str) -> bool:
        return (
            self.db.scalar(
                select(models.ParticipantCertification.id).where(
                    models.ParticipantCertification.participant_id == participant_id,
                    models.ParticipantCertification.course_code == course_code,
                    models.ParticipantCertification.status == "certified",
                )
            )
            is not None
        )

    def evaluate_gate(self, participant_id: int, action: str, *, strict: bool = False) -> dict[str, Any]:
        course_code = GATE_COURSE_BY_ACTION.get(action)
        if not course_code:
            raise TrainingAcademyDataError(f"Unknown training gate action: {action}")
        certified = self.has_certification(participant_id, course_code)
        result = {
            "action": action,
            "course_code": course_code,
            "certified": certified,
            "status": "passed" if certified else ("blocked" if strict else "advisory"),
            "strict": strict,
            "message": "Training certification is valid."
            if certified
            else f"{course_code} is recommended before {action}.",
        }
        if strict and not certified:
            raise TrainingAcademyDataError(result["message"])
        return result
