from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.participant_portal.errors import ParticipantPortalDataError
from app.participant_portal.payout_service import PayoutService


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


def _participant(db: Session) -> models.ParticipantProfile:
    participant = models.ParticipantProfile(
        display_name="Payout safety participant",
        role="partner",
        status="active",
        platforms_json=[],
    )
    db.add(participant)
    db.flush()
    return participant


def _task(db: Session, *, final_url: str) -> models.PublishingTask:
    task = models.PublishingTask(
        publishing_package_id=100,
        destination_id=200,
        platform="Instagram Reels",
        status="published_manual",
        final_url=final_url,
        raw_response_json={},
    )
    db.add(task)
    db.flush()
    return task


def _assignment(
    db: Session,
    *,
    participant: models.ParticipantProfile,
    rule: models.PayoutRule,
    task: models.PublishingTask | None = None,
    campaign_id: int = 700,
) -> models.ParticipantAssignment:
    assignment = models.ParticipantAssignment(
        participant_id=participant.id,
        campaign_id=campaign_id,
        publishing_task_id=task.id if task else None,
        assignment_type="publish_video",
        status="assigned",
        brief_json={},
        payout_rule_id=rule.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _metric(
    db: Session,
    *,
    task: models.PublishingTask | None = None,
    posted_url: str,
    campaign_id: int = 700,
    destination_id: int = 200,
    orders: int | None = None,
    revenue: float | None = None,
) -> models.DestinationPostMetric:
    metric = models.DestinationPostMetric(
        destination_id=destination_id,
        campaign_id=campaign_id,
        publishing_task_id=task.id if task else None,
        platform="Instagram Reels",
        posted_url=posted_url,
        orders=orders,
        revenue=revenue,
        raw_json={},
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@pytest.mark.parametrize(
    ("payout_type", "amount_fixed", "percent_revenue", "expected"),
    [
        ("cpa", 100, None, (200, 700)),
        ("revenue_share", None, 10, (100, 300)),
    ],
)
def test_variable_payout_uses_only_each_assignments_publishing_task_metrics(
    db: Session,
    payout_type: str,
    amount_fixed: float | None,
    percent_revenue: float | None,
    expected: tuple[float, float],
) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(
        name=f"Safe {payout_type}",
        payout_type=payout_type,
        amount_fixed=amount_fixed,
        percent_revenue=percent_revenue,
    )
    first_task = _task(db, final_url="https://example.com/post/first")
    second_task = _task(db, final_url="https://example.com/post/second")
    first = _assignment(db, participant=participant, rule=rule, task=first_task)
    second = _assignment(db, participant=participant, rule=rule, task=second_task)
    _metric(db, task=first_task, posted_url=first_task.final_url, orders=2, revenue=1000)
    _metric(db, task=second_task, posted_url=second_task.final_url, orders=7, revenue=3000)

    first_entry = PayoutService(db).calculate_for_assignment(first.id)
    second_entry = PayoutService(db).calculate_for_assignment(second.id)

    assert (first_entry.amount, second_entry.amount) == expected


def test_campaign_destination_totals_without_assignment_link_fail_closed(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Unsafe aggregate CPA", payout_type="cpa", amount_fixed=250)
    assignment = _assignment(db, participant=participant, rule=rule)
    db.add(
        models.ParticipantDestinationLink(
            participant_id=participant.id,
            destination_id=200,
            relationship_type="partner",
            status="active",
            permissions_json=[],
        )
    )
    db.commit()
    _metric(db, posted_url="https://example.com/post/unrelated", orders=8, revenue=4000)

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 0
    assert entry.reason == "cpa_blocked:assignment_has_no_publishing_task_or_approved_submission_final_url"


def test_exact_task_metric_with_missing_orders_fails_closed(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Incomplete CPA", payout_type="cpa", amount_fixed=250)
    task = _task(db, final_url="https://example.com/post/incomplete")
    assignment = _assignment(db, participant=participant, rule=rule, task=task)
    _metric(db, task=task, posted_url=task.final_url, orders=None, revenue=500)

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 0
    assert entry.reason == "cpa_blocked:attributable_orders_missing"


def test_overlapping_attributable_metric_periods_fail_closed(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Overlapping CPA", payout_type="cpa", amount_fixed=100)
    task = _task(db, final_url="https://example.com/post/overlapping")
    assignment = _assignment(db, participant=participant, rule=rule, task=task)
    first = _metric(db, task=task, posted_url=task.final_url, orders=2, revenue=500)
    second = _metric(db, task=task, posted_url=task.final_url, orders=3, revenue=700)
    first.period_start = date(2026, 7, 1)
    first.period_end = date(2026, 7, 7)
    second.period_start = date(2026, 7, 5)
    second.period_end = date(2026, 7, 12)
    db.commit()

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 0
    assert entry.reason == "cpa_blocked:attributable_metric_periods_overlap_or_missing"


def test_shared_publishing_task_is_not_paid_once_per_assignment(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Shared-task CPA", payout_type="cpa", amount_fixed=100)
    task = _task(db, final_url="https://example.com/post/shared-task")
    first = _assignment(db, participant=participant, rule=rule, task=task)
    second = _assignment(db, participant=participant, rule=rule, task=task)
    _metric(db, task=task, posted_url=task.final_url, orders=5, revenue=1000)

    first_entry = PayoutService(db).calculate_for_assignment(first.id)
    second_entry = PayoutService(db).calculate_for_assignment(second.id)

    assert first_entry.amount == second_entry.amount == 0
    assert first_entry.reason == second_entry.reason == "cpa_blocked:publishing_task_shared_by_multiple_assignments"


def test_hybrid_keeps_only_fixed_part_without_attributable_variable_basis(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(
        name="Hybrid fixed fallback",
        payout_type="hybrid",
        amount_fixed=150,
        percent_revenue=10,
        conditions={"cpa_amount": 50},
    )
    assignment = _assignment(db, participant=participant, rule=rule)
    _metric(db, posted_url="https://example.com/post/campaign-total", orders=10, revenue=5000)

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 150
    assert entry.reason == "hybrid_variable_blocked:assignment_has_no_publishing_task_or_approved_submission_final_url"


def test_submission_final_url_is_an_exact_revenue_share_basis(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(
        name="Submission revenue share",
        payout_type="revenue_share",
        percent_revenue=25,
    )
    assignment = _assignment(db, participant=participant, rule=rule)
    submission = models.ParticipantSubmission(
        participant_assignment_id=assignment.id,
        participant_id=participant.id,
        external_url="https://example.com/video/source.mp4",
        final_post_url="https://example.com/post/submission-linked",
        status="approved",
        review_status="approved",
    )
    db.add(submission)
    db.commit()
    _metric(db, posted_url=submission.final_post_url, orders=3, revenue=800)

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 200
    assert entry.reason == "revenue_share_metric"
    assert entry.submission_id == submission.id


def test_unapproved_submission_final_url_cannot_attribute_variable_payout(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Unapproved URL CPA", payout_type="cpa", amount_fixed=100)
    assignment = _assignment(db, participant=participant, rule=rule)
    submission = models.ParticipantSubmission(
        participant_assignment_id=assignment.id,
        participant_id=participant.id,
        external_url="https://example.com/video/unapproved.mp4",
        final_post_url="https://example.com/post/unapproved-claim",
        status="submitted",
        review_status="needs_review",
    )
    db.add(submission)
    db.commit()
    _metric(db, posted_url=submission.final_post_url, orders=10, revenue=5000)

    entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 0
    assert entry.reason == "cpa_blocked:assignment_has_no_publishing_task_or_approved_submission_final_url"


def test_paid_ledger_is_immutable_when_recalculated(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(name="Immutable paid video", payout_type="per_video", amount_fixed=500)
    assignment = _assignment(db, participant=participant, rule=rule)
    entry = PayoutService(db).calculate_for_assignment(assignment.id)
    PayoutService(db).mark_paid(entry.id)
    rule.amount_fixed = 900
    db.commit()

    recalculated = PayoutService(db).calculate_for_assignment(assignment.id)

    assert recalculated.id == entry.id
    assert recalculated.status == "paid"
    assert recalculated.amount == 500


def test_per_approved_post_requires_approved_submission_and_recalculation_is_idempotent(db: Session) -> None:
    participant = _participant(db)
    rule = PayoutService(db).create_rule(
        name="Approved post only",
        payout_type="per_approved_post",
        amount_fixed=500,
    )
    assignment = _assignment(db, participant=participant, rule=rule)
    submission = models.ParticipantSubmission(
        participant_assignment_id=assignment.id,
        participant_id=participant.id,
        external_url="https://example.com/video/review.mp4",
        status="submitted",
        review_status="needs_review",
    )
    db.add(submission)
    db.commit()

    with pytest.raises(ParticipantPortalDataError, match="requires an approved submission"):
        PayoutService(db).calculate_for_assignment(assignment.id)
    assert db.scalar(select(func.count(models.PayoutLedgerEntry.id))) == 0

    submission.review_status = "approved"
    submission.status = "approved"
    db.commit()
    first_entry = PayoutService(db).calculate_for_assignment(assignment.id)
    second_entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert first_entry.id == second_entry.id
    assert second_entry.submission_id == submission.id
    assert second_entry.amount == 500
    assert db.scalar(select(func.count(models.PayoutLedgerEntry.id))) == 1
