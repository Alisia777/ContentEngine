from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import json

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models
from app.database import (
    Base,
    SessionLocal,
    _ensure_wildberries_seller_analytics_schema,
    engine,
)
from app.interface_productization.factory_dashboard_service import (
    FactoryDashboardService,
)
from app.wildberries_analytics import (
    MAX_NM_IDS_PER_PAGE,
    WILDBERRIES_AUTH_SCHEME,
    WILDBERRIES_HISTORY_ENDPOINT,
    WildberriesAnalyticsConfigurationError,
    WildberriesAnalyticsIdempotencyError,
    WildberriesAnalyticsPeriodError,
    WildberriesAnalyticsResponseError,
    WildberriesAnalyticsScopeError,
    WildberriesSellerAnalyticsService,
)


SECRET_API_KEY = "wb-super-secret-api-key-for-tests"
PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 7)


class FakeCredentialResolver:
    def __init__(self, value: str | None = SECRET_API_KEY):
        self.value = value
        self.references: list[str] = []

    def resolve(self, credential_ref: str) -> str | None:
        self.references.append(credential_ref)
        return self.value


class FakeWildberriesGateway:
    def __init__(self, responder=None):
        self.responder = responder or self._default_response
        self.calls: list[dict] = []

    def post_product_history(self, *, api_key: str, body: dict) -> dict:
        self.calls.append({"api_key": api_key, "body": deepcopy(body)})
        return self.responder(body)

    @staticmethod
    def _default_response(body: dict) -> dict:
        return {
            "data": [
                _product_history(nm_id, metric_date=body["selectedPeriod"]["start"])
                for nm_id in body["nmIds"]
            ]
        }


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_wildberries_seller_analytics_schema(engine)
    yield


def _product_history(
    nm_id: int,
    *,
    metric_date: str = "2026-07-01",
    history_overrides: dict | None = None,
) -> dict:
    history = {
        "date": metric_date,
        "openCount": 120,
        "cartCount": 18,
        "orderCount": 7,
        "orderSum": 1234.56,
        "buyoutCount": 5,
        "buyoutSum": 900.5,
        "buyoutPercent": 71.43,
        "addToCartPercent": 15.0,
        "cartToOrderPercent": 38.89,
    }
    history.update(history_overrides or {})
    return {
        "product": {
            "nmId": int(nm_id),
            "title": f"Owned product {nm_id}",
            "vendorCode": f"VC-{nm_id}",
            "brandName": "ALTEA",
        },
        "history": [history],
    }


def _seed_owned_listings(
    db,
    *,
    slug: str = "wb-official",
    seller_account_ref: str = "main-seller",
    nm_ids: tuple[int, ...] = (100001,),
):
    organization = models.Organization(name=f"Factory {slug}", slug=slug)
    actor = models.UserProfile(
        supabase_user_id=f"{slug}-owner",
        email=f"{slug}@example.test",
        status="active",
        is_active=True,
    )
    db.add_all([organization, actor])
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=actor.id,
            role="owner",
            status="active",
        )
    )
    listings = []
    for index, nm_id in enumerate(nm_ids, start=1):
        product = models.Product(
            organization_id=organization.id,
            sku=f"{slug}-SKU-{index}",
            brand="ALTEA",
            title=f"Owned product {index}",
        )
        db.add(product)
        db.flush()
        listing = models.MarketplaceListing(
            organization_id=organization.id,
            product_id=product.id,
            marketplace="wildberries",
            seller_account_ref=seller_account_ref,
            nm_id=str(nm_id),
            vendor_code=f"VC-{nm_id}",
            status="verified",
            valid_from=datetime(2025, 1, 1),
            verified_at=datetime(2025, 1, 1),
            verified_by=actor.id,
        )
        db.add(listing)
        db.flush()
        listings.append(listing)
    db.commit()
    return organization, actor, listings


