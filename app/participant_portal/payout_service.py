from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.assignment_portal_service import AssignmentPortalService
from app.participant_portal.errors import ParticipantPortalDataError
from app.participant_portal.participant_metrics_service import ParticipantMetricsService
from app.participant_portal.participant_service import ParticipantService


class PayoutService:
    def __init__(self, db: Session):
        self.db = db

    def create_rule(
        self,
        *,
        name: str,
        payout_type: str = "per_video",
        amount_fixed: float | None = None,
        currency: str = "RUB",
        percent_revenue: float | None = None,
        conditions: dict | None = None,
    ) -> models.PayoutRule:
        rule = models.PayoutRule(
            name=name,
            payout_type=payout_type,
            amount_fixed=amount_fixed,
            currency=currency,
            percent_revenue=percent_revenue,
            conditions_json=conditions or {},
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def calculate_for_assignment(self, assignment_id: int) -> models.PayoutLedgerEntry:
        assignment = AssignmentPortalService(self.db).get(assignment_id)
        rule = assignment.payout_rule or self._default_rule()
        existing = self.db.scalar(
            select(models.PayoutLedgerEntry).where(
                models.PayoutLedgerEntry.assignment_id == assignment.id,
                models.PayoutLedgerEntry.payout_rule_id == rule.id,
            )
        )
        amount, reason = self._amount(rule, assignment)
        entry = existing or models.PayoutLedgerEntry(
            participant_id=assignment.participant_id,
            assignment_id=assignment.id,
            payout_rule_id=rule.id,
        )
        entry.submission_id = assignment.submissions[-1].id if assignment.submissions else None
        entry.publishing_task_id = assignment.publishing_task_id
        entry.campaign_id = assignment.campaign_id
        entry.sku = assignment.sku
        entry.amount = amount
        entry.currency = rule.currency
        entry.status = "pending" if not existing else entry.status
        entry.reason = reason
        if not existing:
            self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def payouts(self, participant_id: int) -> list[models.PayoutLedgerEntry]:
        ParticipantService(self.db).get(participant_id)
        return self.db.scalars(
            select(models.PayoutLedgerEntry)
            .where(models.PayoutLedgerEntry.participant_id == participant_id)
            .order_by(models.PayoutLedgerEntry.id.desc())
        ).all()

    def summary(self, participant_id: int) -> dict:
        entries = self.payouts(participant_id)
        totals: dict[str, float] = {}
        for entry in entries:
            totals[entry.status] = round(totals.get(entry.status, 0.0) + entry.amount, 2)
        return {"entries": entries, "totals": totals, "total": round(sum(entry.amount for entry in entries), 2)}

    def mark_paid(self, payout_id: int) -> models.PayoutLedgerEntry:
        entry = self.db.get(models.PayoutLedgerEntry, payout_id)
        if not entry:
            raise ParticipantPortalDataError(f"PayoutLedgerEntry {payout_id} not found.")
        entry.status = "paid"
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _amount(self, rule: models.PayoutRule, assignment: models.ParticipantAssignment) -> tuple[float, str]:
        if rule.payout_type == "per_published_post":
            if not assignment.publishing_task or not assignment.publishing_task.final_url:
                raise ParticipantPortalDataError("per_published_post payout requires a publishing task with final_url.")
            return float(rule.amount_fixed or 0), rule.payout_type
        if rule.payout_type in {"per_video", "per_approved_post"}:
            return float(rule.amount_fixed or 0), rule.payout_type
        metrics = ParticipantMetricsService(self.db).dashboard_stats(assignment.participant_id, campaign_id=assignment.campaign_id)
        if rule.payout_type == "cpa":
            return round((rule.amount_fixed or 0) * metrics["orders_total"], 2), "orders_metric_cpa"
        if rule.payout_type == "revenue_share":
            return round(metrics["revenue_total"] * ((rule.percent_revenue or 0) / 100), 2), "revenue_share_metric"
        if rule.payout_type == "hybrid":
            cpa = (rule.conditions_json or {}).get("cpa_amount", 0)
            revenue_share = (rule.percent_revenue or 0) / 100
            return round((rule.amount_fixed or 0) + cpa * metrics["orders_total"] + metrics["revenue_total"] * revenue_share, 2), "hybrid"
        return 0.0, "unsupported_rule"

    def _default_rule(self) -> models.PayoutRule:
        rule = self.db.scalar(select(models.PayoutRule).where(models.PayoutRule.name == "Default per approved post"))
        if rule:
            return rule
        return self.create_rule(name="Default per approved post", payout_type="per_approved_post", amount_fixed=0, currency="RUB")
