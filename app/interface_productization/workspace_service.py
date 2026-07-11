from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.control_room import ControlRoomSnapshotService
from app.interface_productization.factory_dashboard_service import FactoryDashboardService
from app.interface_productization.mvp_navigation_service import MVPNavigationService
from app.interface_productization.org_scoped_workspace import OrganizationWorkspaceComposer
from app.interface_productization.types import MVPAction, MVPModuleLink, MVPWorkspaceSnapshotOutput
from app.smoke_readiness import ReadinessReportService
from app.product_asset_contract import ProductAssetTierService, ReferenceRequirementService
from app.routers.authorized_media import authorized_media_url, video_output_url


class MVPWorkspaceService:
    """Composes existing audit, control-room and readiness outputs for the product UI."""

    def __init__(self, db: Session):
        self.db = db
        self.navigation = MVPNavigationService()

    def build(
        self,
        *,
        role: str = "owner",
        user_profile_id: int | None = None,
        organization_id: int | None = None,
    ) -> models.MVPWorkspaceSnapshot:
        settings = get_settings()
        strict_mode = settings.public_pilot_mode or settings.auth_required
        if strict_mode and not organization_id:
            raise ValueError("organization_id_required_for_strict_workspace")
        factory_dashboard = FactoryDashboardService(self.db).snapshot(
            user_profile_id=user_profile_id,
            organization_id=organization_id,
        )
        scoped_product = None
        if strict_mode:
            scoped_state = OrganizationWorkspaceComposer(self.db).build(
                organization_id=int(organization_id),
                role=role,
                factory_dashboard=factory_dashboard,
            )
            control = scoped_state.control
            smoke = None
            scoped_product = scoped_state.latest_product
            asset_contract = self._latest_asset_contract(
                scoped_product.id if scoped_product else None,
                organization_id=int(organization_id),
                strict=True,
            )
        else:
            control_service = ControlRoomSnapshotService(self.db)
            control = control_service.output(control_service.refresh(role=role))
            smoke_service = ReadinessReportService(self.db)
            smoke_run = smoke_service.latest()
            smoke = smoke_service.output(smoke_run) if smoke_run else None
            asset_contract = self._latest_asset_contract(
                smoke.product_id if smoke else None
            )
        primary = self.navigation.primary_action(control, smoke, asset_contract)
        blockers = self.navigation.blockers(control, smoke, asset_contract)
        status = "blocked" if any(item.severity == "blocker" for item in blockers) else "ready"
        if control.review_queue:
            status = "needs_review"

        modules = self._module_links(factory_dashboard, strict=strict_mode)
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
            "review_queue": self._review_queue(
                control.review_queue,
                organization_id=organization_id,
                strict=strict_mode,
            ),
            "provider_failures": [
                item.model_dump(mode="json")
                for item in control.blocked_items
                if item.target_module == "runway_product_ugc"
            ],
            "smoke_decision": smoke.report.final_decision if smoke else "not_checked",
            "product_id": (
                scoped_product.id
                if strict_mode and scoped_product is not None
                else (smoke.product_id if smoke else None)
            ),
            "sku": (
                scoped_product.sku
                if strict_mode and scoped_product is not None
                else (smoke.sku if smoke else None)
            ),
            "product_asset_contract": asset_contract,
            "factory_dashboard": factory_dashboard,
            "technical": {
                "engine_audit_run_id": control.engine_audit_run_id,
                "control_room_snapshot_id": None if strict_mode else control.id,
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
            control_room_snapshot_id=None if strict_mode else control.id,
            smoke_readiness_run_id=smoke.id if smoke else None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _review_queue(
        self,
        items,
        *,
        organization_id: int | None = None,
        strict: bool = False,
    ) -> list[dict]:
        queue: list[dict] = []
        for item in items:
            output = item.model_dump(mode="json")
            payload = output.get("payload") or {}
            acceptance_id = payload.get("output_acceptance_id")
            recipe_draft_id = payload.get("recipe_draft_id")
            if acceptance_id:
                if strict:
                    row = self.db.execute(
                        select(models.VideoOutputAcceptance, models.VideoJob)
                        .join(
                            models.ContentCycle,
                            models.ContentCycle.output_acceptance_id
                            == models.VideoOutputAcceptance.id,
                        )
                        .join(
                            models.VideoJob,
                            models.VideoJob.id
                            == models.VideoOutputAcceptance.video_job_id,
                        )
                        .where(
                            models.VideoOutputAcceptance.id == acceptance_id,
                            models.ContentCycle.organization_id == organization_id,
                            models.VideoJob.organization_id == organization_id,
                        )
                    ).first()
                    acceptance = row[0] if row else None
                    video_job = row[1] if row else None
                else:
                    acceptance = self.db.get(models.VideoOutputAcceptance, acceptance_id)
                    video_job = self.db.get(models.VideoJob, acceptance.video_job_id) if acceptance else None
                if acceptance and video_job:
                    output.update(
                        {
                            "video_job_id": video_job.id,
                            "output_url": video_output_url(video_job),
                            "score": acceptance.score,
                            "publishing_readiness": acceptance.publishing_readiness,
                            "target_url": (
                                "/workbench?tab=video-quality"
                                if strict
                                else f"/output-acceptance?video_job_id={video_job.id}"
                            ),
                        }
                    )
                elif strict:
                    continue
            elif recipe_draft_id:
                if strict:
                    draft = self.db.scalar(
                        select(models.ProductUGCRecipeDraft)
                        .join(
                            models.Product,
                            models.Product.id
                            == models.ProductUGCRecipeDraft.product_id,
                        )
                        .where(
                            models.ProductUGCRecipeDraft.id == recipe_draft_id,
                            models.Product.organization_id == organization_id,
                        )
                    )
                else:
                    draft = self.db.get(models.ProductUGCRecipeDraft, recipe_draft_id)
                if draft:
                    paths = draft.local_output_paths_json or []
                    output.update(
                        {
                            "output_url": (
                                authorized_media_url(
                                    paths[0],
                                    f"/media/product-ugc-drafts/{draft.id}/outputs/0",
                                )
                                if paths
                                else None
                            ),
                            "publishing_readiness": draft.publishing_readiness,
                            "target_url": (
                                "/workbench?tab=video-quality"
                                if strict
                                else output.get("target_url")
                            ),
                        }
                    )
                elif strict:
                    continue
            elif strict and payload.get("video_job_id"):
                row = self.db.execute(
                    select(models.ContentCycle, models.VideoJob)
                    .join(
                        models.VideoJob,
                        models.VideoJob.id == models.ContentCycle.video_job_id,
                    )
                    .where(
                        models.ContentCycle.organization_id == organization_id,
                        models.ContentCycle.video_job_id == payload.get("video_job_id"),
                        models.VideoJob.organization_id == organization_id,
                    )
                ).first()
                if row is None:
                    continue
                video_job = row[1]
                output.update(
                    {
                        "video_job_id": video_job.id,
                        "output_url": video_output_url(video_job),
                        "publishing_readiness": "blocked",
                        "target_url": "/workbench?tab=video-quality",
                    }
                )
            if strict:
                output["target_url"] = "/workbench?tab=video-quality"
            queue.append(output)
        return queue

    def _latest_asset_contract(
        self,
        product_id: int | None,
        *,
        organization_id: int | None = None,
        strict: bool = False,
    ) -> dict | None:
        if strict:
            if not organization_id:
                return None
            product = self.db.scalar(
                select(models.Product).where(
                    models.Product.id == product_id,
                    models.Product.organization_id == organization_id,
                )
            ) if product_id else self.db.scalar(
                select(models.Product)
                .where(models.Product.organization_id == organization_id)
                .order_by(models.Product.updated_at.desc(), models.Product.id.desc())
            )
            if product is None:
                return None
            product_id = product.id
        elif not product_id:
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
    def _module_links(
        factory_dashboard: dict[str, object],
        *,
        strict: bool = False,
    ) -> list[MVPModuleLink]:
        internal_routes = {
            "video": "/mvp-launch",
            "video-quality": (
                "/workbench?tab=video-quality"
                if strict
                else "/output-acceptance"
            ),
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
