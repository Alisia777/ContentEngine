from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


SUPPORTED_MARKETPLACE = "wildberries"
ALIAS_TYPES = frozenset({"nm_id", "vendor_code", "barcode", "legacy_ref"})
LISTING_STATUSES = frozenset({"draft", "verified", "quarantined", "inactive"})

_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_NM_ID = re.compile(r"^[0-9]{1,64}$")
_BARCODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f]")


class MarketplaceListingError(ValueError):
    code = "marketplace_listing_error"


class ListingValidationError(MarketplaceListingError):
    code = "invalid_listing_request"


class ListingNotFoundError(MarketplaceListingError):
    code = "listing_not_found"


class ListingConflictError(MarketplaceListingError):
    code = "listing_conflict"


class ListingAmbiguityError(MarketplaceListingError):
    code = "ambiguous_listing"
    disposition = "quarantine"

    def __init__(self, message: str, *, candidate_count: int):
        super().__init__(message)
        self.candidate_count = candidate_count


class ListingResolutionQuarantinedError(MarketplaceListingError):
    code = "listing_resolution_quarantined"
    disposition = "quarantine"


def _utc_naive(value: datetime | None, *, default_now: bool = False) -> datetime | None:
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None) if default_now else None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def _required_text(value: str, *, field: str, max_length: int) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ListingValidationError(f"{field} is required")
    if len(normalized) > max_length:
        raise ListingValidationError(f"{field} cannot exceed {max_length} characters")
    if _CONTROL_CHAR.search(normalized):
        raise ListingValidationError(f"{field} contains control characters")
    return normalized


