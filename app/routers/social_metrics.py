from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.public_pilot.gate_matrix import METRICS_IMPORT
from app.social_metrics_ingestion import (
    SocialMetricAccessError,
    SocialMetricIngestionResult,
    SocialMetricIngestionService,
    SocialMetricObservation,
    SocialMetricValidationError,
)


router = APIRouter(prefix="/api/social-metrics", tags=["social-metrics"])

SourceType = Literal[
    "manual_entry",
    "manual_csv",
    "platform_export",
    "official_connector",
    "partner_report",
]


class SocialMetricValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    views: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    impressions: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    clicks: int | None = Field(default=None, ge=0)
    orders: int | None = Field(default=None, ge=0)
    revenue: float | None = Field(default=None, ge=0)
    spend: float | None = Field(default=None, ge=0)
    watch_time_seconds: float | None = Field(default=None, ge=0)
    retention_rate: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def require_value(self):
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("at least one metric value is required")
        return self


class SocialMetricIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_type: SourceType
    source_ref: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
    platform: str = Field(min_length=1, max_length=120)
    external_post_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    final_url: str | None = Field(default=None, min_length=8, max_length=500)
    publishing_task_id: int | None = Field(default=None, gt=0)
    observed_at: datetime
    period_start: date
    period_end: date
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    metrics: SocialMetricValues

    @model_validator(mode="after")
    def validate_identity_and_time(self):
        if not self.external_post_id and not self.final_url:
            raise ValueError("external_post_id or final_url is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class SocialMetricIngestResponse(BaseModel):
    status: Literal["created", "updated", "unchanged", "stale", "quarantined"]
    disposition: Literal["accepted", "quarantine"]
    metric_id: int | None = None
    quarantine_id: int | None = None
    reason: str | None = None
    canonical_key: str | None = None
    observation_key: str | None = None
    publishing_task_id: int | None = None
    observed_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    details: dict[str, object] = Field(default_factory=dict)


class SocialMetricRead(BaseModel):
    id: int
    publishing_task_id: int
    product_id: int
    sku: str | None
    platform: str
    final_url: str | None
    external_post_id: str | None
    period_start: date
    period_end: date
    observed_at: str
    source_type: str
    source_ref: str
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    clicks: int | None
    orders: int | None
    revenue: float | None
    spend: float | None


class QuarantineRead(BaseModel):
    id: int
    reason: str
    observation_key: str
    created_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


def _require_metrics_authentication(request: Request) -> None:
    settings = get_settings()
    authorization = request.headers.get("authorization", "")
    has_bearer = authorization.lower().startswith("bearer ") and bool(authorization.split(" ", 1)[1].strip())
    has_session_cookie = bool(request.cookies.get(settings.session_cookie_name))
    if (settings.public_pilot_mode or settings.auth_required) and not (has_bearer or has_session_cookie):
        # This dependency runs before get_current_public_user, preventing the
        # dev-bypass auto-provisioning path from mutating users on a rejected
        # anonymous request.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication_required")


def _require_metrics_identity(
    _authentication=Depends(_require_metrics_authentication),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> PublicPilotUser:
    if (
        not user.profile.is_active
        or user.profile.status != "active"
        or user.membership.status != "active"
        or user.organization.status != "active"
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="active_membership_required")
    return user


def _require_metrics_user(
    request: Request,
    user: PublicPilotUser = Depends(_require_metrics_identity),
    db: Session = Depends(get_db),
) -> PublicPilotUser:
    settings = get_settings()
    if settings.public_pilot_mode or settings.auth_required:
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=METRICS_IMPORT,
            payload={"method": request.method, "path": request.url.path},
        )
    return user


def _response(result: SocialMetricIngestionResult) -> SocialMetricIngestResponse:
    return SocialMetricIngestResponse(**result.__dict__)


@router.post("", response_model=SocialMetricIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_social_metric(
    payload: SocialMetricIngestRequest,
    user: PublicPilotUser = Depends(_require_metrics_user),
    db: Session = Depends(get_db),
) -> SocialMetricIngestResponse:
    # organization_id and actor identity intentionally come only from PublicPilotUser.
    try:
        result = SocialMetricIngestionService(db).ingest(
            SocialMetricObservation(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                source_type=payload.source_type,
                source_ref=payload.source_ref,
                platform=payload.platform,
                external_post_id=payload.external_post_id,
                final_url=payload.final_url,
                publishing_task_id=payload.publishing_task_id,
                observed_at=payload.observed_at,
                period_start=payload.period_start,
                period_end=payload.period_end,
                idempotency_key=payload.idempotency_key,
                metrics=payload.metrics.model_dump(exclude_unset=True),
            )
        )
    except SocialMetricAccessError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except SocialMetricValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return _response(result)


@router.get("", response_model=list[SocialMetricRead])
def list_social_metrics(
    limit: int = Query(default=50, ge=1, le=100),
    user: PublicPilotUser = Depends(_require_metrics_identity),
    db: Session = Depends(get_db),
) -> list[SocialMetricRead]:
    rows = SocialMetricIngestionService(db).list_metrics(
        organization_id=user.organization.id,
        limit=limit,
    )
    payloads: list[SocialMetricRead] = []
    for row in rows:
        ingestion = (row.raw_json or {}).get("ingestion_v1", {})
        payloads.append(
            SocialMetricRead(
                id=row.id,
                publishing_task_id=row.publishing_task_id,
                product_id=row.product_id,
                sku=row.sku,
                platform=row.platform,
                final_url=row.posted_url,
                external_post_id=row.provider_post_id,
                period_start=row.period_start,
                period_end=row.period_end,
                observed_at=ingestion["observed_at"],
                source_type=ingestion["source_type"],
                source_ref=ingestion["source_ref"],
                views=row.views,
                likes=row.likes,
                comments=row.comments,
                shares=row.shares,
                saves=row.saves,
                clicks=row.clicks,
                orders=row.orders,
                revenue=row.revenue,
                spend=row.spend,
            )
        )
    return payloads


@router.get("/quarantine", response_model=list[QuarantineRead])
def list_social_metric_quarantine(
    limit: int = Query(default=50, ge=1, le=100),
    user: PublicPilotUser = Depends(_require_metrics_identity),
    db: Session = Depends(get_db),
) -> list[QuarantineRead]:
    rows = SocialMetricIngestionService(db).list_quarantine(
        organization_id=user.organization.id,
        limit=limit,
    )
    return [
        QuarantineRead(
            id=row.id,
            reason=row.reason or "quarantined",
            observation_key=row.entity_id or "",
            created_at=row.created_at,
            metadata=row.metadata_json or {},
        )
        for row in rows
    ]
