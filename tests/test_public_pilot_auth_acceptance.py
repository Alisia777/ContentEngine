from __future__ import annotations

import os
from pathlib import Path

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import ensure_public_pilot_user
from app.public_pilot.local_auth import hash_local_password
from app.public_pilot.gate_matrix import (
    DANGEROUS_ACTIONS,
    METRICS_IMPORT,
    ONE_VIDEO_REAL_RUN,
    OUTPUT_REVIEW,
    PUBLIC_PILOT_ACTIONS,
    PUBLIC_PILOT_ROLES,
    PUBLISHING_APPROVE,
    PublicPilotGateMatrix,
    VIDEO_APPROVE,
)
from scripts.public_pilot_seed import seed


@pytest.fixture(autouse=True)
def reset_public_pilot_db():
    env_keys = [
        "QVF_AUTH_REQUIRED",
        "QVF_PUBLIC_PILOT_MODE",
        "QVF_PUBLIC_PILOT_STRICT_TRAINING_GATES",
        "QVF_LOCAL_AUTH_EMAIL",
        "QVF_LOCAL_AUTH_PASSWORD_HASH",
        "QVF_LOCAL_SESSION_SECRET",
    ]
    previous_env = {key: os.environ.get(key) for key in env_keys}
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    for key, value in previous_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def api_client() -> TestClient:
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    get_settings.cache_clear()
    return TestClient(app)


def test_public_pilot_env_example_documents_auth_vars():
    env_text = Path(".env.example").read_text(encoding="utf-8")
    for name in [
        "QVF_AUTH_REQUIRED=true",
        "QVF_PUBLIC_PILOT_MODE=true",
        "QVF_LOCAL_AUTH_EMAIL=",
        "QVF_LOCAL_AUTH_PASSWORD_HASH=",
        "QVF_LOCAL_SESSION_SECRET=",
        "QVF_LOCAL_SESSION_TTL_SECONDS=28800",
        "SUPABASE_URL=",
        "SUPABASE_PROJECT_REF=",
        "SUPABASE_JWT_SECRET=",
        "SUPABASE_JWKS_URL=",
        "SUPABASE_ISSUER=",
        "SUPABASE_AUDIENCE=authenticated",
        "QVF_SESSION_COOKIE_NAME=qvf_session",
        "QVF_SESSION_COOKIE_SECURE=false",
        "QVF_SESSION_COOKIE_SAMESITE=lax",
    ]:
        assert name in env_text
    assert Path("docs/PUBLIC_PILOT_AUTH_SETUP.md").exists()
    assert Path("docs/ALTEA_PUBLIC_PILOT_BRIEF_EMAIL.md").exists()


def test_local_password_auth_closes_workspaces_media_and_rejects_tampered_cookie(tmp_path):
    password = "Owner-Local-Only-2026!"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_LOCAL_AUTH_EMAIL"] = "owner@local.contentengine"
    os.environ["QVF_LOCAL_AUTH_PASSWORD_HASH"] = hash_local_password(password)
    os.environ["QVF_LOCAL_SESSION_SECRET"] = "local-session-secret-for-tests-only-32-bytes"
    get_settings.cache_clear()

    protected_media = Path("test_media") / "protected.mp4"
    protected_media.parent.mkdir(parents=True, exist_ok=True)
    protected_media.write_bytes(b"protected-video")

    with TestClient(app) as client:
        blocked = client.get("/control-room", follow_redirects=False)
        assert blocked.status_code == 303
        assert blocked.headers["location"] == "/login"
        blocked_media = client.get("/media/protected.mp4", follow_redirects=False)
        assert blocked_media.status_code == 303

        denied = client.post(
            "/login",
            data={"email": "owner@local.contentengine", "password": "wrong-password"},
            follow_redirects=False,
        )
        assert denied.status_code == 303
        assert "invalid_credentials" in denied.headers["location"]

        signed_in = client.post(
            "/login",
            data={"email": "owner@local.contentengine", "password": password},
            follow_redirects=False,
        )
        assert signed_in.status_code == 303
        cookie = signed_in.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert client.get("/control-room").status_code == 200
        assert client.get("/media/protected.mp4").content == b"protected-video"

        client.cookies.set("qvf_session", "tampered-token")
        tampered = client.get("/workbench", follow_redirects=False)
        assert tampered.status_code == 303
        assert tampered.headers["location"] == "/login"


def test_public_pilot_seed_creates_org_profiles_memberships():
    result = seed(with_certifications=True, reset=False)
    assert result["organization"] == "ALTEA Beauty"
    assert result["users"] == 7
    with SessionLocal() as db:
        assert db.scalar(select(models.Organization).where(models.Organization.slug == "altea-beauty")) is not None
        assert len(db.scalars(select(models.UserProfile)).all()) == 7
        assert len(db.scalars(select(models.Membership)).all()) == 7
        assert len(db.scalars(select(models.TrainingCertification)).all()) >= 4


def test_gate_matrix_contains_all_roles_and_dangerous_actions():
    matrix = PublicPilotGateMatrix().matrix()
    assert set(matrix) == set(PUBLIC_PILOT_ACTIONS)
    for action in PUBLIC_PILOT_ACTIONS:
        assert set(matrix[action]) == set(PUBLIC_PILOT_ROLES)
    assert {item["action"] for item in PublicPilotGateMatrix().summary() if item["audit_required"]} == DANGEROUS_ACTIONS


