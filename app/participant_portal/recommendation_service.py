from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.assignment_portal_service import AssignmentPortalService
from app.participant_portal.onboarding_service import OnboardingService
from app.participant_portal.participant_metrics_service import ParticipantMetricsService
from app.participant_portal.participant_service import ParticipantService
from app.participant_portal.payout_service import PayoutService


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def recommendations(self, participant_id: int) -> list[dict]:
        ParticipantService(self.db).get(participant_id)
        recommendations = []
        assignments = AssignmentPortalService(self.db).list_assignments(participant_id)
        for assignment in assignments:
            if assignment.status in {"assigned", "in_progress"}:
                recommendations.append({"action": "submit_video", "assignment_id": assignment.id, "reason": "assignment_waits_for_submission"})
            if assignment.status == "needs_revision":
                recommendations.append({"action": "fix_submission", "assignment_id": assignment.id, "reason": "review_requested_changes"})
            if assignment.publishing_task and not assignment.publishing_task.final_url:
                recommendations.append({"action": "publish_pending_task", "assignment_id": assignment.id, "reason": "publishing_task_has_no_final_url"})
        links = OnboardingService(self.db).destinations(participant_id)
        metric_ids = []
        stats = ParticipantMetricsService(self.db).dashboard_stats(participant_id)
        if stats["published_total"] and not stats["views_total"]:
            recommendations.append({"action": "import_missing_stats", "reason": "published_posts_have_no_metrics"})
        if stats["approval_rate"] is not None and stats["approval_rate"] >= 0.8:
            recommendations.append({"action": "create_more_variants", "reason": "high_approval_rate"})
        for row in stats.get("by_destination", []):
            if row["views"] >= 1000 and row["clicks"] <= 5:
                recommendations.append({"action": "pause_channel", "destination_id": row["destination_id"], "reason": "views_without_clicks"})
            elif row["orders"] > 0:
                recommendations.append({"action": "scale_channel", "destination_id": row["destination_id"], "reason": "orders_present"})
        payouts = PayoutService(self.db).payouts(participant_id)
        if any(entry.status in {"approved", "payable"} for entry in payouts):
            recommendations.append({"action": "payout_ready", "reason": "approved_or_payable_ledger_entries"})
        if any(entry.status == "disputed" for entry in payouts):
            recommendations.append({"action": "payout_dispute_review", "reason": "disputed_ledger_entries"})
        if not links:
            recommendations.append({"action": "link_destination", "reason": "participant_has_no_channels"})
        return recommendations or [{"action": "monitor", "reason": "no_blockers"}]
