from __future__ import annotations

from fastapi import HTTPException, status

from app.config import get_settings


LEGACY_METRICS_BLOCK_DETAIL = {
    "code": "organization_safe_metrics_route_required",
    "message": "This legacy metrics route has no provable organization scope.",
    "replacement": "/api/social-metrics",
}


def require_legacy_global_metrics_local_mode() -> None:
    """Keep global legacy tools local-only; fail closed in strict public mode."""

    settings = get_settings()
    if settings.public_pilot_mode or settings.auth_required:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=LEGACY_METRICS_BLOCK_DETAIL,
        )
