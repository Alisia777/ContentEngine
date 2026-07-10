from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.control_room.next_action_service import ControlRoomNextActionService
from app.control_room.role_dashboard_service import ControlRoomRoleDashboardService
from app.control_room.types import ControlRoomActionOutput, ControlRoomItem, ControlRoomSnapshotOutput
from app.engine_audit import EngineAuditScorecardService
from app.public_pilot.gate_matrix import (
    METRICS_IMPORT,
    ONE_VIDEO_REAL_RUN,
    OUTPUT_REVIEW,
    PUBLISHING_APPROVE,
    PublicPilotGateMatrix,
    VIDEO_APPROVE,
)


ROLE_ALIASES = {
    "owner": "owner",
    "founder": "owner",
    "admin": "admin",
    "content_lead": "producer",
    "campaign_operator": "operator",
    "operator": "operator",
    "reviewer": "reviewer",
    "creator": "trainee",
    "publisher": "operator",
    "creator_publisher": "operator",
    "metrics_operator": "operator",
}

DASHBOARD_ROLE_ALIASES = {
    "admin": "owner",
    "founder": "owner",
    "creator": "creator_publisher",
    "publisher": "creator_publisher",
}


class ControlRoomSnapshotService:
    def __init__(self, db: Session):
        self.db = db
        self.dashboard_service = ControlRoomRoleDashboardService(db)
        self.next_action_service = ControlRoomNextActionService()

    def refresh(self, *, role: str = "owner", scope_type: str = "global", scope_id: int | None = None) -> models.ControlRoomSnapshot:
        dashboard_role = DASHBOARD_ROLE_ALIASES.get(role, role)
        audit_service = EngineAuditScorecardService(self.db)
        audit_run = audit_service.latest(scope_type=scope_type, scope_id=scope_id)
        if not audit_run:
            audit_run = audit_service.run(scope_type=scope_type, scope_id=scope_id)
        audit = audit_service.output(audit_run)
        dashboard = self.dashboard_service.dashboard(dashboard_role)
        next_actions = self.next_action_service.from_scorecard(role=dashboard_role, recommendations=audit.recommendations)
        safe_actions, gated_actions = self._split_gated(dashboard_role, next_actions)
        dimension_scores = {
            item.key: {"score": item.score, "status": item.status}
            for item in audit.dimensions
        }
        operations = self._operations_summary(audit)

        snapshot = models.ControlRoomSnapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            role=dashboard_role,
            overall_status=audit.status,
            engine_audit_run_id=audit_run.id,
            summary_json={
                "engine_audit_total_score": audit.total_score,
                "overall_status": audit.status,
                "top_blocker_count": len(audit.blockers),
                "role": dashboard_role,
                "requested_role": role,
                "dimension_scores": dimension_scores,
                **operations,
            },
            scorecard_json=audit.model_dump(mode="json"),
            ready_items_json=[item.model_dump(mode="json") for item in dashboard["ready"]],
            blocked_items_json=[item.model_dump(mode="json") for item in dashboard["blocked"]],
            review_queue_json=[item.model_dump(mode="json") for item in dashboard["review"]],
            safe_actions_json=[item.model_dump(mode="json") for item in safe_actions],
            gated_actions_json=[item.model_dump(mode="json") for item in gated_actions],
            next_actions_json=[item.model_dump(mode="json") for item in next_actions],
        )
        self.db.add(snapshot)
        self.db.flush()
        for item in [*safe_actions, *gated_actions]:
            self.db.add(
                models.ControlRoomAction(
                    snapshot_id=snapshot.id,
                    action_type=item.action_type,
                    role=item.role,
                    target_module=item.target_module,
                    target_url=item.target_url,
                    status=item.status,
                    safe_to_execute=item.safe_to_execute,
                    requires_human=item.requires_human,
                    requires_spend_gate=item.requires_spend_gate,
                    reason=item.reason,
                    payload_json=item.payload,
                )
            )
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def latest(self, *, role: str = "owner") -> models.ControlRoomSnapshot | None:
        return self.db.scalar(
            select(models.ControlRoomSnapshot)
            .where(models.ControlRoomSnapshot.role == role)
            .order_by(models.ControlRoomSnapshot.id.desc())
        )

    def output(self, snapshot: models.ControlRoomSnapshot) -> ControlRoomSnapshotOutput:
        return ControlRoomSnapshotOutput(
            id=snapshot.id,
            scope_type=snapshot.scope_type,
            scope_id=snapshot.scope_id,
            role=snapshot.role,
            overall_status=snapshot.overall_status,
            engine_audit_run_id=snapshot.engine_audit_run_id,
            summary=snapshot.summary_json or {},
            scorecard=snapshot.scorecard_json or {},
            ready_items=[ControlRoomItem.model_validate(item) for item in (snapshot.ready_items_json or [])],
            blocked_items=[ControlRoomItem.model_validate(item) for item in (snapshot.blocked_items_json or [])],
            review_queue=[ControlRoomItem.model_validate(item) for item in (snapshot.review_queue_json or [])],
            safe_actions=[ControlRoomActionOutput.model_validate(item) for item in (snapshot.safe_actions_json or [])],
            gated_actions=[ControlRoomActionOutput.model_validate(item) for item in (snapshot.gated_actions_json or [])],
            next_actions=[ControlRoomActionOutput.model_validate(item) for item in (snapshot.next_actions_json or [])],
        )

    def actions(self, snapshot_id: int | None = None) -> list[models.ControlRoomAction]:
        stmt = select(models.ControlRoomAction).order_by(models.ControlRoomAction.id.desc())
        if snapshot_id:
            stmt = stmt.where(models.ControlRoomAction.snapshot_id == snapshot_id)
        return self.db.scalars(stmt).all()

    def route_action(self, action_id: int) -> models.ControlRoomAction:
        action = self.db.get(models.ControlRoomAction, action_id)
        if not action:
            raise KeyError(action_id)
        action.status = "routed"
        self.db.commit()
        self.db.refresh(action)
        return action

    def _split_gated(self, role: str, actions: list[ControlRoomActionOutput]) -> tuple[list[ControlRoomActionOutput], list[ControlRoomActionOutput]]:
        gate_role = ROLE_ALIASES.get(role, role)
        matrix = PublicPilotGateMatrix()
        gated: list[ControlRoomActionOutput] = []
        safe: list[ControlRoomActionOutput] = []
        for item in actions:
            gate_action = self._gate_action_for_module(item)
            decision = matrix.evaluate(gate_role, gate_action, spend_gate_confirmed=False) if gate_action else None
            if item.requires_spend_gate or (decision and not decision.allowed):
                item.safe_to_execute = False
                item.requires_spend_gate = item.requires_spend_gate or (decision.spend_gate_required if decision else False)
                item.reason = item.reason or (decision.reason if decision else "spend_gate_required")
                gated.append(item)
            else:
                safe.append(item)
        return safe, gated

    @staticmethod
    def _gate_action_for_module(item: ControlRoomActionOutput) -> str | None:
        if item.target_module == "output_acceptance":
            return OUTPUT_REVIEW if "review" in item.action_type or "acceptance" in item.action_type else VIDEO_APPROVE
        if item.target_module == "one_video_acceptance" and item.requires_spend_gate:
            return ONE_VIDEO_REAL_RUN
        if item.target_module == "metrics_intake":
            return METRICS_IMPORT
        if item.target_module == "publishing":
            return PUBLISHING_APPROVE
        return None

    def _operations_summary(self, audit) -> dict:
        campaigns = self._count(models.Campaign)
        open_campaign_actions = self._count(models.CampaignActionQueueItem, models.CampaignActionQueueItem.status == "open")
        safe_campaign_actions = self._count(models.CampaignActionQueueItem, models.CampaignActionQueueItem.safe_to_execute.is_(True))
        destinations = self._count(models.PublishingDestination)
        active_destinations = self._count(models.PublishingDestination, models.PublishingDestination.status.in_(["active", "ready"]))
        final_url_tasks = self._count(models.PublishingTask, models.PublishingTask.final_url.isnot(None))
        metrics_rows = self._count(models.CampaignPerformanceMetric)
        pending_payout_amount = float(
            self.db.scalar(
                select(func.coalesce(func.sum(models.PayoutLedgerEntry.amount), 0.0))
                .where(models.PayoutLedgerEntry.status != "paid")
            )
            or 0.0
        )
        production_dimension = next((item for item in audit.dimensions if item.key == "production"), None)
        video_quality_dimension = next((item for item in audit.dimensions if item.key == "video_quality"), None)
        paid_smoke_status = "unknown"
        if production_dimension:
            paid_smoke_status = (production_dimension.evidence or {}).get("paid_smoke_status", "unknown")
        real_video_next_action = "one_paid_smoke_then_output_acceptance"
        if video_quality_dimension:
            real_video_next_action = (video_quality_dimension.evidence or {}).get("next_action", video_quality_dimension.next_action)

        return {
            "campaign_readiness": {
                "campaigns": campaigns,
                "open_actions": open_campaign_actions,
                "safe_actions": safe_campaign_actions,
                "status": "blocked" if open_campaign_actions else "ready",
            },
            "destination_capacity": {
                "destinations": destinations,
                "active_destinations": active_destinations,
                "status": "ready" if active_destinations else "needs_setup",
            },
            "metrics_coverage": {
                "tracked_publications": final_url_tasks,
                "metric_rows": metrics_rows,
                "coverage_percent": round((metrics_rows / final_url_tasks) * 100, 1) if final_url_tasks else 0,
            },
            "payout_exposure": {
                "pending_amount": pending_payout_amount,
                "currency": "RUB",
            },
            "paid_smoke_status": paid_smoke_status,
            "real_video_next_action": real_video_next_action,
            "executive_next_decisions": [item.get("next_action") for item in (audit.recommendations or [])[:5]],
        }

    def _count(self, model, *criteria) -> int:
        stmt = select(func.count()).select_from(model)
        for item in criteria:
            stmt = stmt.where(item)
        return int(self.db.scalar(stmt) or 0)
