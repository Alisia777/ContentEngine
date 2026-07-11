from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_wb_marketplace_listings.db")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app import models
from app.database import Base, SessionLocal, engine
from app.marketplace_listings import (
    ListingAmbiguityError,
    ListingNotFoundError,
    ListingValidationError,
    MarketplaceListingService,
)
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers.marketplace_listings import router


@pytest.fixture(autouse=True)
def reset_listing_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def make_user(db, *, slug: str) -> PublicPilotUser:
    organization = models.Organization(name=slug.title(), slug=slug)
    profile = models.UserProfile(
        supabase_user_id=f"test:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"{slug.title()} Owner",
    )
    db.add_all([organization, profile])
    db.flush()
    membership = models.Membership(
        organization_id=organization.id,
        user_profile_id=profile.id,
        role="owner",
        status="active",
    )
    db.add(membership)
    db.commit()
    return PublicPilotUser(profile=profile, organization=organization, membership=membership)


def make_product(db, user: PublicPilotUser, *, sku: str) -> models.Product:
    product = models.Product(
        organization_id=user.organization.id,
        sku=sku,
        brand="Own Brand",
        title=f"Product {sku}",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def create_verified_listing(
    db,
    user: PublicPilotUser,
    product: models.Product,
    *,
    seller_account_ref: str,
    nm_id: str,
    vendor_code: str | None = None,
) -> models.MarketplaceListing:
    service = MarketplaceListingService(db)
    listing = service.create_listing(
        organization_id=user.organization.id,
        actor_user_profile_id=user.profile.id,
        product_id=product.id,
        seller_account_ref=seller_account_ref,
        nm_id=nm_id,
        vendor_code=vendor_code,
        listing_url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx?tracking=removed",
    )
    return service.verify_listing(
        organization_id=user.organization.id,
        listing_id=listing.id,
        verified_by=user.profile.id,
    )


def test_models_scope_unique_keys_by_organization_marketplace_and_seller_account():
    listing_unique_sets = {
        tuple(constraint["column_names"])
        for constraint in inspect(engine).get_unique_constraints("marketplace_listings")
    }
    required_prefix = ("organization_id", "marketplace", "seller_account_ref")
    assert required_prefix + ("nm_id",) in listing_unique_sets
    assert required_prefix + ("vendor_code",) in listing_unique_sets
    assert required_prefix + ("barcode",) in listing_unique_sets

    alias_unique_sets = {
        tuple(index["column_names"])
        for index in inspect(engine).get_indexes("listing_aliases")
        if index["unique"]
    }
    assert required_prefix + ("alias_type", "alias_value") in alias_unique_sets


def test_organization_isolation_covers_products_listings_aliases_and_resolution():
    with SessionLocal() as db:
        alpha = make_user(db, slug="alpha-listings")
        beta = make_user(db, slug="beta-listings")
        alpha_product = make_product(db, alpha, sku="ALPHA-OWN-1")
        beta_product = make_product(db, beta, sku="BETA-OWN-1")
        alpha_listing = create_verified_listing(
            db,
            alpha,
            alpha_product,
            seller_account_ref="seller-main",
            nm_id="100001",
        )
        beta_listing = create_verified_listing(
            db,
            beta,
            beta_product,
            seller_account_ref="seller-main",
            nm_id="100001",
        )

        service = MarketplaceListingService(db)
        assert [item.id for item in service.list_listings(organization_id=alpha.organization.id)] == [
            alpha_listing.id
        ]
        assert service.resolve_exact(
            organization_id=beta.organization.id,
            marketplace="wildberries",
            seller_account_ref="seller-main",
            identifier_type="nm_id",
            identifier_value="100001",
        ).id == beta_listing.id

        with pytest.raises(ListingNotFoundError, match="product not found in organization"):
            service.create_listing(
                organization_id=beta.organization.id,
                actor_user_profile_id=beta.profile.id,
                product_id=alpha_product.id,
                seller_account_ref="seller-main",
                nm_id="100002",
            )
        with pytest.raises(ListingNotFoundError, match="listing not found in organization"):
            service.create_alias(
                organization_id=beta.organization.id,
                approved_by=beta.profile.id,
                canonical_listing_id=alpha_listing.id,
                current_listing_id=beta_listing.id,
                alias_type="legacy_ref",
                alias_value="own-old-card",
                reason="Explicit ownership-preserving replacement",
            )


def test_exact_resolution_fails_closed_when_seller_account_is_ambiguous():
    with SessionLocal() as db:
        user = make_user(db, slug="ambiguous-listings")
        first_product = make_product(db, user, sku="AMB-OWN-1")
        second_product = make_product(db, user, sku="AMB-OWN-2")
        first = create_verified_listing(
            db,
            user,
            first_product,
            seller_account_ref="seller-east",
            nm_id="200001",
        )
        second = create_verified_listing(
            db,
            user,
            second_product,
            seller_account_ref="seller-west",
            nm_id="200001",
        )

        service = MarketplaceListingService(db)
        with pytest.raises(ListingAmbiguityError) as exc_info:
            service.resolve_exact(
                organization_id=user.organization.id,
                marketplace="wildberries",
                identifier_type="nm_id",
                identifier_value="200001",
            )
        assert exc_info.value.disposition == "quarantine"
        assert exc_info.value.candidate_count == 2
        assert service.resolve_exact(
            organization_id=user.organization.id,
            marketplace="wildberries",
            seller_account_ref="seller-east",
            identifier_type="nm_id",
            identifier_value="200001",
        ).id == first.id
        assert first.id != second.id

        api = FastAPI()
        api.include_router(router)
        api.dependency_overrides[get_current_public_user] = lambda: user
        with TestClient(api) as client:
            response = client.post(
                "/api/marketplace-listings/resolve",
                json={
                    "marketplace": "wildberries",
                    "identifier_type": "nm_id",
                    "identifier_value": "200001",
                },
            )
        assert response.status_code == 409
        assert response.json()["detail"] == {
            "code": "ambiguous_listing",
            "message": "multiple exact matches; automatic selection is prohibited",
            "disposition": "quarantine",
            "candidate_count": 2,
        }


def test_alias_replacement_keeps_complete_approved_history_and_exact_resolution():
    with SessionLocal() as db:
        user = make_user(db, slug="history-listings")
        canonical_product = make_product(db, user, sku="HISTORY-CANONICAL")
        first_product = make_product(db, user, sku="HISTORY-CURRENT-1")
        second_product = make_product(db, user, sku="HISTORY-CURRENT-2")
        canonical = create_verified_listing(
            db,
            user,
            canonical_product,
            seller_account_ref="seller-history",
            nm_id="300001",
        )
        first = create_verified_listing(
            db,
            user,
            first_product,
            seller_account_ref="seller-history",
            nm_id="300002",
        )
        second = create_verified_listing(
            db,
            user,
            second_product,
            seller_account_ref="seller-history",
            nm_id="300003",
        )
        service = MarketplaceListingService(db)
        first_start = datetime.now(UTC) + timedelta(seconds=1)
        first_alias = service.create_alias(
            organization_id=user.organization.id,
            approved_by=user.profile.id,
            canonical_listing_id=canonical.id,
            current_listing_id=first.id,
            alias_type="legacy_ref",
            alias_value="OWN-CARD-LEGACY-1",
            reason="Approved transition to the first owned card",
            valid_from=first_start,
        )
        second_start = first_start + timedelta(seconds=1)
        second_alias = service.create_alias(
            organization_id=user.organization.id,
            approved_by=user.profile.id,
            canonical_listing_id=canonical.id,
            current_listing_id=second.id,
            alias_type="legacy_ref",
            alias_value="OWN-CARD-LEGACY-1",
            reason="Approved transition to the current owned card",
            valid_from=second_start,
        )

        db.refresh(first_alias)
        history = service.list_history(
            organization_id=user.organization.id,
            listing_id=canonical.id,
        )
        assert first_alias.valid_to == second_alias.valid_from
        assert [(item.previous_listing_id, item.current_listing_id) for item in history] == [
            (canonical.id, first.id),
            (first.id, second.id),
        ]
        assert history[0].valid_to == history[1].valid_from
        assert {item.approved_by for item in history} == {user.profile.id}
        assert service.resolve_exact(
            organization_id=user.organization.id,
            marketplace="wildberries",
            seller_account_ref="seller-history",
            identifier_type="alias",
            alias_type="legacy_ref",
            identifier_value="OWN-CARD-LEGACY-1",
            at=second_start + timedelta(milliseconds=1),
        ).id == second.id


def test_service_and_api_validation_reject_unowned_unverified_and_spoofed_input():
    with SessionLocal() as db:
        user = make_user(db, slug="validation-listings")
        unscoped_product = models.Product(sku="UNSCOPED-1", brand="Legacy", title="Unscoped")
        db.add(unscoped_product)
        product = make_product(db, user, sku="VALID-OWN-1")
        db.commit()
        service = MarketplaceListingService(db)

        with pytest.raises(ListingNotFoundError):
            service.create_listing(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                product_id=unscoped_product.id,
                seller_account_ref="seller-valid",
                nm_id="400001",
            )
        with pytest.raises(ListingValidationError, match="digits only"):
            service.create_listing(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                product_id=product.id,
                seller_account_ref="seller-valid",
                nm_id="40O001",
            )
        with pytest.raises(ListingValidationError, match="Wildberries URL"):
            service.create_listing(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                product_id=product.id,
                seller_account_ref="seller-valid",
                nm_id="400001",
                listing_url="https://example.test/catalog/400001",
            )

        draft = service.create_listing(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            product_id=product.id,
            seller_account_ref="seller-valid",
            nm_id="400002",
        )
        with pytest.raises(ListingValidationError, match="must be verified"):
            service.create_alias(
                organization_id=user.organization.id,
                approved_by=user.profile.id,
                canonical_listing_id=draft.id,
                current_listing_id=draft.id,
                alias_type="legacy_ref",
                alias_value="OWN-DRAFT",
                reason="Draft must not resolve",
            )

        api = FastAPI()
        api.include_router(router)
        api.dependency_overrides[get_current_public_user] = lambda: user
        with TestClient(api) as client:
            spoofed_create = client.post(
                "/api/marketplace-listings",
                json={
                    "organization_id": 999,
                    "verified_by": 999,
                    "product_id": product.id,
                    "seller_account_ref": "seller-valid",
                    "nm_id": "400003",
                },
            )
            spoofed_alias = client.post(
                "/api/marketplace-listings/aliases",
                json={
                    "canonical_listing_id": draft.id,
                    "current_listing_id": draft.id,
                    "alias_type": "legacy_ref",
                    "alias_value": "OWN-DRAFT",
                    "reason": "Should be rejected by schema",
                    "approved_by": 999,
                },
            )
        assert spoofed_create.status_code == 422
        assert spoofed_alias.status_code == 422
        assert db.scalar(select(models.MarketplaceListing).where(models.MarketplaceListing.nm_id == "400003")) is None


def test_viewer_can_read_but_cannot_change_marketplace_mappings():
    with SessionLocal() as db:
        user = make_user(db, slug="viewer-listings")
        product = make_product(db, user, sku="VIEWER-OWN-1")
        user.membership.role = "viewer"
        db.commit()

        api = FastAPI()
        api.include_router(router)
        api.dependency_overrides[get_current_public_user] = lambda: user
        with TestClient(api) as client:
            listing_page = client.get("/api/marketplace-listings")
            create_attempt = client.post(
                "/api/marketplace-listings",
                json={
                    "product_id": product.id,
                    "seller_account_ref": "seller-viewer",
                    "nm_id": "500001",
                },
            )

        assert listing_page.status_code == 200
        assert create_attempt.status_code == 403
        assert db.scalar(select(models.MarketplaceListing).where(models.MarketplaceListing.nm_id == "500001")) is None
