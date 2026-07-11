from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.product_telemetry import (
    ALLOWED_EVENT_NAMES,
    ProductTelemetryService,
    TelemetryIdempotencyConflict,
    TelemetryValidationError,
)
from app.product_telemetry.service import MAX_PROPERTIES_INPUT_BYTES
from app.public_pilot.auth import ensure_public_pilot_user
from app.routers.product_events import router as product_events_router


@pytest.fixture(autouse=True)
def reset_telemetry_db():
    previous_auth_required = os.environ.get("QVF_AUTH_REQUIRED")
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    if previous_auth_required is None:
        os.environ.pop("QVF_AUTH_REQUIRED", None)
    else:
        os.environ["QVF_AUTH_REQUIRED"] = previous_auth_required
    get_settings.cache_clear()


def telemetry_api() -> TestClient:
    test_app = FastAPI()
    test_app.include_router(product_events_router)
    return TestClient(test_app)


def public_user(db, *, email: str = "producer@telemetry.local", role: str = "producer"):
    return ensure_public_pilot_user(db, email=email, display_name="Telemetry Producer", role=role)


def test_factory_event_table_is_create_all_safe_and_has_measurement_columns():
    columns = {column["name"] for column in inspect(engine).get_columns("factory_events")}
    assert {
        "event_name",
        "event_version",
        "occurred_at",
        "received_at",
        "organization_id",
        "user_profile_id",
        "session_id",
        "role",
        "factory_run_id",
        "entity_type",
        "entity_id",
        "product_id",
        "sku",
        "campaign_id",
        "video_job_id",
        "publishing_task_id",
        "source",
        "idempotency_key",
        "properties_json",
    }.issubset(columns)
    unique_columns = {
        column
        for constraint in inspect(engine).get_unique_constraints("factory_events")
        for column in constraint["column_names"]
    }
    assert "idempotency_key" in unique_columns


def test_service_records_authoritative_context_and_sanitizes_properties():
    occurred_at = datetime.now(UTC) - timedelta(minutes=1)
    with SessionLocal() as db:
        user = public_user(db)
        result = ProductTelemetryService(db).record_event(
            event_name="generation_requested",
            event_version=1,
            occurred_at=occurred_at,
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            session_id="session:test-1",
            role=user.role,
            factory_run_id="factory:run-9",
            entity_type="product",
            entity_id="BOMBBAR-42",
            product_id=None,
            sku="BOMBBAR-42",
            source="web",
            idempotency_key="event:test-1",
            properties={
                "area": "video_factory",
                "api_key": "do-not-store",
                "contact": "operator@example.com",
                "authorization": "Bearer secret-value",
                "url": "https://example.test/workbench?token=secret#private",
                "note": "safe note " * 80,
            },
        )

        assert result.created is True
        event = result.event
        assert event.organization_id == user.organization.id
        assert event.user_profile_id == user.profile.id
        assert event.role == "producer"
        assert event.occurred_at == occurred_at.replace(tzinfo=None)
        assert event.received_at >= event.occurred_at
        assert event.properties_json["api_key"] == "[redacted]"
        assert event.properties_json["authorization"] == "[redacted]"
        assert event.properties_json["contact"] == "[redacted-email]"
        assert event.properties_json["url"] == "https://example.test/workbench"
        assert event.properties_json["note"].endswith("…")
        assert len(event.properties_json["note"]) == 500


def test_service_whitelist_source_rules_and_size_limits_are_enforced():
    assert {
        "session_started",
        "page_viewed",
        "primary_action_clicked",
        "product_created",
        "product_selected",
        "asset_gate_passed",
        "generation_succeeded",
        "video_approved",
        "publication_completed",
        "first_order_attributed",
    }.issubset(ALLOWED_EVENT_NAMES)

    with SessionLocal() as db:
        user = public_user(db)
        service = ProductTelemetryService(db)
        base = {
            "organization_id": user.organization.id,
            "user_profile_id": user.profile.id,
            "role": user.role,
            "idempotency_key": "event:validation",
        }
        with pytest.raises(TelemetryValidationError, match="not allowed"):
            service.record_event(event_name="arbitrary_client_event", **base)
        with pytest.raises(TelemetryValidationError, match="server-only"):
            service.record_event(event_name="generation_succeeded", source="web", **base)
        with pytest.raises(TelemetryValidationError, match="server-only"):
            service.record_event(
                event_name="product_created",
                source="web",
                idempotency_key="event:product-created-web",
                **{key: value for key, value in base.items() if key != "idempotency_key"},
            )
        with pytest.raises(TelemetryValidationError, match="cannot exceed"):
            service.record_event(
                event_name="page_viewed",
                source="web",
                properties={"blob": "x" * (MAX_PROPERTIES_INPUT_BYTES + 1)},
                **base,
            )


