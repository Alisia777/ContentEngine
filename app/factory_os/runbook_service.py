from __future__ import annotations

from sqlalchemy.orm import Session

from app.factory_os.report_service import FactoryAcceptanceReportService
from app.factory_os.types import FactoryRunbook


class FactoryRunbookService:
    def __init__(self, db: Session):
        self.db = db

    def build(self, campaign_id: int) -> FactoryRunbook:
        report = FactoryAcceptanceReportService(self.db).build(campaign_id)
        steps: list[dict] = []
        blocker_names = {item.get("blocker") for item in report.blockers}
        if report.blockers:
            steps.append({"step": "resolve_blockers", "reason": "Campaign has open blockers.", "count": len(report.blockers)})
        if "missing_reference_blocks_real_video" in blocker_names or "missing_reference" in blocker_names:
            steps.append({"step": "attach_product_references", "reason": "Real video remains blocked until approved product references exist."})
        if report.prompt_packs_created:
            steps.append({"step": "human_review_prompt_outputs", "reason": "Prompt-ready content must be reviewed before packaging or real video."})
        if report.publishing_packages_approved == 0:
            steps.append({"step": "create_or_approve_publishing_packages", "reason": "Distribution uses approved packages only."})
        if report.distribution_plan_status in {"missing", "blocked"}:
            steps.append({"step": "prepare_distribution_capacity", "reason": "Distribution plan is not ready."})
        if report.performance_metrics_imported == 0:
            steps.append({"step": "import_performance_metrics", "reason": "Scaling decisions need imported metrics."})
        if report.recommendations_generated:
            steps.append({"step": "review_scaling_recommendations", "reason": "Accept or reject scale/pause/regenerate proposals."})
        steps.append({"step": "keep_paid_and_publishing_gates_closed", "reason": "Prompt-only acceptance must not spend or auto-publish."})
        return FactoryRunbook(
            campaign_id=campaign_id,
            next_manual_steps=steps,
            blockers=report.blockers,
            commands=[
                f"python scripts\\factory_acceptance_report.py --campaign-id {campaign_id}",
                f"python scripts\\factory_runbook.py --campaign-id {campaign_id}",
                f"python scripts\\campaign_batch_dry_run.py --campaign-id {campaign_id} --action-type run_prompt_only",
                f"python scripts\\campaign_performance_recommendations.py --campaign-id {campaign_id}",
            ],
        )
