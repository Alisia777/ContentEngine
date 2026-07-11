from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
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
        assignment = self.db.scalar(
            select(models.ParticipantAssignment)
            .where(models.ParticipantAssignment.id == assignment_id)
            .with_for_update()
        )
        if not assignment:
            raise ParticipantPortalDataError(f"ParticipantAssignment {assignment_id} not found.")
        existing_entries = self.db.scalars(
            select(models.PayoutLedgerEntry)
            .where(models.PayoutLedgerEntry.assignment_id == assignment.id)
            .order_by(models.PayoutLedgerEntry.id)
            .limit(2)
        ).all()
        if len(existing_entries) > 1:
            raise ParticipantPortalDataError(
                f"ParticipantAssignment {assignment.id} has multiple payout ledger entries; manual reconciliation required."
            )
        existing = existing_entries[0] if existing_entries else None
        if existing and existing.status == "paid":
            return existing

        rule = assignment.payout_rule or self._default_rule()
        amount, reason = self._amount(rule, assignment)
        entry = existing or models.PayoutLedgerEntry(
            participant_id=assignment.participant_id,
            assignment_id=assignment.id,
        )
        submission = self._ledger_submission(rule, assignment)
        entry.submission_id = submission.id if submission else None
        entry.publishing_task_id = assignment.publishing_task_id
        entry.campaign_id = assignment.campaign_id
        entry.sku = assignment.sku
        entry.payout_rule_id = rule.id
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
        if entry.amount <= 0 or (entry.reason and "_blocked:" in entry.reason):
            raise ParticipantPortalDataError("Blocked or zero payout ledger entries cannot be marked paid.")
        entry.status = "paid"
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _amount(self, rule: models.PayoutRule, assignment: models.ParticipantAssignment) -> tuple[float, str]:
        if rule.payout_type == "per_published_post":
            if self._publishing_task_is_shared(assignment):
                raise ParticipantPortalDataError(
                    "per_published_post payout requires a publishing task assigned to exactly one assignment."
                )
            if not assignment.publishing_task or not assignment.publishing_task.final_url:
                raise ParticipantPortalDataError("per_published_post payout requires a publishing task with final_url.")
            return float(rule.amount_fixed or 0), rule.payout_type
        if rule.payout_type == "per_approved_post":
            if not self._approved_submission(assignment):
                raise ParticipantPortalDataError(
                    "per_approved_post payout requires an approved submission for this assignment."
                )
            return float(rule.amount_fixed or 0), rule.payout_type
        if rule.payout_type == "per_video":
            return float(rule.amount_fixed or 0), rule.payout_type
        metrics = ParticipantMetricsService(self.db).attributable_stats_for_assignment(assignment)
        if rule.payout_type == "cpa":
            if metrics["attribution_error"]:
                return 0.0, f"cpa_blocked:{metrics['attribution_error']}"
            if not metrics["orders_complete"]:
                return 0.0, "cpa_blocked:attributable_orders_missing"
            return round((rule.amount_fixed or 0) * metrics["orders_total"], 2), "orders_metric_cpa"
        if rule.payout_type == "revenue_share":
            if metrics["attribution_error"]:
                return 0.0, f"revenue_share_blocked:{metrics['attribution_error']}"
            if not metrics["revenue_complete"]:
                return 0.0, "revenue_share_blocked:attributable_revenue_missing"
            return round(metrics["revenue_total"] * ((rule.percent_revenue or 0) / 100), 2), "revenue_share_metric"
        if rule.payout_type == "hybrid":
            fixed = float(rule.amount_fixed or 0)
            cpa = float((rule.conditions_json or {}).get("cpa_amount", 0) or 0)
            revenue_share = (rule.percent_revenue or 0) / 100
            if not cpa and not revenue_share:
                return round(fixed, 2), "hybrid_fixed_only"
            if metrics["attribution_error"]:
                return round(fixed, 2), f"hybrid_variable_blocked:{metrics['attribution_error']}"
            if cpa and not metrics["orders_complete"]:
                return round(fixed, 2), "hybrid_variable_blocked:attributable_orders_missing"
            if revenue_share and not metrics["revenue_complete"]:
                return round(fixed, 2), "hybrid_variable_blocked:attributable_revenue_missing"
            return round(fixed + cpa * metrics["orders_total"] + metrics["revenue_total"] * revenue_share, 2), "hybrid"
        return 0.0, "unsupported_rule"

    def _ledger_submission(
        self,
        rule: models.PayoutRule,
        assignment: models.ParticipantAssignment,
    ) -> models.ParticipantSubmission | None:
        if rule.payout_type == "per_approved_post":
            return self._approved_submission(assignment)
        if rule.payout_type in {"cpa", "revenue_share", "hybrid"}:
            query = select(models.ParticipantSubmission).where(
                models.ParticipantSubmission.participant_assignment_id == assignment.id,
                models.ParticipantSubmission.review_status == "approved",
                models.ParticipantSubmission.final_post_url.is_not(None),
            )
            if assignment.publishing_task and assignment.publishing_task.final_url:
                query = query.where(
                    models.ParticipantSubmission.final_post_url == assignment.publishing_task.final_url
                )
            return self.db.scalar(query.order_by(models.ParticipantSubmission.id.desc()))
        return self.db.scalar(
            select(models.ParticipantSubmission)
            .where(models.ParticipantSubmission.participant_assignment_id == assignment.id)
            .order_by(models.ParticipantSubmission.id.desc())
        )

    def _approved_submission(self, assignment: models.ParticipantAssignment) -> models.ParticipantSubmission | None:
        return self.db.scalar(
            select(models.ParticipantSubmission)
            .where(
                models.ParticipantSubmission.participant_assignment_id == assignment.id,
                models.ParticipantSubmission.review_status == "approved",
            )
            .order_by(models.ParticipantSubmission.id.desc())
        )

    def _publishing_task_is_shared(self, assignment: models.ParticipantAssignment) -> bool:
        if not assignment.publishing_task_id:
            return False
        return (
            self.db.scalar(
                select(models.ParticipantAssignment.id)
                .where(
                    models.ParticipantAssignment.publishing_task_id == assignment.publishing_task_id,
                    models.ParticipantAssignment.id != assignment.id,
                )
                .limit(1)
            )
            is not None
        )

    def _default_rule(self) -> models.PayoutRule:
        rule = self.db.scalar(select(models.PayoutRule).where(models.PayoutRule.name == "Default per approved post"))
        if rule:
            return rule
        rule = models.PayoutRule(
            name="Default per approved post",
            payout_type="per_approved_post",
            amount_fixed=0,
            currency="RUB",
            conditions_json={},
        )
        self.db.add(rule)
        self.db.flush()
        return rule
