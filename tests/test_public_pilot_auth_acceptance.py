from __future__ import annotations

import asyncio
import os
import base64
import hashlib
import hmac
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app, settings as app_settings
from app.novice_learning_path import NoviceLearningPathService
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import (
    SupabaseJWTValidator,
    clear_supabase_jwks_cache,
    ensure_public_pilot_user,
)
from app.public_pilot.local_auth import hash_local_password, issue_local_session
from app.public_pilot.supabase_auth import SupabaseAuthClient, SupabaseSessionTokens
from app.public_pilot.training_catalog import ONBOARDING_EXAM_CODE
from app.public_pilot.gate_matrix import (
    DANGEROUS_ACTIONS,
    CUSTOMER_BILLING_MANAGE,
    METRICS_IMPORT,
    MARKETPLACE_LISTING_MANAGE,
    GENERATION_COST_MANAGE,
    ONE_VIDEO_REAL_RUN,
    OUTPUT_REVIEW,
    PAYOUT_MANAGE,
    PUBLIC_PILOT_ACTIONS,
    PUBLIC_PILOT_ROLES,
    PUBLISHING_APPROVE,
    PublicPilotGateMatrix,
    VIDEO_APPROVE,
)
from scripts.public_pilot_seed import seed


def post_login(
    client: TestClient,
    *,
    email: str,
    password: str,
    follow_redirects: bool = False,
):
    page = client.get("/login")
    assert page.status_code == 200
    match = re.search(r'name="login_nonce" value="([A-Za-z0-9_-]+)"', page.text)
    assert match is not None
    return client.post(
        "/login",
        data={"email": email, "password": password, "login_nonce": match.group(1)},
        follow_redirects=follow_redirects,
    )


def test_password_login_requires_one_time_same_site_nonce():
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    get_settings.cache_clear()

    with TestClient(app) as client:
        missing = client.post(
            "/login",
            data={"email": "attacker@example.test", "password": "attacker-password"},
            follow_redirects=False,
        )

    assert missing.status_code == 303
    assert missing.headers["location"] == "/login?error=invalid_login_request"
    assert not any(
        "qvf_session=" in value and "Max-Age=0" not in value
        for value in missing.headers.get_list("set-cookie")
    )


@pytest.fixture(autouse=True)
def reset_public_pilot_db():
    env_keys = [
        "QVF_AUTH_REQUIRED",
        "QVF_PUBLIC_PILOT_MODE",
        "QVF_PUBLIC_PILOT_STRICT_TRAINING_GATES",
        "QVF_PUBLIC_PILOT_INVITE_ONLY",
        "QVF_LOCAL_AUTH_EMAIL",
        "QVF_LOCAL_AUTH_PASSWORD_HASH",
        "QVF_LOCAL_SESSION_SECRET",
        "SUPABASE_URL",
        "QVF_SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
        "QVF_SUPABASE_PUBLISHABLE_KEY",
        "QVF_SUPABASE_JWT_SECRET",
        "QVF_SUPABASE_JWKS_URL",
        "QVF_SUPABASE_ISSUER",
        "QVF_SUPABASE_AUDIENCE",
        "QVF_SESSION_REFRESH_COOKIE_NAME",
        "QVF_SESSION_REFRESH_COOKIE_MAX_AGE_SECONDS",
    ]
    previous_env = {key: os.environ.get(key) for key in env_keys}
    get_settings.cache_clear()
    clear_supabase_jwks_cache()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    for key, value in previous_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    clear_supabase_jwks_cache()


def api_client() -> TestClient:
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    get_settings.cache_clear()
    return TestClient(app)


def external_token(
    *,
    subject: str,
    secret: str,
    role: str = "owner",
    expires_in: int = 600,
) -> str:
    def encoded(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    now = int(time.time())
    header = encoded({"alg": "HS256", "typ": "JWT"})
    payload = encoded(
        {
            "sub": subject,
            "email": f"{subject}@example.test",
            "iss": "https://auth.example.test",
            "aud": "authenticated",
            "iat": now,
            "exp": now + expires_in,
            "app_metadata": {"role": role},
        }
    )
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), f"{header}.{payload}".encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return f"{header}.{payload}.{signature}"


