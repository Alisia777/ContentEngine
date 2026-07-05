from __future__ import annotations

from sqlalchemy.orm import Session

from app.campaign_execution.action_queue_service import ActionQueueService
from app.campaign_execution.execution_state_service import ExecutionStateService
from app.campaign_execution.types import ExecutionReport


class ExecutionReportService:
    def __init__(self, db: Session):
        self.db = db

    def build_report(self, campaign_id: int) -> ExecutionReport:
        snapshot = ExecutionStateService(self.db).latest_snapshot(campaign_id)
        actions = ActionQueueService(self.db).refresh_actions(campaign_id)
        summary = {
            "total_sku": snapshot.total_sku,
            "ready_sku": snapshot.ready_sku,
            "blocked_sku": snapshot.blocked_sku,
            "prompt_ready_count": snapshot.prompt_ready_count,
            "needs_review_count": snapshot.needs_review_count,
            "publishing_package_ready_count": snapshot.publishing_package_ready_count,
            "distribution_task_ready_count": snapshot.distribution_task_ready_count,
            "open_action_count": len([item for item in actions if item.status == "open"]),
            "blocked_action_count": len([item for item in actions if item.status == "blocked"]),
        }
        return ExecutionReport(
            campaign_id=campaign_id,
            snapshot=snapshot,
            actions=actions,
            blockers=snapshot.blockers,
            summary=summary,
            summary_csv=self._summary_csv(summary),
        )

    @staticmethod
    def _summary_csv(summary: dict) -> str:
        keys = list(summary.keys())
        values = [str(summary.get(key, "")) for key in keys]
        return ",".join(keys) + "\n" + ",".join(values)
