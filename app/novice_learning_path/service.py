from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.public_pilot.training_catalog import PUBLIC_PILOT_TRAINING_MODULES

from .types import (
    CompletionCriterion,
    LearningStep,
    NextLearningMove,
    NoviceLearningPath,
    QuizQuestionResult,
    QuizSubmissionResult,
)


class NoviceLearningPathError(ValueError):
    """Raised when a learning path or quiz cannot be built safely."""


@dataclass(frozen=True)
class _StepDefinition:
    code: str
    title: str
    purpose: str
    estimated_minutes: int
    module_code: str | None
    action_label: str
    action_href: str
    criteria: tuple[tuple[str, str, str], ...]


_STEPS: tuple[_StepDefinition, ...] = (
    _StepDefinition(
        code="factory_basics",
        title="Поймите безопасный цикл завода",
        purpose="За несколько минут увидеть путь от товара до измеримого результата и границы ответственности ИИ.",
        estimated_minutes=4,
        module_code="contentengine_overview",
        action_label="Пройти вводный урок и мини-тест",
        action_href="/workbench?tab=people",
        criteria=(("overview_quiz_passed", "Мини-тест по циклу завода пройден с нужным баллом", "training"),),
    ),
    _StepDefinition(
        code="product_ready",
        title="Выберите свой товар",
        purpose="Закрепить ролик за реальным товаром вашей организации, а не за демонстрационной карточкой.",
        estimated_minutes=3,
        module_code=None,
        action_label="Добавить или выбрать товар",
        action_href="/mvp-launch",
        criteria=(("product_registered", "Товар создан или выбран вами в заводе", "product_registered"),),
    ),
    _StepDefinition(
        code="inputs_ready",
        title="Подготовьте материалы и промпт",
        purpose="Проверить фото, ограничения и сценарий до любого платного запуска.",
        estimated_minutes=6,
        module_code=None,
        action_label="Проверить карточку и подготовить промпт",
        action_href="/mvp-launch",
        criteria=(
            ("asset_gate_passed", "Фото и обязательные материалы прошли входную проверку", "asset_gate_passed"),
            ("prompt_ready", "Промпт подготовлен без запуска провайдера", "prompt_ready"),
        ),
    ),
    _StepDefinition(
        code="first_video",
        title="Получите первый ролик",
        purpose="Запустить один контролируемый вариант и дождаться реального результата генерации.",
        estimated_minutes=5,
        module_code=None,
        action_label="Запустить одну генерацию",
        action_href="/mvp-launch",
        criteria=(("generation_succeeded", "Сервер подтвердил успешную генерацию ролика", "generation_succeeded"),),
    ),
    _StepDefinition(
        code="quality_approved",
        title="Проверьте качество глазами",
        purpose="Научиться блокировать подмену товара, неверные обещания и визуальные артефакты.",
        estimated_minutes=6,
        module_code="review_qa",
        action_label="Открыть проверку качества",
        action_href="/workbench?tab=video-quality",
        criteria=(
            ("review_quiz_passed", "Мини-тест по проверке качества пройден", "training"),
            ("human_review_completed", "Человек подтвердил, что просмотрел MP4", "human_review_completed"),
            ("video_approved", "Ролик одобрен человеком для следующего этапа", "video_approved"),
        ),
    ),
    _StepDefinition(
        code="published_with_tracking",
        title="Опубликуйте с отслеживанием",
        purpose="Связать одобренный ролик, площадку, финальную ссылку и будущие метрики.",
        estimated_minutes=7,
        module_code="publishing_manual_upload",
        action_label="Подготовить и завершить публикацию",
        action_href="/workbench?tab=funnel",
        criteria=(
            ("publishing_quiz_passed", "Мини-тест по безопасной публикации пройден", "training"),
            ("publishing_package_approved", "Пакет публикации одобрен", "publishing_package_approved"),
            ("publication_completed", "Сервер подтвердил финальную опубликованную ссылку", "publication_completed"),
        ),
    ),
    _StepDefinition(
        code="first_metric",
        title="Получите первую измеримую метрику",
        purpose="Завершить первый полный контент-цикл фактическими данными, а не прогнозом.",
        estimated_minutes=3,
        module_code=None,
        action_label="Проверить привязку метрик",
        action_href="/workbench?tab=analytics",
        criteria=(("first_metric_attributed", "Первая фактическая метрика привязана к публикации", "first_metric_attributed"),),
    ),
)

