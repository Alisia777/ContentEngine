from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import or_, select
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

    def attributable_stats_for_assignment(self, assignment: models.ParticipantAssignment) -> dict[str, Any]:
        """Return only conversion metrics that can be tied to one assignment safely.

        Participant/campaign/destination totals are useful for dashboards, but they are
        not a payout attribution key.  A payout basis must resolve through a unique
        publishing task or through the assignment's unique final post URL.
        """
        metrics, attribution_method, attribution_error = self._attributable_metrics(assignment)
        if not attribution_error and not self._metric_periods_are_unambiguous(metrics):
            metrics = []
            attribution_method = None
            attribution_error = "attributable_metric_periods_overlap_or_missing"
        return {
            "metric_ids": [metric.id for metric in metrics],
            "orders_total": sum(metric.orders or 0 for metric in metrics),
            "revenue_total": round(sum(metric.revenue or 0 for metric in metrics), 2),
            "orders_complete": bool(metrics) and all(metric.orders is not None for metric in metrics),
            "revenue_complete": bool(metrics) and all(metric.revenue is not None for metric in metrics),
            "attribution_method": attribution_method,
            "attribution_error": attribution_error,
        }

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
            query = query.where(or_(*clauses))
        if campaign_id:
            query = query.where(models.DestinationPostMetric.campaign_id == campaign_id)
        if period_start:
            query = query.where(models.DestinationPostMetric.period_start >= period_start)
        if period_end:
            query = query.where(models.DestinationPostMetric.period_end <= period_end)
        return self.db.scalars(query).all()

    def _attributable_metrics(
        self,
        assignment: models.ParticipantAssignment,
    ) -> tuple[list[models.DestinationPostMetric], str | None, str | None]:
        if assignment.publishing_task_id:
            other_assignment_id = self.db.scalar(
                select(models.ParticipantAssignment.id)
                .where(
                    models.ParticipantAssignment.publishing_task_id == assignment.publishing_task_id,
                    models.ParticipantAssignment.id != assignment.id,
                )
                .limit(1)
            )
            if other_assignment_id:
                return [], None, "publishing_task_shared_by_multiple_assignments"

            task_metrics = self.db.scalars(
                select(models.DestinationPostMetric).where(
                    models.DestinationPostMetric.publishing_task_id == assignment.publishing_task_id
                )
            ).all()
            if task_metrics:
                if self._has_campaign_conflict(task_metrics, assignment.campaign_id):
                    return [], None, "publishing_task_metrics_campaign_mismatch"
                return task_metrics, "publishing_task_id", None

            task = assignment.publishing_task or self.db.get(models.PublishingTask, assignment.publishing_task_id)
            if not task or not task.final_url:
                return [], None, "publishing_task_has_no_attributable_metrics"
            if not self._post_url_is_unique(task.final_url, assignment):
                return [], None, "publishing_task_final_url_is_ambiguous"
            url_metrics = self._unassigned_task_metrics_by_url(task.final_url, assignment.campaign_id)
            if url_metrics:
                return url_metrics, "publishing_task_final_url", None
            return [], None, "publishing_task_has_no_attributable_metrics"

        approved_submissions = self.db.scalars(
            select(models.ParticipantSubmission).where(
                models.ParticipantSubmission.participant_assignment_id == assignment.id,
                models.ParticipantSubmission.review_status == "approved",
                models.ParticipantSubmission.final_post_url.is_not(None),
            )
        ).all()
        final_urls = {submission.final_post_url for submission in approved_submissions}
        final_urls.discard("")
        if not final_urls:
            return [], None, "assignment_has_no_publishing_task_or_approved_submission_final_url"
        if len(final_urls) != 1:
            return [], None, "assignment_has_multiple_submission_final_urls"
        final_url = next(iter(final_urls))
        if not self._post_url_is_unique(final_url, assignment):
            return [], None, "submission_final_url_is_ambiguous"
        url_metrics = self._unassigned_task_metrics_by_url(final_url, assignment.campaign_id)
        if url_metrics:
            return url_metrics, "submission_final_post_url", None
        return [], None, "submission_has_no_attributable_metrics"

    def _unassigned_task_metrics_by_url(
        self,
        final_url: str,
        campaign_id: int | None,
    ) -> list[models.DestinationPostMetric]:
        query = select(models.DestinationPostMetric).where(
            models.DestinationPostMetric.posted_url == final_url,
            models.DestinationPostMetric.publishing_task_id.is_(None),
        )
        if campaign_id is not None:
            query = query.where(
                or_(
                    models.DestinationPostMetric.campaign_id == campaign_id,
                    models.DestinationPostMetric.campaign_id.is_(None),
                )
            )
        return self.db.scalars(query).all()

    def _post_url_is_unique(self, final_url: str, assignment: models.ParticipantAssignment) -> bool:
        task_query = select(models.PublishingTask.id).where(models.PublishingTask.final_url == final_url)
        if assignment.publishing_task_id:
            task_query = task_query.where(models.PublishingTask.id != assignment.publishing_task_id)
        if self.db.scalar(task_query.limit(1)):
            return False
        return (
            self.db.scalar(
                select(models.ParticipantSubmission.id)
                .where(
                    models.ParticipantSubmission.final_post_url == final_url,
                    models.ParticipantSubmission.participant_assignment_id != assignment.id,
                )
                .limit(1)
            )
            is None
        )

    @staticmethod
    def _metric_periods_are_unambiguous(metrics: list[models.DestinationPostMetric]) -> bool:
        if len(metrics) <= 1:
            return True
        if any(metric.period_start is None or metric.period_end is None for metric in metrics):
            return False
        periods = sorted((metric.period_start, metric.period_end) for metric in metrics)
        if any(period_start > period_end for period_start, period_end in periods):
            return False
        return all(current_start > previous_end for (_, previous_end), (current_start, _) in zip(periods, periods[1:]))

    @staticmethod
    def _has_campaign_conflict(metrics: list[models.DestinationPostMetric], campaign_id: int | None) -> bool:
        if campaign_id is None:
            return False
        return any(metric.campaign_id is not None and metric.campaign_id != campaign_id for metric in metrics)

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