def complete_verified_onboarding_exam(
    db,
    *,
    user_profile_id: int,
    organization_id: int,
) -> None:
    PublicPilotAccessService(db).ensure_training_catalog()
    module = db.scalar(
        select(models.TrainingModule).where(
            models.TrainingModule.code == ONBOARDING_EXAM_CODE,
            models.TrainingModule.is_active.is_(True),
        )
    )
    assert module is not None
    questions = db.scalars(
        select(models.TrainingQuestion)
        .where(models.TrainingQuestion.module_id == module.id)
        .order_by(models.TrainingQuestion.order_index, models.TrainingQuestion.id)
    ).all()
    assert questions
    answers = {
        str(question.id): (
            list(question.correct_answer_json or [])
            if question.question_type == "multi_select"
            else (question.correct_answer_json or [None])[0]
        )
        for question in questions
    }
    result = NoviceLearningPathService(db).submit_quiz(
        user_profile_id=user_profile_id,
        organization_id=organization_id,
        module_code=ONBOARDING_EXAM_CODE,
        answers=answers,
    )
    assert result.passed is True
    assert ONBOARDING_EXAM_CODE in NoviceLearningPathService(db).verified_certification_codes(
        user_profile_id=user_profile_id
    )


def test_public_pilot_env_example_documents_auth_vars():
    env_text = Path(".env.example").read_text(encoding="utf-8")
    for name in [
        "QVF_AUTH_REQUIRED=true",
        "QVF_PUBLIC_PILOT_MODE=true",
        "QVF_PUBLIC_PILOT_INVITE_ONLY=true",
        "QVF_LOCAL_AUTH_EMAIL=",
        "QVF_LOCAL_AUTH_PASSWORD_HASH=",
        "QVF_LOCAL_SESSION_SECRET=",
        "QVF_LOCAL_SESSION_TTL_SECONDS=28800",
        "SUPABASE_URL=",
        "SUPABASE_PROJECT_REF=",
        "SUPABASE_PUBLISHABLE_KEY=",
        "SUPABASE_JWT_SECRET=",
        "SUPABASE_JWKS_URL=",
        "SUPABASE_ISSUER=",
        "SUPABASE_AUDIENCE=authenticated",
        "QVF_SESSION_COOKIE_NAME=qvf_session",
        "QVF_SESSION_REFRESH_COOKIE_NAME=qvf_refresh",
        "QVF_SESSION_REFRESH_COOKIE_MAX_AGE_SECONDS=2592000",
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

    protected_media = app_settings.media_root / "protected.mp4"
    protected_media.parent.mkdir(parents=True, exist_ok=True)
    protected_media.write_bytes(b"protected-video")

    owned_media = app_settings.media_root / "authorized" / "owned-character.png"
    foreign_media = app_settings.media_root / "authorized" / "foreign-character.png"
    owned_media.parent.mkdir(parents=True, exist_ok=True)
    owned_media.write_bytes(b"owned-character")
    foreign_media.write_bytes(b"foreign-character")
    owned_video_media = app_settings.media_root / "authorized" / "owned-video.mp4"
    owned_contact_sheet = app_settings.media_root / "authorized" / "owned-contact.png"
    owned_frame = app_settings.media_root / "authorized" / "owned-frame.png"
    owned_video_media.write_bytes(b"owned-video")
    owned_contact_sheet.write_bytes(b"owned-contact-sheet")
    owned_frame.write_bytes(b"owned-frame")
    outside_media = tmp_path / "outside-media-root.png"
    outside_media.write_bytes(b"must-not-leak")

    with SessionLocal() as db:
        local_user = ensure_public_pilot_user(
            db,
            email="owner@local.contentengine",
            display_name="Local Owner",
            role="reviewer",
            supabase_user_id="local:owner@local.contentengine",
        )
        owned_product = models.Product(
            organization_id=local_user.organization.id,
            sku="MEDIA-OWNED",
            brand="Media",
            title="Owned media product",
        )
        foreign_org = models.Organization(name="Foreign media org", slug="foreign-media-org")
        db.add_all([owned_product, foreign_org])
        db.flush()
        foreign_product = models.Product(
            organization_id=foreign_org.id,
            sku="MEDIA-FOREIGN",
            brand="Media",
            title="Foreign media product",
        )
        db.add(foreign_product)
        db.flush()
        template = models.CreativeTemplate(name="Authorized media template")
        brand_guide = models.BrandGuide(brand="Authorized media")
        db.add_all([template, brand_guide])
        db.flush()
        script_job = models.ScriptJob(
            product_id=owned_product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
        )
        db.add(script_job)
        db.flush()
        script_variant = models.ScriptVariant(script_job_id=script_job.id)
        db.add(script_variant)
        db.flush()
        video_job = models.VideoJob(
            script_variant_id=script_variant.id,
            organization_id=local_user.organization.id,
            created_by_user_profile_id=local_user.profile.id,
            product_id=owned_product.id,
            output_video_path=owned_video_media.as_posix(),
            provider="runway",
            status="generated",
        )
        db.add(video_job)
        db.flush()
        frame_result = models.FrameExtractionResult(
            video_job_id=video_job.id,
            frame_paths_json=[owned_frame.as_posix()],
            contact_sheet_path=owned_contact_sheet.as_posix(),
        )
        db.add(frame_result)
        owned_draft = models.ProductUGCRecipeDraft(
            product_id=owned_product.id,
            sku=owned_product.sku,
            character_image_path=owned_media.as_posix(),
            character_image_filename=owned_media.name,
            product_info="Owned product",
            user_concept="Owned concept",
        )
        foreign_draft = models.ProductUGCRecipeDraft(
            product_id=foreign_product.id,
            sku=foreign_product.sku,
            character_image_path=foreign_media.as_posix(),
            character_image_filename=foreign_media.name,
            product_info="Foreign product",
            user_concept="Foreign concept",
        )
        unsafe_path_draft = models.ProductUGCRecipeDraft(
            product_id=owned_product.id,
            sku=owned_product.sku,
            character_image_path=outside_media.as_posix(),
            character_image_filename=outside_media.name,
            product_info="Unsafe path product",
            user_concept="Unsafe path concept",
        )
        db.add_all([owned_draft, foreign_draft, unsafe_path_draft])
        db.commit()
        local_org_id = local_user.organization.id
        local_profile_id = local_user.profile.id
        local_membership_id = local_user.membership.id
        owned_draft_id = owned_draft.id
        foreign_draft_id = foreign_draft.id
        unsafe_path_draft_id = unsafe_path_draft.id
        video_job_id = video_job.id
        frame_result_id = frame_result.id

    with TestClient(app) as client:
        blocked = client.get("/control-room", follow_redirects=False)
        assert blocked.status_code == 303
        assert blocked.headers["location"] == "/login"
        blocked_media = client.get("/media/protected.mp4", follow_redirects=False)
        assert blocked_media.status_code == 303
        blocked_scoped_media = client.get(
            f"/media/product-ugc-drafts/{owned_draft_id}/character",
            follow_redirects=False,
        )
        assert blocked_scoped_media.status_code == 303
        assert client.get(
            f"/media/video-jobs/{video_job_id}/output",
            follow_redirects=False,
        ).status_code == 303

        denied = post_login(
            client,
            email="owner@local.contentengine",
            password="wrong-password",
        )
        assert denied.status_code == 303
        assert "invalid_credentials" in denied.headers["location"]

        signed_in = post_login(
            client,
            email="owner@local.contentengine",
            password=password,
        )
        assert signed_in.status_code == 303
        cookie = signed_in.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert client.get("/control-room").status_code == 200
        with SessionLocal() as db:
            # The local session claims owner, but the stored membership remains
            # authoritative and cannot be promoted by logging in again.
            assert db.get(models.Membership, local_membership_id).role == "reviewer"
        # A valid login no longer grants access to a guessable shared path.
        assert client.get("/media/protected.mp4").status_code == 404
        owned_response = client.get(
            f"/media/product-ugc-drafts/{owned_draft_id}/character"
        )
        assert owned_response.status_code == 200
        assert owned_response.content == b"owned-character"
        assert owned_response.headers["cache-control"] == "private, no-store"
        assert client.get(
            f"/media/video-jobs/{video_job_id}/output"
        ).content == b"owned-video"
        ranged_video = client.get(
            f"/media/video-jobs/{video_job_id}/output",
            headers={"range": "bytes=0-4"},
        )
        assert ranged_video.status_code == 206
        assert ranged_video.content == b"owned"
        assert ranged_video.headers["content-range"] == "bytes 0-4/11"
        assert client.get(
            f"/media/frame-extractions/{frame_result_id}/contact-sheet"
        ).content == b"owned-contact-sheet"
        assert client.get(
            f"/media/frame-extractions/{frame_result_id}/frames/0"
        ).content == b"owned-frame"
        foreign_response = client.get(
            f"/media/product-ugc-drafts/{foreign_draft_id}/character"
        )
        assert foreign_response.status_code == 404
        assert foreign_response.json() == {"detail": "media_not_found"}
        escaped_path_response = client.get(
            f"/media/product-ugc-drafts/{unsafe_path_draft_id}/character"
        )
        assert escaped_path_response.status_code == 404
        assert b"must-not-leak" not in escaped_path_response.content

        with SessionLocal() as db:
            membership = db.scalar(
                select(models.Membership).where(
                    models.Membership.organization_id == local_org_id,
                    models.Membership.user_profile_id == local_profile_id,
                )
            )
            membership.status = "inactive"
            db.commit()
        inactive_membership = client.get(
            f"/media/product-ugc-drafts/{owned_draft_id}/character"
        )
        assert inactive_membership.status_code == 403
        assert inactive_membership.json() == {"detail": "active_membership_required"}
        inactive_app_route = client.get("/api/factory-dashboard")
        assert inactive_app_route.status_code == 403
        assert inactive_app_route.json() == {"detail": "active_membership_required"}

        client.cookies.set("qvf_session", "tampered-token")
        tampered = client.get("/workbench", follow_redirects=False)
        assert tampered.status_code == 303
        assert tampered.headers["location"] == "/login"


def test_supabase_auth_rest_uses_password_and_refresh_grants():
    os.environ["SUPABASE_URL"] = "https://project.supabase.co"
    os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
    get_settings.cache_clear()
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/auth/v1/logout":
            assert request.url.params["scope"] == "local"
            assert request.headers["authorization"] == "Bearer header.payload.signature"
            return httpx.Response(204)
        grant_type = request.url.params["grant_type"]
        body = json.loads(request.content)
        assert request.headers["apikey"] == "sb_publishable_test"
        if grant_type == "password":
            assert body == {"email": "creator@example.test", "password": "strong-password"}
            refresh = "refresh-token-password"
        else:
            assert body == {"refresh_token": "refresh-token-password"}
            refresh = "refresh-token-rotated"
        return httpx.Response(
            200,
            json={
                "access_token": "header.payload.signature",
                "refresh_token": refresh,
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    auth_client = SupabaseAuthClient(transport=httpx.MockTransport(handler))
    password_session = asyncio.run(
        auth_client.exchange_password(email="creator@example.test", password="strong-password")
    )
    refreshed_session = asyncio.run(auth_client.refresh_session(password_session.refresh_token))
    asyncio.run(auth_client.revoke(password_session.access_token))

    assert [request.url.path for request in requests] == [
        "/auth/v1/token",
        "/auth/v1/token",
        "/auth/v1/logout",
    ]
    assert [request.url.params["grant_type"] for request in requests[:2]] == ["password", "refresh_token"]
    assert refreshed_session.refresh_token == "refresh-token-rotated"


def test_supabase_password_login_sets_http_only_session_and_keeps_membership_authoritative(monkeypatch):
    secret = "supabase-password-login-shared-secret"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_PUBLIC_PILOT_INVITE_ONLY"] = "true"
    os.environ["SUPABASE_URL"] = "https://project.supabase.co"
    os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()

    with SessionLocal() as db:
        invited = ensure_public_pilot_user(
            db,
            email="creator@example.test",
            display_name="Invited Creator",
            role="operator",
            supabase_user_id="creator-one",
        )
        membership_id = invited.membership.id

    async def fake_exchange(_self, *, email: str, password: str):
        assert password == "Creator-Password-2026!"
        subject = "creator-one" if email == "creator@example.test" else "not-invited"
        return SupabaseSessionTokens(
            access_token=external_token(subject=subject, secret=secret, role="owner"),
            refresh_token=f"refresh-token-{subject}",
            expires_in=3600,
        )

    monkeypatch.setattr(SupabaseAuthClient, "exchange_password", fake_exchange)
    with TestClient(app) as client:
        signed_in = post_login(
            client,
            email="creator@example.test",
            password="Creator-Password-2026!",
        )
        assert signed_in.status_code == 303
        assert signed_in.headers["location"] == "/control-room"
        set_cookies = signed_in.headers.get_list("set-cookie")
        assert any("qvf_session=" in value and "HttpOnly" in value for value in set_cookies)
        assert any("qvf_refresh=" in value and "HttpOnly" in value for value in set_cookies)
        assert client.get("/control-room").status_code == 200

    with SessionLocal() as db:
        assert db.get(models.Membership, membership_id).role == "operator"

    with TestClient(app) as client:
        denied = post_login(
            client,
            email="unknown@example.test",
            password="Creator-Password-2026!",
        )
        assert denied.status_code == 303
        assert denied.headers["location"] == "/login?error=invite_required"
        assert not any("qvf_session=" in value for value in denied.headers.get_list("set-cookie"))


def test_expired_supabase_access_cookie_refreshes_and_rotates_browser_session(monkeypatch):
    secret = "supabase-refresh-shared-secret"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["SUPABASE_URL"] = "https://project.supabase.co"
    os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()
    with SessionLocal() as db:
        ensure_public_pilot_user(
            db,
            email="refresh@example.test",
            display_name="Refresh User",
            role="viewer",
            supabase_user_id="refresh-user",
        )

    expired_access = external_token(subject="refresh-user", secret=secret, expires_in=-120)
    new_access = external_token(subject="refresh-user", secret=secret)
    refresh_calls = []

    async def fake_refresh(_self, refresh_token: str):
        refresh_calls.append(refresh_token)
        return SupabaseSessionTokens(
            access_token=new_access,
            refresh_token="rotated-refresh-token",
            expires_in=3600,
        )

    monkeypatch.setattr(SupabaseAuthClient, "refresh_session", fake_refresh)
    with TestClient(app) as client:
        client.cookies.set("qvf_session", expired_access)
        client.cookies.set("qvf_refresh", "original-refresh-token")
        response = client.get("/onboarding")
        assert response.status_code == 200, response.text
        set_cookies = response.headers.get_list("set-cookie")
        assert any(f"qvf_session={new_access}" in value for value in set_cookies)
        assert any("qvf_refresh=rotated-refresh-token" in value for value in set_cookies)
    assert refresh_calls == ["original-refresh-token"]


def test_logout_revokes_supabase_session_best_effort_and_clears_both_cookies(monkeypatch):
    secret = "supabase-logout-shared-secret"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["SUPABASE_URL"] = "https://project.supabase.co"
    os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()
    access_token = external_token(subject="logout-user", secret=secret)
    revoked = []

    async def fake_revoke(_self, token: str):
        revoked.append(token)

    monkeypatch.setattr(SupabaseAuthClient, "revoke", fake_revoke)
    csrf_token = hmac.new(
        b"qvf-public-pilot-form-csrf-v1",
        access_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    with TestClient(app) as client:
        client.cookies.set("qvf_session", access_token)
        client.cookies.set("qvf_refresh", "logout-refresh-token")
        response = client.post(
            "/logout",
            data={"csrf_token": csrf_token},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        deleted = response.headers.get_list("set-cookie")
        assert any("qvf_session=" in value and "Max-Age=0" in value for value in deleted)
        assert any("qvf_refresh=" in value and "Max-Age=0" in value for value in deleted)
    assert revoked == [access_token]


def test_authenticated_billing_write_requires_session_bound_csrf_token():
    password = "Owner-Csrf-Only-2026!"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_LOCAL_AUTH_EMAIL"] = "owner@local.contentengine"
    os.environ["QVF_LOCAL_AUTH_PASSWORD_HASH"] = hash_local_password(password)
    os.environ["QVF_LOCAL_SESSION_SECRET"] = "local-csrf-session-secret-for-tests-32"
    get_settings.cache_clear()

    with TestClient(app) as client:
        signed_in = post_login(
            client,
            email="owner@local.contentengine",
            password=password,
        )
        assert signed_in.status_code == 303

        rendered_post_forms = 0
        for route in ["/control-room", "/workbench", "/mvp-launch", "/settings/access"]:
            rendered = client.get(route)
            assert rendered.status_code == 200
            for form in re.findall(r"<form\b.*?</form>", rendered.text, flags=re.IGNORECASE | re.DOTALL):
                opening_tag = form.split(">", 1)[0]
                if re.search(r'method=["\']post["\']', opening_tag, flags=re.IGNORECASE):
                    rendered_post_forms += 1
                    assert 'name="csrf_token"' in form
        assert rendered_post_forms > 0

        previously_unprotected = client.post(
            "/workbench/wb/listings/create",
            data={"product_id": 999, "seller_account_ref": "main-cabinet"},
            follow_redirects=False,
        )
        assert previously_unprotected.status_code == 403
        assert previously_unprotected.json() == {"detail": "invalid_csrf_token"}

        missing = client.post(
            "/workbench/customer-billing/account",
            data={"currency": "RUB", "confirm_ledger_only": "true"},
            follow_redirects=False,
        )
        assert missing.status_code == 403
        assert missing.json() == {"detail": "invalid_csrf_token"}

        page = client.get("/workbench?tab=payments")
        match = re.search(
            r'name="csrf_token" value="([a-f0-9]{64})"',
            page.text,
        )
        assert match is not None
        created = client.post(
            "/workbench/customer-billing/account",
            data={
                "currency": "RUB",
                "confirm_ledger_only": "true",
                "csrf_token": match.group(1),
            },
            follow_redirects=False,
        )
        assert created.status_code == 303
        assert "billing_notice=account_created" in created.headers["location"]

        legacy_wizard = client.post(
            "/mvp-launch/start",
            data={"csrf_token": match.group(1)},
            follow_redirects=False,
        )
        assert legacy_wizard.status_code == 404
        assert legacy_wizard.json() == {"detail": "not_found"}


def test_raw_media_path_remains_available_only_in_non_public_local_mode():
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "false"
    get_settings.cache_clear()
    legacy_media = app_settings.media_root / "legacy-local-only.mp4"
    legacy_media.parent.mkdir(parents=True, exist_ok=True)
    legacy_media.write_bytes(b"legacy-local-video")

    with TestClient(app) as client:
        response = client.get("/media/legacy-local-only.mp4")
    assert response.status_code == 200
    assert response.content == b"legacy-local-video"

    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    get_settings.cache_clear()
    with TestClient(app) as client:
        blocked = client.get("/media/legacy-local-only.mp4")
    assert blocked.status_code == 404
    assert blocked.json() == {"detail": "media_not_found"}


def test_invite_only_supabase_token_cannot_auto_join_or_escalate_default_org():
    secret = "supabase-shared-secret-for-test-only"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_INVITE_ONLY"] = "true"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()

    uninvited = external_token(subject="uninvited-user", secret=secret, role="owner")
    with TestClient(app) as client:
        dashboard_denied = client.get(
            "/api/factory-dashboard",
            headers={"authorization": f"Bearer {uninvited}"},
        )
        denied = client.get("/api/social-metrics", headers={"authorization": f"Bearer {uninvited}"})
    assert dashboard_denied.status_code == 403
    assert dashboard_denied.json() == {"detail": "public_pilot_invite_required"}
    assert denied.status_code == 403
    assert denied.json() == {"detail": "public_pilot_invite_required"}

    with SessionLocal() as db:
        invited = ensure_public_pilot_user(
            db,
            email="invited@example.test",
            display_name="Invited Viewer",
            role="viewer",
            supabase_user_id="invited-user",
        )
        membership_id = invited.membership.id
        profile_id = invited.profile.id
        organization_id = invited.organization.id

    escalated_claim = external_token(subject="invited-user", secret=secret, role="owner")
    with TestClient(app) as client:
        onboarding_blocked = client.get(
            "/api/social-metrics",
            headers={"authorization": f"Bearer {escalated_claim}"},
        )
    assert onboarding_blocked.status_code == 403
    assert onboarding_blocked.json() == {
        "detail": "onboarding_required",
        "onboarding_url": "/onboarding",
        "required_certification": ONBOARDING_EXAM_CODE,
    }
    with SessionLocal() as db:
        complete_verified_onboarding_exam(
            db,
            user_profile_id=profile_id,
            organization_id=organization_id,
        )
    with TestClient(app) as client:
        accepted = client.get(
            "/api/social-metrics",
            headers={"authorization": f"Bearer {escalated_claim}"},
        )
    assert accepted.status_code == 200
    with SessionLocal() as db:
        assert db.get(models.Membership, membership_id).role == "viewer"


def test_invited_user_can_only_reach_explicit_scoped_allowlist():
    secret = "scoped-allowlist-shared-secret"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_PUBLIC_PILOT_INVITE_ONLY"] = "true"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()

    with SessionLocal() as db:
        scoped_user = ensure_public_pilot_user(
            db,
            email="scoped-owner@example.test",
            display_name="Scoped Owner",
            role="owner",
            supabase_user_id="scoped-owner",
        )
        owned_product = models.Product(
            organization_id=scoped_user.organization.id,
            sku="SCOPED-POLL-OWNED",
            brand="Scoped",
            title="Owned polling product",
        )
        foreign_org = models.Organization(name="Foreign scoped org", slug="foreign-scoped-org")
        db.add_all([owned_product, foreign_org])
        db.flush()
        foreign_product = models.Product(
            organization_id=foreign_org.id,
            sku="SCOPED-POLL-FOREIGN",
            brand="Foreign",
            title="Foreign polling product",
        )
        db.add(foreign_product)
        db.flush()
        owned_draft = models.ProductUGCRecipeDraft(
            product_id=owned_product.id,
            sku=owned_product.sku,
            character_image_path="owned.png",
            character_image_filename="owned.png",
            product_info="Owned product",
            user_concept="Owned concept",
        )
        foreign_draft = models.ProductUGCRecipeDraft(
            product_id=foreign_product.id,
            sku=foreign_product.sku,
            character_image_path="foreign.png",
            character_image_filename="foreign.png",
            product_info="Foreign product",
            user_concept="Foreign concept",
        )
        db.add_all([owned_draft, foreign_draft])
        db.commit()
        scoped_profile_id = scoped_user.profile.id
        scoped_organization_id = scoped_user.organization.id
        owned_draft_id = owned_draft.id
        foreign_draft_id = foreign_draft.id

    token = external_token(subject="scoped-owner", secret=secret, role="owner")
    headers = {"authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        onboarding_blocked = client.get("/api/factory-dashboard", headers=headers)
    assert onboarding_blocked.status_code == 403
    assert onboarding_blocked.json() == {
        "detail": "onboarding_required",
        "onboarding_url": "/onboarding",
        "required_certification": ONBOARDING_EXAM_CODE,
    }
    with SessionLocal() as db:
        complete_verified_onboarding_exam(
            db,
            user_profile_id=scoped_profile_id,
            organization_id=scoped_organization_id,
        )
    with TestClient(app) as client:
        scoped_dashboard = client.get("/api/factory-dashboard", headers=headers)
        legacy_products = client.get("/api/products", headers=headers)
        legacy_mutation = client.post("/api/publishing/tasks/999/cancel", headers=headers)
        legacy_polling = client.get(
            f"/api/runway-recipes/product-ugc/{owned_draft_id}",
            headers=headers,
        )
        scoped_polling = client.get(
            f"/api/public-pilot/product-ugc/{owned_draft_id}",
            headers=headers,
        )
        foreign_polling = client.get(
            f"/api/public-pilot/product-ugc/{foreign_draft_id}",
            headers=headers,
        )

    assert scoped_dashboard.status_code == 200
    for blocked in [legacy_products, legacy_mutation, legacy_polling]:
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "legacy_global_workspace_disabled"
    assert scoped_polling.status_code == 200
    assert scoped_polling.json()["id"] == owned_draft_id
    assert foreign_polling.status_code == 404
    assert foreign_polling.json() == {"detail": "product_ugc_draft_not_found"}


def test_inactive_profile_and_membership_are_denied_before_scoped_route():
    secret = "inactive-principal-shared-secret"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = secret
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()

    with SessionLocal() as db:
        inactive_profile = ensure_public_pilot_user(
            db,
            email="inactive-profile@example.test",
            display_name="Inactive Profile",
            role="viewer",
            supabase_user_id="inactive-profile",
        )
        inactive_profile.profile.is_active = False
        inactive_membership = ensure_public_pilot_user(
            db,
            email="inactive-membership@example.test",
            display_name="Inactive Membership",
            role="viewer",
            supabase_user_id="inactive-membership",
        )
        inactive_membership.membership.status = "inactive"
        db.commit()

    tokens = [
        external_token(subject="inactive-profile", secret=secret, role="owner"),
        external_token(subject="inactive-membership", secret=secret, role="owner"),
    ]
    with TestClient(app) as client:
        responses = [
            client.get(
                "/api/factory-dashboard",
                headers={"authorization": f"Bearer {token}"},
            )
            for token in tokens
        ]
    for response in responses:
        assert response.status_code == 403
        assert response.json() == {"detail": "active_membership_required"}


def test_tracking_redirect_is_public_and_records_click():
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    get_settings.cache_clear()

    with SessionLocal() as db:
        link = models.TrackingLink(
            slug="public-pilot-click",
            target_url="https://shop.example.test/product",
            status="active",
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        link_id = link.id

    with TestClient(app) as client:
        redirected = client.get(
            "/r/public-pilot-click",
            headers={"referer": "https://social.example.test/post/42"},
            follow_redirects=False,
        )

    assert redirected.status_code == 307
    assert redirected.headers["location"] == "https://shop.example.test/product"
    with SessionLocal() as db:
        click = db.scalar(
            select(models.TrackingClick).where(models.TrackingClick.tracking_link_id == link_id)
        )
        assert click is not None
        assert click.referrer == "https://social.example.test/post/42"
        assert click.metadata_json == {"path": "/r/public-pilot-click"}


def test_jwks_verifies_es256_and_rs256_with_cached_client_and_rejects_bad_signature(monkeypatch):
    os.environ.pop("QVF_SUPABASE_JWT_SECRET", None)
    os.environ["QVF_SUPABASE_JWKS_URL"] = "https://auth.example.test/.well-known/jwks.json"
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()
    clear_supabase_jwks_cache()

    rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    es_private = ec.generate_private_key(ec.SECP256R1())
    public_keys = {"RS256": rsa_private.public_key(), "ES256": es_private.public_key()}
    constructed = []

    class FakeJWKClient:
        def __init__(self, *args, **kwargs):
            constructed.append((args, kwargs))

        def get_signing_key_from_jwt(self, token):
            algorithm = jwt.get_unverified_header(token)["alg"]
            return SimpleNamespace(key=public_keys[algorithm])

    monkeypatch.setattr(jwt, "PyJWKClient", FakeJWKClient)
    now = int(time.time())
    payload = {
        "sub": "jwks-user",
        "email": "jwks-user@example.test",
        "iss": "https://auth.example.test",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 600,
    }
    for algorithm, private_key in (("RS256", rsa_private), ("ES256", es_private)):
        token = jwt.encode(payload, private_key, algorithm=algorithm, headers={"kid": f"{algorithm}-key"})
        assert SupabaseJWTValidator().validate(token)["sub"] == "jwks-user"

    # One cached client serves both validations for the configured JWKS URL.
    assert len(constructed) == 1
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad_token = jwt.encode(payload, attacker_key, algorithm="RS256", headers={"kid": "RS256-key"})
    with pytest.raises(HTTPException) as exc_info:
        SupabaseJWTValidator().validate(bad_token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid_token"


def test_jwt_validator_keeps_local_and_legacy_supabase_hs256_compatibility():
    os.environ["QVF_LOCAL_SESSION_SECRET"] = "local-backward-compatible-session-secret"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = "legacy-supabase-hs256-secret"
    os.environ["QVF_SUPABASE_ISSUER"] = "https://auth.example.test"
    get_settings.cache_clear()

    local_token = issue_local_session(email="owner@local.contentengine", role="owner")
    external = external_token(subject="legacy-hs-user", secret="legacy-supabase-hs256-secret")

    assert SupabaseJWTValidator().validate(local_token)["auth_source"] == "local"
    assert SupabaseJWTValidator().validate(external)["sub"] == "legacy-hs-user"


def test_global_legacy_participant_workspace_is_closed_in_public_mode():
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    get_settings.cache_clear()
    with TestClient(app) as client:
        page = client.get("/participant-portal")
        api_response = client.get("/api/participant-portal/participants")
        academy = client.get("/training-academy")
    assert page.status_code == 409
    assert api_response.status_code == 409
    assert academy.status_code == 409


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


def test_only_financial_roles_can_manage_payouts():
    matrix = PublicPilotGateMatrix()
    assert matrix.evaluate("owner", PAYOUT_MANAGE).allowed
    assert matrix.evaluate("admin", PAYOUT_MANAGE).allowed
    assert not matrix.evaluate("operator", PAYOUT_MANAGE).allowed
    assert not matrix.evaluate("viewer", PAYOUT_MANAGE).allowed


def test_only_owner_and_admin_can_change_marketplace_mapping():
    matrix = PublicPilotGateMatrix()
    assert matrix.evaluate("owner", MARKETPLACE_LISTING_MANAGE).allowed
    assert matrix.evaluate("admin", MARKETPLACE_LISTING_MANAGE).allowed
    assert not matrix.evaluate("operator", MARKETPLACE_LISTING_MANAGE).allowed
    assert not matrix.evaluate("viewer", MARKETPLACE_LISTING_MANAGE).allowed


def test_only_owner_and_admin_can_reconcile_generation_costs():
    matrix = PublicPilotGateMatrix()
    assert matrix.evaluate("owner", GENERATION_COST_MANAGE).allowed
    assert matrix.evaluate("admin", GENERATION_COST_MANAGE).allowed
    assert not matrix.evaluate("operator", GENERATION_COST_MANAGE).allowed
    assert not matrix.evaluate("viewer", GENERATION_COST_MANAGE).allowed


def test_only_owner_and_admin_can_manage_customer_billing():
    matrix = PublicPilotGateMatrix()
    assert matrix.evaluate("owner", CUSTOMER_BILLING_MANAGE).allowed
    assert matrix.evaluate("admin", CUSTOMER_BILLING_MANAGE).allowed
    assert not matrix.evaluate("operator", CUSTOMER_BILLING_MANAGE).allowed
    assert not matrix.evaluate("viewer", CUSTOMER_BILLING_MANAGE).allowed


def test_legacy_real_generation_api_is_disabled_before_role_gate():
    response = api_client().post(
        "/api/generator/run-real",
        headers={"x-public-pilot-role": "viewer"},
        json={"product_id": 999, "video_provider": "runway", "confirm_real_spend": True},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "legacy_global_workspace_disabled"


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


def test_altea_motion_demo_routes_are_not_exposed_in_public_mode():
    client = api_client()
    for route in [
        "/altea-motion/splash",
        "/altea-motion/login",
        "/altea-motion/auth-loading",
        "/altea-motion/dashboard-loading",
        "/altea-motion/dashboard",
    ]:
        response = client.get(route)
        assert response.status_code == 409
        assert response.json()["detail"] == "legacy_global_workspace_disabled"


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
