from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.errors import ParticipantPortalDataError
from app.participant_portal.onboarding_service import OnboardingService
from app.participant_portal.participant_service import ParticipantService
from app.participant_portal.types import ParticipantMetricResult


class ParticipantMetricsService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(
        self,
        participant_id: int,
        *,
        campaign_id: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> ParticipantMetricResult:
        ParticipantService(self.db).get(participant_id)
        assignments = self._assignments(participant_id, campaign_id)
        submissions = self._submissions(participant_id)
        metrics = self._destination_metrics(participant_id, campaign_id, period_start, period_end)
        payouts = self._payouts(participant_id, campaign_id)
        approved_total = sum(1 for submission in submissions if submission.review_status == "approved")
        rejected_total = sum(1 for submission in submissions if submission.review_status == "rejected")
        submitted_total = len(submissions)
        published_total = sum(1 for assignment in assignments if assignment.status in {"published", "paid"} or assignment.publishing_task_id)
        payout_total = round(sum(entry.amount for entry in payouts if entry.status != "rejected"), 2)
        views_total = sum(metric.views or 0 for metric in metrics)
        clicks_total = sum(metric.clicks or 0 for metric in metrics)
        orders_total = sum(metric.orders or 0 for metric in metrics)
        revenue_total = round(sum(metric.revenue or 0 for metric in metrics), 2)
        engagement_rate = self._ratio(sum((metric.likes or 0) + (metric.comments or 0) + (metric.shares or 0) + (metric.saves or 0) for metric in metrics), views_total)
        approval_rate = self._ratio(approved_total, submitted_total)
        snapshot = models.ParticipantMetricSnapshot(
            participant_id=participant_id,
            campaign_id=campaign_id,
            period_start=period_start,
            period_end=period_end,
            assignments_total=len(assignments),
            submitted_total=submitted_total,
            approved_total=approved_total,
            rejected_total=rejected_total,
            published_total=published_total,
            views_total=views_total,
            clicks_total=clicks_total,
            orders_total=orders_total,
            revenue_total=revenue_total,
            engagement_rate=engagement_rate,
            approval_rate=approval_rate,
            payout_total=payout_total,
            raw_json={
                "metric_ids": [metric.id for metric in metrics],
                "assignment_ids": [assignment.id for assignment in assignments],
                "payout_ids": [entry.id for entry in payouts],
            },
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return self._result(snapshot)

    def latest_or_refresh(self, participant_id: int, *, campaign_id: int | None = None) -> ParticipantMetricResult:
        snapshot = self.db.scalar(
            select(models.ParticipantMetricSnapshot)
            .where(
                models.ParticipantMetricSnapshot.participant_id == participant_id,
                models.ParticipantMetricSnapshot.campaign_id == campaign_id,
            )
            .order_by(models.ParticipantMetricSnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh(participant_id, campaign_id=campaign_id)
        return self._result(snapshot)

    def dashboard_stats(self, participant_id: int, *, campaign_id: int | None = None) -> dict[str, Any]:
        result = self.latest_or_refresh(participant_id, campaign_id=campaign_id)
        metrics = self._destination_metrics(participant_id, campaign_id, None, None)
        by_destination: dict[int, dict[str, Any]] = {}
        for metric in metrics:
            bucket = by_destination.setdefault(
                metric.destination_id or 0,
                {"destination_id": metric.destination_id, "views": 0, "clicks": 0, "orders": 0, "revenue": 0.0},
            )
            bucket["views"] += metric.views or 0
            bucket["clicks"] += metric.clicks or 0
            bucket["orders"] += metric.orders or 0
            bucket["revenue"] = round(bucket["revenue"] + (metric.revenue or 0), 2)
        return {**result.model_dump(mode="json"), "by_destination": list(by_destination.values())}

    def _assignments(self, participant_id: int, campaign_id: int | None) -> list[models.ParticipantAssignment]:
        query = select(models.ParticipantAssignment).where(models.ParticipantAssignment.participant_id == participant_id)
        if campaign_id:
            query = query.where(models.ParticipantAssignment.campaign_id == campaign_id)
        return self.db.scalars(query).all()

    def _submissions(self, participant_id: int) -> list[models.ParticipantSubmission]:
        return self.db.scalars(select(models.ParticipantSubmission).where(models.ParticipantSubmission.participant_id == participant_id)).all()

    def _payouts(self, participant_id: int, campaign_id: int | None) -> list[models.PayoutLedgerEntry]:
        query = select(models.PayoutLedgerEntry).where(models.PayoutLedgerEntry.participant_id == participant_id)
        if campaign_id:
            query = query.where(models.PayoutLedgerEntry.campaign_id == campaign_id)
        return self.db.scalars(query).all()

    def _destination_metrics(
        self,
        participant_id: int,
        campaign_id: int | None,
        period_start: date | None,
        period_end: date | None,
    ) -> list[models.DestinationPostMetric]:
        destination_ids = [link.destination_id for link in OnboardingService(self.db).destinations(participant_id) if link.status == "active"]
        task_ids = [
            assignment.publishing_task_id
            for assignment in self._assignments(participant_id, campaign_id)
            if assignment.publishing_task_id
        ]
        if not destination_ids and not task_ids:
            return []
        query = select(models.DestinationPostMetric)
        clauses = []
        if destination_ids:
            clauses.append(models.DestinationPostMetric.destination_id.in_(destination_ids))
        if task_ids:
            clauses.append(models.DestinationPostMetric.publishing_task_id.in_(task_ids))
        if len(clauses) == 1:
            query = query.where(clauses[0])
        else:
            from sqlalchemy import or_

            query = query.where(or_(*clauses))
        if campaign_id:
            query = query.where(models.DestinationPostMetric.campaign_id == campaign_id)
        if period_start:
            query = query.where(models.DestinationPostMetric.period_start >= period_start)
        if period_end:
            query = query.where(models.DestinationPostMetric.period_end <= period_end)
        return self.db.scalars(query).all()

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)

    @staticmethod
    def _result(snapshot: models.ParticipantMetricSnapshot) -> ParticipantMetricResult:
        return ParticipantMetricResult(
            snapshot_id=snapshot.id,
            participant_id=snapshot.participant_id,
            campaign_id=snapshot.campaign_id,
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            assignments_total=snapshot.assignments_total,
            submitted_total=snapshot.submitted_total,
            approved_total=snapshot.approved_total,
            rejected_total=snapshot.rejected_total,
            published_total=snapshot.published_total,
            views_total=snapshot.views_total,
            clicks_total=snapshot.clicks_total,
            orders_total=snapshot.orders_total,
            revenue_total=snapshot.revenue_total,
            engagement_rate=snapshot.engagement_rate,
            approval_rate=snapshot.approval_rate,
            payout_total=snapshot.payout_total,
            raw=snapshot.raw_json or {},
        )
