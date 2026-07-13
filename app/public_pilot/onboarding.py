from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import models
from app.config import get_settings
from app.database import SessionLocal
from app.novice_learning_path import NoviceLearningPathService
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser, active_public_pilot_user_from_payload
from app.public_pilot.training_catalog import (
    ONBOARDING_EXAM_CODE,
    ONBOARDING_PREREQUISITE_CODES,
)


ONBOARDING_ALLOWED_PATHS = frozenset({"/onboarding"})
ONBOARDING_ALLOWED_PREFIXES = ("/onboarding/", "/static/", "/r/")
CREATOR_GENERATION_ROLES = frozenset({"producer"})
CREATOR_GENERATION_WORKSPACE = "/creator-operations?tab=generation"
CONTROL_WORKSPACE = "/control-room"


def workspace_home_for_role(role: str | None) -> str:
    """Send hands-on creators to their primary job instead of an admin dashboard."""

    normalized_role = str(role or "").strip().casefold()
    if normalized_role in CREATOR_GENERATION_ROLES:
        return CREATOR_GENERATION_WORKSPACE
    return CONTROL_WORKSPACE


def safe_workspace_next(value: str | None, *, role: str | None = None) -> str:
    fallback = workspace_home_for_role(role)
    candidate = str(value or "").strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or candidate.startswith("/onboarding")
        or "\r" in candidate
        or "\n" in candidate
    ):
        return fallback
    return candidate[:1000]


def onboarding_complete(db: Session, *, user_profile_id: int) -> bool:
    return ONBOARDING_EXAM_CODE in NoviceLearningPathService(
        db
    ).verified_certification_codes(user_profile_id=user_profile_id)


class CloudOnboardingService:
    def __init__(self, db: Session):
        self.db = db

    def context(
        self,
        user: PublicPilotUser,
        *,
        selected_code: str | None = None,
    ) -> dict[str, object]:
        PublicPilotAccessService(self.db).ensure_training_catalog()
        modules = list(
            self.db.scalars(
                select(models.TrainingModule)
                .where(models.TrainingModule.is_active.is_(True))
                .order_by(models.TrainingModule.order_index, models.TrainingModule.id)
            )
        )
        verified = NoviceLearningPathService(self.db).verified_certification_codes(
            user_profile_id=user.profile.id
        )
        missing_prerequisites = [
            code for code in ONBOARDING_PREREQUISITE_CODES if code not in verified
        ]
        module_views: list[dict[str, object]] = []
        for module in modules:
            is_exam = module.code == ONBOARDING_EXAM_CODE
            module_views.append(
                {
                    "module": module,
                    "code": module.code,
                    "is_exam": is_exam,
                    "completed": module.code in verified,
                    "available": not is_exam or not missing_prerequisites,
                    "question_count": len(module.questions),
                }
            )
        allowed_codes = {str(item["code"]) for item in module_views}
        if selected_code not in allowed_codes:
            selected_code = next(
                (
                    str(item["code"])
                    for item in module_views
                    if not bool(item["completed"])
                    and bool(item["available"])
                ),
                ONBOARDING_EXAM_CODE,
            )
        selected = next(
            (item for item in module_views if item["code"] == selected_code),
            module_views[0] if module_views else None,
        )
        return {
            "modules": module_views,
            "selected": selected,
            "verified_codes": verified,
            "missing_prerequisites": missing_prerequisites,
            "prerequisite_count": len(ONBOARDING_PREREQUISITE_CODES),
            "prerequisite_completed": len(ONBOARDING_PREREQUISITE_CODES)
            - len(missing_prerequisites),
            "workspace_open": ONBOARDING_EXAM_CODE in verified,
            "exam_code": ONBOARDING_EXAM_CODE,
        }

    def require_exam_prerequisites(self, *, user_profile_id: int) -> None:
        verified = NoviceLearningPathService(self.db).verified_certification_codes(
            user_profile_id=user_profile_id
        )
        missing = [code for code in ONBOARDING_PREREQUISITE_CODES if code not in verified]
        if missing:
            raise HTTPException(
                status_code=409,
                detail={"code": "onboarding_prerequisites_required", "missing": missing},
            )


class CloudOnboardingGateMiddleware(BaseHTTPMiddleware):
    """Keep authenticated cloud members in onboarding until the final exam passes."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        if (
            not settings.auth_required
            or path in ONBOARDING_ALLOWED_PATHS
            or any(path.startswith(prefix) for prefix in ONBOARDING_ALLOWED_PREFIXES)
        ):
            return await call_next(request)

        payload = getattr(request.state, "public_pilot_auth_payload", None)
        if not isinstance(payload, dict):
            # The outer auth wall owns login/invalid-token behavior.  This case
            # is retained for middleware-order safety and cannot grant access.
            return await call_next(request)
        if payload.get("auth_source") == "local":
            # The local session is an operator/development recovery path, not a
            # cloud creator account. Cloud JWT members are always gated.
            return await call_next(request)

        try:
            with SessionLocal() as db:
                user = active_public_pilot_user_from_payload(db, payload)
                complete = onboarding_complete(db, user_profile_id=user.profile.id)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

        if complete:
            return await call_next(request)
        if path.startswith("/api"):
            return JSONResponse(
                {
                    "detail": "onboarding_required",
                    "onboarding_url": "/onboarding",
                    "required_certification": ONBOARDING_EXAM_CODE,
                },
                status_code=403,
            )
        query = request.url.query
        target = path + (f"?{query}" if query else "")
        return RedirectResponse(
            f"/onboarding?next={quote(safe_workspace_next(target), safe='')}",
            status_code=303,
        )