def test_service_is_idempotent_and_rejects_key_reuse_for_another_event():
    with SessionLocal() as db:
        user = public_user(db)
        service = ProductTelemetryService(db)
        common = {
            "organization_id": user.organization.id,
            "user_profile_id": user.profile.id,
            "role": user.role,
            "session_id": "session:idempotency",
            "source": "web",
            "idempotency_key": "event:idempotency",
        }
        first = service.record_event(event_name="page_viewed", properties={"path": "/workbench"}, **common)
        duplicate = service.record_event(event_name="page_viewed", properties={"path": "/ignored-retry"}, **common)

        assert first.created is True
        assert duplicate.created is False
        assert duplicate.event.id == first.event.id
        assert db.scalar(select(func.count()).select_from(models.FactoryEvent)) == 1
        assert duplicate.event.properties_json == {"path": "/workbench"}

        with pytest.raises(TelemetryIdempotencyConflict):
            service.record_event(event_name="help_opened", **common)


def test_factory_event_rejects_orm_update_and_delete():
    with SessionLocal() as db:
        user = public_user(db)
        event = ProductTelemetryService(db).record_event(
            event_name="page_viewed",
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            role=user.role,
            source="web",
            idempotency_key="event:append-only",
        ).event

        event.role = "viewer"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()

        persisted = db.get(models.FactoryEvent, event.id)
        db.delete(persisted)
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()
        assert db.get(models.FactoryEvent, event.id) is not None


def test_product_events_endpoint_uses_authenticated_user_and_is_idempotent():
    headers = {
        "x-public-pilot-email": "endpoint-producer@telemetry.local",
        "x-public-pilot-role": "producer",
    }
    payload = {
        "event_name": "primary_action_clicked",
        "event_version": 1,
        "occurred_at": "2026-07-11T10:00:00Z",
        "session_id": "session:endpoint",
        "source": "web",
        "idempotency_key": "event:endpoint",
        "entity_type": "page",
        "entity_id": "workbench",
        "properties": {"path": "/workbench", "password": "never-store"},
    }
    with telemetry_api() as client:
        created = client.post("/api/product-events", json=payload, headers=headers)
        duplicate = client.post("/api/product-events", json=payload, headers=headers)

    assert created.status_code == 202
    assert created.json()["accepted"] is True
    assert created.json()["duplicate"] is False
    assert duplicate.status_code == 202
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["event_id"] == created.json()["event_id"]

    with SessionLocal() as db:
        event = db.scalar(select(models.FactoryEvent).where(models.FactoryEvent.id == created.json()["event_id"]))
        membership = db.scalar(select(models.Membership).where(models.Membership.user_profile_id == event.user_profile_id))
        profile = db.get(models.UserProfile, event.user_profile_id)
        assert profile.email == headers["x-public-pilot-email"]
        assert membership.organization_id == event.organization_id
        assert event.role == "producer"
        assert event.properties_json["password"] == "[redacted]"


def test_product_events_endpoint_rejects_identity_spoofing_unknown_events_and_anonymous_access():
    headers = {"x-public-pilot-email": "safe-user@telemetry.local"}
    base = {
        "event_name": "page_viewed",
        "session_id": "session:safe",
        "source": "web",
        "idempotency_key": "event:safe",
        "properties": {},
    }
    with telemetry_api() as client:
        spoofed = client.post(
            "/api/product-events",
            json={**base, "organization_id": 999, "user_profile_id": 999, "role": "owner"},
            headers=headers,
        )
        unknown = client.post(
            "/api/product-events",
            json={**base, "event_name": "capture_everything", "idempotency_key": "event:unknown"},
            headers=headers,
        )

        assert spoofed.status_code == 422
        assert unknown.status_code == 422

        os.environ["QVF_AUTH_REQUIRED"] = "true"
        get_settings.cache_clear()
        anonymous = client.post(
            "/api/product-events",
            json={**base, "idempotency_key": "event:anonymous"},
        )
        assert anonymous.status_code == 401


def test_browser_telemetry_tracks_page_and_declared_clicks_without_sensitive_dom_data():
    source = Path("app/static/public_pilot/product_telemetry.js").read_text(encoding="utf-8")
    assert 'send("page_viewed")' in source
    assert 'send("session_started")' in source
    assert "[data-track-event]" in source
    assert "sessionStorage" in source
    assert "/api/product-events" in source
    for forbidden in [
        "document.cookie",
        "localStorage",
        "location.search",
        "location.hash",
        "textContent",
        "innerText",
        ".value",
    ]:
        assert forbidden not in source
