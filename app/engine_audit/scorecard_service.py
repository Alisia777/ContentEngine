from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.engine_audit.types import EngineAuditDimension, EngineAuditOutput


DIMENSION_DEFINITIONS = (
    ("interface_usability", "Interface usability"),
    ("video_quality", "Video quality"),
    ("ai_brief_quality", "AI brief quality"),
    ("creator_clarity", "Creator clarity"),
    ("training_readiness", "Training readiness"),
    ("metrics_traceability", "Metrics traceability"),
    ("destination_readiness", "Destination readiness"),
    ("campaign_operations", "Campaign operations"),
    ("production_readiness", "Production readiness"),
)


class EngineAuditScorecardService:
    """Builds the v2.5 quality scorecard without provider or publishing side effects."""

    def __init__(self, db: Session):
        self.db = db

    def run(self, *, scope_type: str = "global", scope_id: int | None = None) -> models.EngineAuditReport:
        dimensions = [
            self._interface_usability(),
            self._video_quality(),
            self._ai_brief_quality(),
            self._creator_clarity(),
            self._training_readiness(),
            self._metrics_traceability(),
            self._destination_readiness(),
            self._campaign_operations(),
            self._production_readiness(),
        ]
        overall_score = round(mean(item.score for item in dimensions), 1)
        blocking_dimensions = [item.key for item in dimensions if item.status == "blocked"]
        status = "ready" if overall_score >= 8 and not blocking_dimensions else "needs_work"
        road_to_10 = self._road_to_10(dimensions)
        next_actions = road_to_10[:5]
        report = models.EngineAuditReport(
            scope_type=scope_type,
            scope_id=scope_id,
            status=status,
            overall_score=overall_score,
            score_scale="1_to_10",
            dimensions_json=[item.model_dump(mode="json") for item in dimensions],
            reasons_json=self._flatten(dimensions, "reasons"),
            required_fixes_json=self._flatten(dimensions, "required_fixes"),
            road_to_10_json=road_to_10,
            next_actions_json=next_actions,
            evidence_json={
                "dimension_count": len(dimensions),
                "blocking_dimensions": blocking_dimensions,
                "score_method": "weighted operational heuristics from current ContentEngine records",
            },
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def latest(self, *, scope_type: str = "global", scope_id: int | None = None) -> models.EngineAuditReport | None:
        query = select(models.EngineAuditReport).where(models.EngineAuditReport.scope_type == scope_type)
        if scope_id is None:
            query = query.where(models.EngineAuditReport.scope_id.is_(None))
        else:
            query = query.where(models.EngineAuditReport.scope_id == scope_id)
        return self.db.scalar(query.order_by(models.EngineAuditReport.id.desc()))

    def output(self, report: models.EngineAuditReport) -> EngineAuditOutput:
        return EngineAuditOutput(
            id=report.id,
            scope_type=report.scope_type,
            scope_id=report.scope_id,
            status=report.status,
            overall_score=report.overall_score,
            score_scale=report.score_scale,
            dimensions=[EngineAuditDimension.model_validate(item) for item in (report.dimensions_json or [])],
            reasons=report.reasons_json or [],
            required_fixes=report.required_fixes_json or [],
            road_to_10=report.road_to_10_json or [],
            next_actions=report.next_actions_json or [],
            evidence=report.evidence_json or {},
            report_path=report.report_path,
        )

    def _interface_usability(self) -> EngineAuditDimension:
        nav_links = 31
        control_room_exists = False
        score = 4.5
        reasons = ["too_many_operator_entry_points", "no_unified_control_room"]
        fixes = ["Build /control-room with role-based next actions.", "Group operator views by workflow stage and role."]
        if control_room_exists:
            score = 8
            reasons = []
            fixes = ["Keep role navigation tied to audit next actions."]
        return self._dimension(
            "interface_usability",
            score,
            reasons,
            fixes,
            "build_unified_control_room",
            {"top_nav_link_count_estimate": nav_links, "control_room_route_exists": control_room_exists},
        )

    def _video_quality(self) -> EngineAuditDimension:
        video_jobs = self._count(models.VideoJob)
        generated_jobs = self._count(models.VideoJob, models.VideoJob.status == "video_generated")
        acceptances = self._count(models.VideoOutputAcceptance)
        approved = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "approved")
        needs_regeneration = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "needs_regeneration")
        score = 3.5
        reasons = ["real_output_not_yet_accepted"]
        fixes = ["Run limited real smoke and record OutputAcceptance before publishing."]
        if generated_jobs:
            score = 5.0
            reasons = ["real_outputs_exist_but_not_approved"]
            fixes = ["Use OutputAcceptance to reject/regenerate packaging drift.", "Move high identity-risk scenes to packshot overlay or end card."]
        if acceptances:
            score = 6.0 if approved else 5.5
            reasons = ["human_review_still_required"] if not approved else ["approved_outputs_exist_but_scale_needs_more_evidence"]
            fixes = ["Review sampled outputs visually.", "Request regeneration or product compositing for product drift."]
        if needs_regeneration:
            score = min(score, 5.5)
            reasons.append("latest_outputs_need_regeneration")
            fixes.append("Close regeneration loop before marking video quality strong.")
        return self._dimension(
            "video_quality",
            score,
            reasons,
            fixes,
            "run_real_smoke_v2_or_product_compositing",
            {
                "video_jobs": video_jobs,
                "generated_video_jobs": generated_jobs,
                "output_acceptances": acceptances,
                "approved_acceptances": approved,
                "needs_regeneration_acceptances": needs_regeneration,
            },
        )

    def _ai_brief_quality(self) -> EngineAuditDimension:
        briefs = self._count(models.AIProductionBrief)
        blueprints = self._count(models.SceneBlueprint)
        prompt_packs = self._count(models.DirectorPromptPack)
        checks = self._count(models.BriefQualityCheck)
        complete = sum(1 for value in (briefs, blueprints, prompt_packs) if value > 0)
        score = 4.0 + complete * 1.4 + min(checks, 3) * 0.3
        reasons: list[str] = []
        fixes: list[str] = []
        if not briefs:
            reasons.append("ai_production_briefs_missing")
            fixes.append("Build AIProductionBrief from product strategy, offer and UGC script.")
        if not blueprints:
            reasons.append("scene_blueprints_missing")
            fixes.append("Build scene blueprints before provider prompts.")
        if not prompt_packs:
            reasons.append("director_prompt_packs_missing")
            fixes.append("Build director prompt packs with product lock rules.")
        if not reasons:
            reasons.append("brief_contract_exists_but_needs_more_real_output_feedback")
            fixes.append("Feed output acceptance and regeneration learning back into brief contract.")
        return self._dimension(
            "ai_brief_quality",
            min(8.5, score),
            reasons,
            fixes,
            "run_brief_quality_checks",
            {
                "ai_production_briefs": briefs,
                "scene_blueprints": blueprints,
                "director_prompt_packs": prompt_packs,
                "brief_quality_checks": checks,
            },
        )

    def _creator_clarity(self) -> EngineAuditDimension:
        participants = self._count(models.ParticipantProfile)
        assignments = self._count(models.ParticipantAssignment)
        submissions = self._count(models.ParticipantSubmission)
        linked_destinations = self._count(models.ParticipantDestinationLink)
        score = 4.0
        reasons = ["participant_flow_not_proven"]
        fixes = ["Create participant assignments with clear briefs and traceable final URL requirements."]
        if participants:
            score += 1
        if assignments:
            score += 1
            reasons = ["assignments_exist_but_need_pilot_feedback"]
            fixes = ["Run pilot with real creator submissions and final URLs."]
        if linked_destinations:
            score += 0.7
        if submissions:
            score += 0.8
            reasons = ["submissions_exist_but_need_metrics_feedback"]
        return self._dimension(
            "creator_clarity",
            min(7.5, score),
            reasons,
            fixes,
            "run_creator_pilot",
            {
                "participants": participants,
                "assignments": assignments,
                "submissions": submissions,
                "participant_destination_links": linked_destinations,
            },
        )

    def _training_readiness(self) -> EngineAuditDimension:
        courses = self._count(models.TrainingCourse)
        lessons = self._count(models.TrainingLesson)
        quizzes = self._count(models.TrainingQuiz)
        certifications = self._count(models.ParticipantCertification)
        score = 3.5
        reasons = ["training_catalog_missing_or_unseeded"]
        fixes = ["Seed Training Academy courses, lessons and quizzes."]
        if courses and lessons and quizzes:
            score = 7.0
            reasons = ["academy_exists_but_real_completion_feedback_missing"]
            fixes = ["Collect pilot completion, quiz and blocker feedback."]
        if certifications:
            score = 7.5
        return self._dimension(
            "training_readiness",
            score,
            reasons,
            fixes,
            "seed_or_run_training_academy",
            {"courses": courses, "lessons": lessons, "quizzes": quizzes, "certifications": certifications},
        )

    def _metrics_traceability(self) -> EngineAuditDimension:
        tracking_links = self._count(models.TrackingLink)
        intake_batches = self._count(models.MetricsIntakeBatch)
        metrics = self._count(models.CampaignPerformanceMetric)
        snapshots = self._count(models.ParticipantMetricSnapshot)
        score = 4.0
        reasons = ["real_metrics_pipeline_not_proven"]
        fixes = ["Create tracking links and import platform CSV metrics with matched final URLs."]
        if tracking_links:
            score += 1.2
            reasons = ["tracking_links_exist_but_import_matching_needs_evidence"]
        if intake_batches:
            score += 1
        if metrics:
            score += 1
            reasons = ["metrics_imported_but_pilot_scale_needed"]
        if snapshots:
            score += 0.5
        return self._dimension(
            "metrics_traceability",
            min(7.5, score),
            reasons,
            fixes,
            "import_real_metrics_csv",
            {
                "tracking_links": tracking_links,
                "metrics_intake_batches": intake_batches,
                "campaign_performance_metrics": metrics,
                "participant_metric_snapshots": snapshots,
            },
        )

    def _destination_readiness(self) -> EngineAuditDimension:
        destinations = self._count(models.PublishingDestination)
        connections = self._count(models.DestinationConnection)
        readiness = self._count(models.DestinationReadinessSnapshot)
        ready_snapshots = self._count(models.DestinationReadinessSnapshot, models.DestinationReadinessSnapshot.status == "ready")
        score = 4.0
        reasons = ["owned_destination_registry_not_populated"]
        fixes = ["Import owned destinations and run destination readiness checks."]
        if destinations:
            score += 1.2
            reasons = ["destinations_exist_but_readiness_needs_capacity_proof"]
        if connections:
            score += 0.8
        if readiness:
            score += 0.8
        if ready_snapshots:
            score += 0.7
            reasons = ["some_destinations_ready_but_pilot_capacity_needed"]
        return self._dimension(
            "destination_readiness",
            min(7.5, score),
            reasons,
            fixes,
            "refresh_destination_readiness",
            {
                "publishing_destinations": destinations,
                "destination_connections": connections,
                "readiness_snapshots": readiness,
                "ready_snapshots": ready_snapshots,
            },
        )

    def _campaign_operations(self) -> EngineAuditDimension:
        campaigns = self._count(models.Campaign)
        execution_snapshots = self._count(models.CampaignExecutionSnapshot)
        action_items = self._count(models.CampaignActionQueueItem)
        batch_runs = self._count(models.CampaignBatchRun)
        launch_plans = self._count(models.LaunchActionPlan)
        performance_scores = self._count(models.CampaignPerformanceScore)
        score = 4.5
        reasons = ["campaign_operations_not_seeded"]
        fixes = ["Create campaign, execution snapshot, action plan and batch dry-run."]
        if campaigns:
            score += 1
            reasons = ["campaign_core_exists_but_operator_flow_needs_unification"]
        if execution_snapshots:
            score += 0.8
        if action_items:
            score += 0.8
        if batch_runs:
            score += 0.7
        if launch_plans:
            score += 0.7
        if performance_scores:
            score += 0.5
        return self._dimension(
            "campaign_operations",
            min(8.0, score),
            reasons,
            fixes,
            "open_campaign_execution_control_room",
            {
                "campaigns": campaigns,
                "execution_snapshots": execution_snapshots,
                "action_queue_items": action_items,
                "batch_runs": batch_runs,
                "launch_action_plans": launch_plans,
                "performance_scores": performance_scores,
            },
        )

    def _production_readiness(self) -> EngineAuditDimension:
        products = self._count(models.Product)
        reference_bundles = self._count(models.ProductReferenceBundle)
        safe_assets = self._count(models.ProductAsset, models.ProductAsset.is_safe_for_real_generation.is_(True))
        approved_outputs = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "approved")
        publishing_tasks = self._count(models.PublishingTask)
        final_urls = self._count(models.PublishingTask, models.PublishingTask.final_url.isnot(None))
        score = 3.5
        reasons = ["production_pilot_not_run"]
        fixes = ["Run v3.2 pilot with 5 SKU, traceable publishing tasks, final URLs and metrics."]
        if products:
            score += 0.7
        if reference_bundles and safe_assets:
            score += 1.2
            reasons = ["product_references_exist_but_pilot_acceptance_missing"]
            fixes = ["Use three approved references per SKU before strict real generation."]
        if approved_outputs:
            score += 1
        if publishing_tasks:
            score += 0.8
        if final_urls:
            score += 0.8
            reasons = ["some_publication_traceability_exists_but_real_pilot_needed"]
        return self._dimension(
            "production_readiness",
            min(7.0, score),
            reasons,
            fixes,
            "run_production_pilot_acceptance",
            {
                "products": products,
                "reference_bundles": reference_bundles,
                "safe_product_assets": safe_assets,
                "approved_output_acceptances": approved_outputs,
                "publishing_tasks": publishing_tasks,
                "publishing_tasks_with_final_url": final_urls,
            },
        )

    def _dimension(
        self,
        key: str,
        score: float,
        reasons: list[str],
        required_fixes: list[str],
        next_action: str,
        evidence: dict[str, Any],
    ) -> EngineAuditDimension:
        definition = dict(DIMENSION_DEFINITIONS)
        score = round(max(1.0, min(10.0, score)), 1)
        status = "strong" if score >= 8 else "usable" if score >= 6.5 else "needs_work" if score >= 4 else "blocked"
        return EngineAuditDimension(
            key=key,
            label=definition[key],
            score=score,
            status=status,
            reasons=list(dict.fromkeys(reasons)),
            required_fixes=list(dict.fromkeys(required_fixes)),
            next_action=next_action,
            evidence=evidence,
        )

    def _count(self, model, *criteria) -> int:
        stmt = select(func.count()).select_from(model)
        for item in criteria:
            stmt = stmt.where(item)
        return int(self.db.scalar(stmt) or 0)

    @staticmethod
    def _flatten(dimensions: list[EngineAuditDimension], attr: str) -> list[str]:
        values: list[str] = []
        for dimension in dimensions:
            values.extend(getattr(dimension, attr))
        return list(dict.fromkeys(values))

    @staticmethod
    def _road_to_10(dimensions: list[EngineAuditDimension]) -> list[dict[str, Any]]:
        ordered = sorted(dimensions, key=lambda item: item.score)
        return [
            {
                "dimension": item.key,
                "label": item.label,
                "current_score": item.score,
                "target_score": 10,
                "why_not_10": item.reasons,
                "required_fixes": item.required_fixes,
                "next_action": item.next_action,
            }
            for item in ordered
        ]
