from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.campaign_batch.batch_selector import BatchSelector
from app.campaign_batch.errors import CampaignBatchDataError
from app.campaign_batch.types import BatchRunResult
from app.campaign_execution import ActionQueueService, ExecutionStateService


class BatchExecutor:
    def __init__(self, db: Session):
        self.db = db

    def dry_run(self, campaign_id: int, action_type: str | None = None) -> BatchRunResult:
        return self._run(campaign_id, action_type=action_type, dry_run=True)

    def execute(self, campaign_id: int, action_type: str | None = None) -> BatchRunResult:
        return self._run(campaign_id, action_type=action_type, dry_run=False)

    def get_run(self, batch_run_id: int) -> BatchRunResult:
        return self._result(self._batch_run(batch_run_id))

    def _run(self, campaign_id: int, *, action_type: str | None, dry_run: bool) -> BatchRunResult:
        selection = BatchSelector(self.db).select_safe_actions(campaign_id, action_type)
        batch = models.CampaignBatchRun(
            campaign_id=campaign_id,
            status="dry_run" if dry_run else "running",
            action_type=action_type,
            dry_run=dry_run,
            selected_action_ids_json=[item.action_id for item in selection.selected_actions],
            total_selected=len(selection.selected_actions),
            total_skipped=len(selection.skipped_actions),
            warnings_json=[f"skipped:{item.action_id}:{item.skip_reason}" for item in selection.skipped_actions],
        )
        self.db.add(batch)
        self.db.flush()
        results = []
        total_executed = 0
        total_failed = 0
        prompt_only_executed = False
        for preview in selection.selected_actions:
            action = self.db.get(models.CampaignActionQueueItem, preview.action_id)
            if not action:
                total_failed += 1
                results.append({"action_id": preview.action_id, "status": "failed", "error": "action_missing"})
                continue
            item = models.CampaignBatchItem(
                batch_run_id=batch.id,
                action_queue_item_id=action.id,
                product_id=action.product_id,
                sku=action.sku,
                action_type=action.action_type,
                status="would_execute" if dry_run else "running",
            )
            self.db.add(item)
            self.db.flush()
            if dry_run:
                item.result_json = {"message": "Safe action would be executed.", "action_id": action.id}
                results.append({"action_id": action.id, "status": "would_execute", "action_type": action.action_type})
                continue
            try:
                execution = self._execute_action(action, prompt_only_executed=prompt_only_executed)
                if action.action_type == "run_prompt_only":
                    prompt_only_executed = True
                item.status = "done"
                item.result_json = execution
                results.append({"action_id": action.id, "status": "done", "action_type": action.action_type})
                total_executed += 1
            except Exception as exc:  # pragma: no cover - defensive persistence path
                item.status = "failed"
                item.error_message = str(exc)
                results.append({"action_id": action.id, "status": "failed", "error": str(exc)})
                total_failed += 1
        batch.total_executed = total_executed
        batch.total_failed = total_failed
        batch.results_json = results
        batch.status = self._status(batch, dry_run=dry_run)
        if not dry_run:
            ExecutionStateService(self.db).refresh_snapshot(campaign_id)
        self.db.commit()
        self.db.refresh(batch)
        return self._result(batch)

    def _execute_action(self, action: models.CampaignActionQueueItem, *, prompt_only_executed: bool) -> dict:
        if action.action_type == "run_prompt_only":
            if prompt_only_executed:
                action.status = "done"
                self.db.flush()
                return {"message": "Covered by campaign-level prompt-only batch execution.", "executed": True}
            result = ActionQueueService(self.db).execute(action.id)
            return result.model_dump(mode="json")
        action.status = "done"
        self.db.flush()
        return {"message": "Safe batch action recorded.", "executed": True, "action_type": action.action_type}

    @staticmethod
    def _status(batch: models.CampaignBatchRun, *, dry_run: bool) -> str:
        if dry_run:
            return "dry_run"
        if batch.total_failed:
            return "completed_with_errors"
        if batch.total_executed:
            return "completed"
        return "blocked"

    def _batch_run(self, batch_run_id: int) -> models.CampaignBatchRun:
        batch = self.db.get(models.CampaignBatchRun, batch_run_id)
        if not batch:
            raise CampaignBatchDataError(f"CampaignBatchRun {batch_run_id} not found.")
        return batch

    @staticmethod
    def _result(batch: models.CampaignBatchRun) -> BatchRunResult:
        return BatchRunResult(
            batch_run_id=batch.id,
            campaign_id=batch.campaign_id,
            status=batch.status,
            action_type=batch.action_type,
            dry_run=batch.dry_run,
            selected_action_ids=batch.selected_action_ids_json or [],
            total_selected=batch.total_selected,
            total_executed=batch.total_executed,
            total_skipped=batch.total_skipped,
            total_failed=batch.total_failed,
            results=batch.results_json or [],
            warnings=batch.warnings_json or [],
            errors=batch.errors_json or [],
            generated_at=batch.created_at,
        )