def _configured_service(db, organization, actor, *, gateway=None, resolver=None):
    resolver = resolver or FakeCredentialResolver()
    gateway = gateway or FakeWildberriesGateway()
    service = WildberriesSellerAnalyticsService(
        db,
        credential_resolver=resolver,
        http_gateway=gateway,
    )
    connection = service.configure_connection(
        organization_id=organization.id,
        actor_user_profile_id=actor.id,
        seller_account_ref="main-seller",
        credential_ref="env:WB_SELLER_ANALYTICS_TOKEN",
    )
    return service, connection, gateway, resolver


def test_official_sync_persists_exact_org_owned_snapshot_without_raw_api_key(monkeypatch):
    monkeypatch.setenv("WB_SELLER_ANALYTICS_TOKEN", SECRET_API_KEY)
    with SessionLocal() as db:
        organization, actor, listings = _seed_owned_listings(db)
        service, connection, gateway, resolver = _configured_service(
            db, organization, actor
        )

        result = service.sync(
            organization_id=organization.id,
            actor_user_profile_id=actor.id,
            connection_id=connection.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="wb-sync-exact-owned-1",
        )

        snapshot = db.scalar(select(models.WildberriesMetricSnapshot))
        audit = db.get(models.WildberriesAnalyticsSyncAudit, result.audit_id)
        assert result.status == "completed"
        assert result.snapshot_count == result.new_snapshot_count == 1
        assert result.quarantine_count == 0
        assert gateway.calls == [
            {
                "api_key": SECRET_API_KEY,
                "body": {
                    "selectedPeriod": {"start": "2026-07-01", "end": "2026-07-07"},
                    "nmIds": [100001],
                    "skipDeletedNm": True,
                },
            }
        ]
        assert resolver.references == ["env:WB_SELLER_ANALYTICS_TOKEN"]
        assert snapshot.organization_id == organization.id
        assert snapshot.listing_id == listings[0].id
        assert snapshot.product_id == listings[0].product_id
        assert snapshot.nm_id == "100001"
        assert snapshot.order_sum_minor == 123456
        assert snapshot.buyout_sum_minor == 90050
        assert audit.request_body_sha256 and audit.response_sha256
        assert connection.credential_ref == "env:WB_SELLER_ANALYTICS_TOKEN"
        persisted = json.dumps(
            {
                "connection": connection.settings_json,
                "audit": {
                    "error": audit.error_code,
                    "request": audit.request_body_sha256,
                    "response": audit.response_sha256,
                },
                "snapshot": snapshot.raw_json,
                "readiness": service.readiness(organization_id=organization.id),
            },
            default=str,
        )
        assert SECRET_API_KEY not in persisted
        readiness = service.readiness(organization_id=organization.id)
        assert readiness["ready"] is True
        assert readiness["mode"] == "official_api"
        assert readiness["auth_scheme"] == WILDBERRIES_AUTH_SCHEME
        assert readiness["endpoint"] == WILDBERRIES_HISTORY_ENDPOINT
        assert readiness["metric_snapshot_count"] == 1

        dashboard = FactoryDashboardService(db).snapshot(
            user_profile_id=actor.id,
            organization_id=organization.id,
        )
        assert dashboard["wildberries_seller_analytics"]["ready"] is True
        assert dashboard["metrics"]["wildberries_metric_snapshots"] == 1


