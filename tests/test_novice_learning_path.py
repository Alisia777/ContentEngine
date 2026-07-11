from __future__ import annotations

import os
from datetime import UTC, datetime

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_novice_learning_path.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.novice_learning_path import NoviceLearningPathService
from app.product_telemetry import ProductTelemetryService
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import ensure_public_pilot_user


@pytest.fixture(autouse=True)
def reset_learning_path_db():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def _user(db, *, email: str = "novice@example.test", role: str = "owner"):
    user = ensure_public_pilot_user(db, email=email, display_name="Novice", role=role)
    PublicPilotAccessService(db).ensure_training_catalog()
    return user


def _correct_answers(db, module_code: str) -> dict[str, object]:
    questions = db.scalars(
        select(models.TrainingQuestion)
        .join(models.TrainingModule)
        .where(models.TrainingModule.code == module_code)
        .order_by(models.TrainingQuestion.order_index, models.TrainingQuestion.id)
    ).all()
    return {
        str(question.id): (
            list(question.correct_answer_json)
            if question.question_type == "multi_select"
            else question.correct_answer_json[0]
        )
        for question in questions
    }


def _pass_module(db, user, module_code: str):
    return NoviceLearningPathService(db).submit_quiz(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        module_code=module_code,
        answers=_correct_answers(db, module_code),
    )


def _record(
    db,
    user,
    *,
    name: str,
    key: str,
    run_id: str | None = None,
    product_id: int | None = None,
    properties: dict | None = None,
):
    return ProductTelemetryService(db).record_event(
        event_name=name,
        organization_id=user.organization.id,
        user_profile_id=user.profile.id,
        role=user.role,
        idempotency_key=key,
        factory_run_id=run_id,
        product_id=product_id,
        source="server",
        properties=properties or {},
    ).event


def test_path_has_seven_short_steps_exact_evidence_and_one_next_lesson_without_writes():
    with SessionLocal() as db:
        user = _user(db)
        before = {
            "attempts": db.scalar(select(func.count()).select_from(models.UserTrainingAttempt)),
            "certifications": db.scalar(select(func.count()).select_from(models.TrainingCertification)),
            "events": db.scalar(select(func.count()).select_from(models.FactoryEvent)),
        }

        path = NoviceLearningPathService(db).build(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )

        after = {
            "attempts": db.scalar(select(func.count()).select_from(models.UserTrainingAttempt)),
            "certifications": db.scalar(select(func.count()).select_from(models.TrainingCertification)),
            "events": db.scalar(select(func.count()).select_from(models.FactoryEvent)),
        }

    assert before == after
    assert path.total_steps == 7
    assert [step.code for step in path.steps] == [
        "factory_basics",
        "product_ready",
        "inputs_ready",
        "first_video",
        "quality_approved",
        "published_with_tracking",
        "first_metric",
    ]
    assert [criterion.code for step in path.steps for criterion in step.completion_criteria] == [
        "overview_quiz_passed",
        "product_registered",
        "asset_gate_passed",
        "prompt_ready",
        "generation_succeeded",
        "review_quiz_passed",
        "human_review_completed",
        "video_approved",
        "publishing_quiz_passed",
        "publishing_package_approved",
        "publication_completed",
        "first_metric_attributed",
    ]
    assert all(1 <= step.estimated_minutes <= 7 for step in path.steps)
    assert path.progress_percent == 0
    assert path.next_move.kind == "lesson"
    assert path.next_move.module_code == "contentengine_overview"
    assert path.next_move.lesson_title == "Путь одного ролика"


def test_empty_and_wrong_quiz_answers_create_failed_attempts_but_never_certify():
    with SessionLocal() as db:
        user = _user(db)
        empty = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code="contentengine_overview",
            answers={},
        )
        wrong = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code="contentengine_overview",
            answers={str(db.scalar(select(models.TrainingQuestion.id))): "definitely-not-an-option"},
        )
        certification_count = db.scalar(select(func.count()).select_from(models.TrainingCertification))
        attempts = db.scalars(select(models.UserTrainingAttempt).order_by(models.UserTrainingAttempt.id)).all()

    assert empty.passed is False
    assert empty.score == 0
    assert empty.certification_id is None
    assert wrong.passed is False
    assert wrong.score == 0
    assert wrong.certification_id is None
    assert certification_count == 0
    assert len(attempts) == 2
    assert all(attempt.status == "failed" and not attempt.passed for attempt in attempts)
    assert attempts[1].answers_json[str(empty.question_results[0].question_id)] is None


def test_correct_quiz_submission_certifies_once_and_is_idempotent():
    with SessionLocal() as db:
        user = _user(db)
        answers = _correct_answers(db, "contentengine_overview")
        first = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code="contentengine_overview",
            answers=answers,
        )
        second = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code="contentengine_overview",
            answers=answers,
        )
        attempt_count = db.scalar(select(func.count()).select_from(models.UserTrainingAttempt))
        certification_count = db.scalar(select(func.count()).select_from(models.TrainingCertification))
        path = NoviceLearningPathService(db).build(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )

    assert first.passed is True
    assert first.score == 1
    assert first.attempt_created is True
    assert first.certification_created is True
    assert second.passed is True
    assert second.attempt_created is False
    assert second.certification_created is False
    assert second.attempt_id == first.attempt_id
    assert second.certification_id == first.certification_id
    assert attempt_count == 1
    assert certification_count == 1
    assert path.steps[0].status == "completed"
    assert path.next_move.kind == "action"
    assert path.next_move.step_code == "product_ready"


