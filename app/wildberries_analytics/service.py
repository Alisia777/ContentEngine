from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.credential_status import (
    CredentialResolver,
    EnvironmentCredentialResolver,
    sanitize_payload,
)
from app.marketplace_listings.service import (
    ListingAmbiguityError,
    ListingNotFoundError,
    ListingResolutionQuarantinedError,
    MarketplaceListingService,
)
from app.models import utcnow
from app.wildberries_analytics.connector import (
    MAX_NM_IDS_PER_PAGE,
    WILDBERRIES_AUTH_SCHEME,
    WILDBERRIES_HISTORY_ENDPOINT,
    WildberriesSellerAnalyticsConnector,
    WildberriesSellerAnalyticsHttpGateway,
)
from app.wildberries_analytics.errors import (
    WildberriesAnalyticsConfigurationError,
    WildberriesAnalyticsError,
    WildberriesAnalyticsIdempotencyError,
    WildberriesAnalyticsScopeError,
)
from app.wildberries_analytics.types import WildberriesSyncResult


_SELLER_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_CREDENTIAL_REF = re.compile(r"^env:[A-Z][A-Z0-9_]{2,95}$")
_SYNC_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_CONFIGURE_ROLES = {"owner", "admin"}
_SYNC_ROLES = {"owner", "admin", "operator", "metrics_operator"}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_id(value: int, *, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise WildberriesAnalyticsScopeError(code)
    return value


class WildberriesSellerAnalyticsService:
    def __init__(
        self,
        db: Session,
        *,
        credential_resolver: CredentialResolver | None = None,
        http_gateway: WildberriesSellerAnalyticsHttpGateway | None = None,
        connector: WildberriesSellerAnalyticsConnector | None = None,
    ):
        self.db = db
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.connector = connector or WildberriesSellerAnalyticsConnector(
            credential_resolver=self.credential_resolver,
            http_gateway=http_gateway,
        )

    def configure_connection(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        seller_account_ref: str,
        credential_ref: str,
    ) -> models.WildberriesAnalyticsConnection:
        organization_id = _positive_id(
            organization_id,
            code="wildberries_organization_scope_required",
        )
        actor_user_profile_id = _positive_id(
            actor_user_profile_id,
            code="wildberries_actor_scope_required",
        )
        self._require_role(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            allowed_roles=_CONFIGURE_ROLES,
        )
        seller_ref = str(seller_account_ref or "").strip()
        if not _SELLER_REF.fullmatch(seller_ref):
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_seller_account_ref_invalid"
            )
        secret_reference = str(credential_ref or "").strip()
        if not _CREDENTIAL_REF.fullmatch(secret_reference):
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_credential_ref_must_be_environment_reference"
            )

        connection = self.db.scalar(
            select(models.WildberriesAnalyticsConnection).where(
                models.WildberriesAnalyticsConnection.organization_id == organization_id,
                models.WildberriesAnalyticsConnection.seller_account_ref == seller_ref,
            )
        )
        if connection is None:
            connection = models.WildberriesAnalyticsConnection(
                organization_id=organization_id,
                seller_account_ref=seller_ref,
                credential_ref=secret_reference,
                status="needs_verification",
                auth_status="credential_reference_configured",
                created_by_user_profile_id=actor_user_profile_id,
                settings_json={
                    "endpoint": WILDBERRIES_HISTORY_ENDPOINT,
                    "auth_scheme": WILDBERRIES_AUTH_SCHEME,
                    "page_size": MAX_NM_IDS_PER_PAGE,
                    "max_period_days": 7,
                },
            )
            self.db.add(connection)
            self.db.flush()
        else:
            connection.credential_ref = secret_reference
            connection.status = "needs_verification"
            connection.auth_status = "credential_reference_configured"
            connection.last_error_code = None
        self.db.add(
            models.AuditLog(
                user_profile_id=actor_user_profile_id,
                organization_id=organization_id,
                action="wildberries_analytics_connection_configured",
                status="allowed",
                entity_type="wildberries_analytics_connection",
                entity_id=str(connection.id),
                metadata_json={
                    "seller_account_ref": seller_ref,
                    "credential_reference_configured": True,
                    "auth_scheme": WILDBERRIES_AUTH_SCHEME,
                },
            )
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def sync(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        connection_id: int,
        period_start: date,
        period_end: date,
        idempotency_key: str,
    ) -> WildberriesSyncResult:
        organization_id = _positive_id(
            organization_id,
            code="wildberries_organization_scope_required",
        )
        actor_user_profile_id = _positive_id(
            actor_user_profile_id,
            code="wildberries_actor_scope_required",
        )
        connection_id = _positive_id(
            connection_id,
            code="wildberries_connection_id_required",
        )
        self._require_role(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            allowed_roles=_SYNC_ROLES,
        )
        connection = self._owned_connection(
            organization_id=organization_id,
            connection_id=connection_id,
        )
        if connection.status == "disabled":
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_connection_disabled"
            )
        if not _CREDENTIAL_REF.fullmatch(str(connection.credential_ref or "")):
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_credential_ref_must_be_environment_reference"
            )
        sync_key = str(idempotency_key or "").strip()
        if not _SYNC_KEY.fullmatch(sync_key):
            raise WildberriesAnalyticsIdempotencyError(
                "wildberries_sync_idempotency_key_invalid"
            )
        self.connector.validate_period(period_start, period_end)
        listings = self._eligible_listings(
            organization_id=organization_id,
            seller_account_ref=connection.seller_account_ref,
            period_start=period_start,
            period_end=period_end,
        )
        nm_ids = [str(listing.nm_id) for listing in listings if listing.nm_id]
        request_bodies = self.connector.request_bodies(
            period_start=period_start,
            period_end=period_end,
            nm_ids=nm_ids,
        )
        request_hash = _canonical_sha256(
            {
                "organization_id": organization_id,
                "connection_id": connection.id,
                "seller_account_ref": connection.seller_account_ref,
                "request_bodies": request_bodies,
            }
        )
        existing_audit = self.db.scalar(
            select(models.WildberriesAnalyticsSyncAudit).where(
                models.WildberriesAnalyticsSyncAudit.organization_id == organization_id,
                models.WildberriesAnalyticsSyncAudit.idempotency_key == sync_key,
            )
        )
        if existing_audit is not None:
            return self._replay(existing_audit, request_hash=request_hash)

        try:
            collection = self.connector.collect(
                credential_ref=connection.credential_ref,
                period_start=period_start,
                period_end=period_end,
                nm_ids=nm_ids,
            )
        except WildberriesAnalyticsError as exc:
            self._record_failed_sync(
                connection=connection,
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                sync_key=sync_key,
                request_hash=request_hash,
                period_start=period_start,
                period_end=period_end,
                requested_nm_id_count=len(set(nm_ids)),
                page_count=len(request_bodies),
                error_code=exc.code,
            )
            raise

        requested_nm_ids = {
            str(value) for body in request_bodies for value in body["nmIds"]
        }
        accepted: list[tuple[Any, models.MarketplaceListing, str]] = []
        quarantined: list[tuple[Any, str, str]] = []
        for metric in collection.metrics:
            try:
                listing = MarketplaceListingService(self.db).resolve_exact(
                    organization_id=organization_id,
                    marketplace="wildberries",
                    identifier_type="nm_id",
                    identifier_value=metric.nm_id,
                    seller_account_ref=connection.seller_account_ref,
                    at=datetime.combine(metric.metric_date, time(hour=12)),
                )
            except ListingNotFoundError:
                reason = "unknown_nm_id"
                quarantined.append(
                    (metric, reason, self._quarantine_fingerprint(connection, metric, reason))
                )
                continue
            except ListingAmbiguityError:
                reason = "ambiguous_nm_id"
                quarantined.append(
                    (metric, reason, self._quarantine_fingerprint(connection, metric, reason))
                )
                continue
            except ListingResolutionQuarantinedError:
                reason = "unverified_nm_id"
                quarantined.append(
                    (metric, reason, self._quarantine_fingerprint(connection, metric, reason))
                )
                continue
            if metric.nm_id not in requested_nm_ids:
                reason = "unrequested_nm_id"
                quarantined.append(
                    (metric, reason, self._quarantine_fingerprint(connection, metric, reason))
                )
                continue
            fingerprint = _canonical_sha256(
                {
                    "organization_id": organization_id,
                    "seller_account_ref": connection.seller_account_ref,
                    "listing_id": listing.id,
                    "nm_id": metric.nm_id,
                    "metric_date": metric.metric_date.isoformat(),
                    "metrics": metric.history_json,
                }
            )
            accepted.append((metric, listing, fingerprint))

        snapshot_fingerprints = [item[2] for item in accepted]
        existing_snapshot_fingerprints = set(
            self.db.scalars(
                select(models.WildberriesMetricSnapshot.source_fingerprint).where(
                    models.WildberriesMetricSnapshot.organization_id == organization_id,
                    models.WildberriesMetricSnapshot.source_fingerprint.in_(
                        snapshot_fingerprints
                    ),
                )
            ).all()
            if snapshot_fingerprints
            else []
        )
        quarantine_fingerprints = [item[2] for item in quarantined]
        existing_quarantine_fingerprints = set(
            self.db.scalars(
                select(models.WildberriesMetricQuarantine.source_fingerprint).where(
                    models.WildberriesMetricQuarantine.organization_id == organization_id,
                    models.WildberriesMetricQuarantine.source_fingerprint.in_(
                        quarantine_fingerprints
                    ),
                )
            ).all()
            if quarantine_fingerprints
            else []
        )
        new_snapshot_count = sum(
            1
            for _metric, _listing, fingerprint in accepted
            if fingerprint not in existing_snapshot_fingerprints
        )
        response_hash = _canonical_sha256(collection.response_payloads)
        status = "completed_with_quarantine" if quarantined else "completed"
        audit = models.WildberriesAnalyticsSyncAudit(
            organization_id=organization_id,
            connection_id=connection.id,
            actor_user_profile_id=actor_user_profile_id,
            seller_account_ref=connection.seller_account_ref,
            idempotency_key=sync_key,
            request_body_sha256=request_hash,
            response_sha256=response_hash,
            period_start=period_start,
            period_end=period_end,
            status=status,
            page_count=len(collection.request_bodies),
            requested_nm_id_count=len(requested_nm_ids),
            response_product_count=collection.response_product_count,
            snapshot_count=len(accepted),
            new_snapshot_count=new_snapshot_count,
            quarantine_count=len(quarantined),
        )
        self.db.add(audit)
        self.db.flush()
        observed_at = utcnow()
        for metric, listing, fingerprint in accepted:
            if fingerprint in existing_snapshot_fingerprints:
                continue
            self.db.add(
                models.WildberriesMetricSnapshot(
                    organization_id=organization_id,
                    connection_id=connection.id,
                    sync_audit_id=audit.id,
                    marketplace="wildberries",
                    seller_account_ref=connection.seller_account_ref,
                    listing_id=listing.id,
                    product_id=listing.product_id,
                    nm_id=metric.nm_id,
                    period_start=period_start,
                    period_end=period_end,
                    metric_date=metric.metric_date,
                    open_count=metric.open_count,
                    cart_count=metric.cart_count,
                    order_count=metric.order_count,
                    order_sum_minor=metric.order_sum_minor,
                    buyout_count=metric.buyout_count,
                    buyout_sum_minor=metric.buyout_sum_minor,
                    buyout_percent=metric.buyout_percent,
                    add_to_cart_percent=metric.add_to_cart_percent,
                    cart_to_order_percent=metric.cart_to_order_percent,
                    source_fingerprint=fingerprint,
                    raw_json=sanitize_payload(metric.raw_row()),
                    observed_at=observed_at,
                )
            )
        for metric, reason_code, fingerprint in quarantined:
            if fingerprint in existing_quarantine_fingerprints:
                continue
            self.db.add(
                models.WildberriesMetricQuarantine(
                    organization_id=organization_id,
                    connection_id=connection.id,
                    sync_audit_id=audit.id,
                    seller_account_ref=connection.seller_account_ref,
                    nm_id=metric.nm_id,
                    reason_code=reason_code,
                    period_start=period_start,
                    period_end=period_end,
                    source_fingerprint=fingerprint,
                    raw_row_json=sanitize_payload(metric.raw_row()),
                    observed_at=observed_at,
                )
            )
        connection.status = "connected"
        connection.auth_status = "api_key_verified"
        connection.last_checked_at = observed_at
        connection.last_sync_at = observed_at
        connection.last_error_code = None
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            winner = self.db.scalar(
                select(models.WildberriesAnalyticsSyncAudit).where(
                    models.WildberriesAnalyticsSyncAudit.organization_id
                    == organization_id,
                    models.WildberriesAnalyticsSyncAudit.idempotency_key == sync_key,
                )
            )
            if winner is not None:
                return self._replay(winner, request_hash=request_hash)
            raise WildberriesAnalyticsIdempotencyError(
                "wildberries_sync_concurrent_conflict"
            ) from exc
        self.db.refresh(audit)
        return self._result(audit, replayed=False)

    def readiness(self, *, organization_id: int | None) -> dict[str, Any]:
        if (
            isinstance(organization_id, bool)
            or not isinstance(organization_id, int)
            or organization_id <= 0
        ):
            return {
                "key": "wildberries_seller_analytics",
                "label": "Wildberries Seller Analytics",
                "platform": "wb",
                "mode": "official_api",
                "endpoint": WILDBERRIES_HISTORY_ENDPOINT,
                "auth_scheme": WILDBERRIES_AUTH_SCHEME,
                "ready": False,
                "can_attempt_sync": False,
                "status": "organization_scope_required",
                "status_label": "Нужна организация",
                "credential_reference_status": "missing",
                "last_sync_at": None,
                "connection_count": 0,
                "seller_account_count": 0,
                "verified_listing_count": 0,
                "metric_snapshot_count": 0,
                "quarantine_count": 0,
                "implemented_connector_types": ["wildberries_seller_analytics"],
                "connections": [],
            }
        connections = list(
            self.db.scalars(
                select(models.WildberriesAnalyticsConnection)
                .where(
                    models.WildberriesAnalyticsConnection.organization_id
                    == organization_id
                )
                .order_by(models.WildberriesAnalyticsConnection.id)
            ).all()
        )
        connection_rows: list[dict[str, Any]] = []
        for connection in connections:
            verified_listing_count = int(
                self.db.scalar(
                    select(func.count())
                    .select_from(models.MarketplaceListing)
                    .where(
                        models.MarketplaceListing.organization_id == organization_id,
                        models.MarketplaceListing.marketplace == "wildberries",
                        models.MarketplaceListing.seller_account_ref
                        == connection.seller_account_ref,
                        models.MarketplaceListing.status == "verified",
                        models.MarketplaceListing.nm_id.is_not(None),
                    )
                )
                or 0
            )
            try:
                credential_available = bool(
                    _CREDENTIAL_REF.fullmatch(str(connection.credential_ref or ""))
                    and self.credential_resolver.resolve(connection.credential_ref)
                )
            except Exception:
                credential_available = False
            can_attempt = (
                connection.status != "disabled"
                and credential_available
                and verified_listing_count > 0
            )
            verified = (
                connection.status == "connected"
                and connection.auth_status == "api_key_verified"
            )
            ready = can_attempt and verified
            if connection.status == "disabled":
                status = "disabled"
                status_label = "Отключён"
            elif not credential_available:
                status = "credential_unavailable"
                status_label = "Нужен API-ключ"
            elif not verified_listing_count:
                status = "needs_verified_listings"
                status_label = "Нужны подтверждённые nmID"
            elif not verified:
                status = "needs_verification"
                status_label = "Можно проверить подключение"
            else:
                status = "ready"
                status_label = "Официальный API подключён"
            connection_rows.append(
                {
                    "connection_id": connection.id,
                    "seller_account_ref": connection.seller_account_ref,
                    "connection_type": connection.connection_type,
                    "ready": ready,
                    "can_attempt_sync": can_attempt,
                    "status": status,
                    "status_label": status_label,
                    "credential_reference_status": (
                        "available"
                        if credential_available
                        else "configured_but_unavailable"
                    ),
                    "verified_listing_count": verified_listing_count,
                    "last_checked_at": (
                        connection.last_checked_at.isoformat()
                        if connection.last_checked_at
                        else None
                    ),
                    "last_sync_at": (
                        connection.last_sync_at.isoformat()
                        if connection.last_sync_at
                        else None
                    ),
                    "last_error_code": connection.last_error_code,
                }
            )
        any_ready = any(row["ready"] for row in connection_rows)
        any_attempt = any(row["can_attempt_sync"] for row in connection_rows)
        if any_ready:
            status = "ready"
            status_label = "Официальный API подключён"
        elif connections and any_attempt:
            status = "needs_verification"
            status_label = "Можно проверить подключение"
        elif connections:
            status = "action_required"
            status_label = "Нужна настройка"
        else:
            status = "not_configured"
            status_label = "Не подключён"
        credential_states = {
            str(row["credential_reference_status"]) for row in connection_rows
        }
        credential_status = (
            "missing"
            if not credential_states
            else next(iter(credential_states))
            if len(credential_states) == 1
            else "mixed"
        )
        last_sync_values = [
            str(row["last_sync_at"])
            for row in connection_rows
            if row["last_sync_at"]
        ]
        snapshot_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.WildberriesMetricSnapshot)
                .where(
                    models.WildberriesMetricSnapshot.organization_id == organization_id
                )
            )
            or 0
        )
        quarantine_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.WildberriesMetricQuarantine)
                .where(
                    models.WildberriesMetricQuarantine.organization_id == organization_id
                )
            )
            or 0
        )
        return {
            "key": "wildberries_seller_analytics",
            "label": "Wildberries Seller Analytics",
            "platform": "wb",
            "mode": "official_api",
            "endpoint": WILDBERRIES_HISTORY_ENDPOINT,
            "auth_scheme": WILDBERRIES_AUTH_SCHEME,
            "ready": any_ready,
            "can_attempt_sync": any_attempt,
            "status": status,
            "status_label": status_label,
            "credential_reference_status": credential_status,
            "last_sync_at": max(last_sync_values) if last_sync_values else None,
            "connection_count": len(connection_rows),
            "seller_account_count": len(connection_rows),
            "verified_listing_count": sum(
                int(row["verified_listing_count"]) for row in connection_rows
            ),
            "metric_snapshot_count": snapshot_count,
            "quarantine_count": quarantine_count,
            "implemented_connector_types": ["wildberries_seller_analytics"],
            "connections": connection_rows,
        }

    def _eligible_listings(
        self,
        *,
        organization_id: int,
        seller_account_ref: str,
        period_start: date,
        period_end: date,
    ) -> list[models.MarketplaceListing]:
        start_at = datetime.combine(period_start, time.min)
        end_exclusive = datetime.combine(period_end + timedelta(days=1), time.min)
        return list(
            self.db.scalars(
                select(models.MarketplaceListing)
                .where(
                    models.MarketplaceListing.organization_id == organization_id,
                    models.MarketplaceListing.marketplace == "wildberries",
                    models.MarketplaceListing.seller_account_ref == seller_account_ref,
                    models.MarketplaceListing.status == "verified",
                    models.MarketplaceListing.nm_id.is_not(None),
                    models.MarketplaceListing.valid_from < end_exclusive,
                    or_(
                        models.MarketplaceListing.valid_to.is_(None),
                        models.MarketplaceListing.valid_to > start_at,
                    ),
                )
                .order_by(
                    models.MarketplaceListing.nm_id,
                    models.MarketplaceListing.id,
                )
            ).all()
        )

    def _owned_connection(
        self,
        *,
        organization_id: int,
        connection_id: int,
    ) -> models.WildberriesAnalyticsConnection:
        connection = self.db.scalar(
            select(models.WildberriesAnalyticsConnection).where(
                models.WildberriesAnalyticsConnection.id == connection_id,
                models.WildberriesAnalyticsConnection.organization_id
                == organization_id,
            )
        )
        if connection is None:
            raise WildberriesAnalyticsScopeError(
                "wildberries_connection_not_found_in_organization"
            )
        return connection

    def _require_role(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        allowed_roles: set[str],
    ) -> models.Membership:
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == actor_user_profile_id,
                models.Membership.status == "active",
            )
        )
        if membership is None or membership.role not in allowed_roles:
            raise WildberriesAnalyticsScopeError(
                "wildberries_connector_role_required"
            )
        return membership

    @staticmethod
    def _quarantine_fingerprint(connection, metric, reason_code: str) -> str:
        return _canonical_sha256(
            {
                "organization_id": connection.organization_id,
                "seller_account_ref": connection.seller_account_ref,
                "nm_id": metric.nm_id,
                "metric_date": metric.metric_date.isoformat(),
                "reason_code": reason_code,
                "row": metric.raw_row(),
            }
        )

    def _record_failed_sync(
        self,
        *,
        connection: models.WildberriesAnalyticsConnection,
        organization_id: int,
        actor_user_profile_id: int,
        sync_key: str,
        request_hash: str,
        period_start: date,
        period_end: date,
        requested_nm_id_count: int,
        page_count: int,
        error_code: str,
    ) -> None:
        safe_code = (
            error_code
            if re.fullmatch(r"[a-z0-9_]{1,160}", str(error_code or ""))
            else "wildberries_sync_failed"
        )
        now = utcnow()
        self.db.add(
            models.WildberriesAnalyticsSyncAudit(
                organization_id=organization_id,
                connection_id=connection.id,
                actor_user_profile_id=actor_user_profile_id,
                seller_account_ref=connection.seller_account_ref,
                idempotency_key=sync_key,
                request_body_sha256=request_hash,
                period_start=period_start,
                period_end=period_end,
                status="failed",
                error_code=safe_code,
                page_count=page_count,
                requested_nm_id_count=requested_nm_id_count,
            )
        )
        connection.status = "error"
        connection.last_checked_at = now
        connection.last_error_code = safe_code
        self.db.commit()

    @staticmethod
    def _result(
        audit: models.WildberriesAnalyticsSyncAudit,
        *,
        replayed: bool,
    ) -> WildberriesSyncResult:
        return WildberriesSyncResult(
            status=audit.status,
            audit_id=audit.id,
            page_count=audit.page_count,
            requested_nm_id_count=audit.requested_nm_id_count,
            response_product_count=audit.response_product_count,
            snapshot_count=audit.snapshot_count,
            new_snapshot_count=audit.new_snapshot_count,
            quarantine_count=audit.quarantine_count,
            replayed=replayed,
        )

    def _replay(
        self,
        audit: models.WildberriesAnalyticsSyncAudit,
        *,
        request_hash: str,
    ) -> WildberriesSyncResult:
        if audit.request_body_sha256 != request_hash:
            raise WildberriesAnalyticsIdempotencyError(
                "wildberries_sync_idempotency_payload_conflict"
            )
        if audit.status == "failed":
            raise WildberriesAnalyticsIdempotencyError(
                "wildberries_sync_idempotency_previously_failed"
            )
        return self._result(audit, replayed=True)
