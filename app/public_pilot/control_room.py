from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser
from app.public_pilot.gate_matrix import ACTION_LABELS, PublicPilotGateMatrix


class PublicPilotControlRoomService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.access = PublicPilotAccessService(db)

    def context(self, user: PublicPilotUser) -> dict:
        self.access.ensure_training_catalog()
        certifications = self.access.certification_codes(user.profile.id)
        matrix = PublicPilotGateMatrix(strict_training=self.settings.public_pilot_strict_training_gates)
        modules = self.db.scalars(select(models.TrainingModule).order_by(models.TrainingModule.order_index)).all()
        audit_count = self.db.scalar(select(func.count()).select_from(models.AuditLog)) or 0
        denied_count = self.db.scalar(select(func.count()).select_from(models.AuditLog).where(models.AuditLog.status == "denied")) or 0
        return {
            "user": user,
            "settings": self.settings,
            "role": user.role,
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

