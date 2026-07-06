from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.training_academy.academy_catalog import PLATFORM_PLAYBOOKS
from app.training_academy.certification_service import CertificationService, GATE_COURSE_BY_ACTION
from app.training_academy.curriculum_service import CurriculumService
from app.training_academy.errors import TrainingAcademyDataError
from app.training_academy.types import TrainingProgressResult


class ProgressService:
    def __init__(self, db: Session):
        self.db = db

    def start_course(self, *, participant_id: int, course_id: int) -> models.TrainingAttempt:
        participant = self.db.get(models.ParticipantProfile, participant_id)
        if not participant:
            raise TrainingAcademyDataError(f"ParticipantProfile {participant_id} not found.")
        course = CurriculumService(self.db).get_course(course_id)
        attempt = models.TrainingAttempt(participant_id=participant_id, course_id=course.id, status="started")
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def progress(self, participant_id: int) -> TrainingProgressResult:
        participant = self.db.get(models.ParticipantProfile, participant_id)
        if not participant:
            raise TrainingAcademyDataError(f"ParticipantProfile {participant_id} not found.")
        courses = CurriculumService(self.db).list_courses()
        attempts = self.db.scalars(
            select(models.TrainingAttempt)
            .where(models.TrainingAttempt.participant_id == participant_id)
            .order_by(models.TrainingAttempt.created_at.desc(), models.TrainingAttempt.id.desc())
        ).all()
        cert_service = CertificationService(self.db)
        certifications = cert_service.list_certifications(participant_id)
        certification_codes = {cert.course_code for cert in certifications if cert.status == "certified"}
        certified_badges = cert_service.certified_badges(participant_id)
        latest_attempt_by_course: dict[int, models.TrainingAttempt] = {}
        for attempt in attempts:
            latest_attempt_by_course.setdefault(attempt.course_id, attempt)
        course_payloads: list[dict[str, Any]] = []
        for course in courses:
            latest = latest_attempt_by_course.get(course.id)
            course_payloads.append(
                {
                    "course_id": course.id,
                    "course_code": course.code,
                    "title": course.title,
                    "role": course.role,
                    "status": "certified"
                    if course.code in certification_codes
                    else (latest.status if latest else "not_started"),
                    "latest_score": latest.score if latest else None,
                    "certified": course.code in certification_codes,
                    "badge": cert_service.badge_for_course(course.code),
                }
            )
        gate_payload = {}
        for action in GATE_COURSE_BY_ACTION:
            gate_payload[action] = cert_service.evaluate_gate(participant_id, action, strict=False)
        platform_payload = {
            playbook["platform"]: cert_service.platform_readiness(participant_id, playbook["platform"], strict=False)
            for playbook in PLATFORM_PLAYBOOKS
        }
        return TrainingProgressResult(
            participant_id=participant_id,
            courses=course_payloads,
            certifications=[
                {
                    "id": cert.id,
                    "course_id": cert.course_id,
                    "course_code": cert.course_code,
                    "badge": cert_service.badge_for_course(cert.course_code),
                    "status": cert.status,
                    "issued_at": cert.issued_at,
                    "expires_at": cert.expires_at,
                }
                for cert in certifications
            ],
            gates={**gate_payload, "platforms": platform_payload},
            badges=certified_badges,
        )
