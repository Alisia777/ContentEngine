from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.control_room import ControlRoomSnapshotService
from app.interface_productization.factory_dashboard_service import FactoryDashboardService
from app.interface_productization.mvp_navigation_service import MVPNavigationService
from app.interface_productization.types import MVPAction, MVPModuleLink, MVPWorkspaceSnapshotOutput
from app.smoke_readiness import ReadinessReportService
from app.product_asset_contract import ProductAssetTierService, ReferenceRequirementService


class MVPWorkspaceService:
    """Composes existing audit, control-room and readiness outputs for the product UI."""

    def __init__(self, db: Session):
        self.db = db
        self.navigation = MVPNavigationService()
        self.settings = get_settings()

    def build(self, *, role: str = "owner", user_profile_id: int | None = None) -> models.MVPWorkspaceSnapshot:
        control_service = ControlRoomSnapshotService(self.db)
        control = control_service.output(control_service.refresh(role=role))
        smoke_service = ReadinessReportService(self.db)
        smoke_run = smoke_service.latest()
        smoke = smoke_service.output(smoke_run) if smoke_run else None
        asset_contract = self._latest_asset_contract(smoke.product_id if smoke else None)
        primary = self.navigation.primary_action(control, smoke, asset_contract)
        blockers = self.navigation.blockers(control, smoke, asset_contract)
        status = "blocked" if any(item.severity == "blocker" for item in blockers) else "ready"
        if control.review_queue:
            status = "needs_review"

        factory_dashboard = FactoryDashboardService(self.db).snapshot(user_profile_id=user_profile_id)
        modules = self._module_links(factory_dashboard)
        secondary = [
            MVPAction(
                action_type="open_workbench",
                label="Открыть рабочую область",
                url="/workbench",
                detail="Вся готовность SKU в одном месте.",
            ),
            MVPAction(
                action_type="check_access",
                label="Проверить доступ",
                url="/settings/access",
                detail="Роли, сертификаты и spend gates.",
            ),
        ]
        context = {
            "engine_score": control.summary.get("engine_audit_total_score"),
            "video_quality": (control.summary.get("dimension_scores") or {}).get("video_quality", {}),
            "paid_smoke_status": control.summary.get("paid_smoke_status"),
            "ready_count": len(control.ready_items),
            "blocked_count": len(control.blocked_items),
            "review_count": len(control.review_queue),
            "review_queue": self._review_queue(control.review_queue),
            "provider_failures": [
                item.model_dump(mode="json")
                for item in control.blocked_items
                if item.target_module == "runway_product_ugc"
            ],
            "smoke_decision": smoke.report.final_decision if smoke else "not_checked",
            "product_id": smoke.product_id if smoke else None,
            "sku": smoke.sku if smoke else None,
            "product_asset_contract": asset_contract,
            "factory_dashboard": factory_dashboard,
            "technical": {
                "engine_audit_run_id": control.engine_audit_run_id,
                "control_room_snapshot_id": control.id,
                "smoke_readiness_run_id": smoke.id if smoke else None,
            },
        }
        record = models.MVPWorkspaceSnapshot(
            role=role,
            status=status,
            current_step=primary.action_type,
            primary_action_json=primary.model_dump(mode="json"),
            secondary_actions_json=[item.model_dump(mode="json") for item in secondary],
            blockers_json=[item.model_dump(mode="json") for item in blockers],
            module_links_json=[item.model_dump(mode="json") for item in modules],
            context_json=context,
            control_room_snapshot_id=control.id,
            smoke_readiness_run_id=smoke.id if smoke else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _review_queue(self, items) -> list[dict]:
        queue: list[dict] = []
        for item in items:
            output = item.model_dump(mode="json")
            payload = output.get("payload") or {}
            acceptance_id = payload.get("output_acceptance_id")
            recipe_draft_id = payload.get("recipe_draft_id")
            if acceptance_id:
                acceptance = self.db.get(models.VideoOutputAcceptance, acceptance_id)
                video_job = self.db.get(models.VideoJob, acceptance.video_job_id) if acceptance else None
                if acceptance and video_job:
                    output.update(
                        {
                            "video_job_id": video_job.id,
                            "output_url": self._media_url(video_job.output_video_path),
                            "score": acceptance.score,
                            "publishing_readiness": acceptance.publishing_readiness,
                            "target_url": f"/output-acceptance?video_job_id={video_job.id}",
                        }
                    )
            elif recipe_draft_id:
                draft = self.db.get(models.ProductUGCRecipeDraft, recipe_draft_id)
                if draft:
                    paths = draft.local_output_paths_json or []
                    output.update(
                        {
                            "output_url": self._media_url(paths[0]) if paths else None,
                            "publishing_readiness": draft.publishing_readiness,
                        }
                    )
            queue.append(output)
        return queue

    def _media_url(self, source_ref: str | None) -> str | None:
        if not source_ref:
            return None
        source = Path(source_ref)
        root = Path(self.settings.media_root)
        try:
            relative = source.relative_to(root)
        except ValueError:
            try:
                relative = source.resolve().relative_to(root.resolve())
            except ValueError:
                return None
        return f"/media/{relative.as_posix()}"

    def _latest_asset_contract(self, product_id: int | None) -> dict | None:
        if not product_id:
            latest_plan = self.db.scalar(select(models.OneVideoRenderPlan).order_by(models.OneVideoRenderPlan.id.desc()))
            product_id = latest_plan.product_id if latest_plan else self.db.scalar(select(models.Product.id).order_by(models.Product.id.desc()))
        if not product_id:
            return None
        tier_service = ProductAssetTierService(self.db)
        tier = tier_service.output(tier_service.evaluate(product_id))
        requirement_service = ReferenceRequirementService(self.db)
        requirement = requirement_service.output(
            requirement_service.evaluate(tier, purpose="final_ad"),
            permission=tier.permissions.model_dump(mode="json"),
        )
        return {"tier": tier.model_dump(mode="json"), "requirement": requirement.model_dump(mode="json")}

    def output(self, record: models.MVPWorkspaceSnapshot) -> MVPWorkspaceSnapshotOutput:
        return MVPWorkspaceSnapshotOutput(
            id=record.id,
            role=record.role,
            status=record.status,
            current_step=record.current_step,
            primary_action=record.primary_action_json,
            secondary_actions=record.secondary_actions_json or [],
            blockers=record.blockers_json or [],
            module_links=record.module_links_json or [],
            context=record.context_json or {},
            control_room_snapshot_id=record.control_room_snapshot_id,
            smoke_readiness_run_id=record.smoke_readiness_run_id,
        )

    @staticmethod
    def _module_links(factory_dashboard: dict[str, object]) -> list[MVPModuleLink]:
        internal_routes = {
            "video": "/mvp-launch",
            "video-quality": "/output-acceptance",
            "funnel": "/metrics-intake",
            "sources": "/destination-connectors",
            "payments": "/participant-portal",
            "analytics": "/campaign-performance",
            "people": "/training-academy",
        }
        return [
            MVPModuleLink(**item, internal_route=internal_routes.get(str(item["key"])))
            for item in factory_dashboard.get("modules", [])
        ]
