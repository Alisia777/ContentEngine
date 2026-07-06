from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot import CampaignDistributionPlanner, CampaignRunner, CampaignService, ProductMatrixImporter
from app.campaign_batch import BatchExecutor
from app.campaign_execution import ActionQueueService, ExecutionStateService
from app.campaign_performance import CampaignMetricsImporter, CampaignRecommendationEngine
from app.factory_os.errors import FactoryOSDataError
from app.factory_os.health_check import FactoryHealthCheck
from app.factory_os.report_service import FactoryAcceptanceReportService
from app.factory_os.types import FactoryAcceptanceReport, FactoryHealthStatus, FactoryLaunchResult


class FactoryLaunchWorkflow:
    def __init__(self, db: Session):
        self.db = db

    def run_prompt_only_launch(
        self,
        input_matrix_path: str | Path,
        campaign_name: str,
        target_videos: int,
        target_destinations: int,
        *,
        brand: str = "Factory OS",
        performance_csv_path: str | Path | None = None,
    ) -> FactoryLaunchResult:
        steps: list[dict[str, Any]] = []
        matrix_path = Path(input_matrix_path)
        if not matrix_path.exists():
            raise FactoryOSDataError(f"Matrix file not found: {matrix_path}")
        matrix_import = ProductMatrixImporter(self.db).import_path(matrix_path)
        steps.append({"step": "import_product_matrix", "status": matrix_import.status, "import_id": matrix_import.import_id})
        campaign = CampaignService(self.db).create_campaign(
            name=campaign_name,
            brand=brand,
            import_id=matrix_import.import_id,
            target_video_count=target_videos,
            target_destination_count=target_destinations,
            source_type="factory_os_prompt_only",
        )
        steps.append({"step": "create_campaign", "status": campaign.status, "campaign_id": campaign.campaign_id})
        prepare = CampaignRunner(self.db).prepare_campaign(campaign.campaign_id)
        steps.append({"step": "prepare_campaign", "status": prepare.status, "content_runs": prepare.total_content_runs})
        initial_snapshot = ExecutionStateService(self.db).refresh_snapshot(campaign.campaign_id)
        ActionQueueService(self.db).refresh_actions(campaign.campaign_id)
        steps.append({"step": "refresh_execution_snapshot", "status": initial_snapshot.status, "snapshot_id": initial_snapshot.snapshot_id})
        dry_run = BatchExecutor(self.db).dry_run(campaign.campaign_id, action_type="run_prompt_only")
        steps.append({"step": "dry_run_safe_batch", "status": dry_run.status, "selected": dry_run.total_selected, "skipped": dry_run.total_skipped})
        batch_run = BatchExecutor(self.db).execute(campaign.campaign_id, action_type="run_prompt_only")
        steps.append({"step": "execute_safe_prompt_only_batch", "status": batch_run.status, "executed": batch_run.total_executed})
        final_snapshot = ExecutionStateService(self.db).refresh_snapshot(campaign.campaign_id)
        ActionQueueService(self.db).refresh_actions(campaign.campaign_id)
        steps.append({"step": "refresh_execution_snapshot_after_batch", "status": final_snapshot.status, "snapshot_id": final_snapshot.snapshot_id})
        distribution_plan = CampaignDistributionPlanner(self.db).generate_plan(campaign.campaign_id)
        steps.append({"step": "generate_distribution_plan", "status": distribution_plan.status, "scheduled_slots": distribution_plan.scheduled_slots})
        if performance_csv_path:
            performance_path = Path(performance_csv_path)
            if performance_path.exists():
                performance = CampaignMetricsImporter(self.db).import_csv_text(
                    campaign.campaign_id,
                    performance_path.read_text(encoding="utf-8-sig"),
                    source_file=performance_path.as_posix(),
                )
                steps.append({"step": "import_performance_metrics", "status": performance.status, "imported": performance.imported_count})
            else:
                steps.append({"step": "import_performance_metrics", "status": "skipped", "reason": "file_not_found"})
        recommendations = CampaignRecommendationEngine(self.db).generate(campaign.campaign_id)
        steps.append({"step": "generate_scaling_recommendations", "status": "generated", "count": len(recommendations)})
        report = self.generate_acceptance_report(campaign.campaign_id)
        return FactoryLaunchResult(
            campaign_id=campaign.campaign_id,
            import_id=matrix_import.import_id,
            status="prompt_only_acceptance_ready",
            steps=steps,
            acceptance_report=report,
        )

    def run_existing_campaign(self, campaign_id: int) -> FactoryLaunchResult:
        if not self.db.get(models.Campaign, campaign_id):
            raise FactoryOSDataError(f"Campaign {campaign_id} not found.")
        steps: list[dict[str, Any]] = []
        snapshot = ExecutionStateService(self.db).refresh_snapshot(campaign_id)
        ActionQueueService(self.db).refresh_actions(campaign_id)
        steps.append({"step": "refresh_execution_snapshot", "status": snapshot.status, "snapshot_id": snapshot.snapshot_id})
        dry_run = BatchExecutor(self.db).dry_run(campaign_id, action_type="run_prompt_only")
        steps.append({"step": "dry_run_safe_batch", "status": dry_run.status, "selected": dry_run.total_selected, "skipped": dry_run.total_skipped})
        batch_run = BatchExecutor(self.db).execute(campaign_id, action_type="run_prompt_only")
        steps.append({"step": "execute_safe_prompt_only_batch", "status": batch_run.status, "executed": batch_run.total_executed})
        plan = CampaignDistributionPlanner(self.db).generate_plan(campaign_id)
        steps.append({"step": "generate_distribution_plan", "status": plan.status, "scheduled_slots": plan.scheduled_slots})
        recommendations = CampaignRecommendationEngine(self.db).generate(campaign_id)
        steps.append({"step": "generate_scaling_recommendations", "status": "generated", "count": len(recommendations)})
        report = self.generate_acceptance_report(campaign_id)
        return FactoryLaunchResult(campaign_id=campaign_id, status="existing_campaign_checked", steps=steps, acceptance_report=report)

    def generate_acceptance_report(self, campaign_id: int) -> FactoryAcceptanceReport:
        return FactoryAcceptanceReportService(self.db).build(campaign_id)

    def check_system_health(self) -> FactoryHealthStatus:
        return FactoryHealthCheck(self.db).run()
