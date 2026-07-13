from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.config import get_settings
from app.database import get_db
from app.public_pilot.auth import (
    PublicPilotUser,
    SupabaseJWTValidator,
    active_public_pilot_user_from_payload,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.public_pilot.supabase_auth import (
    SupabaseAuthClient,
    SupabaseAuthError,
    clear_session_cookies,
    set_supabase_session_cookies,
)
from app.ui import templates


router = APIRouter(tags=["invite-acceptance"])
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1_024
INVITE_BRIDGE_COOKIE = "qvf_invite_bridge"
INVITE_BRIDGE_MAX_AGE_SECONDS = 300


def _private_response(response: Response) -> Response:
    response.headers["cache-control"] = "no-store, max-age=0"
    response.headers["pragma"] = "no-cache"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["x-robots-tag"] = "noindex, nofollow"
    return response


def _redirect(path: str) -> RedirectResponse:
    return _private_response(RedirectResponse(path, status_code=303))


def _clear_bridge_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        INVITE_BRIDGE_COOKIE,
        path="/auth/confirm",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def _bridge_redirect(path: str) -> RedirectResponse:
    response = _redirect(path)
    _clear_bridge_cookie(response)
    return response


def _valid_token_hash(value: str | None) -> bool:
    normalized = str(value or "").strip()
    return 8 <= len(normalized) <= 2_048 and all(
        33 <= ord(character) <= 126 for character in normalized
    )


def _supabase_access_token(request: Request) -> str:
    token = getattr(request.state, "public_pilot_session_token", None)
    if not isinstance(token, str) or not token:
        token = request.cookies.get(get_settings().session_cookie_name)
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=401, detail="authentication_required")
    payload = getattr(request.state, "public_pilot_auth_payload", None)
    if not isinstance(payload, dict):
        payload = SupabaseJWTValidator().validate(token)
    if payload.get("auth_source") == "local":
        raise HTTPException(status_code=403, detail="supabase_session_required")
    return token


@router.get("/auth/accept", response_class=HTMLResponse)
def accept_invite_bridge(request: Request) -> HTMLResponse:
    """Render a local fragment-to-form bridge without receiving the invite hash."""

    bridge_nonce = secrets.token_urlsafe(32)
    csp_nonce = secrets.token_urlsafe(24)
    response = templates.TemplateResponse(
        request,
        "invite_accept.html",
        {
            "page_title": "Контент ИИ Завод · Подтверждение приглашения",
            "bridge_nonce": bridge_nonce,
            "csp_nonce": csp_nonce,
        },
    )
    _private_response(response)
    response.headers["content-security-policy"] = (
        "default-src 'none'; "
        f"script-src 'nonce-{csp_nonce}'; style-src 'nonce-{csp_nonce}'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    response.headers["x-frame-options"] = "DENY"
    settings = get_settings()
    response.set_cookie(
        INVITE_BRIDGE_COOKIE,
        bridge_nonce,
        max_age=INVITE_BRIDGE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/auth/confirm",
    )
    return response


@router.get("/auth/confirm")
def reject_get_confirmation(request: Request) -> RedirectResponse:
    # Legacy or malformed links must never redeem a query-string token. Clear
    # the in-process access-log scope as defense in depth and return generically.
    request.scope["query_string"] = b""
    return _bridge_redirect("/login?error=invalid_invite")


@router.post("/auth/confirm")
async def confirm_invite(
    request: Request,
    token_hash: str = Form(""),
    invite_type: str = Form("", alias="type"),
    bridge_nonce: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redeem one invite hash server-side and move secrets into HttpOnly cookies."""

    cookie_nonce = request.cookies.get(INVITE_BRIDGE_COOKIE, "")
    valid_bridge = (
        20 <= len(bridge_nonce) <= 200
        and len(cookie_nonce) == len(bridge_nonce)
        and hmac.compare_digest(cookie_nonce, bridge_nonce)
    )
    if not valid_bridge:
        return _bridge_redirect("/login?error=invalid_invite")
    if invite_type != "invite" or not _valid_token_hash(token_hash):
        return _bridge_redirect("/login?error=invalid_invite")
    try:
        session = await SupabaseAuthClient().verify_otp(
            token_hash=token_hash.strip(),
            verification_type="invite",
        )
        payload = SupabaseJWTValidator().validate(session.access_token)
        active_public_pilot_user_from_payload(db, payload)
    except SupabaseAuthError as exc:
        error = (
            "auth_rate_limited"
            if exc.status_code == 429
            else "auth_unavailable"
            if exc.status_code >= 500
            else "invalid_invite"
        )
        return _bridge_redirect(f"/login?error={error}")
    except HTTPException as exc:
        # Membership and token failures are intentionally indistinguishable to
        # anyone holding a stale or forwarded invitation link.
        error = "auth_unavailable" if exc.status_code >= 500 else "invalid_invite"
        return _bridge_redirect(f"/login?error={error}")

    response = _redirect("/onboarding/set-password")
    _clear_bridge_cookie(response)
    set_supabase_session_cookies(response, session)
    return response


@router.get("/onboarding/set-password", response_class=HTMLResponse)
def set_password_page(
    request: Request,
    error: str | None = None,
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    _supabase_access_token(request)
    error_messages = {
        "weak_password": "Пароль должен содержать не менее 12 символов.",
        "password_mismatch": "Пароли не совпадают. Введите их ещё раз.",
        "password_rejected": "Пароль не принят. Выберите другой надёжный пароль.",
        "auth_rate_limited": "Слишком много попыток. Подождите и попробуйте снова.",
        "auth_unavailable": "Сервис входа временно недоступен. Попробуйте снова через минуту.",
    }
    response = templates.TemplateResponse(
        request,
        "set_password.html",
        {
            "page_title": "Контент ИИ Завод · Создание пароля",
            "user": user,
            "form_csrf_token": form_csrf_token(request),
            "error_message": error_messages.get(error),
            "password_min_length": PASSWORD_MIN_LENGTH,
            "password_max_length": PASSWORD_MAX_LENGTH,
        },
    )
    return _private_response(response)


@router.post("/onboarding/set-password")
async def set_password_submit(
    request: Request,
    csrf_token: str = Form(...),
    password: str = Form(...),
    password_confirmation: str = Form(...),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user  # The dependency is the active-membership gate for this write.
    require_form_csrf(request, csrf_token)
    access_token = _supabase_access_token(request)
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        return _redirect("/onboarding/set-password?error=weak_password")
    if len(password_confirmation) > PASSWORD_MAX_LENGTH:
        return _redirect("/onboarding/set-password?error=password_mismatch")
    if not hmac.compare_digest(
        password.encode("utf-8"),
        password_confirmation.encode("utf-8"),
    ):
        return _redirect("/onboarding/set-password?error=password_mismatch")
    try:
        await SupabaseAuthClient().update_password(
            access_token=access_token,
            password=password,
        )
    except SupabaseAuthError as exc:
        if exc.code == "invalid_session":
            response = _redirect("/login?error=session_expired")
            clear_session_cookies(response)
            return response
        error = (
            "auth_rate_limited"
            if exc.status_code == 429
            else "auth_unavailable"
            if exc.status_code >= 500
            else "password_rejected"
        )
        return _redirect(f"/onboarding/set-password?error={error}")
    return _redirect("/onboarding")
