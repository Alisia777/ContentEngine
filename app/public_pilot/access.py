from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.public_pilot.gate_matrix import DANGEROUS_ACTIONS, PublicPilotGateMatrix
from app.public_pilot.training_catalog import PUBLIC_PILOT_TRAINING_MODULES

SENSITIVE_KEY_PARTS = ("secret", "token", "key", "password", "authorization", "cookie", "signed_url")


def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = sanitize_payload(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [sanitize_payload(item) for item in payload]
    return payload


class PublicPilotAccessService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.gate_matrix = PublicPilotGateMatrix(strict_training=self.settings.public_pilot_strict_training_gates)

    def ensure_training_catalog(self) -> list[models.TrainingModule]:
        modules: list[models.TrainingModule] = []
        for module_data in PUBLIC_PILOT_TRAINING_MODULES:
            module = self.db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == module_data["code"]))
            if module is None:
                module = models.TrainingModule(
                    code=module_data["code"],
                    title=module_data["title"],
                    description=module_data.get("description"),
                )
                self.db.add(module)
                self.db.flush()
            module.title = module_data["title"]
            module.description = module_data.get("description")
            module.order_index = module_data.get("order_index", 100)
            module.required_for_roles_json = module_data.get("required_for_roles", [])
            module.required_for_permissions_json = module_data.get("required_for_permissions", [])
            module.is_active = True
            modules.append(module)

            existing_lessons = {lesson.title: lesson for lesson in module.lessons}
            existing_lessons_by_order = {lesson.order_index: lesson for lesson in module.lessons}
            retained_lesson_ids: set[int] = set()
            for index, lesson_data in enumerate(module_data.get("lessons", []), start=1):
                order_index = index * 10
                lesson = existing_lessons.get(lesson_data["title"]) or existing_lessons_by_order.get(order_index)
                if lesson is None:
                    lesson = models.PublicTrainingLesson(module_id=module.id, title=lesson_data["title"], content_markdown="")
                    self.db.add(lesson)
                    self.db.flush()
                lesson.title = lesson_data["title"]
                lesson.content_markdown = lesson_data["content_markdown"]
                lesson.order_index = order_index
                retained_lesson_ids.add(lesson.id)
            for stale_lesson in module.lessons:
                if stale_lesson.id not in retained_lesson_ids:
                    self.db.delete(stale_lesson)

            existing_questions = {question.question_text: question for question in module.questions}
            existing_questions_by_order = {question.order_index: question for question in module.questions}
            retained_question_ids: set[int] = set()
            for index, question_data in enumerate(module_data.get("questions", []), start=1):
                order_index = index * 10
                question = existing_questions.get(question_data["question_text"]) or existing_questions_by_order.get(order_index)
                if question is None:
                    question = models.TrainingQuestion(module_id=module.id, question_text=question_data["question_text"])
                    self.db.add(question)
                    self.db.flush()
                question.question_text = question_data["question_text"]
                question.question_type = question_data.get("question_type", "single_choice")
                question.options_json = question_data.get("options", [])
                question.correct_answer_json = question_data.get("correct_answer", [])
                question.explanation = question_data.get("explanation")
                question.order_index = order_index
                retained_question_ids.add(question.id)
            for stale_question in module.questions:
                if stale_question.id not in retained_question_ids:
                    self.db.delete(stale_question)
        self.db.commit()
        return modules

    def certification_codes(self, user_profile_id: int | None) -> set[str]:
        if user_profile_id is None:
            return set()
        # Local import avoids a package cycle: the learning service reads the
        # public training catalog, while app.public_pilot exports this service.
        from app.novice_learning_path import NoviceLearningPathService

        return NoviceLearningPathService(self.db).verified_certification_codes(
            user_profile_id=user_profile_id
        )

    def grant_certification(self, user_profile_id: int, module_code: str) -> models.TrainingCertification:
        module = self.db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == module_code))
        if module is None:
            self.ensure_training_catalog()
            module = self.db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == module_code))
        if module is None:
            raise ValueError(f"Unknown training module: {module_code}")

        certification = self.db.scalar(
            select(models.TrainingCertification).where(
                models.TrainingCertification.user_profile_id == user_profile_id,
                models.TrainingCertification.module_code == module_code,
                models.TrainingCertification.status == "passed",
            )
        )
        if certification is None:
            attempt = models.UserTrainingAttempt(
                user_profile_id=user_profile_id,
                module_id=module.id,
                status="completed",
                score=1.0,
                passed=True,
                answers_json={"seeded": True},
            )
            self.db.add(attempt)
            self.db.flush()
            certification = models.TrainingCertification(
                user_profile_id=user_profile_id,
                module_id=module.id,
                attempt_id=attempt.id,
                module_code=module_code,
                status="passed",
            )
            self.db.add(certification)
        self.db.commit()
        self.db.refresh(certification)
        return certification

    def evaluate_action(
        self,
        *,
        user_profile_id: int | None,
        organization_id: int | None,
        role: str | None,
        action: str,
        payload: dict[str, Any] | None = None,
        spend_gate_confirmed: bool = False,
    ):
        certifications = self.certification_codes(user_profile_id)
        return self.gate_matrix.evaluate(
            role,
            action,
            certification_codes=certifications,
            spend_gate_confirmed=spend_gate_confirmed,
        )

    def require_action(
        self,
        *,
        user_profile_id: int | None,
        organization_id: int | None,
        role: str | None,
        action: str,
        payload: dict[str, Any] | None = None,
        spend_gate_confirmed: bool = False,
    ):
        certifications = self.certification_codes(user_profile_id)
        decision = self.gate_matrix.evaluate(
            role,
            action,
            certification_codes=certifications,
            spend_gate_confirmed=spend_gate_confirmed,
        )
        if decision.audit_required or not decision.allowed:
            self.log_action(
                user_profile_id=user_profile_id,
                organization_id=organization_id,
                action=action,
                status="allowed" if decision.allowed else "denied",
                reason=decision.reason,
                role=role,
                certifications=sorted(certifications),
                spend_gate_confirmed=spend_gate_confirmed,
                payload=payload or {},
            )
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)
        return decision

    def log_action(
        self,
        *,
        user_profile_id: int | None,
        organization_id: int | None,
        action: str,
        status: str,
        reason: str,
        role: str | None,
        certifications: list[str],
        spend_gate_confirmed: bool,
        payload: dict[str, Any],
    ) -> models.AuditLog:
        log = models.AuditLog(
            user_profile_id=user_profile_id,
            organization_id=organization_id,
            action=action,
            status=status,
            reason=reason,
            metadata_json={
                "role": role,
                "certifications": certifications,
                "spend_gate_confirmed": spend_gate_confirmed,
                "dangerous_action": action in DANGEROUS_ACTIONS,
                "payload": sanitize_payload(payload),
            },
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