def test_passed_seeded_or_forged_certificate_without_real_answer_evidence_is_ignored():
    with SessionLocal() as db:
        user = _user(db)
        module = db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == "contentengine_overview"))
        fake_attempt = models.UserTrainingAttempt(
            user_profile_id=user.profile.id,
            module_id=module.id,
            status="completed",
            score=1,
            passed=True,
            answers_json={"seeded": True},
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(fake_attempt)
        db.flush()
        db.add(
            models.TrainingCertification(
                user_profile_id=user.profile.id,
                module_id=module.id,
                attempt_id=fake_attempt.id,
                module_code=module.code,
                status="passed",
            )
        )
        forged_attempt = models.UserTrainingAttempt(
            user_profile_id=user.profile.id,
            module_id=module.id,
            status="passed",
            score=1,
            passed=True,
            answers_json={"unrelated": "pretend-correct"},
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(forged_attempt)
        db.flush()
        db.add(
            models.TrainingCertification(
                user_profile_id=user.profile.id,
                module_id=module.id,
                attempt_id=forged_attempt.id,
                module_code=module.code,
                status="passed",
            )
        )
        db.commit()

        path = NoviceLearningPathService(db).build(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )

    criterion = path.steps[0].completion_criteria[0]
    assert criterion.satisfied is False
    assert path.completed_steps == 0
    assert path.next_move.kind == "lesson"


def test_all_questions_are_scored_against_threshold_not_just_any_correct_answer():
    with SessionLocal() as db:
        user = _user(db)
        module = db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == "contentengine_overview"))
        first_question = db.scalar(
            select(models.TrainingQuestion).where(models.TrainingQuestion.module_id == module.id)
        )
        second_question = models.TrainingQuestion(
            module_id=module.id,
            question_text="Second safety check",
            question_type="single_choice",
            options_json=["safe", "unsafe"],
            correct_answer_json=["safe"],
            explanation="Both questions form the complete quiz.",
            order_index=20,
        )
        db.add(second_question)
        db.commit()
        db.refresh(second_question)

        result = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code=module.code,
            answers={str(first_question.id): first_question.correct_answer_json[0]},
        )
        certification_count = db.scalar(select(func.count()).select_from(models.TrainingCertification))

    assert result.total_count == 2
    assert result.correct_count == 1
    assert result.score == 0.5
    assert result.passing_threshold == 0.8
    assert result.passed is False
    assert certification_count == 0


def test_progress_uses_one_coherent_server_run_and_finishes_only_on_real_metric():
    with SessionLocal() as db:
        user = _user(db)
        for module_code in ("contentengine_overview", "review_qa", "publishing_manual_upload"):
            assert _pass_module(db, user, module_code).passed is True
        product = models.Product(
            organization_id=user.organization.id,
            sku="NOVICE-WB-1",
            brand="Own",
            title="Owned product",
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        _record(db, user, name="product_selected", key="path:product", product_id=product.id)

        # These fragments must not be combined into a fictitious successful cycle.
        _record(db, user, name="asset_gate_passed", key="path:a:assets", run_id="run-a", product_id=product.id)
        _record(db, user, name="prompt_ready", key="path:a:prompt", run_id="run-a", product_id=product.id)
        for name in ("generation_succeeded", "human_review_completed", "video_approved"):
            _record(db, user, name=name, key=f"path:b:{name}", run_id="run-b", product_id=product.id)

        fragmented = NoviceLearningPathService(db).build(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )
        assert fragmented.is_complete is False
        assert fragmented.active_factory_run_id == "run-b"
        assert fragmented.steps[2].status == "current"
        assert fragmented.steps[2].progress_percent == 0

        for name in (
            "asset_gate_passed",
            "prompt_ready",
            "generation_succeeded",
            "human_review_completed",
            "video_approved",
            "publishing_package_approved",
            "publication_completed",
            "first_metric_attributed",
        ):
            _record(db, user, name=name, key=f"path:c:{name}", run_id="run-c", product_id=product.id)

        complete = NoviceLearningPathService(db).build(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )

    assert complete.active_factory_run_id == "run-c"
    assert complete.completed_steps == 7
    assert complete.satisfied_criteria == complete.total_criteria == 12
    assert complete.progress_percent == 100
    assert complete.is_complete is True
    assert complete.next_move.kind == "complete"


def test_other_organization_or_user_events_never_advance_this_path():
    with SessionLocal() as db:
        novice = _user(db, email="novice-a@example.test")
        other = _user(db, email="novice-b@example.test")
        _record(db, other, name="asset_gate_passed", key="other:assets", run_id="other-run")
        _record(db, other, name="prompt_ready", key="other:prompt", run_id="other-run")
        path = NoviceLearningPathService(db).build(
            user_profile_id=novice.profile.id,
            organization_id=novice.organization.id,
        )

    assert path.active_factory_run_id is None
    assert path.steps[2].progress_percent == 0
    assert all(not criterion.satisfied for criterion in path.steps[2].completion_criteria)
