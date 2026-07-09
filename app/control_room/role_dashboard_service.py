from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.control_room.types import ControlRoomItem


class ControlRoomRoleDashboardService:
    def __init__(self, db: Session):
        self.db = db

    def dashboard(self, role: str) -> dict[str, list[ControlRoomItem]]:
        method = getattr(self, f"_{role}", None) or self._owner
        return method()

    def _owner(self) -> dict[str, list[ControlRoomItem]]:
        return {
            "ready": [
                self._item("Engine scorecard available", "engine_audit", "/engine-audit", detail="Production readiness is measurable."),
            ],
            "blocked": self._audit_blockers(),
            "review": self._review_queue(),
        }

    def _content_lead(self) -> dict[str, list[ControlRoomItem]]:
        products_needing_strategy = max(0, self._count(models.Product) - self._count(models.ProductStrategySpec))
        weak_briefs = self._count(models.BriefQualityCheck, models.BriefQualityCheck.status != "passed")
        plans_ready = self._count(models.OneVideoRenderPlan, models.OneVideoRenderPlan.status.in_(["plan_ready", "prompt_only_ready"]))
        prompt_only_ready = self._count(models.OneVideoRenderPlan, models.OneVideoRenderPlan.status == "prompt_only_ready")
        approved_candidates = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "approved")
        regeneration_needed = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.status == "needs_regeneration")
        missing_refs = max(0, self._count(models.Product) - self._count(models.ProductAsset))
        return {
            "ready": [
                self._item(f"{plans_ready} one-video plans ready", "one_video_acceptance", "/one-video-acceptance", status="ready"),
                self._item(f"{prompt_only_ready} prompt-only ready items", "one_video_acceptance", "/one-video-acceptance", status="ready"),
                self._item(f"{approved_candidates} approved candidates", "output_acceptance", "/output-acceptance", status="ready"),
            ],
            "blocked": [
                self._item(f"{products_needing_strategy} products needing strategy", "product_strategy", "/product-strategy"),
                self._item(f"{weak_briefs} weak AI briefs", "ai_brief_studio", "/ai-brief-studio", severity="high"),
                self._item(f"{missing_refs} products missing references", "one_video_acceptance", "/one-video-acceptance"),
                self._item(f"{regeneration_needed} videos needing regeneration", "output_acceptance", "/output-acceptance", severity="high" if regeneration_needed else "normal"),
            ],
            "review": self._review_queue(),
        }

    def _campaign_operator(self) -> dict[str, list[ControlRoomItem]]:
        open_actions = self._count(models.CampaignActionQueueItem, models.CampaignActionQueueItem.status == "open")
        safe_actions = self._count(models.CampaignActionQueueItem, models.CampaignActionQueueItem.safe_to_execute.is_(True))
        publishing_ready = self._count(models.PublishingPackage, models.PublishingPackage.status == "approved")
        return {
            "ready": [self._item(f"{safe_actions} safe campaign actions", "campaign_execution", "/campaign-execution", status="ready")],
            "blocked": [self._item(f"{open_actions} open campaign actions", "campaign_execution", "/campaign-execution")],
            "review": [self._item(f"{publishing_ready} approved packages ready for publishing", "publishing", "/publishing")],
        }

    def _reviewer(self) -> dict[str, list[ControlRoomItem]]:
        identity_failures = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.product_identity_status.in_(["fail", "failed", "mismatch", "rejected"]))
        packaging_drift = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.packaging_status.in_(["fail", "failed", "drift", "mismatch", "rejected"]))
        edible_drift = self._count(models.VideoOutputAcceptance, models.VideoOutputAcceptance.blockers_json.like("%muesli%"))
        return {
            "ready": [
                self._item("Approve / reject / needs_regeneration links available", "output_acceptance", "/output-acceptance", status="ready"),
            ],
            "blocked": [
                self._item(f"{identity_failures} product identity failures", "output_acceptance", "/output-acceptance", severity="high" if identity_failures else "normal"),
                self._item(f"{packaging_drift} packaging drift items", "output_acceptance", "/output-acceptance", severity="high" if packaging_drift else "normal"),
                self._item(f"{edible_drift} edible identity or muesli/granola drift items", "output_acceptance", "/output-acceptance", severity="high" if edible_drift else "normal"),
                *self._regeneration_items(),
            ],
            "review": self._review_queue(),
        }

    def _creator_publisher(self) -> dict[str, list[ControlRoomItem]]:
        assignments = self._count(models.ParticipantAssignment, models.ParticipantAssignment.status.in_(["assigned", "in_progress"]))
        briefs = self._count(models.ParticipantAssignment)
        training_blockers = self._count(models.ParticipantProfile) - self._count(models.ParticipantCertification)
        missing_final_url = self._count(models.ParticipantSubmission, models.ParticipantSubmission.final_post_url.is_(None))
        missing_stats = self._count(models.ParticipantSubmission, models.ParticipantSubmission.final_post_url.isnot(None)) - self._count(models.CampaignPerformanceMetric)
        payout_blockers = self._count(models.PayoutLedgerEntry, models.PayoutLedgerEntry.status != "payable")
        return {
            "ready": [
                self._item(f"{assignments} my assignments", "participant_portal", "/participant-portal", status="ready"),
                self._item(f"{briefs} brief cards", "participant_portal", "/participant-portal", status="ready"),
            ],
            "blocked": [
                self._item(f"{max(0, training_blockers)} training blockers", "training", "/training-academy"),
                self._item(f"{missing_final_url} submissions missing final_url", "participant_portal", "/participant-portal", severity="high"),
                self._item(f"{max(0, missing_stats)} submissions missing stats", "metrics_intake", "/metrics-intake"),
                self._item(f"{payout_blockers} payout blockers", "participant_portal", "/participant-portal"),
            ],
            "review": [self._item("Next action is routed from Control Room", "participant_portal", "/participant-portal", status="ready")],
        }

    def _metrics_operator(self) -> dict[str, list[ControlRoomItem]]:
        unmatched = int(self.db.scalar(select(func.coalesce(func.sum(models.MetricsIntakeBatch.unmatched_count), 0))) or 0)
        missing_stats = self._count(models.PublishingTask, models.PublishingTask.final_url.isnot(None)) - self._count(models.CampaignPerformanceMetric)
        destinations_without_stats = max(0, self._count(models.PublishingDestination) - self._count(models.DestinationPostMetric))
        final_url_tasks = self._count(models.PublishingTask, models.PublishingTask.final_url.isnot(None))
        metric_rows = self._count(models.CampaignPerformanceMetric)
        funnel_coverage = round((metric_rows / final_url_tasks) * 100, 1) if final_url_tasks else 0
        return {
            "ready": [
                self._item("CSV import actions available", "metrics_intake", "/metrics-intake", status="ready"),
                self._item(f"{funnel_coverage}% funnel coverage", "metrics_intake", "/metrics-intake", status="ready"),
            ],
            "blocked": [
                self._item(f"{unmatched} unmatched metric rows", "metrics_intake", "/metrics-intake", severity="high"),
                self._item(f"{max(0, missing_stats)} publications missing metrics", "metrics_intake", "/metrics-intake"),
                self._item(f"{destinations_without_stats} destinations without stats", "destination_control", "/destination-control"),
                self._item(f"{unmatched + max(0, missing_stats) + destinations_without_stats} metrics blockers", "metrics_intake", "/metrics-intake", severity="high"),
            ],
            "review": [],
        }

    def _audit_blockers(self) -> list[ControlRoomItem]:
        run = self.db.scalar(select(models.EngineAuditRun).order_by(models.EngineAuditRun.id.desc()))
        return [
            self._item(item.get("label", item.get("dimension", "Audit blocker")), "engine_audit", "/engine-audit", detail=", ".join(item.get("reasons") or []), severity="high")
            for item in ((run.blockers_json if run else []) or [])
        ]

    def _review_queue(self) -> list[ControlRoomItem]:
        acceptances = self.db.scalars(
            select(models.VideoOutputAcceptance).where(models.VideoOutputAcceptance.status.in_(["needs_human_review", "needs_regeneration"]))
        ).all()
        return [
            self._item(
                f"OutputAcceptance #{item.id}: {item.status}",
                "output_acceptance",
                "/output-acceptance",
                detail=", ".join(item.blockers_json or []) or item.product_identity_status,
                severity="high" if item.status == "needs_regeneration" else "normal",
                payload={"output_acceptance_id": item.id},
            )
            for item in acceptances
        ]

    def _regeneration_items(self) -> list[ControlRoomItem]:
        requests = self.db.scalars(select(models.SceneRegenerationRequest).where(models.SceneRegenerationRequest.status == "requested")).all()
        return [
            self._item(f"Regeneration request #{item.id}", "output_acceptance", "/output-acceptance", detail=item.reason, severity="high")
            for item in requests
        ]

    def _count(self, model, *criteria) -> int:
        stmt = select(func.count()).select_from(model)
        for item in criteria:
            stmt = stmt.where(item)
        return int(self.db.scalar(stmt) or 0)

    @staticmethod
    def _item(label: str, target_module: str, target_url: str, *, status: str = "open", detail: str | None = None, severity: str = "normal", payload: dict | None = None) -> ControlRoomItem:
        return ControlRoomItem(label=label, status=status, detail=detail, target_module=target_module, target_url=target_url, severity=severity, payload=payload or {})
