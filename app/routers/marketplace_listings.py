from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.marketplace_listings import (
    ListingAmbiguityError,
    ListingConflictError,
    ListingNotFoundError,
    ListingResolutionQuarantinedError,
    ListingValidationError,
    MarketplaceListingError,
    MarketplaceListingService,
)
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.gate_matrix import MARKETPLACE_LISTING_MANAGE


router = APIRouter(prefix="/api/marketplace-listings", tags=["marketplace-listings"])

MarketplaceName = Literal["wildberries"]
AliasType = Literal["nm_id", "vendor_code", "barcode", "legacy_ref"]
IdentifierType = Literal["nm_id", "vendor_code", "barcode", "alias"]


class MarketplaceListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int = Field(gt=0)
    marketplace: MarketplaceName = "wildberries"
    seller_account_ref: str = Field(min_length=1, max_length=160)
    nm_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[0-9]+$")
    vendor_code: str | None = Field(default=None, min_length=1, max_length=160)
    barcode: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    listing_url: AnyHttpUrl | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_identifiers_and_interval(self):
        if not any((self.nm_id, self.vendor_code, self.barcode)):
            raise ValueError("at least one exact listing identifier is required")
        if self.valid_from is not None and self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class MarketplaceListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    marketplace: str
    seller_account_ref: str
    nm_id: str | None
    vendor_code: str | None
    barcode: str | None
    listing_url: str | None
    status: str
    valid_from: datetime
    valid_to: datetime | None
    verified_at: datetime | None
    verified_by: int | None
    created_at: datetime
    updated_at: datetime


class MarketplaceListingList(BaseModel):
    items: list[MarketplaceListingRead]
    count: int = Field(ge=0)


class ListingAliasCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_listing_id: int = Field(gt=0)
    current_listing_id: int = Field(gt=0)
    alias_type: AliasType
    alias_value: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=1000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_interval(self):
        if self.valid_from is not None and self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class ListingAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    marketplace: str
    seller_account_ref: str
    canonical_listing_id: int
    current_listing_id: int
    alias_type: str
    alias_value: str
    valid_from: datetime
    valid_to: datetime | None
    reason: str
    approved_by: int
    created_at: datetime


class ReplacementHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    marketplace: str
    seller_account_ref: str
    canonical_listing_id: int
    previous_listing_id: int | None
    current_listing_id: int
    alias_type: str
    alias_value: str
    valid_from: datetime
    valid_to: datetime | None
    reason: str
    approved_by: int
    created_at: datetime


class ListingResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    marketplace: MarketplaceName = "wildberries"
    seller_account_ref: str | None = Field(default=None, min_length=1, max_length=160)
    identifier_type: IdentifierType
    identifier_value: str = Field(min_length=1, max_length=200)
    alias_type: AliasType | None = None
    at: datetime | None = None

    @model_validator(mode="after")
    def validate_alias_selector(self):
        if self.identifier_type == "alias" and self.alias_type is None:
            raise ValueError("alias_type is required for alias resolution")
        if self.identifier_type != "alias" and self.alias_type is not None:
            raise ValueError("alias_type is only allowed for alias resolution")
        return self


class ListingResolution(BaseModel):
    status: Literal["resolved"] = "resolved"
    listing: MarketplaceListingRead


def _raise_http_error(exc: MarketplaceListingError) -> None:
    if isinstance(exc, ListingNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ListingValidationError):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        http_status = status.HTTP_409_CONFLICT
    detail: dict[str, object] = {"code": exc.code, "message": str(exc)}
    if isinstance(exc, (ListingAmbiguityError, ListingResolutionQuarantinedError)):
        detail["disposition"] = "quarantine"
    if isinstance(exc, ListingAmbiguityError):
        detail["candidate_count"] = exc.candidate_count
    raise HTTPException(status_code=http_status, detail=detail) from exc


def _require_manage(db: Session, user: PublicPilotUser, *, operation: str, payload: dict) -> None:
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=MARKETPLACE_LISTING_MANAGE,
        payload={"operation": operation, **payload},
    )


