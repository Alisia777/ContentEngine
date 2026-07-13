from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.database import Base, get_db
from app.public_pilot.auth import active_public_pilot_user_from_payload
from app.public_pilot.supabase_auth import (
    SupabaseAuthClient,
    SupabaseAuthError,
    SupabaseSessionTokens,
)
from app.routers import invite_acceptance


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
JWT_SECRET = "invite-flow-test-secret-at-least-32-bytes"
JWT_ISSUER = "https://auth.invite.test"


@pytest.fixture(autouse=True)
def isolated_settings_and_database(monkeypatch):
    monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
    monkeypatch.setenv("QVF_PUBLIC_PILOT_MODE", "true")
    monkeypatch.setenv("QVF_PUBLIC_PILOT_INVITE_ONLY", "true")
    monkeypatch.setenv("QVF_SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("QVF_SUPABASE_PUBLISHABLE_KEY", "publishable-test-key")
    monkeypatch.setenv("QVF_SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("QVF_SUPABASE_ISSUER", JWT_ISSUER)
    monkeypatch.setenv("QVF_SUPABASE_AUDIENCE", "authenticated")
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.mount("/static", StaticFiles(directory="app/static"), name="static")
    application.include_router(invite_acceptance.router)

    def override_db():
        with TestSession() as db:
            yield db

    application.dependency_overrides[get_db] = override_db
    return application


def _active_invited_user(
    *,
    subject: str = "invited-user",
    organization_name: str = "ALTEA Beauty",
    organization_slug: str = "altea-beauty",
) -> tuple[int, int]:
    with TestSession() as db:
        organization = models.Organization(
            name=organization_name,
            slug=organization_slug,
            status="active",
            settings_json={},
        )
        profile = models.UserProfile(
            supabase_user_id=subject,
            email=f"{subject}@example.test",
            display_name="New creator",
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add_all([organization, profile])
        db.flush()
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="producer",
            status="active",
            permissions_json=[],
        )
        db.add(membership)
        db.commit()
        return profile.id, membership.id


def _access_token(
    *,
    subject: str = "invited-user",
    organization_slug: str | None = None,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "email": f"{subject}@example.test",
            "iss": JWT_ISSUER,
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "app_metadata": {
                "role": "owner",
                **({"organization_slug": organization_slug} if organization_slug else {}),
            },
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def _tokens(*, subject: str = "invited-user") -> SupabaseSessionTokens:
    return SupabaseSessionTokens(
        access_token=_access_token(subject=subject),
        refresh_token="refresh-token-secret-value",
        expires_in=1_800,
    )


def _csrf_from_page(response) -> str:
    match = re.search(r'name="csrf_token" value="([a-f0-9]{64})"', response.text)
    assert match is not None
    return match.group(1)


def _bridge_nonce_from_page(response) -> str:
    match = re.search(r'name="bridge_nonce" value="([A-Za-z0-9_-]{20,200})"', response.text)
    assert match is not None
    return match.group(1)


def _response_surface(response) -> str:
    headers = "\n".join(f"{key}: {value}" for key, value in response.headers.multi_items())
    return f"{headers}\n{response.text}"


def test_supabase_rest_verify_invite_and_update_password_contracts():
    token_hash = "server-side-invite-token-hash"
    password = "Correct-Horse-Battery-2026!"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/verify"):
            return httpx.Response(
                200,
                json={
                    "access_token": "header.payload.signature",
                    "refresh_token": "refresh-token-value",
                    "expires_in": 3600,
                    "token_type": "bearer",
                },
            )
        return httpx.Response(200, json={"id": "user-id"})

    client = SupabaseAuthClient(settings=get_settings(), transport=httpx.MockTransport(handler))
    session = asyncio.run(client.verify_otp(token_hash=token_hash, verification_type="invite"))
    asyncio.run(client.update_password(access_token=session.access_token, password=password))

    assert [request.method for request in requests] == ["POST", "PUT"]
    assert [request.url.path for request in requests] == ["/auth/v1/verify", "/auth/v1/user"]
    assert json.loads(requests[0].content) == {"token_hash": token_hash, "type": "invite"}
    assert json.loads(requests[1].content) == {"password": password}
    assert requests[1].headers["authorization"] == f"Bearer {session.access_token}"
    assert requests[0].headers["apikey"] == "publishable-test-key"


def test_supabase_rest_errors_never_include_provider_secret_body():
    token_hash = "expired-secret-invite-hash"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": f"expired {token_hash}"})

    client = SupabaseAuthClient(
        settings=get_settings(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SupabaseAuthError) as raised:
        asyncio.run(client.verify_invite(token_hash=token_hash))
    assert raised.value.code == "invalid_or_expired_invite"
    assert token_hash not in str(raised.value)


def test_invite_success_sets_httponly_session_then_updates_password(app: FastAPI, monkeypatch):
    _active_invited_user()
    invite_hash = "one-time-invite-hash-secret"
    session = _tokens()
    verify_calls: list[tuple[str, str]] = []
    update_calls: list[tuple[str, str]] = []

    async def verify(self, *, token_hash: str, verification_type: str):
        verify_calls.append((token_hash, verification_type))
        return session

    async def update(self, *, access_token: str, password: str):
        update_calls.append((access_token, password))

    monkeypatch.setattr(SupabaseAuthClient, "verify_otp", verify)
    monkeypatch.setattr(SupabaseAuthClient, "update_password", update)
    password = "Correct-Horse-Battery-2026!"
    with TestClient(app) as client:
        bridge = client.get("/auth/accept")
        assert bridge.status_code == 200
        assert invite_hash not in _response_surface(bridge)
        assert "default-src 'none'" in bridge.headers["content-security-policy"]
        assert "form-action 'self'" in bridge.headers["content-security-policy"]
        bridge_cookies = bridge.headers.get_list("set-cookie")
        assert any(
            "qvf_invite_bridge=" in value and "httponly" in value.casefold()
            for value in bridge_cookies
        )
        confirmed = client.post(
            "/auth/confirm",
            data={
                "token_hash": invite_hash,
                "type": "invite",
                "bridge_nonce": _bridge_nonce_from_page(bridge),
            },
            follow_redirects=False,
        )
        assert confirmed.status_code == 303
        assert confirmed.headers["location"] == "/onboarding/set-password"
        set_cookies = confirmed.headers.get_list("set-cookie")
        session_cookies = [value for value in set_cookies if "qvf_session=" in value or "qvf_refresh=" in value]
        assert len(session_cookies) == 2
        assert all("httponly" in value.casefold() for value in session_cookies)
        assert all("path=/" in value.casefold() for value in session_cookies)
        assert confirmed.headers["cache-control"].startswith("no-store")
        assert confirmed.headers["referrer-policy"] == "no-referrer"
        assert invite_hash not in _response_surface(confirmed)

        page = client.get("/onboarding/set-password")
        assert page.status_code == 200
        assert invite_hash not in page.text
        csrf_token = _csrf_from_page(page)
        completed = client.post(
            "/onboarding/set-password",
            data={
                "csrf_token": csrf_token,
                "password": password,
                "password_confirmation": password,
            },
            follow_redirects=False,
        )

    assert completed.status_code == 303
    assert completed.headers["location"] == "/onboarding"
    assert password not in _response_surface(completed)
    assert verify_calls == [(invite_hash, "invite")]
    assert update_calls == [(session.access_token, password)]


@pytest.mark.parametrize("provider_status", [400, 401, 422])
def test_invalid_or_expired_invite_is_generic_and_secret_free(
    app: FastAPI,
    monkeypatch,
    provider_status: int,
):
    invite_hash = f"expired-private-hash-{provider_status}"

    async def reject(self, *, token_hash: str, verification_type: str):
        assert token_hash == invite_hash
        assert verification_type == "invite"
        raise SupabaseAuthError("invalid_or_expired_invite", status_code=401)

    monkeypatch.setattr(SupabaseAuthClient, "verify_otp", reject)
    with TestClient(app) as client:
        bridge = client.get("/auth/accept")
        response = client.post(
            "/auth/confirm",
            data={
                "token_hash": invite_hash,
                "type": "invite",
                "bridge_nonce": _bridge_nonce_from_page(bridge),
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=invalid_invite"
    assert invite_hash not in _response_surface(response)


def test_only_invite_type_is_accepted_without_contacting_provider(app: FastAPI, monkeypatch):
    invite_hash = "recovery-hash-must-not-be-used"

    async def must_not_run(*args, **kwargs):
        raise AssertionError("provider must not be contacted for non-invite types")

    monkeypatch.setattr(SupabaseAuthClient, "verify_otp", must_not_run)
    with TestClient(app) as client:
        bridge = client.get("/auth/accept")
        response = client.post(
            "/auth/confirm",
            data={
                "token_hash": invite_hash,
                "type": "recovery",
                "bridge_nonce": _bridge_nonce_from_page(bridge),
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=invalid_invite"
    assert invite_hash not in _response_surface(response)


def test_get_confirm_never_redeems_query_token(app: FastAPI, monkeypatch):
    invite_hash = "query-token-must-never-reach-provider"

    async def must_not_run(*args, **kwargs):
        raise AssertionError("GET confirmation must not contact Supabase")

    monkeypatch.setattr(SupabaseAuthClient, "verify_otp", must_not_run)
    with TestClient(app) as client:
        response = client.get(
            f"/auth/confirm?token_hash={invite_hash}&type=invite",
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=invalid_invite"
    assert invite_hash not in _response_surface(response)


def test_confirm_post_requires_same_site_bridge_nonce(app: FastAPI, monkeypatch):
    invite_hash = "cross-site-login-token"

    async def must_not_run(*args, **kwargs):
        raise AssertionError("invalid bridge must be rejected before Supabase")

    monkeypatch.setattr(SupabaseAuthClient, "verify_otp", must_not_run)
    with TestClient(app) as client:
        response = client.post(
            "/auth/confirm",
            data={
                "token_hash": invite_hash,
                "type": "invite",
                "bridge_nonce": "forged-bridge-nonce-value",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=invalid_invite"
    assert invite_hash not in _response_surface(response)


def test_password_write_rejects_csrf_weak_and_mismatched_values(app: FastAPI, monkeypatch):
    _active_invited_user()
    access_token = _access_token()
    update_calls: list[str] = []

    async def update(self, *, access_token: str, password: str):
        update_calls.append(password)

    monkeypatch.setattr(SupabaseAuthClient, "update_password", update)
    settings = get_settings()
    weak = "too-short"
    strong = "Correct-Horse-Battery-2026!"
    mismatch = "Different-Horse-Battery-2026!"
    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, access_token)
        page = client.get("/onboarding/set-password")
        assert page.status_code == 200
        csrf_token = _csrf_from_page(page)

        invalid_csrf = client.post(
            "/onboarding/set-password",
            data={
                "csrf_token": "invalid-csrf",
                "password": strong,
                "password_confirmation": strong,
            },
            follow_redirects=False,
        )
        weak_response = client.post(
            "/onboarding/set-password",
            data={
                "csrf_token": csrf_token,
                "password": weak,
                "password_confirmation": weak,
            },
            follow_redirects=False,
        )
        mismatch_response = client.post(
            "/onboarding/set-password",
            data={
                "csrf_token": csrf_token,
                "password": strong,
                "password_confirmation": mismatch,
            },
            follow_redirects=False,
        )

    assert invalid_csrf.status_code == 403
    assert invalid_csrf.json() == {"detail": "invalid_csrf_token"}
    assert weak_response.status_code == 303
    assert weak_response.headers["location"] == "/onboarding/set-password?error=weak_password"
    assert mismatch_response.status_code == 303
    assert mismatch_response.headers["location"] == "/onboarding/set-password?error=password_mismatch"
    for response in (invalid_csrf, weak_response, mismatch_response):
        surface = _response_surface(response)
        assert weak not in surface
        assert strong not in surface
        assert mismatch not in surface
    assert update_calls == []


def test_set_password_requires_active_membership(app: FastAPI):
    _, membership_id = _active_invited_user()
    with TestSession() as db:
        membership = db.get(models.Membership, membership_id)
        membership.status = "inactive"
        db.commit()
    with TestClient(app) as client:
        client.cookies.set(get_settings().session_cookie_name, _access_token())
        response = client.get("/onboarding/set-password")
    assert response.status_code == 403
    assert response.json() == {"detail": "active_membership_required"}


def test_external_user_without_org_claim_uses_sole_non_default_membership():
    profile_id, _ = _active_invited_user(
        subject="sole-non-default",
        organization_name="Creator Studio",
        organization_slug="creator-studio",
    )
    payload = jwt.decode(
        _access_token(subject="sole-non-default"),
        options={"verify_signature": False},
    )
    with TestSession() as db:
        user = active_public_pilot_user_from_payload(db, payload)
    assert user.profile.id == profile_id
    assert user.organization.slug == "creator-studio"


def test_explicit_foreign_org_claim_never_falls_back_to_sole_membership():
    _active_invited_user(
        subject="forged-claim-user",
        organization_name="Owned Studio",
        organization_slug="owned-studio",
    )
    with TestSession() as db:
        db.add(
            models.Organization(
                name="Foreign Studio",
                slug="foreign-studio",
                status="active",
                settings_json={},
            )
        )
        db.commit()
    payload = jwt.decode(
        _access_token(
            subject="forged-claim-user",
            organization_slug="foreign-studio",
        ),
        options={"verify_signature": False},
    )
    with TestSession() as db, pytest.raises(HTTPException) as raised:
        active_public_pilot_user_from_payload(db, payload)
    assert raised.value.status_code == 403
    assert raised.value.detail == "public_pilot_invite_required"


def test_no_claim_prefers_only_active_membership_over_suspended_default():
    profile_id, _ = _active_invited_user(
        subject="active-over-suspended",
        organization_name="Active Studio",
        organization_slug="active-studio",
    )
    with TestSession() as db:
        default_org = models.Organization(
            name="ALTEA Beauty",
            slug="altea-beauty",
            status="active",
            settings_json={},
        )
        db.add(default_org)
        db.flush()
        db.add(
            models.Membership(
                organization_id=default_org.id,
                user_profile_id=profile_id,
                role="viewer",
                status="suspended",
                permissions_json=[],
            )
        )
        db.commit()
    payload = jwt.decode(
        _access_token(subject="active-over-suspended"),
        options={"verify_signature": False},
    )
    with TestSession() as db:
        user = active_public_pilot_user_from_payload(db, payload)
    assert user.organization.slug == "active-studio"
    assert user.membership.status == "active"


def test_no_claim_with_multiple_active_memberships_uses_active_default():
    profile_id, _ = _active_invited_user(subject="multi-with-default")
    with TestSession() as db:
        second_org = models.Organization(
            name="Second Studio",
            slug="second-studio",
            status="active",
            settings_json={},
        )
        db.add(second_org)
        db.flush()
        db.add(
            models.Membership(
                organization_id=second_org.id,
                user_profile_id=profile_id,
                role="producer",
                status="active",
                permissions_json=[],
            )
        )
        db.commit()
    payload = jwt.decode(
        _access_token(subject="multi-with-default"),
        options={"verify_signature": False},
    )
    with TestSession() as db:
        user = active_public_pilot_user_from_payload(db, payload)
    assert user.organization.slug == "altea-beauty"


def test_no_claim_with_multiple_active_non_default_memberships_fails_closed():
    profile_id, _ = _active_invited_user(
        subject="ambiguous-non-default",
        organization_name="First Studio",
        organization_slug="first-studio",
    )
    with TestSession() as db:
        second_org = models.Organization(
            name="Second Studio",
            slug="second-studio",
            status="active",
            settings_json={},
        )
        db.add(second_org)
        db.flush()
        db.add(
            models.Membership(
                organization_id=second_org.id,
                user_profile_id=profile_id,
                role="producer",
                status="active",
                permissions_json=[],
            )
        )
        db.commit()
    payload = jwt.decode(
        _access_token(subject="ambiguous-non-default"),
        options={"verify_signature": False},
    )
    with TestSession() as db, pytest.raises(HTTPException) as raised:
        active_public_pilot_user_from_payload(db, payload)
    assert raised.value.status_code == 403
    assert raised.value.detail == "public_pilot_invite_required"


def test_password_template_contains_csrf_and_never_prefills_secrets():
    template = (
        Path(__file__).parents[1]
        / "app"
        / "templates"
        / "set_password.html"
    ).read_text(encoding="utf-8")
    assert 'name="csrf_token"' in template
    assert template.count('autocomplete="new-password"') == 2
    assert 'name="password" type="password"' in template
    assert 'name="password_confirmation" type="password"' in template
    assert "token_hash" not in template
    assert 'value="{{ password' not in template


def test_fragment_bridge_is_local_clears_history_and_posts_once():
    template = (
        Path(__file__).parents[1]
        / "app"
        / "templates"
        / "invite_accept.html"
    ).read_text(encoding="utf-8")
    assert 'action="/auth/confirm"' in template
    assert 'method="post"' in template
    assert 'name="token_hash"' in template
    assert 'name="type"' in template
    assert 'name="bridge_nonce"' in template
    assert "window.location.hash" in template
    assert "window.history.replaceState" in template
    assert template.index("window.history.replaceState") < template.index("form.submit()")
    assert "https://" not in template
    assert "<script src=" not in template
    assert "console." not in template
