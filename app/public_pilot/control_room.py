from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.control_room import ControlRoomSnapshotService
from app.interface_productization.mvp_navigation_service import MVPNavigationService
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
        audit_count = self.db.scalar(select(func.count()).select_from(models.AuditLog)) or 0
        denied_count = self.db.scalar(select(func.count()).select_from(models.AuditLog).where(models.AuditLog.status == "denied")) or 0
        requested_role = role or (user.role if user.role in {"owner", "admin", "reviewer", "operator"} else "creator_publisher")
        snapshot_service = ControlRoomSnapshotService(self.db)
        snapshot = snapshot_service.refresh(role=requested_role)
        snapshot_output = snapshot_service.output(snapshot)
        smoke_service = ReadinessReportService(self.db)
        smoke_run = smoke_service.latest()
        smoke_output = smoke_service.output(smoke_run) if smoke_run else None
        contract = self._asset_contract(smoke_output.product_id if smoke_output else None)
        navigation = MVPNavigationService()
        return {
            "user": user,
            "settings": self.settings,
            "role": user.role,
            "control_role": snapshot_output.role,
            "control_roles": ["owner", "content_lead", "campaign_operator", "reviewer", "creator", "creator_publisher", "metrics_operator"],
            "control_snapshot": snapshot_output,
            "smoke_readiness": smoke_output,
            "primary_action": navigation.primary_action(snapshot_output, smoke_output, contract),
            "product_blockers": navigation.blockers(snapshot_output, smoke_output, contract),
            "product_asset_contract": contract,
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

    def _asset_contract(self, product_id: int | None) -> dict | None:
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

