from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_batch.batch_executor import BatchExecutor
from app.campaign_batch.errors import CampaignBatchDataError
from app.campaign_batch.types import BatchReport


class BatchReporter:
    def __init__(self, db: Session):
        self.db = db

    def build_report(self, batch_run_id: int) -> BatchReport:
        batch = self.db.get(models.CampaignBatchRun, batch_run_id)
        if not batch:
            raise CampaignBatchDataError(f"CampaignBatchRun {batch_run_id} not found.")
        items = self.db.scalars(
            select(models.CampaignBatchItem)
            .where(models.CampaignBatchItem.batch_run_id == batch_run_id)
            .order_by(models.CampaignBatchItem.id)
        ).all()
        item_rows = [
            {
                "batch_item_id": item.id,
                "action_queue_item_id": item.action_queue_item_id,
                "sku": item.sku,
                "action_type": item.action_type,
                "status": item.status,
                "result": item.result_json or {},
                "error": item.error_message,
            }
            for item in items
        ]
        summary = {
            "batch_run_id": batch.id,
            "campaign_id": batch.campaign_id,
            "status": batch.status,
            "action_type": batch.action_type or "",
            "dry_run": batch.dry_run,
            "total_selected": batch.total_selected,
            "total_executed": batch.total_executed,
            "total_skipped": batch.total_skipped,
            "total_failed": batch.total_failed,
        }
        return BatchReport(
            batch_run=BatchExecutor(self.db).get_run(batch_run_id),
            items=item_rows,
            summary=summary,
            summary_csv=self._summary_csv(summary),
        )

    @staticmethod
    def _summary_csv(summary: dict) -> str:
        keys = list(summary.keys())
        return ",".join(keys) + "\n" + ",".join(str(summary.get(key, "")) for key in keys)