@router.get("", response_model=MarketplaceListingList)
def list_marketplace_listings(
    include_inactive: bool = Query(default=False),
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> MarketplaceListingList:
    items = MarketplaceListingService(db).list_listings(
        organization_id=user.organization.id,
        include_inactive=include_inactive,
    )
    return MarketplaceListingList(
        items=[MarketplaceListingRead.model_validate(item) for item in items],
        count=len(items),
    )


@router.post("", response_model=MarketplaceListingRead, status_code=status.HTTP_201_CREATED)
def create_marketplace_listing(
    payload: MarketplaceListingCreate,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> MarketplaceListingRead:
    _require_manage(db, user, operation="create_listing", payload={"product_id": payload.product_id})
    try:
        listing = MarketplaceListingService(db).create_listing(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            product_id=payload.product_id,
            marketplace=payload.marketplace,
            seller_account_ref=payload.seller_account_ref,
            nm_id=payload.nm_id,
            vendor_code=payload.vendor_code,
            barcode=payload.barcode,
            listing_url=str(payload.listing_url) if payload.listing_url is not None else None,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
        )
    except MarketplaceListingError as exc:
        _raise_http_error(exc)
    return MarketplaceListingRead.model_validate(listing)


@router.post("/aliases", response_model=ListingAliasRead, status_code=status.HTTP_201_CREATED)
def create_listing_alias(
    payload: ListingAliasCreate,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> ListingAliasRead:
    _require_manage(
        db,
        user,
        operation="create_alias",
        payload={
            "canonical_listing_id": payload.canonical_listing_id,
            "current_listing_id": payload.current_listing_id,
            "alias_type": payload.alias_type,
        },
    )
    try:
        alias = MarketplaceListingService(db).create_alias(
            organization_id=user.organization.id,
            approved_by=user.profile.id,
            canonical_listing_id=payload.canonical_listing_id,
            current_listing_id=payload.current_listing_id,
            alias_type=payload.alias_type,
            alias_value=payload.alias_value,
            reason=payload.reason,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
        )
    except MarketplaceListingError as exc:
        _raise_http_error(exc)
    return ListingAliasRead.model_validate(alias)


@router.post("/resolve", response_model=ListingResolution)
def resolve_marketplace_listing(
    payload: ListingResolveRequest,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> ListingResolution:
    try:
        listing = MarketplaceListingService(db).resolve_exact(
            organization_id=user.organization.id,
            marketplace=payload.marketplace,
            identifier_type=payload.identifier_type,
            identifier_value=payload.identifier_value,
            seller_account_ref=payload.seller_account_ref,
            alias_type=payload.alias_type,
            at=payload.at,
        )
    except MarketplaceListingError as exc:
        _raise_http_error(exc)
    return ListingResolution(listing=MarketplaceListingRead.model_validate(listing))


@router.post("/{listing_id}/verify", response_model=MarketplaceListingRead)
def verify_marketplace_listing(
    listing_id: int,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> MarketplaceListingRead:
    _require_manage(db, user, operation="verify_listing", payload={"listing_id": listing_id})
    try:
        listing = MarketplaceListingService(db).verify_listing(
            organization_id=user.organization.id,
            listing_id=listing_id,
            verified_by=user.profile.id,
        )
    except MarketplaceListingError as exc:
        _raise_http_error(exc)
    return MarketplaceListingRead.model_validate(listing)


@router.get("/{listing_id}/history", response_model=list[ReplacementHistoryRead])
def list_replacement_history(
    listing_id: int,
    user: PublicPilotUser = Depends(get_current_public_user),
    db: Session = Depends(get_db),
) -> list[ReplacementHistoryRead]:
    try:
        history = MarketplaceListingService(db).list_history(
            organization_id=user.organization.id,
            listing_id=listing_id,
        )
    except MarketplaceListingError as exc:
        _raise_http_error(exc)
    return [ReplacementHistoryRead.model_validate(item) for item in history]
