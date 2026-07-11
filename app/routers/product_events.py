from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.product_telemetry import (
    ProductTelemetryService,
    TelemetryIdempotencyConflict,
    TelemetryValidationError,
)
from app.public_pilot.auth import PublicPilotUser, get_current_public_user


router = APIRouter(prefix="/api", tags=["product-telemetry"])


class ProductEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(min_length=1, max_length=120)
    event_version: int = Field(default=1, ge=1, le=1)
    occurred_at: datetime | None = None
    session_id: str | None = Field(default=None, max_length=128)
    factory_run_id: str | None = Field(default=None, max_length=160)
    entity_type: str | None = Field(default=None, max_length=120)
    entity_id: str | None = Field(default=None, max_length=160)
    product_id: int | None = Field(default=None, gt=0)
    sku: str | None = Field(default=None, max_length=120)
    campaign_id: int | None = Field(default=None, gt=0)
    video_job_id: int | None = Field(default=None, gt=0)
    publishing_task_id: int | None = Field(default=None, gt=0)
    source: Literal["web"] = "web"
    idempotency_key: str = Field(min_length=1, max_length=160)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "event_name",
        "session_id",
        "factory_run_id",
        "entity_type",
        "entity_id",
        "sku",
        "idempotency_key",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class ProductEventAccepted(BaseModel):
    accepted: bool = True
    duplicate: bool
    event_id: int
    received_at: datetime


@router.post(
    "/product-events",
    response_model=ProductEventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_product_event(
    payload: ProductEventCreate,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> ProductEventAccepted:
    try:
        result = ProductTelemetryService(db).record_event(
            event_name=payload.event_name,
            event_version=payload.event_version,
            occurred_at=payload.occurred_at,
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            session_id=payload.session_id,
            role=user.role,
            factory_run_id=payload.factory_run_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            product_id=payload.product_id,
            sku=payload.sku,
            campaign_id=payload.campaign_id,
            video_job_id=payload.video_job_id,
            publishing_task_id=payload.publishing_task_id,
            source=payload.source,
            idempotency_key=payload.idempotency_key,
            properties=payload.properties,
        )
    except TelemetryIdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TelemetryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ProductEventAccepted(
        duplicate=not result.created,
        event_id=result.event.id,
        received_at=result.event.received_at,
    )
