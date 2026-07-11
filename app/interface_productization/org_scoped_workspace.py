from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app import models
from app.control_room.types import (
    ControlRoomActionOutput,
    ControlRoomItem,
    ControlRoomSnapshotOutput,
)


@dataclass(frozen=True)
class OrganizationWorkspaceState:
    control: ControlRoomSnapshotOutput
    latest_product: models.Product | None
    latest_draft: models.ProductUGCRecipeDraft | None
    latest_cycle: models.ContentCycle | None


class OrganizationWorkspaceComposer:
    """Compose strict-mode navigation without reading legacy global snapshots.

    A canonical cycle is considered owned only when its explicit organization,
    product organization and video-job organization all agree. Drafts are
    reached through an owned Product join; no SKU or "latest row" inference is
    used to claim legacy data for a tenant.
    """

    REVIEW_STATUSES = {
        "needs_human_review",
        "needs_review",
        "needs_regeneration",
    }
    BLOCKED_DRAFT_STATUSES = {
        "blocked",
        "failed",
        "provider_failed",
        "quarantined",
    }
    BLOCKED_MODULE_STATUSES = {
        "blocked",
        "needs_attention",
        "needs_data",
        "needs_review",
    }

    def __init__(self, db: Session):
        self.db = db

    def build(
        self,
        *,
        organization_id: int,
        role: str,
        factory_dashboard: dict[str, object],
    ) -> OrganizationWorkspaceState:
        if not organization_id:
            raise ValueError("organization_id_required_for_strict_workspace")

        cycle_rows = self.db.execute(
            select(models.ContentCycle, models.Product)
            .join(
                models.Product,
                and_(
                    models.Product.id == models.ContentCycle.product_id,
                    models.Product.organization_id
                    == models.ContentCycle.organization_id,
                ),
            )
            .join(
                models.VideoJob,
                models.VideoJob.id == models.ContentCycle.video_job_id,
            )
            .where(
                models.ContentCycle.organization_id == organization_id,
                models.Product.organization_id == organization_id,
                models.VideoJob.organization_id == organization_id,
            )
            .order_by(
                models.ContentCycle.updated_at.desc(),
                models.ContentCycle.id.desc(),
            )
            .limit(50)
        ).all()
        latest_cycle = cycle_rows[0][0] if cycle_rows else None

        draft_row = self.db.execute(
            select(models.ProductUGCRecipeDraft, models.Product)
            .join(
                models.Product,
                models.Product.id == models.ProductUGCRecipeDraft.product_id,
            )
            .where(models.Product.organization_id == organization_id)
            .order_by(
                models.ProductUGCRecipeDraft.updated_at.desc(),
                models.ProductUGCRecipeDraft.id.desc(),
            )
            .limit(1)
        ).first()
        latest_draft = draft_row[0] if draft_row else None

        if cycle_rows:
            latest_product = cycle_rows[0][1]
        elif draft_row:
            latest_product = draft_row[1]
        else:
            latest_product = self.db.scalar(
                select(models.Product)
                .where(models.Product.organization_id == organization_id)
                .order_by(models.Product.updated_at.desc(), models.Product.id.desc())
            )

        review_queue = self._review_queue(cycle_rows, latest_draft)
        ready_items, blocked_items = self._module_items(factory_dashboard)
        blocked_items.extend(self._draft_blockers(latest_draft))

        metrics = dict(factory_dashboard.get("metrics") or {})
        module_count = max(len(factory_dashboard.get("modules") or []), 1)
        ready_count = len(
            [
                module
                for module in (factory_dashboard.get("modules") or [])
                if str(module.get("status")) == "ready"
            ]
        )
        total_score = round((ready_count / module_count) * 10, 1)
        reviews_waiting = int(metrics.get("reviews_waiting") or 0)
        approved_videos = int(metrics.get("approved_videos") or 0)
        if reviews_waiting:
            video_quality_score = 5.0
            video_quality_status = "needs_review"
        elif approved_videos:
            video_quality_score = 10.0
            video_quality_status = "ready"
        else:
            video_quality_score = 0.0
            video_quality_status = "not_started"
        metrics_coverage = 100.0 if int(metrics.get("metric_rows") or 0) else 0.0

        if review_queue:
            overall_status = "needs_review"
            next_action = ControlRoomActionOutput(
                action_type="review_output",
                role=role,
                target_module="output_acceptance",
                target_url="/workbench?tab=video-quality",
                status="open",
                safe_to_execute=True,
                requires_human=True,
                requires_spend_gate=False,
                reason="organization_owned_content_cycle_requires_human_review",
            )
        elif blocked_items:
            overall_status = "blocked"
            next_action = ControlRoomActionOutput(
                action_type="open_mvp_launch",
                role=role,
                target_module="mvp_launch",
                target_url="/mvp-launch",
                status="open",
                safe_to_execute=True,
                requires_human=True,
                requires_spend_gate=False,
                reason="organization_owned_workflow_has_blockers",
            )
        else:
            overall_status = "ready"
            next_action = ControlRoomActionOutput(
                action_type="open_mvp_launch",
                role=role,
                target_module="mvp_launch",
                target_url="/mvp-launch",
                status="open",
                safe_to_execute=True,
                requires_human=True,
                requires_spend_gate=False,
                reason="continue_organization_owned_content_cycle",
            )

        summary = {
            "engine_audit_total_score": total_score,
            "dimension_scores": {
                "video_quality": {
                    "score": video_quality_score,
                    "status": video_quality_status,
                }
            },
            "metrics_coverage": {"coverage_percent": metrics_coverage},
            "paid_smoke_status": "not_used_in_strict_mode",
            "factory_metrics": metrics,
        }
        control = ControlRoomSnapshotOutput(
            # No global ControlRoomSnapshot row is read or created in strict mode.
            id=0,
            scope_type="organization",
            scope_id=organization_id,
            role=role,
            overall_status=overall_status,
            engine_audit_run_id=None,
            summary=summary,
            scorecard={"factory_dashboard": factory_dashboard},
            ready_items=ready_items,
            blocked_items=blocked_items,
            review_queue=review_queue,
            safe_actions=[next_action],
            gated_actions=[],
            next_actions=[next_action],
        )
        return OrganizationWorkspaceState(
            control=control,
            latest_product=latest_product,
            latest_draft=latest_draft,
            latest_cycle=latest_cycle,
        )

    def _review_queue(
        self,
        cycle_rows: list[tuple[models.ContentCycle, models.Product]],
        latest_draft: models.ProductUGCRecipeDraft | None,
    ) -> list[ControlRoomItem]:
        queue: list[ControlRoomItem] = []
        cycle_draft_ids: set[int] = set()
        for cycle, product in cycle_rows:
            cycle_draft_ids.add(cycle.product_ugc_recipe_draft_id)
            if cycle.output_acceptance_id is not None:
                continue
            queue.append(
                ControlRoomItem(
                    label=f"{product.sku}: video requires human review",
                    status="needs_review",
                    detail="Review the exact organization-owned video before distribution.",
                    target_module="output_acceptance",
                    target_url="/workbench?tab=video-quality",
                    severity="needs_review",
                    payload={
                        "content_cycle_id": cycle.id,
                        "product_id": product.id,
                        "sku": product.sku,
                        "video_job_id": cycle.video_job_id,
                    },
                )
            )

        if (
            latest_draft is not None
            and latest_draft.id not in cycle_draft_ids
            and latest_draft.human_review_status in self.REVIEW_STATUSES
        ):
            queue.append(
                ControlRoomItem(
                    label=f"{latest_draft.sku}: generated draft requires review",
                    status="needs_review",
                    detail="Review this organization-owned generated output.",
                    target_module="output_acceptance",
                    target_url="/workbench?tab=video-quality",
                    severity="needs_review",
                    payload={
                        "recipe_draft_id": latest_draft.id,
                        "product_id": latest_draft.product_id,
                        "sku": latest_draft.sku,
                    },
                )
            )
        return queue

    def _module_items(
        self,
        factory_dashboard: dict[str, object],
    ) -> tuple[list[ControlRoomItem], list[ControlRoomItem]]:
        ready: list[ControlRoomItem] = []
        blocked: list[ControlRoomItem] = []
        for module in factory_dashboard.get("modules") or []:
            item = ControlRoomItem(
                label=str(module.get("label") or module.get("key") or "module"),
                status=str(module.get("status") or "not_started"),
                detail=str(module.get("summary") or ""),
                target_module=str(module.get("key") or "workbench"),
                target_url=str(module.get("url") or "/workbench"),
                severity=(
                    "blocker"
                    if str(module.get("status")) in self.BLOCKED_MODULE_STATUSES
                    else "normal"
                ),
                payload={},
            )
            if str(module.get("status")) == "ready":
                ready.append(item)
            elif str(module.get("status")) in self.BLOCKED_MODULE_STATUSES:
                blocked.append(item)
        return ready, blocked

    def _draft_blockers(
        self,
        draft: models.ProductUGCRecipeDraft | None,
    ) -> list[ControlRoomItem]:
        if draft is None:
            return []
        blockers = list(draft.blockers_json or [])
        if draft.status not in self.BLOCKED_DRAFT_STATUSES and not blockers:
            return []
        detail = ", ".join(str(item) for item in blockers[:4]) or str(draft.status)
        return [
            ControlRoomItem(
                label=f"{draft.sku}: generation requires attention",
                status="blocked",
                detail=detail,
                target_module="runway_product_ugc",
                target_url="/workbench?tab=video",
                severity="blocker",
                payload={
                    "recipe_draft_id": draft.id,
                    "product_id": draft.product_id,
                    "provider_status": draft.provider_status,
                },
            )
        ]