def test_connection_rejects_raw_token_and_cross_organization_use():
    with SessionLocal() as db:
        first, first_actor, _ = _seed_owned_listings(db, slug="first-wb")
        second, second_actor, _ = _seed_owned_listings(db, slug="second-wb")
        service, connection, gateway, _resolver = _configured_service(
            db, first, first_actor
        )

        with pytest.raises(WildberriesAnalyticsConfigurationError):
            service.configure_connection(
                organization_id=first.id,
                actor_user_profile_id=first_actor.id,
                seller_account_ref="main-seller",
                credential_ref="eyJhbGciOiJIUzI1NiJ9.raw-secret-token",
            )
        db.add(
            models.WildberriesAnalyticsConnection(
                organization_id=first.id,
                seller_account_ref="raw-token-bypass",
                credential_ref="raw-secret-token",
                created_by_user_profile_id=first_actor.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        with pytest.raises(WildberriesAnalyticsScopeError):
            service.sync(
                organization_id=second.id,
                actor_user_profile_id=second_actor.id,
                connection_id=connection.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                idempotency_key="cross-org-must-fail",
            )
        assert gateway.calls == []
        assert db.scalar(select(func.count()).select_from(models.WildberriesAnalyticsConnection)) == 1


def test_period_is_limited_to_seven_inclusive_days_before_transport():
    with SessionLocal() as db:
        organization, actor, _ = _seed_owned_listings(db, slug="period-wb")
        service, connection, gateway, _resolver = _configured_service(
            db, organization, actor
        )

        with pytest.raises(
            WildberriesAnalyticsPeriodError,
            match="wildberries_period_exceeds_seven_days",
        ):
            service.sync(
                organization_id=organization.id,
                actor_user_profile_id=actor.id,
                connection_id=connection.id,
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 8),
                idempotency_key="period-too-large",
            )
        assert gateway.calls == []
        assert db.scalar(select(func.count()).select_from(models.WildberriesAnalyticsSyncAudit)) == 0


def test_owned_nm_ids_are_paginated_at_official_limit():
    with SessionLocal() as db:
        nm_ids = tuple(range(200001, 200001 + MAX_NM_IDS_PER_PAGE + 1))
        organization, actor, _ = _seed_owned_listings(
            db,
            slug="pagination-wb",
            nm_ids=nm_ids,
        )
        service, connection, gateway, _resolver = _configured_service(
            db, organization, actor
        )

        result = service.sync(
            organization_id=organization.id,
            actor_user_profile_id=actor.id,
            connection_id=connection.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="wb-pagination-21",
        )

        assert result.page_count == 2
        assert result.requested_nm_id_count == len(nm_ids)
        assert result.snapshot_count == len(nm_ids)
        assert [len(call["body"]["nmIds"]) for call in gateway.calls] == [
            MAX_NM_IDS_PER_PAGE,
            1,
        ]
        flattened = [nm_id for call in gateway.calls for nm_id in call["body"]["nmIds"]]
        assert flattened == list(nm_ids)


def test_sync_replay_is_idempotent_and_changed_payload_conflicts():
    with SessionLocal() as db:
        organization, actor, _ = _seed_owned_listings(db, slug="idempotent-wb")
        service, connection, gateway, _resolver = _configured_service(
            db, organization, actor
        )
        kwargs = {
            "organization_id": organization.id,
            "actor_user_profile_id": actor.id,
            "connection_id": connection.id,
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "idempotency_key": "wb-idempotent-one",
        }

        first = service.sync(**kwargs)
        replay = service.sync(**kwargs)

        assert first.audit_id == replay.audit_id
        assert replay.replayed is True
        assert len(gateway.calls) == 1
        assert db.scalar(select(func.count()).select_from(models.WildberriesMetricSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(models.WildberriesAnalyticsSyncAudit)) == 1

        with pytest.raises(
            WildberriesAnalyticsIdempotencyError,
            match="wildberries_sync_idempotency_payload_conflict",
        ):
            service.sync(
                **{
                    **kwargs,
                    "period_start": date(2026, 7, 2),
                }
            )
        assert len(gateway.calls) == 1


def test_unknown_and_ambiguous_nm_ids_are_quarantined_not_guessed():
    def response(_body):
        return {
            "data": [
                _product_history(300001),
                _product_history(399999),
            ]
        }

    with SessionLocal() as db:
        organization, actor, listings = _seed_owned_listings(
            db,
            slug="quarantine-wb",
            nm_ids=(300001, 300002),
        )
        # Explicit alias data can make a historical nmID point to another
        # verified listing.  A direct card plus that alias is deliberately
        # ambiguous and must never be guessed by the connector.
        db.add(
            models.ListingAlias(
                organization_id=organization.id,
                marketplace="wildberries",
                seller_account_ref="main-seller",
                canonical_listing_id=listings[1].id,
                current_listing_id=listings[1].id,
                alias_type="nm_id",
                alias_value="300001",
                valid_from=datetime(2025, 2, 1),
                reason="Explicit ambiguity regression fixture",
                approved_by=actor.id,
            )
        )
        db.commit()
        gateway = FakeWildberriesGateway(response)
        service, connection, _gateway, _resolver = _configured_service(
            db,
            organization,
            actor,
            gateway=gateway,
        )

        result = service.sync(
            organization_id=organization.id,
            actor_user_profile_id=actor.id,
            connection_id=connection.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="wb-quarantine-exact",
        )

        reasons = set(db.scalars(select(models.WildberriesMetricQuarantine.reason_code)))
        assert result.status == "completed_with_quarantine"
        assert result.snapshot_count == 0
        assert result.quarantine_count == 2
        assert reasons == {"unknown_nm_id", "ambiguous_nm_id"}
        assert db.scalar(select(func.count()).select_from(models.WildberriesMetricSnapshot)) == 0


def test_strict_invalid_response_is_atomically_rejected_and_audited():
    def invalid_response(body):
        return {
            "data": [
                _product_history(
                    body["nmIds"][0],
                    history_overrides={"openCount": -1},
                )
            ]
        }

    with SessionLocal() as db:
        organization, actor, _ = _seed_owned_listings(db, slug="strict-wb")
        gateway = FakeWildberriesGateway(invalid_response)
        service, connection, _gateway, _resolver = _configured_service(
            db,
            organization,
            actor,
            gateway=gateway,
        )

        with pytest.raises(
            WildberriesAnalyticsResponseError,
            match="wildberries_official_api_open_count_invalid",
        ):
            service.sync(
                organization_id=organization.id,
                actor_user_profile_id=actor.id,
                connection_id=connection.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                idempotency_key="wb-invalid-response",
            )

        audit = db.scalar(select(models.WildberriesAnalyticsSyncAudit))
        assert audit.status == "failed"
        assert audit.error_code == "wildberries_official_api_open_count_invalid"
        assert SECRET_API_KEY not in json.dumps(audit.__dict__, default=str)
        assert db.scalar(select(func.count()).select_from(models.WildberriesMetricSnapshot)) == 0
        assert db.scalar(select(func.count()).select_from(models.WildberriesMetricQuarantine)) == 0


def test_sqlite_upgrade_installs_append_only_evidence_guards():
    for table in (
        models.WildberriesMetricQuarantine.__table__,
        models.WildberriesMetricSnapshot.__table__,
        models.WildberriesAnalyticsSyncAudit.__table__,
        models.WildberriesAnalyticsConnection.__table__,
    ):
        table.drop(bind=engine, checkfirst=True)
    _ensure_wildberries_seller_analytics_schema(engine)

    with SessionLocal() as db:
        organization, actor, _ = _seed_owned_listings(db, slug="append-wb")
        service, connection, _gateway, _resolver = _configured_service(
            db, organization, actor
        )
        result = service.sync(
            organization_id=organization.id,
            actor_user_profile_id=actor.id,
            connection_id=connection.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="wb-append-only",
        )

        trigger_names = set(
            db.scalars(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE 'wildberries_%'"
                )
            ).all()
        )
        assert "wildberries_analytics_sync_audit_no_update" in trigger_names
        assert "wildberries_metric_snapshot_no_delete" in trigger_names
        assert "wildberries_metric_quarantine_no_update" in trigger_names
        with pytest.raises(SQLAlchemyError):
            db.execute(
                text(
                    "UPDATE wildberries_analytics_sync_audits "
                    "SET status = 'failed' WHERE id = :audit_id"
                ),
                {"audit_id": result.audit_id},
            )
            db.commit()
        db.rollback()
