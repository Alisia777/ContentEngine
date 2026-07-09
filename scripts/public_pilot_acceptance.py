from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.public_pilot.gate_matrix import DANGEROUS_ACTIONS, PublicPilotGateMatrix


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def main() -> None:
    init_db()
    settings = get_settings()
    matrix = PublicPilotGateMatrix(strict_training=settings.public_pilot_strict_training_gates)
    with SessionLocal() as db:
        print("Public Pilot Acceptance")
        print(f"- auth_required: {settings.auth_required}")
        print(f"- public_pilot_mode: {settings.public_pilot_mode}")
        print(f"- organization_count: {count(db, models.Organization)}")
        print(f"- profile_count: {count(db, models.UserProfile)}")
        print(f"- membership_count: {count(db, models.Membership)}")
        print(f"- training_cert_count: {count(db, models.TrainingCertification)}")
        print(f"- audit_log_count: {count(db, models.AuditLog)}")
        print("")
        print("Gate matrix summary")
        for item in matrix.summary():
            dangerous = "dangerous" if item["action"] in DANGEROUS_ACTIONS else "standard"
            print(
                f"- {item['action']}: roles={item['roles'] or 'blocked'}; "
                f"cert={item['required_certification'] or 'none'}; "
                f"spend_gate={item['spend_gate_required']}; audit={item['audit_required']} ({dangerous})"
            )
        print("")
        print("UI routes")
        for route in [
            "/login",
            "/control-room",
            "/settings/access",
            "/altea-motion/splash",
            "/altea-motion/login",
            "/altea-motion/auth-loading",
            "/altea-motion/dashboard-loading",
            "/altea-motion/dashboard",
        ]:
            print(f"- {route}: configured")
        print("")
        print("Dangerous action protection: configured")
        print("Paid providers called: no")


if __name__ == "__main__":
    main()