_RUN_EVENT_NAMES = frozenset(
    {
        "asset_gate_passed",
        "prompt_ready",
        "generation_succeeded",
        "human_review_completed",
        "video_approved",
        "publishing_package_approved",
        "publication_completed",
        "first_metric_attributed",
    }
)

_REJECTED_ATTEMPT_MARKERS = frozenset({"seeded", "demo", "bypass", "auto_granted", "auto_certified"})


class NoviceLearningPathService:
    """Read real learning/action evidence and recommend one safe next move.

    ``build`` is read-only. It does not seed modules, write telemetry, or grant a
    certificate. A certificate counts only when it is backed by the same user's
    completed, passing, non-seeded attempt.
    """

    def __init__(self, db: Session, *, now: datetime | None = None):
        self.db = db
        self.now = _utc_naive(now or datetime.now(UTC))
        self.threshold = float(get_settings().public_pilot_training_threshold)

    def build(self, *, user_profile_id: int, organization_id: int) -> NoviceLearningPath:
        membership = self._active_membership(user_profile_id=user_profile_id, organization_id=organization_id)
        verified_training = self._verified_training(user_profile_id)
        events = self.db.scalars(
            select(models.FactoryEvent)
            .where(
                models.FactoryEvent.user_profile_id == user_profile_id,
                models.FactoryEvent.organization_id == organization_id,
                models.FactoryEvent.source == "server",
            )
            .order_by(models.FactoryEvent.occurred_at, models.FactoryEvent.id)
        ).all()
        active_run_id, run_events = self._select_active_run(events)
        product_event = self._product_event(events, run_events)

        evidence: dict[str, models.FactoryEvent | models.UserTrainingAttempt | None] = {
            "overview_quiz_passed": verified_training.get("contentengine_overview"),
            "product_registered": product_event,
            "review_quiz_passed": verified_training.get("review_qa"),
            "publishing_quiz_passed": verified_training.get("publishing_manual_upload"),
        }
        for event_name in _RUN_EVENT_NAMES:
            evidence[event_name] = self._latest_event(run_events, event_name)

        raw_steps: list[LearningStep] = []
        first_incomplete_index: int | None = None
        for index, definition in enumerate(_STEPS):
            criteria = [
                self._criterion(code=code, label=label, source=source, evidence=evidence.get(code))
                for code, label, source in definition.criteria
            ]
            satisfied = sum(criterion.satisfied for criterion in criteria)
            completed = satisfied == len(criteria)
            if not completed and first_incomplete_index is None:
                first_incomplete_index = index
            raw_steps.append(
                LearningStep(
                    code=definition.code,
                    order=index + 1,
                    title=definition.title,
                    purpose=definition.purpose,
                    estimated_minutes=definition.estimated_minutes,
                    status="completed" if completed else "upcoming",
                    progress_percent=round(100 * satisfied / len(criteria)),
                    module_code=definition.module_code,
                    lesson_title=self._lesson_title(definition.module_code),
                    action_label=definition.action_label,
                    action_href=definition.action_href,
                    completion_criteria=criteria,
                )
            )

        if first_incomplete_index is not None:
            raw_steps[first_incomplete_index].status = "current"

        completed_steps = sum(step.status == "completed" for step in raw_steps)
        total_criteria = sum(len(step.completion_criteria) for step in raw_steps)
        satisfied_criteria = sum(
            criterion.satisfied for step in raw_steps for criterion in step.completion_criteria
        )
        is_complete = completed_steps == len(raw_steps)
        next_move = (
            self._complete_move()
            if is_complete
            else self._next_move(_STEPS[first_incomplete_index], raw_steps[first_incomplete_index])
        )
        return NoviceLearningPath(
            user_profile_id=user_profile_id,
            organization_id=organization_id,
            role=membership.role,
            active_factory_run_id=active_run_id,
            steps=raw_steps,
            completed_steps=completed_steps,
            total_steps=len(raw_steps),
            satisfied_criteria=satisfied_criteria,
            total_criteria=total_criteria,
            progress_percent=round(100 * completed_steps / len(raw_steps)),
            is_complete=is_complete,
            next_move=next_move,
        )

    def verified_certification_codes(self, *, user_profile_id: int) -> set[str]:
        """Return only certificates backed by a complete, re-scoreable attempt."""

        return set(self._verified_training(user_profile_id))

    def submit_quiz(
        self,
        *,
        user_profile_id: int,
        organization_id: int,
        module_code: str,
        answers: Mapping[str | int, Any] | None,
    ) -> QuizSubmissionResult:
        """Validate every active module question and certify only a real pass.

        Answer keys are question ids (integers or their string form). Only known
        option values are persisted. Repeating a correct submission reuses the
        already verified attempt/certificate instead of creating duplicates.
        """

        self._active_membership(user_profile_id=user_profile_id, organization_id=organization_id)
        module = self.db.scalar(
            select(models.TrainingModule).where(
                models.TrainingModule.code == module_code,
                models.TrainingModule.is_active.is_(True),
            )
        )
        if module is None:
            raise NoviceLearningPathError(f"Unknown active training module: {module_code}")
        questions = self.db.scalars(
            select(models.TrainingQuestion)
            .where(models.TrainingQuestion.module_id == module.id)
            .order_by(models.TrainingQuestion.order_index, models.TrainingQuestion.id)
        ).all()
        if not questions:
            raise NoviceLearningPathError(f"Training module has no quiz questions: {module_code}")

        submitted = {str(key): value for key, value in (answers or {}).items()}
        stored_answers: dict[str, Any] = {}
        question_results: list[QuizQuestionResult] = []
        correct_count = 0
        for question in questions:
            raw_answer = submitted.get(str(question.id))
            canonical_answer, is_valid = self._canonical_answer(question, raw_answer)
            stored_answers[str(question.id)] = canonical_answer
            expected = {_normalize_answer(item) for item in (question.correct_answer_json or [])}
            if question.question_type == "multi_select":
                actual = set(canonical_answer) if isinstance(canonical_answer, list) else set()
                correct = is_valid and bool(expected) and actual == expected
            else:
                actual = canonical_answer if isinstance(canonical_answer, str) else None
                correct = is_valid and bool(expected) and actual in expected
            correct_count += int(correct)
            question_results.append(
                QuizQuestionResult(
                    question_id=question.id,
                    correct=correct,
                    explanation=question.explanation,
                )
            )

        total_count = len(questions)
        score = correct_count / total_count
        passed = score >= self.threshold

        if passed:
            existing = self._verified_certification(user_profile_id, module.code)
            if existing is not None:
                certification, attempt = existing
                return QuizSubmissionResult(
                    module_code=module.code,
                    attempt_id=attempt.id,
                    certification_id=certification.id,
                    score=score,
                    passing_threshold=self.threshold,
                    passed=True,
                    correct_count=correct_count,
                    total_count=total_count,
                    attempt_created=False,
                    certification_created=False,
                    question_results=question_results,
                )

        attempt = models.UserTrainingAttempt(
            user_profile_id=user_profile_id,
            module_id=module.id,
            status="passed" if passed else "failed",
            score=score,
            passed=passed,
            answers_json=stored_answers,
            started_at=self.now,
            completed_at=self.now,
        )
        self.db.add(attempt)
        self.db.flush()
        certification = None
        if passed:
            certification = models.TrainingCertification(
                user_profile_id=user_profile_id,
                module_id=module.id,
                attempt_id=attempt.id,
                module_code=module.code,
                status="passed",
                granted_at=self.now,
            )
            self.db.add(certification)
        self.db.commit()
        self.db.refresh(attempt)
        if certification is not None:
            self.db.refresh(certification)
        return QuizSubmissionResult(
            module_code=module.code,
            attempt_id=attempt.id,
            certification_id=certification.id if certification else None,
            score=score,
            passing_threshold=self.threshold,
            passed=passed,
            correct_count=correct_count,
            total_count=total_count,
            attempt_created=True,
            certification_created=certification is not None,
            question_results=question_results,
        )

    def _active_membership(self, *, user_profile_id: int, organization_id: int) -> models.Membership:
        profile = self.db.get(models.UserProfile, user_profile_id)
        if profile is None or not profile.is_active or profile.status != "active":
            raise NoviceLearningPathError("Active user profile is required.")
        organization = self.db.get(models.Organization, organization_id)
        if organization is None or organization.status != "active":
            raise NoviceLearningPathError("Active organization is required.")
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.organization_id == organization_id,
                models.Membership.status == "active",
            )
        )
        if membership is None:
            raise NoviceLearningPathError("Active organization membership is required.")
        return membership

    def _verified_training(self, user_profile_id: int) -> dict[str, models.UserTrainingAttempt]:
        verified: dict[str, models.UserTrainingAttempt] = {}
        rows = self.db.execute(
            select(models.TrainingCertification, models.UserTrainingAttempt)
            .join(models.UserTrainingAttempt, models.TrainingCertification.attempt_id == models.UserTrainingAttempt.id)
            .where(
                models.TrainingCertification.user_profile_id == user_profile_id,
                models.TrainingCertification.status == "passed",
            )
            .order_by(models.TrainingCertification.granted_at.desc(), models.TrainingCertification.id.desc())
        ).all()
        for certification, attempt in rows:
            if certification.module_code in verified:
                continue
            if self._is_verified_attempt(certification, attempt, user_profile_id=user_profile_id):
                verified[certification.module_code] = attempt
        return verified

    def _verified_certification(
        self, user_profile_id: int, module_code: str
    ) -> tuple[models.TrainingCertification, models.UserTrainingAttempt] | None:
        rows = self.db.execute(
            select(models.TrainingCertification, models.UserTrainingAttempt)
            .join(models.UserTrainingAttempt, models.TrainingCertification.attempt_id == models.UserTrainingAttempt.id)
            .where(
                models.TrainingCertification.user_profile_id == user_profile_id,
                models.TrainingCertification.module_code == module_code,
                models.TrainingCertification.status == "passed",
            )
            .order_by(models.TrainingCertification.granted_at.desc(), models.TrainingCertification.id.desc())
        ).all()
        for certification, attempt in rows:
            if self._is_verified_attempt(certification, attempt, user_profile_id=user_profile_id):
                return certification, attempt
        return None

    def _is_verified_attempt(
        self,
        certification: models.TrainingCertification,
        attempt: models.UserTrainingAttempt,
        *,
        user_profile_id: int,
    ) -> bool:
        if certification.expires_at is not None and _utc_naive(certification.expires_at) <= self.now:
            return False
        if certification.user_profile_id != user_profile_id or attempt.user_profile_id != user_profile_id:
            return False
        if certification.module_id != attempt.module_id or certification.attempt_id != attempt.id:
            return False
        if not attempt.passed or attempt.status not in {"passed", "completed"}:
            return False
        if float(attempt.score or 0) < self.threshold or attempt.completed_at is None:
            return False
        answers = attempt.answers_json
        if not isinstance(answers, dict) or not answers:
            return False
        lowered_keys = {str(key).strip().casefold() for key in answers}
        if lowered_keys.intersection(_REJECTED_ATTEMPT_MARKERS):
            return False
        module = self.db.get(models.TrainingModule, attempt.module_id)
        if module is None or not module.is_active or module.code != certification.module_code:
            return False
        questions = self.db.scalars(
            select(models.TrainingQuestion)
            .where(models.TrainingQuestion.module_id == module.id)
            .order_by(models.TrainingQuestion.order_index, models.TrainingQuestion.id)
        ).all()
        if not questions:
            return False
        correct_count = 0
        for question in questions:
            canonical, valid = self._canonical_answer(question, answers.get(str(question.id)))
            expected = {_normalize_answer(item) for item in (question.correct_answer_json or [])}
            if question.question_type == "multi_select":
                actual = set(canonical) if isinstance(canonical, list) else set()
                correct = valid and bool(expected) and actual == expected
            else:
                actual = canonical if isinstance(canonical, str) else None
                correct = valid and bool(expected) and actual in expected
            correct_count += int(correct)
        verified_score = correct_count / len(questions)
        return verified_score >= self.threshold and abs(verified_score - float(attempt.score)) < 1e-9

    @staticmethod
    def _select_active_run(
        events: list[models.FactoryEvent],
    ) -> tuple[str | None, list[models.FactoryEvent]]:
        grouped: dict[str, list[models.FactoryEvent]] = defaultdict(list)
        for event in events:
            if event.factory_run_id and event.event_name in _RUN_EVENT_NAMES:
                grouped[event.factory_run_id].append(event)
        if not grouped:
            return None, []

        def rank(item: tuple[str, list[models.FactoryEvent]]) -> tuple[int, datetime, int]:
            _, run_events = item
            distinct_events = len({event.event_name for event in run_events})
            latest = max(event.occurred_at for event in run_events)
            latest_id = max(event.id for event in run_events)
            return distinct_events, latest, latest_id

        run_id, run_events = max(grouped.items(), key=rank)
        return run_id, sorted(run_events, key=lambda event: (event.occurred_at, event.id))

    @staticmethod
    def _product_event(
        events: list[models.FactoryEvent], run_events: list[models.FactoryEvent]
    ) -> models.FactoryEvent | None:
        product_ids = {event.product_id for event in run_events if event.product_id is not None}
        candidates = [event for event in events if event.event_name in {"product_created", "product_selected"}]
        if product_ids:
            matching = [event for event in candidates if event.product_id in product_ids]
            if matching:
                candidates = matching
        return max(candidates, key=lambda event: (event.occurred_at, event.id), default=None)

    @staticmethod
    def _latest_event(events: list[models.FactoryEvent], event_name: str) -> models.FactoryEvent | None:
        return max(
            (event for event in events if event.event_name == event_name),
            key=lambda event: (event.occurred_at, event.id),
            default=None,
        )

    @staticmethod
    def _criterion(
        *,
        code: str,
        label: str,
        source: str,
        evidence: models.FactoryEvent | models.UserTrainingAttempt | None,
    ) -> CompletionCriterion:
        is_training = source == "training"
        return CompletionCriterion(
            code=code,
            label=label,
            satisfied=evidence is not None,
            evidence_source="training_attempt" if is_training else "factory_event",
            evidence_id=evidence.id if evidence is not None else None,
            observed_at=(
                evidence.completed_at
                if isinstance(evidence, models.UserTrainingAttempt)
                else (evidence.occurred_at if isinstance(evidence, models.FactoryEvent) else None)
            ),
        )

    def _lesson_title(self, module_code: str | None) -> str | None:
        if module_code is None:
            return None
        lesson = self.db.scalar(
            select(models.PublicTrainingLesson)
            .join(models.TrainingModule)
            .where(models.TrainingModule.code == module_code, models.TrainingModule.is_active.is_(True))
            .order_by(models.PublicTrainingLesson.order_index, models.PublicTrainingLesson.id)
        )
        if lesson is not None:
            return lesson.title
        for module in PUBLIC_PILOT_TRAINING_MODULES:
            if module["code"] == module_code and module.get("lessons"):
                return module["lessons"][0]["title"]
        return None

    def _next_move(self, definition: _StepDefinition, step: LearningStep) -> NextLearningMove:
        missing_codes = {criterion.code for criterion in step.completion_criteria if not criterion.satisfied}
        training_code = next((code for code, _, source in definition.criteria if source == "training"), None)
        if definition.module_code and training_code in missing_codes:
            lesson_title = step.lesson_title or "Короткий урок"
            return NextLearningMove(
                kind="lesson",
                step_code=definition.code,
                title=definition.title,
                label=f"Пройти: {lesson_title}",
                href=f"/workbench?tab=people&module={quote(definition.module_code)}",
                module_code=definition.module_code,
                lesson_title=lesson_title,
            )
        return NextLearningMove(
            kind="action",
            step_code=definition.code,
            title=definition.title,
            label=definition.action_label,
            href=definition.action_href,
            module_code=definition.module_code,
            lesson_title=step.lesson_title,
        )

    @staticmethod
    def _complete_move() -> NextLearningMove:
        return NextLearningMove(
            kind="complete",
            title="Первый измеримый контент-цикл завершён",
            label="Открыть аналитику и выбрать следующий товар",
            href="/workbench?tab=analytics",
        )

    @staticmethod
    def _canonical_answer(question: models.TrainingQuestion, raw_answer: Any) -> tuple[str | list[str] | None, bool]:
        allowed = {_normalize_answer(option) for option in (question.options_json or [])}
        if question.question_type == "multi_select":
            raw_values = raw_answer if isinstance(raw_answer, (list, tuple, set)) else [raw_answer]
            values = [_normalize_answer(value) for value in raw_values if value is not None]
            valid = bool(values) and len(values) == len(set(values)) and all(value in allowed for value in values)
            return (sorted(set(values)) if valid else None), valid
        if isinstance(raw_answer, (list, tuple, set)):
            if len(raw_answer) != 1:
                return None, False
            raw_answer = next(iter(raw_answer))
        if raw_answer is None:
            return None, False
        value = _normalize_answer(raw_answer)
        return (value if value in allowed else None), value in allowed


def _normalize_answer(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return " ".join(str(value or "").strip().casefold().split())[:300]


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