def test_trainee_cannot_run_paid_generation():
    decision = PublicPilotGateMatrix().evaluate("trainee", ONE_VIDEO_REAL_RUN, spend_gate_confirmed=True)
    assert not decision.allowed
    assert decision.reason == "role_trainee_cannot_one_video_real_run"


def test_viewer_cannot_review_or_approve():
    matrix = PublicPilotGateMatrix()
    assert not matrix.evaluate("viewer", OUTPUT_REVIEW).allowed
    assert not matrix.evaluate("viewer", VIDEO_APPROVE).allowed


def test_producer_cannot_approve_output():
    decision = PublicPilotGateMatrix().evaluate("producer", VIDEO_APPROVE, certification_codes={"review_qa"})
    assert not decision.allowed
    assert decision.reason == "role_producer_cannot_video_approve"


def test_reviewer_requires_certification_for_video_approval_when_strict():
    matrix = PublicPilotGateMatrix(strict_training=True)
    denied = matrix.evaluate("reviewer", VIDEO_APPROVE)
    allowed = matrix.evaluate("reviewer", VIDEO_APPROVE, certification_codes={"review_qa"})
    assert not denied.allowed
    assert denied.required_certification == "review_qa"
    assert allowed.allowed


def test_operator_requires_certification_for_publishing_approval_when_strict():
    matrix = PublicPilotGateMatrix(strict_training=True)
    denied = matrix.evaluate("operator", PUBLISHING_APPROVE)
    allowed = matrix.evaluate("operator", PUBLISHING_APPROVE, certification_codes={"publishing_manual_upload"})
    assert not denied.allowed
    assert denied.required_certification == "publishing_manual_upload"
    assert allowed.allowed


def test_owner_paid_generation_still_requires_spend_gate():
    matrix = PublicPilotGateMatrix()
    denied = matrix.evaluate("owner", ONE_VIDEO_REAL_RUN)
    allowed = matrix.evaluate("owner", ONE_VIDEO_REAL_RUN, spend_gate_confirmed=True)
    assert not denied.allowed
    assert denied.reason == "spend_gate_required"
    assert allowed.allowed


def test_denied_action_writes_audit_log():
    with SessionLocal() as db:
        user = ensure_public_pilot_user(db, email="trainee@altea.local", display_name="Trainee", role="trainee")
        service = PublicPilotAccessService(db)
        with pytest.raises(HTTPException):
            service.require_action(
                user_profile_id=user.profile.id,
                organization_id=user.organization.id,
                role=user.role,
                action=ONE_VIDEO_REAL_RUN,
                payload={"api_key": "secret-value"},
                spend_gate_confirmed=True,
            )
        log = db.scalar(select(models.AuditLog).where(models.AuditLog.status == "denied"))
        assert log is not None
        assert log.reason == "role_trainee_cannot_one_video_real_run"
        assert log.metadata_json["payload"]["api_key"] == "[redacted]"


def test_allowed_dangerous_action_writes_sanitized_audit_log():
    with SessionLocal() as db:
        user = ensure_public_pilot_user(db, email="owner@altea.local", display_name="Owner", role="owner")
        service = PublicPilotAccessService(db)
        decision = service.require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=ONE_VIDEO_REAL_RUN,
            payload={"runway_token": "secret-token", "plan_id": 3},
            spend_gate_confirmed=True,
        )
        assert decision.allowed
        log = db.scalar(select(models.AuditLog).where(models.AuditLog.status == "allowed"))
        assert log is not None
        assert log.metadata_json["spend_gate_confirmed"] is True
        assert log.metadata_json["payload"]["runway_token"] == "[redacted]"
        assert log.metadata_json["payload"]["plan_id"] == 3


def test_settings_access_ui_renders_gate_matrix():
    response = api_client().get("/settings/access")
    assert response.status_code == 200
    assert "Settings / Access" in response.text
    assert "one_video_real_run" in response.text
    assert "spend gate" in response.text


def test_altea_motion_splash_login_loading_dashboard_routes_render():
    client = api_client()
    for route in [
        "/altea-motion/splash",
        "/altea-motion/login",
        "/altea-motion/auth-loading",
        "/altea-motion/dashboard-loading",
        "/altea-motion/dashboard",
    ]:
        response = client.get(route)
        assert response.status_code == 200
        assert "ALTEA" in response.text


def test_altea_motion_uses_local_assets_no_external_cdn():
    for path in [
        Path("app/templates/altea_motion/base.html"),
        Path("app/static/altea_motion/altea_motion.css"),
        Path("app/static/altea_motion/altea_motion.js"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "https://" not in text
        assert "http://" not in text
        assert "cdn" not in text.lower()


def test_altea_motion_has_reduced_motion_support():
    text = Path("app/static/altea_motion/altea_motion.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in text
    assert "animation: none" in text


def test_control_room_uses_premium_shell():
    response = api_client().get("/control-room")
    assert response.status_code == 200
    assert "public-pilot-body" in response.text
    assert "altea_motion/altea_motion.css" in response.text
    assert "Public Pilot Control Room" in response.text


def test_metrics_import_requires_operator_certification_when_strict():
    denied = PublicPilotGateMatrix(strict_training=True).evaluate("operator", METRICS_IMPORT)
    allowed = PublicPilotGateMatrix(strict_training=True).evaluate(
        "operator",
        METRICS_IMPORT,
        certification_codes={"publishing_manual_upload"},
    )
    assert not denied.allowed
    assert allowed.allowed
