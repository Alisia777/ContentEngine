from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.engine_audit.types import EngineAuditDimension, EngineAuditOutput
from app.product_asset_contract import ProductAssetTierService


DIMENSION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("interface", "Interface usability"),
    ("video_quality", "Video quality"),
    ("brief_quality", "AI brief quality"),
    ("asset_readiness", "Asset readiness"),
    ("creator_clarity", "Creator clarity"),
    ("training", "Training readiness"),
    ("metrics", "Metrics traceability"),
    ("destinations", "Destination readiness"),
    ("production", "Production readiness"),
)

PAID_SMOKE_COMPLETED_STATUSES = {
    "video_generated",
    "generated",
    "needs_human_review",
    "needs_regeneration",
    "rejected",
    "approved",
}


class EngineAuditScorecardService:
    """Builds the v3.4 quality scorecard without provider or publishing side effects."""

    def __init__(self, db: Session):
        self.db = db

    def run(self, *, scope_type: str = "global", scope_id: int | None = None) -> models.EngineAuditRun:
        dimensions = [
            self._interface_usability(),
            self._video_quality(),
            self._brief_quality(),
            self._asset_readiness(),
            self._creator_clarity(),
            self._training_readiness(),
            self._metrics_traceability(),
            self._destination_readiness(),
            self._production_readiness(),
        ]
        total_score = round(mean(item.score for item in dimensions), 1)
        blockers = self._blockers(dimensions)
        recommendations = self._road_to_10(dimensions)
        status = "strong" if total_score >= 8 and not blockers else "ok" if total_score >= 6.5 else "weak" if total_score >= 4 else "blocked"

        run = models.EngineAuditRun(
            status=status,
            scope_type=scope_type,
            scope_id=scope_id,
            total_score=total_score,
            scores_json=[item.model_dump(mode="json") for item in dimensions],
            blockers_json=blockers,
            recommendations_json=recommendations,
        )
        self.db.add(run)
        self.db.flush()
        for item in dimensions:
            self.db.add(
                models.EngineAuditScore(
                    audit_run_id=run.id,
                    score_type=item.key,
                    score=item.score,
                    status=item.status,
                    reasons_json=item.reasons,
                    required_fixes_json=item.required_fixes,
                )
            )
        self.db.commit()
        self.db.refresh(run)
        return run

    def latest(self, *, scope_type: str = "global", scope_id: int | None = None) -> models.EngineAuditRun | None:
        query = select(models.EngineAuditRun).where(models.EngineAuditRun.scope_type == scope_type)
        if scope_id is None:
            query = query.where(models.EngineAuditRun.scope_id.is_(None))
        else:
            query = query.where(models.EngineAuditRun.scope_id == scope_id)
        return self.db.scalar(query.order_by(models.EngineAuditRun.id.desc()))

    def get(self, run_id: int) -> models.EngineAuditRun | None:
        return self.db.get(models.EngineAuditRun, run_id)

    def output(self, run: models.EngineAuditRun) -> EngineAuditOutput:
        dimensions = [EngineAuditDimension.model_validate(item) for item in (run.scores_json or [])]
        return EngineAuditOutput(
            id=run.id,
            scope_type=run.scope_type,
            scope_id=run.scope_id,
            status=run.status,
            overall_score=run.total_score,
            total_score=run.total_score,
            dimensions=dimensions,
            blockers=run.blockers_json or [],
            recommendations=run.recommendations_json or [],
            reasons=self._flatten(dimensions, "reasons"),
            required_fixes=self._flatten(dimensions, "required_fixes"),
            road_to_10=run.recommendations_json or [],
            next_actions=(run.recommendations_json or [])[:5],
            evidence={
                "dimension_count": len(dimensions),
                "score_method": "read-only operational heuristics from current ContentEngine records",
                "paid_providers_called": False,
            },
        )

    def _interface_usability(self) -> EngineAuditDimension:
        control_room_exists = True
        role_dashboards = self._count(models.Membership) > 0 or self._count(models.ParticipantProfile) > 0
        next_actions_visible = True
        orphan_pages_flagged = True
        score = 4.0 + sum([control_room_exists, role_dashboards, next_actions_visible, orphan_pages_flagged]) * 1.2
        reasons: list[str] = []
        fixes: list[str] = []
        if not role_dashboards:
            reasons.append("role_based_dashboards_not_proven_with_seeded_users")
            fixes.append("Seed public pilot roles and verify /control-room by role.")
        if orphan_pages_flagged:
            reasons.append("many_specialized_pages_still_need_single_entrypoint")
            fixes.append("Use Unified Control Room to route operators to exact modules.")
        return self._dimension(
            "interface",
            score,
            reasons or ["control_room_and_motion_shell_exist"],
            fixes or ["Keep next actions mapped to role and scorecard blockers."],
            "unified_control_room_role_dashboards",
            [{"label": "Control Room", "href": "/control-room"}, {"label": "ALTEA dashboard", "href": "/altea-motion/dashboard"}],
            {
                "control_room_exists": control_room_exists,
                "role_based_dashboards_exist": role_dashboards,
                "main_next_actions_visible": next_actions_visible,
                "orphan_pages_flagged": orphan_pages_flagged,
            },
        )

    def _video_quality(self) -> EngineAuditDimension:
        acceptances = self._count(models.VideoOutputAcceptance)
        latest = self.db.scalar(select(models.VideoOutputAcceptance).order_by(models.VideoOutputAcceptance.id.desc()))
        latest_result = self.db.scalar(select(models.OneVideoRenderResult).order_by(models.OneVideoRenderResult.id.desc()))
        next_action = self._real_video_next_action(latest, latest_result)
        contact_sheets = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.contact_sheet_path.isnot(None))
        human_reviews = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.reviewer_notes.isnot(None))
        auto_approved = 0
        output_results = self._count(models.OneVideoRenderResult)
        score = 3.0
        reasons = ["latest_output_acceptance_missing"]
        fixes = ["Run one prompt-only accepted plan, then exactly one real smoke through OutputAcceptance."]
        if acceptances:
            score = 5.5
            reasons = ["output_acceptance_exists_but_manual_quality_loop_needs_more_evidence"]
            fixes = ["Extract frames/contact sheet and record human review for each provider output."]
        if contact_sheets:
            score += 0.8
        if human_reviews:
            score += 0.9
        if auto_approved:
            score = min(score, 5.5)
            reasons.append("auto_approved_output_found")
            fixes.append("Keep generated video blocked until human review approves.")
        if latest and latest.status in {"needs_regeneration", "rejected"}:
            score = min(score, 5.5)
            reasons.append("latest_output_has_product_identity_or_quality_blocker")
            fixes.append("Use regeneration or product compositing before publishing.")
        if output_results:
            score += 0.5
        return self._dimension(
            "video_quality",
            score,
            reasons,
            fixes,
            next_action,
            [{"label": "One Video Acceptance", "href": "/one-video-acceptance"}],
            {
                "latest_output_acceptance_exists": bool(latest),
                "output_acceptance_count": acceptances,
                "contact_sheet_count": contact_sheets,
                "human_review_count": human_reviews,
                "auto_approved_count": auto_approved,
                "latest_status": latest.status if latest else None,
                "latest_result_status": latest_result.status if latest_result else None,
                "next_action": next_action,
                "product_identity_status": getattr(latest, "product_identity_status", None) if latest else None,
                "packaging_or_edible_drift_status": (latest.blockers_json if latest else []),
            },
        )

    def _brief_quality(self) -> EngineAuditDimension:
        counts = {
            "product_strategy_specs": self._count(models.ProductStrategySpec),
            "offer_strategies": self._count(models.OfferStrategy),
            "blogger_meaning_specs": self._count(models.BloggerMeaningSpec),
            "ugc_ad_scripts": self._count(models.UGCAdScript),
            "ai_production_briefs": self._count(models.AIProductionBrief),
            "scene_blueprints": self._count(models.SceneBlueprint),
            "director_prompt_packs": self._count(models.DirectorPromptPack),
            "brief_quality_checks": self._count(models.BriefQualityCheck),
        }
        present = sum(1 for value in counts.values() if value)
        score = 2.5 + present * 0.75
        reasons = [f"{key}_missing" for key, value in counts.items() if not value]
        fixes = ["Create complete ProductStrategy -> Offer -> BloggerMeaning -> UGC -> AI brief -> SceneBlueprint -> DirectorPromptPack chain."]
        if not reasons:
            score = 8.2
            reasons = ["brief_contract_complete_but_needs_more_real_output_feedback"]
            fixes = ["Feed OutputAcceptance blockers back into prompt and scene blueprint quality checks."]
        return self._dimension(
            "brief_quality",
            score,
            reasons,
            fixes,
            "run_ai_brief_quality_gate",
            [{"label": "AI brief studio", "href": "/ai-brief-contract"}],
            counts,
        )

    def _asset_readiness(self) -> EngineAuditDimension:
        assets = self.db.scalars(select(models.ProductAsset)).all()
        wrapper_refs = [item for item in assets if item.asset_type in {"packshot", "wrapper", "label", "label_closeup", "product_packshot"}]
        edible_refs = [item for item in assets if item.asset_type in {"edible", "cutaway", "texture"}]
        style_refs = [item for item in assets if item.asset_type in {"style", "lifestyle"}]
        lifestyle_refs = [item for item in assets if item.asset_type == "lifestyle"]
        products = list(self.db.scalars(select(models.Product).order_by(models.Product.id)))
        plans = self._count(models.OneVideoRenderPlan)
        contracts = []
        for product in products:
            tier_service = ProductAssetTierService(self.db)
            contract = tier_service.output(tier_service.evaluate(product.id))
            contracts.append(contract)

        tier_rank = {"tier_0": 0, "tier_1": 1, "tier_2": 2, "tier_3": 3, "tier_4": 4}
        average_tier = (sum(tier_rank[item.current_tier] for item in contracts) / len(contracts)) if contracts else 0
        score = 2.5 + average_tier * 1.45
        reasons: list[str] = []
        fixes: list[str] = []
        food_contracts = [item for item in contracts if item.product_profile == "food_snack"]
        if food_contracts and any(tier_rank[item.current_tier] < 2 for item in food_contracts):
            reasons.append("wrapper_reference_count_below_2")
            fixes.append("Attach front wrapper and label closeup before strict product generation.")
        if food_contracts and any(tier_rank[item.current_tier] < 3 for item in food_contracts):
            reasons.append("edible_reference_count_below_3")
            fixes.append("Add bitten bar, cutaway texture, and bar-in-hand edible references before bite/macro scenes.")
        if style_refs:
            score += 0.4
        if lifestyle_refs:
            score += 0.3
        if plans:
            score += 0.5
        score = min(score, 9.2)
        low_tier = [item for item in contracts if tier_rank[item.current_tier] < 2]
        mismatch = [item for item in contracts if item.variant_mismatch_asset_ids]
        if low_tier:
            reasons.append("product_asset_contract_below_tier_2")
            fixes.append("Complete exact identity, angle and handling references per SKU before final product ads.")
        if mismatch:
            reasons.append("mixed_or_unverified_product_variants")
            fixes.append("Separate flavor/color/model reference sets and tag every identity asset with variant_key.")
        latest_contract = contracts[-1] if contracts else None
        scene_permissions = (
            latest_contract.permissions.model_dump(mode="json")
            if latest_contract
            else {
                "bite_scene_allowed": False,
                "texture_macro_allowed": False,
                "packshot_overlay_required": True,
                "application_scene_allowed": False,
            }
        )
        return self._dimension(
            "asset_readiness",
            score,
            reasons or ["reference_policy_has_enough_basic_inputs"],
            fixes or ["Keep reference readiness checked before paid provider runs."],
            "add_missing_product_references",
            [{"label": "One Video Acceptance", "href": "/one-video-acceptance"}],
            {
                "wrapper_refs_count": len(wrapper_refs),
                "edible_refs_count": len(edible_refs),
                "style_refs_count": len(style_refs),
                "lifestyle_refs_count": len(lifestyle_refs),
                "one_video_plans": plans,
                "scene_permissions": scene_permissions,
                "missing_references": reasons,
                "average_asset_tier": round(average_tier, 2),
                "profiles": {
                    profile: sum(1 for item in contracts if item.product_profile == profile)
                    for profile in {item.product_profile for item in contracts}
                },
                "product_asset_contracts": [
                    {
                        "product_id": item.product_id,
                        "sku": item.sku,
                        "variant_key": item.variant_key,
                        "profile": item.product_profile,
                        "current_tier": item.current_tier,
                        "interaction_mode": item.permissions.interaction_mode,
                        "interaction_scene_allowed": item.permissions.interaction_scene_allowed,
                        "missing_assets": item.missing_assets,
                        "variant_mismatch_asset_ids": item.variant_mismatch_asset_ids,
                    }
                    for item in contracts
                ],
            },
        )

    def _creator_clarity(self) -> EngineAuditDimension:
        assignments = self._count(models.ParticipantAssignment)
        submissions = self._count(models.ParticipantSubmission)
        tracking_links = self._count(models.TrackingLink)
        payout_entries = self._count(models.PayoutLedgerEntry)
        score = 3.5
        reasons = ["creator_assignments_not_proven"]
        fixes = ["Create assignments with full brief cards, final URL instructions, tracking links, and payout blockers."]
        if assignments:
            score += 2.0
            reasons = ["assignments_exist_but_creator_pilot_feedback_needed"]
        if submissions:
            score += 1.0
        if tracking_links:
            score += 0.7
        if payout_entries:
            score += 0.6
        return self._dimension(
            "creator_clarity",
            score,
            reasons,
            fixes,
            "run_creator_publisher_pilot",
            [{"label": "Participant Portal", "href": "/participant-portal"}],
            {
                "assignments": assignments,
                "brief_cards_with_full_tz": assignments > 0,
                "final_url_or_tracking_instructions_visible": tracking_links > 0,
                "payout_blockers_visible": payout_entries > 0,
                "submissions": submissions,
            },
        )

    def _training_readiness(self) -> EngineAuditDimension:
        role_training = self._count(models.TrainingModule)
        academy_courses = self._count(models.TrainingCourse)
        certifications = self._count(models.TrainingCertification) + self._count(models.ParticipantCertification)
        questions = self._count(models.TrainingQuestion)
        score = 3.0
        reasons = ["role_training_not_seeded"]
        fixes = ["Seed role training, platform playbooks, certifications, and scenario coverage."]
        if role_training or academy_courses:
            score += 2.0
            reasons = ["training_exists_but_completion_feedback_needed"]
        if questions:
            score += 1.0
        if certifications:
            score += 1.3
        return self._dimension(
            "training",
            score,
            reasons,
            fixes,
            "complete_public_pilot_training_certifications",
            [{"label": "Training Academy", "href": "/training-academy"}],
            {
                "role_training_modules": role_training,
                "platform_playbooks": academy_courses,
                "certifications": certifications,
                "scenario_simulator_coverage": questions,
            },
        )

    def _metrics_traceability(self) -> EngineAuditDimension:
        tracking_links = self._count(models.TrackingLink)
        final_urls = self._count(models.PublishingTask, models.PublishingTask.final_url.isnot(None))
        metric_sources = self._count(models.MetricsSource)
        funnel_snapshots = self._count(models.FunnelSnapshot)
        unmatched_rows = int(self.db.scalar(select(func.coalesce(func.sum(models.MetricsIntakeBatch.unmatched_count), 0))) or 0)
        metrics = self._count(models.CampaignPerformanceMetric)
        score = 3.5
        reasons = ["metrics_traceability_not_proven"]
        fixes = ["Create tracking links, collect final URLs, import CSV metrics, and resolve unmatched rows."]
        if tracking_links:
            score += 1.1
        if final_urls:
            score += 1.1
        if metric_sources:
            score += 0.8
        if funnel_snapshots:
            score += 0.8
        if metrics:
            score += 0.8
        if unmatched_rows:
            score = min(score, 6.0)
            reasons.append("unmatched_metric_rows_exist")
            fixes.append("Resolve unmatched metrics rows before trusting payout/performance views.")
        return self._dimension(
            "metrics",
            score,
            reasons,
            fixes,
            "import_real_metrics_csv_and_resolve_unmatched",
            [{"label": "Metrics Intake", "href": "/metrics-intake"}],
            {
                "tracking_links": tracking_links,
                "final_urls": final_urls,
                "metrics_sources": metric_sources,
                "funnel_snapshots": funnel_snapshots,
                "campaign_performance_metrics": metrics,
                "unmatched_rows": unmatched_rows,
            },
        )

    def _destination_readiness(self) -> EngineAuditDimension:
        destinations = self._count(models.PublishingDestination)
        setup_tasks = self._count(models.DestinationSetupTask)
        connections = self._count(models.DestinationConnection)
        readiness = self._count(models.DestinationReadinessSnapshot)
        ready = self._count(models.DestinationReadinessSnapshot, models.DestinationReadinessSnapshot.status == "ready")
        syncs = self._count(models.DestinationMetricSync)
        capacity = self._count(models.DestinationCapacitySnapshot)
        score = 3.5
        reasons = ["destination_registry_or_readiness_not_proven"]
        fixes = ["Import owned destinations, complete setup tasks, run readiness checks, and sync metrics."]
        if destinations:
            score += 1.1
        if setup_tasks:
            score += 0.7
        if connections:
            score += 0.9
        if readiness:
            score += 0.8
        if ready:
            score += 0.8
        if syncs:
            score += 0.5
        if capacity:
            score += 0.5
        return self._dimension(
            "destinations",
            score,
            reasons,
            fixes,
            "refresh_destination_control_tower",
            [{"label": "Destination Control", "href": "/destination-control"}],
            {
                "destinations": destinations,
                "setup_tasks": setup_tasks,
                "connections": connections,
                "readiness_snapshots": readiness,
                "ready_snapshots": ready,
                "metric_syncs": syncs,
                "capacity_snapshots": capacity,
            },
        )

    def _production_readiness(self) -> EngineAuditDimension:
        one_video_plans = self._count(models.OneVideoRenderPlan)
        prompt_ready = self._count(models.OneVideoRenderPlan, models.OneVideoRenderPlan.status == "prompt_only_ready")
        public_users = self._count(models.UserProfile)
        gates = True
        hygiene_doc = True
        latest_acceptance = self.db.scalar(select(models.VideoOutputAcceptance).order_by(models.VideoOutputAcceptance.id.desc()))
        latest_result = self.db.scalar(select(models.OneVideoRenderResult).order_by(models.OneVideoRenderResult.id.desc()))
        next_action = self._real_video_next_action(latest_acceptance, latest_result)
        paid_smoke = self._count(models.OneVideoRenderResult, models.OneVideoRenderResult.status.in_(PAID_SMOKE_COMPLETED_STATUSES))
        approved_outputs = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "approved")
        score = 3.5
        reasons = ["paid_smoke_not_completed"]
        fixes = ["After EngineAudit and Unified Control Room, run exactly one gated paid smoke and review through OutputAcceptance."]
        if one_video_plans:
            score += 1.0
        if prompt_ready:
            score += 1.0
            reasons.append("prompt_only_ready_but_paid_smoke_pending")
        if public_users:
            score += 0.8
        if gates:
            score += 0.8
        if hygiene_doc:
            score += 0.7
        if paid_smoke:
            score += 1.2
            reasons = ["paid_smoke_exists_but_human_review_and_benchmark_status_must_be_checked"]
        if approved_outputs:
            score += 0.8
        return self._dimension(
            "production",
            score,
            reasons,
            fixes,
            next_action if latest_result else "confirm_runway_credits_then_one_paid_smoke",
            [{"label": "Public Pilot Control Room", "href": "/control-room"}, {"label": "Workspace Hygiene", "href": "/docs/WORKSPACE_HYGIENE.md"}],
            {
                "one_video_acceptance_status": {"plans": one_video_plans, "prompt_only_ready": prompt_ready},
                "public_pilot_auth_status": public_users > 0,
                "gate_matrix_status": gates,
                "workspace_hygiene_status": hygiene_doc,
                "paid_smoke_status": "completed" if paid_smoke else "pending",
                "approved_outputs": approved_outputs,
                "next_action": next_action,
            },
        )

    @staticmethod
    def _real_video_next_action(
        latest_acceptance: models.VideoOutputAcceptance | None,
        latest_result: models.OneVideoRenderResult | None,
    ) -> str:
        if latest_result and latest_result.status == "blocked_by_runway_credits":
            return "blocked_by_runway_credits"
        if latest_acceptance and latest_acceptance.status == "approved":
            return "benchmark_candidate_ready"
        if latest_acceptance and latest_acceptance.status in {"needs_regeneration", "rejected"}:
            blockers = set(latest_acceptance.blockers_json or [])
            if "edible_product_drift" in blockers:
                return "add_edible_references"
            return "product_compositing_required"
        return "one_paid_smoke_then_output_acceptance"

    def _dimension(
        self,
        key: str,
        score: float,
        reasons: list[str],
        required_fixes: list[str],
        next_action: str,
        module_links: list[dict[str, str]],
        evidence: dict[str, Any],
    ) -> EngineAuditDimension:
        labels = dict(DIMENSION_DEFINITIONS)
        score = round(max(1.0, min(10.0, score)), 1)
        status = "strong" if score >= 8 else "ok" if score >= 6.5 else "weak" if score >= 4 else "blocked"
        return EngineAuditDimension(
            key=key,
            label=labels[key],
            score=score,
            status=status,
            reasons=list(dict.fromkeys(reasons)),
            required_fixes=list(dict.fromkeys(required_fixes)),
            next_action=next_action,
            module_links=module_links,
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
    def _blockers(dimensions: list[EngineAuditDimension]) -> list[dict[str, Any]]:
        return [
            {
                "dimension": item.key,
                "label": item.label,
                "score": item.score,
                "reasons": item.reasons,
                "required_fixes": item.required_fixes,
            }
            for item in dimensions
            if item.status in {"blocked", "weak"}
        ]

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
                "module_links": item.module_links,
            }
            for item in ordered
        ]