def _optional_text(value: str | None, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    return _required_text(value, field=field, max_length=max_length)


def _positive_id(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ListingValidationError(f"{field} must be a positive integer")
    return value


def _marketplace(value: str) -> str:
    normalized = _required_text(value, field="marketplace", max_length=80).casefold()
    if normalized != SUPPORTED_MARKETPLACE:
        raise ListingValidationError("only wildberries is supported")
    return normalized


def _seller_account_ref(value: str) -> str:
    normalized = _required_text(value, field="seller_account_ref", max_length=160)
    if not _SAFE_REFERENCE.fullmatch(normalized):
        raise ListingValidationError("seller_account_ref must be an opaque internal reference")
    return normalized


def _identifier(value: str | None, *, identifier_type: str) -> str | None:
    max_length = 160 if identifier_type == "vendor_code" else 200 if identifier_type == "legacy_ref" else 80
    normalized = _optional_text(value, field=identifier_type, max_length=max_length)
    if normalized is None:
        return None
    if identifier_type == "nm_id" and not _NM_ID.fullmatch(normalized):
        raise ListingValidationError("nm_id must contain digits only")
    if identifier_type == "barcode" and not _BARCODE.fullmatch(normalized):
        raise ListingValidationError("barcode contains unsupported characters")
    return normalized


def _listing_url(value: str | None) -> str | None:
    normalized = _optional_text(value, field="listing_url", max_length=1000)
    if normalized is None:
        return None
    parsed = urlsplit(normalized)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() != "https" or not (hostname == "wildberries.ru" or hostname.endswith(".wildberries.ru")):
        raise ListingValidationError("listing_url must be an HTTPS Wildberries URL")
    if parsed.username or parsed.password:
        raise ListingValidationError("listing_url must not contain credentials")
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def _interval(valid_from: datetime | None, valid_to: datetime | None) -> tuple[datetime, datetime | None]:
    start = _utc_naive(valid_from, default_now=True)
    end = _utc_naive(valid_to)
    assert start is not None
    if end is not None and end <= start:
        raise ListingValidationError("valid_to must be later than valid_from")
    return start, end


def _active_at(model, at: datetime):
    return and_(model.valid_from <= at, or_(model.valid_to.is_(None), model.valid_to > at))


class MarketplaceListingService:
    def __init__(self, db: Session):
        self.db = db

    def _require_member(self, *, organization_id: int, user_profile_id: int) -> None:
        organization_id = _positive_id(organization_id, field="organization_id")
        user_profile_id = _positive_id(user_profile_id, field="user_profile_id")
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        if membership is None:
            raise ListingNotFoundError("active organization membership not found")

    def _owned_product(self, *, organization_id: int, product_id: int) -> models.Product:
        product = self.db.scalar(
            select(models.Product).where(
                models.Product.id == _positive_id(product_id, field="product_id"),
                models.Product.organization_id == _positive_id(organization_id, field="organization_id"),
            )
        )
        if product is None:
            raise ListingNotFoundError("product not found in organization")
        return product

    def _owned_listing(self, *, organization_id: int, listing_id: int) -> models.MarketplaceListing:
        listing = self.db.scalar(
            select(models.MarketplaceListing).where(
                models.MarketplaceListing.id == _positive_id(listing_id, field="listing_id"),
                models.MarketplaceListing.organization_id
                == _positive_id(organization_id, field="organization_id"),
            )
        )
        if listing is None:
            raise ListingNotFoundError("listing not found in organization")
        return listing

    def create_listing(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        product_id: int,
        marketplace: str = SUPPORTED_MARKETPLACE,
        seller_account_ref: str,
        nm_id: str | None = None,
        vendor_code: str | None = None,
        barcode: str | None = None,
        listing_url: str | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> models.MarketplaceListing:
        organization_id = _positive_id(organization_id, field="organization_id")
        self._require_member(organization_id=organization_id, user_profile_id=actor_user_profile_id)
        self._owned_product(organization_id=organization_id, product_id=product_id)
        marketplace = _marketplace(marketplace)
        seller_account_ref = _seller_account_ref(seller_account_ref)
        identifiers = {
            "nm_id": _identifier(nm_id, identifier_type="nm_id"),
            "vendor_code": _identifier(vendor_code, identifier_type="vendor_code"),
            "barcode": _identifier(barcode, identifier_type="barcode"),
        }
        if not any(identifiers.values()):
            raise ListingValidationError("at least one exact listing identifier is required")
        start, end = _interval(valid_from, valid_to)
        listing = models.MarketplaceListing(
            organization_id=organization_id,
            product_id=product_id,
            marketplace=marketplace,
            seller_account_ref=seller_account_ref,
            **identifiers,
            listing_url=_listing_url(listing_url),
            status="draft",
            valid_from=start,
            valid_to=end,
        )
        self.db.add(listing)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ListingConflictError("an exact identifier already exists in this seller account") from exc
        self.db.refresh(listing)
        return listing

    def verify_listing(
        self,
        *,
        organization_id: int,
        listing_id: int,
        verified_by: int,
        verified_at: datetime | None = None,
    ) -> models.MarketplaceListing:
        organization_id = _positive_id(organization_id, field="organization_id")
        self._require_member(organization_id=organization_id, user_profile_id=verified_by)
        listing = self._owned_listing(organization_id=organization_id, listing_id=listing_id)
        at = _utc_naive(verified_at, default_now=True)
        assert at is not None
        if listing.valid_from > at or (listing.valid_to is not None and listing.valid_to <= at):
            raise ListingValidationError("listing is outside its validity interval")
        if listing.status == "inactive":
            raise ListingValidationError("inactive listing cannot be verified")

        for alias_type in ("nm_id", "vendor_code", "barcode"):
            value = getattr(listing, alias_type)
            if value is None:
                continue
            collision = self.db.scalar(
                select(models.ListingAlias.id).where(
                    models.ListingAlias.organization_id == organization_id,
                    models.ListingAlias.marketplace == listing.marketplace,
                    models.ListingAlias.seller_account_ref == listing.seller_account_ref,
                    models.ListingAlias.alias_type == alias_type,
                    models.ListingAlias.alias_value == value,
                    models.ListingAlias.current_listing_id != listing.id,
                    _active_at(models.ListingAlias, at),
                )
            )
            if collision is not None:
                raise ListingConflictError("identifier conflicts with an active alias; verification quarantined")

        listing.status = "verified"
        listing.verified_at = at
        listing.verified_by = verified_by
        self.db.commit()
        self.db.refresh(listing)
        return listing

    def list_listings(
        self,
        *,
        organization_id: int,
        include_inactive: bool = False,
    ) -> list[models.MarketplaceListing]:
        query = select(models.MarketplaceListing).where(
            models.MarketplaceListing.organization_id
            == _positive_id(organization_id, field="organization_id")
        )
        if not include_inactive:
            query = query.where(models.MarketplaceListing.status != "inactive")
        return list(self.db.scalars(query.order_by(models.MarketplaceListing.id.desc())).all())

    def create_alias(
        self,
        *,
        organization_id: int,
        approved_by: int,
        canonical_listing_id: int,
        current_listing_id: int,
        alias_type: str,
        alias_value: str,
        reason: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> models.ListingAlias:
        organization_id = _positive_id(organization_id, field="organization_id")
        self._require_member(organization_id=organization_id, user_profile_id=approved_by)
        canonical = self._owned_listing(organization_id=organization_id, listing_id=canonical_listing_id)
        current = self._owned_listing(organization_id=organization_id, listing_id=current_listing_id)
        if (canonical.marketplace, canonical.seller_account_ref) != (
            current.marketplace,
            current.seller_account_ref,
        ):
            raise ListingValidationError("canonical and current listings must share marketplace and seller account")
        if current.status != "verified":
            raise ListingValidationError("current listing must be verified before alias activation")
        alias_type = _required_text(alias_type, field="alias_type", max_length=40)
        if alias_type not in ALIAS_TYPES:
            raise ListingValidationError("unsupported alias_type")
        alias_value = _identifier(alias_value, identifier_type=alias_type)
        assert alias_value is not None
        reason = _required_text(reason, field="reason", max_length=1000)
        start, end = _interval(valid_from, valid_to)

        existing = self.db.scalar(
            select(models.ListingAlias).where(
                models.ListingAlias.organization_id == organization_id,
                models.ListingAlias.marketplace == canonical.marketplace,
                models.ListingAlias.seller_account_ref == canonical.seller_account_ref,
                models.ListingAlias.alias_type == alias_type,
                models.ListingAlias.alias_value == alias_value,
                models.ListingAlias.valid_to.is_(None),
            )
        )
        overlap_scope = [
            models.ListingAlias.organization_id == organization_id,
            models.ListingAlias.marketplace == canonical.marketplace,
            models.ListingAlias.seller_account_ref == canonical.seller_account_ref,
            models.ListingAlias.alias_type == alias_type,
            models.ListingAlias.alias_value == alias_value,
            or_(models.ListingAlias.valid_to.is_(None), models.ListingAlias.valid_to > start),
        ]
        if end is not None:
            overlap_scope.append(models.ListingAlias.valid_from < end)
        if existing is not None:
            overlap_scope.append(models.ListingAlias.id != existing.id)
        overlapping_alias = self.db.scalar(select(models.ListingAlias.id).where(*overlap_scope))
        if overlapping_alias is not None:
            raise ListingConflictError("alias validity interval overlaps another mapping")
        if existing is not None:
            if existing.canonical_listing_id != canonical.id:
                raise ListingConflictError("active alias belongs to another canonical listing")
            if existing.current_listing_id == current.id:
                return existing
            if start <= existing.valid_from:
                raise ListingValidationError("replacement valid_from must be later than the active alias")

        if alias_type in {"nm_id", "vendor_code", "barcode"}:
            direct_field = getattr(models.MarketplaceListing, alias_type)
            direct_collision = self.db.scalar(
                select(models.MarketplaceListing.id).where(
                    models.MarketplaceListing.organization_id == organization_id,
                    models.MarketplaceListing.marketplace == canonical.marketplace,
                    models.MarketplaceListing.seller_account_ref == canonical.seller_account_ref,
                    direct_field == alias_value,
                    models.MarketplaceListing.id != current.id,
                )
            )
            if direct_collision is not None:
                raise ListingConflictError("alias conflicts with another exact listing identifier")

        previous_listing_id: int | None = None
        if existing is not None:
            previous_listing_id = existing.current_listing_id
            existing.valid_to = start
            active_history = self.db.scalar(
                select(models.ReplacementHistory).where(
                    models.ReplacementHistory.organization_id == organization_id,
                    models.ReplacementHistory.marketplace == canonical.marketplace,
                    models.ReplacementHistory.seller_account_ref == canonical.seller_account_ref,
                    models.ReplacementHistory.alias_type == alias_type,
                    models.ReplacementHistory.alias_value == alias_value,
                    models.ReplacementHistory.valid_to.is_(None),
                )
            )
            if active_history is not None:
                active_history.valid_to = start
            self.db.flush()
        elif canonical.id != current.id:
            previous_listing_id = canonical.id

        alias = models.ListingAlias(
            organization_id=organization_id,
            marketplace=canonical.marketplace,
            seller_account_ref=canonical.seller_account_ref,
            canonical_listing_id=canonical.id,
            current_listing_id=current.id,
            alias_type=alias_type,
            alias_value=alias_value,
            valid_from=start,
            valid_to=end,
            reason=reason,
            approved_by=approved_by,
        )
        self.db.add(alias)
        if previous_listing_id is not None:
            self.db.add(
                models.ReplacementHistory(
                    organization_id=organization_id,
                    marketplace=canonical.marketplace,
                    seller_account_ref=canonical.seller_account_ref,
                    canonical_listing_id=canonical.id,
                    previous_listing_id=previous_listing_id,
                    current_listing_id=current.id,
                    alias_type=alias_type,
                    alias_value=alias_value,
                    valid_from=start,
                    valid_to=end,
                    reason=reason,
                    approved_by=approved_by,
                )
            )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ListingConflictError("alias overlaps an active mapping in this seller account") from exc
        self.db.refresh(alias)
        return alias

    def list_history(
        self,
        *,
        organization_id: int,
        listing_id: int,
    ) -> list[models.ReplacementHistory]:
        listing = self._owned_listing(organization_id=organization_id, listing_id=listing_id)
        query = select(models.ReplacementHistory).where(
            models.ReplacementHistory.organization_id == listing.organization_id,
            or_(
                models.ReplacementHistory.canonical_listing_id == listing.id,
                models.ReplacementHistory.previous_listing_id == listing.id,
                models.ReplacementHistory.current_listing_id == listing.id,
            ),
        )
        return list(self.db.scalars(query.order_by(models.ReplacementHistory.valid_from)).all())

    def resolve_exact(
        self,
        *,
        organization_id: int,
        marketplace: str,
        identifier_type: str,
        identifier_value: str,
        seller_account_ref: str | None = None,
        alias_type: str | None = None,
        at: datetime | None = None,
    ) -> models.MarketplaceListing:
        organization_id = _positive_id(organization_id, field="organization_id")
        marketplace = _marketplace(marketplace)
        identifier_type = _required_text(identifier_type, field="identifier_type", max_length=40)
        if identifier_type not in {"nm_id", "vendor_code", "barcode", "alias"}:
            raise ListingValidationError("unsupported identifier_type")
        if identifier_type == "alias":
            if alias_type is None:
                raise ListingValidationError("alias_type is required for alias resolution")
            resolved_alias_type = _required_text(alias_type, field="alias_type", max_length=40)
            if resolved_alias_type not in ALIAS_TYPES:
                raise ListingValidationError("unsupported alias_type")
        else:
            if alias_type is not None:
                raise ListingValidationError("alias_type is only allowed for alias resolution")
            resolved_alias_type = identifier_type
        value = _identifier(identifier_value, identifier_type=resolved_alias_type)
        assert value is not None
        seller_ref = _seller_account_ref(seller_account_ref) if seller_account_ref is not None else None
        resolved_at = _utc_naive(at, default_now=True)
        assert resolved_at is not None

        candidates: dict[int, models.MarketplaceListing] = {}
        listing_scope = [
            models.MarketplaceListing.organization_id == organization_id,
            models.MarketplaceListing.marketplace == marketplace,
            _active_at(models.MarketplaceListing, resolved_at),
        ]
        if seller_ref is not None:
            listing_scope.append(models.MarketplaceListing.seller_account_ref == seller_ref)

        if identifier_type != "alias":
            direct_field = getattr(models.MarketplaceListing, identifier_type)
            direct_query = select(models.MarketplaceListing).where(*listing_scope, direct_field == value)
            for listing in self.db.scalars(direct_query):
                candidates[listing.id] = listing

        alias_scope = [
            models.ListingAlias.organization_id == organization_id,
            models.ListingAlias.marketplace == marketplace,
            models.ListingAlias.alias_type == resolved_alias_type,
            models.ListingAlias.alias_value == value,
            _active_at(models.ListingAlias, resolved_at),
        ]
        if seller_ref is not None:
            alias_scope.append(models.ListingAlias.seller_account_ref == seller_ref)
        alias_query = (
            select(models.MarketplaceListing)
            .join(
                models.ListingAlias,
                and_(
                    models.ListingAlias.current_listing_id == models.MarketplaceListing.id,
                    models.ListingAlias.organization_id == models.MarketplaceListing.organization_id,
                    models.ListingAlias.marketplace == models.MarketplaceListing.marketplace,
                    models.ListingAlias.seller_account_ref == models.MarketplaceListing.seller_account_ref,
                ),
            )
            .where(*alias_scope, *listing_scope)
        )
        for listing in self.db.scalars(alias_query):
            candidates[listing.id] = listing

        if not candidates:
            raise ListingNotFoundError("no exact active listing match")
        if len(candidates) != 1:
            raise ListingAmbiguityError(
                "multiple exact matches; automatic selection is prohibited",
                candidate_count=len(candidates),
            )
        listing = next(iter(candidates.values()))
        if listing.status != "verified":
            raise ListingResolutionQuarantinedError(
                f"exact match is {listing.status}; verified listing required"
            )
        return listing
