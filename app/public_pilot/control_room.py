from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.control_room import ControlRoomSnapshotService
from app.interface_productization import FactoryDashboardService
from app.interface_productization.mvp_navigation_service import MVPNavigationService
from app.interface_productization.org_scoped_workspace import OrganizationWorkspaceComposer
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser
from app.public_pilot.gate_matrix import ACTION_LABELS, PublicPilotGateMatrix
from app.smoke_readiness import ReadinessReportService
from app.product_asset_contract import ProductAssetTierService, ReferenceRequirementService


class PublicPilotControlRoomService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.access = PublicPilotAccessService(db)

    def context(self, user: PublicPilotUser, *, role: str | None = None) -> dict:
        self.access.ensure_training_catalog()
        certifications = self.access.certification_codes(user.profile.id)
        matrix = PublicPilotGateMatrix(strict_training=self.settings.public_pilot_strict_training_gates)
        modules = self.db.scalars(select(models.TrainingModule).order_by(models.TrainingModule.order_index)).all()
        strict_mode = self.settings.public_pilot_mode or self.settings.auth_required
        audit_statement = select(func.count()).select_from(models.AuditLog)
        denied_statement = select(func.count()).select_from(models.AuditLog).where(
            models.AuditLog.status == "denied"
        )
        if strict_mode:
            audit_statement = audit_statement.where(
                models.AuditLog.organization_id == user.organization.id
            )
            denied_statement = denied_statement.where(
                models.AuditLog.organization_id == user.organization.id
            )
        audit_count = self.db.scalar(audit_statement) or 0
        denied_count = self.db.scalar(denied_statement) or 0
        requested_role = role or (user.role if user.role in {"owner", "admin", "reviewer", "operator"} else "creator_publisher")
        factory_dashboard = FactoryDashboardService(self.db).snapshot(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )
        if strict_mode:
            scoped_state = OrganizationWorkspaceComposer(self.db).build(
                organization_id=user.organization.id,
                role=requested_role,
                factory_dashboard=factory_dashboard,
            )
            snapshot_output = scoped_state.control
            smoke_output = None
            contract = self._asset_contract(
                scoped_state.latest_product.id if scoped_state.latest_product else None,
                organization_id=user.organization.id,
                strict=True,
            )
        else:
            snapshot_service = ControlRoomSnapshotService(self.db)
            snapshot = snapshot_service.refresh(role=requested_role)
            snapshot_output = snapshot_service.output(snapshot)
            smoke_service = ReadinessReportService(self.db)
            smoke_run = smoke_service.latest()
            smoke_output = smoke_service.output(smoke_run) if smoke_run else None
            contract = self._asset_contract(
                smoke_output.product_id if smoke_output else None
            )
        navigation = MVPNavigationService()
        control_role_options = [
            {"value": "owner", "label": "Владелец"},
            {"value": "content_lead", "label": "Руководитель контента"},
            {"value": "campaign_operator", "label": "Оператор кампании"},
            {"value": "reviewer", "label": "Проверяющий"},
            {"value": "creator", "label": "Автор"},
            {"value": "creator_publisher", "label": "Автор и публикатор"},
            {"value": "metrics_operator", "label": "Оператор метрик"},
        ]
        return {
            "user": user,
            "settings": self.settings,
            "role": user.role,
            "control_role": snapshot_output.role,
            "control_roles": ["owner", "content_lead", "campaign_operator", "reviewer", "creator", "creator_publisher", "metrics_operator"],
            "control_role_options": control_role_options,
            "control_snapshot": snapshot_output,
            "smoke_readiness": smoke_output,
            "primary_action": navigation.primary_action(snapshot_output, smoke_output, contract),
            "product_blockers": navigation.blockers(snapshot_output, smoke_output, contract),
            "product_asset_contract": contract,
            "factory_dashboard": factory_dashboard,
            "certifications": sorted(certifications),
            "training_modules": modules,
            "gate_summary": matrix.summary(),
            "gate_matrix": matrix.matrix(certification_codes_by_role={user.role: certifications}, spend_gate_confirmed=False),
            "action_labels": ACTION_LABELS,
            "metrics": [
                {"label": "Organization", "value": user.organization.name, "detail": "public pilot workspace"},
                {"label": "Role", "value": user.role, "detail": "active membership"},
                {"label": "Certifications", "value": str(len(certifications)), "detail": ", ".join(sorted(certifications)) or "none yet"},
                {"label": "Audit events", "value": str(audit_count), "detail": f"{denied_count} denied"},
            ],
            "next_actions": [
                "Seed demo users and certifications before external pilot access.",
                "Run prompt-only and review gates before any paid provider call.",
                "Use /settings/access to verify who can perform dangerous actions.",
            ],
        }

    def _asset_contract(
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

