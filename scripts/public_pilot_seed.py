from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, func, select

from app import models
from app.database import SessionLocal, init_db
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import ensure_public_pilot_user

DEMO_ROLES = ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"]
ROLE_CERTIFICATIONS = {
    "reviewer": ["review_qa"],
    "operator": ["publishing_manual_upload"],
    "owner": ["review_qa", "publishing_manual_upload"],
    "admin": ["review_qa", "publishing_manual_upload"],
}


def reset_demo(db) -> None:
    db.execute(delete(models.AuditLog))
    db.execute(delete(models.TrainingCertification))
    db.execute(delete(models.UserTrainingAttempt))
    db.execute(delete(models.TrainingQuestion))
    db.execute(delete(models.PublicTrainingLesson))
    db.execute(delete(models.TrainingModule))
    db.execute(delete(models.Membership))
    db.execute(delete(models.UserProfile).where(models.UserProfile.email.like("%@altea-public.local")))
    db.execute(delete(models.Organization).where(models.Organization.slug == "altea-beauty"))
    db.commit()


def seed(with_certifications: bool, reset: bool) -> dict:
    init_db()
    with SessionLocal() as db:
        if reset:
            reset_demo(db)
        access = PublicPilotAccessService(db)
        modules = access.ensure_training_catalog()
        users = []
        for role in DEMO_ROLES:
            user = ensure_public_pilot_user(
                db,
                email=f"{role}@altea-public.local",
                display_name=f"ALTEA {role.title()}",
                role=role,
                supabase_user_id=f"demo-{role}",
            )
            users.append(user)
            if with_certifications:
                for module_code in ROLE_CERTIFICATIONS.get(role, []):
                    access.grant_certification(user.profile.id, module_code)

        return {
            "organization": users[0].organization.name if users else "ALTEA Beauty",
            "users": len(users),
            "memberships": len(users),
            "training_modules": len(modules),
            "certifications": db.query(models.TrainingCertification).count(),
            "organizations": db.scalar(select(func.count()).select_from(models.Organization)),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local ALTEA public pilot users, roles and training records.")
    parser.add_argument("--with-certifications", action="store_true", help="Grant reviewer/operator/admin/owner demo certifications.")
    parser.add_argument("--reset-demo", action="store_true", help="Remove seeded demo records before creating them again.")
    args = parser.parse_args()
    result = seed(with_certifications=args.with_certifications, reset=args.reset_demo)
    print("Public pilot seed complete")
    for key, value in result.items():
        if value is not None:
            print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
