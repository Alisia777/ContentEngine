from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import models
from app.config import get_settings, validate_runtime_settings
from app.database import SessionLocal, engine, init_db
from app.media_storage import close_storage_backends
from app.migration_state import require_database_at_migration_head
from app.public_pilot.auth import SupabaseJWTValidator, active_public_pilot_user_from_payload
from app.public_pilot.supabase_auth import (
    SupabaseAuthClient,
    SupabaseAuthError,
    clear_session_cookies,
    set_supabase_session_cookies,
)
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.public_pilot.onboarding import CloudOnboardingGateMiddleware
from app.routers import (
    altea_motion,
    api,
    authorized_media,
    creator_operations,
    invite_acceptance,
    marketplace_listings,
    media_library,
    onboarding,
    pages,
    product_events,
    public_pilot,
    public_pilot_api,
    readiness,
    social_metrics,
    team,
)
from app.ui import templates

settings = get_settings()


PUBLIC_UNAUTHENTICATED_PATHS = frozenset(
    {"/login", "/logout", "/health", "/ready", "/auth/accept", "/auth/confirm"}
)
PUBLIC_UNAUTHENTICATED_PREFIXES = ("/static/", "/r/")
PUBLIC_PILOT_SCOPED_PATHS = frozenset(
    {
        "/",
        "/control-room",
        "/workbench",
        "/mvp-launch",
        "/creator-operations",
        "/media-library",
        "/team",
        "/onboarding",
        "/settings",
        "/settings/access",
        "/api/factory-dashboard",
        "/api/product-events",
    }
)
PUBLIC_PILOT_SCOPED_PREFIXES = (
    "/control-room/",
    "/workbench/",
    "/mvp-launch/",
    "/creator-operations/",
    "/media-library/",
    "/team/",
    "/onboarding/",
    "/media/",
    "/api/public-pilot/",
    "/api/marketplace-listings/",
    "/api/social-metrics/",
)


def _matches_exact_or_prefix(path: str, exact: frozenset[str], prefixes: tuple[str, ...]) -> bool:
    if path in exact:
        return True
    return any(path.startswith(prefix) for prefix in prefixes)


def _is_public_unauthenticated_path(path: str) -> bool:
    return _matches_exact_or_prefix(
        path,
        PUBLIC_UNAUTHENTICATED_PATHS,
        PUBLIC_UNAUTHENTICATED_PREFIXES,
    )


def _is_public_pilot_scoped_path(path: str) -> bool:
    if path in {"/api/marketplace-listings", "/api/social-metrics"}:
        return True
    return _matches_exact_or_prefix(
        path,
        PUBLIC_PILOT_SCOPED_PATHS,
        PUBLIC_PILOT_SCOPED_PREFIXES,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_settings = validate_runtime_settings(get_settings())
    # Schema DDL is a migration concern in cloud deployments. Local/test
    # profiles retain the convenient bootstrap path for isolated development.
    if current_settings.auto_init_db:
        init_db()
    if current_settings.runtime_profile == "production":
        # Fail before any queue reconciliation or other write when a service
        # is started outside the normal reference pre-deploy path.
        with engine.connect() as connection:
            require_database_at_migration_head(connection)
    # Reclaim expired leases and quarantine any ambiguous paid submission
    # before web traffic can enqueue another attempt after a restart.
    with SessionLocal() as db:
        ProductUGCGenerationQueueService(db).reconcile_stale()
    try:
        yield
    finally:
        close_storage_backends()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    # Registered before the decorator middleware so authentication remains the
    # outer wall and onboarding can trust the validated token payload.
    app.add_middleware(CloudOnboardingGateMiddleware)

    @app.middleware("http")
    async def public_pilot_auth_wall(request: Request, call_next):
        current_settings = get_settings()
        path = request.url.path
        pilot_boundary = current_settings.public_pilot_mode or current_settings.auth_required
        public_path = _is_public_unauthenticated_path(path)
        if pilot_boundary and not public_path and not _is_public_pilot_scoped_path(path):
            return JSONResponse(
                {
                    "detail": "legacy_global_workspace_disabled",
                    "message": "This route has no verified organization boundary; use the public pilot workspace.",
                },
                status_code=409,
            )
        if public_path:
            return await call_next(request)

        token = request.cookies.get(current_settings.session_cookie_name)
        refresh_token = request.cookies.get(current_settings.session_refresh_cookie_name)
        auth_header = request.headers.get("authorization", "")
        bearer_request = auth_header.lower().startswith("bearer ")
        if bearer_request:
            token = auth_header.split(" ", 1)[1].strip()
            # A bearer API caller owns its own refresh flow. Never rotate a
            # browser refresh cookie in response to an Authorization header.
            refresh_token = None
        refreshed_session = None
        if current_settings.auth_required and not token and refresh_token:
            try:
                refreshed_session = await SupabaseAuthClient().refresh_session(refresh_token)
                token = refreshed_session.access_token
            except SupabaseAuthError as exc:
                status_code = 503 if exc.status_code >= 500 else 401
                if path.startswith("/api"):
                    response = JSONResponse({"detail": exc.code}, status_code=status_code)
                else:
                    error = "auth_unavailable" if status_code == 503 else "session_expired"
                    response = RedirectResponse(f"/login?error={error}", status_code=303)
                if status_code != 503:
                    clear_session_cookies(response)
                return response
        if current_settings.auth_required and not token:
            if path.startswith("/api"):
                return JSONResponse({"detail": "authentication_required"}, status_code=401)
            response = RedirectResponse("/login", status_code=303)
            clear_session_cookies(response)
            return response
        if token and pilot_boundary:
            try:
                payload = SupabaseJWTValidator().validate(token)
            except HTTPException as exc:
                if exc.status_code == 401 and exc.detail == "token_expired" and refresh_token:
                    try:
                        refreshed_session = await SupabaseAuthClient().refresh_session(refresh_token)
                        token = refreshed_session.access_token
                        payload = SupabaseJWTValidator().validate(token)
                    except SupabaseAuthError as refresh_exc:
                        status_code = 503 if refresh_exc.status_code >= 500 else 401
                        if path.startswith("/api"):
                            response = JSONResponse({"detail": refresh_exc.code}, status_code=status_code)
                        else:
                            error = "auth_unavailable" if status_code == 503 else "session_expired"
                            response = RedirectResponse(f"/login?error={error}", status_code=303)
                        if status_code != 503:
                            clear_session_cookies(response)
                        return response
                    except HTTPException as refreshed_exc:
                        status_code = 503 if refreshed_exc.status_code == 503 else 401
                        if path.startswith("/api"):
                            detail = refreshed_exc.detail if status_code == 503 else "authentication_required"
                            response = JSONResponse({"detail": detail}, status_code=status_code)
                        else:
                            error = "auth_unavailable" if status_code == 503 else "session_expired"
                            response = RedirectResponse(f"/login?error={error}", status_code=303)
                        if status_code != 503:
                            clear_session_cookies(response)
                        return response
                else:
                    if exc.status_code == 403:
                        return JSONResponse({"detail": exc.detail}, status_code=403)
                    if exc.status_code == 503:
                        if path.startswith("/api"):
                            return JSONResponse({"detail": exc.detail}, status_code=503)
                        response = RedirectResponse("/login?error=auth_unavailable", status_code=303)
                        return response
                    if path.startswith("/api"):
                        response = JSONResponse({"detail": "authentication_required"}, status_code=401)
                    else:
                        response = RedirectResponse("/login", status_code=303)
                    clear_session_cookies(response)
                    return response

            try:
                with SessionLocal() as db:
                    active_public_pilot_user_from_payload(db, payload)
                request.state.public_pilot_auth_payload = payload
                request.state.public_pilot_session_token = token
            except HTTPException as exc:
                if exc.status_code == 403:
                    return JSONResponse({"detail": exc.detail}, status_code=403)
                if path.startswith("/api"):
                    return JSONResponse({"detail": "authentication_required"}, status_code=401)
                response = RedirectResponse("/login", status_code=303)
                clear_session_cookies(response)
                return response
            except (ValueError, TypeError, json.JSONDecodeError):
                if path.startswith("/api"):
                    return JSONResponse({"detail": "authentication_required"}, status_code=401)
                response = RedirectResponse("/login", status_code=303)
                clear_session_cookies(response)
                return response
        response = await call_next(request)
        if refreshed_session is not None:
            set_supabase_session_cookies(response, refreshed_session)
        return response

    app.include_router(api.router)
    app.include_router(product_events.router)
    app.include_router(marketplace_listings.router)
    app.include_router(social_metrics.router)
    app.include_router(altea_motion.router)
    # Entity-scoped routes must be registered before the legacy catch-all.
    app.include_router(authorized_media.router)
    app.include_router(public_pilot_api.router)
    app.include_router(invite_acceptance.router)
    app.include_router(onboarding.router)
    app.include_router(creator_operations.router)
    app.include_router(media_library.router)
    app.include_router(team.router)
    app.include_router(public_pilot.router)
    app.include_router(readiness.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        current_settings = get_settings()
        if current_settings.public_pilot_mode or current_settings.auth_required:
            return RedirectResponse("/control-room", status_code=302)
        with SessionLocal() as db:
            metrics = {
                "Products": db.scalar(select(func.count()).select_from(models.Product)) or 0,
                "Scripts": db.scalar(select(func.count()).select_from(models.ScriptJob)) or 0,
                "Videos": db.scalar(select(func.count()).select_from(models.VideoJob)) or 0,
                "Publishing Jobs": db.scalar(select(func.count()).select_from(models.PublishingJob)) or 0,
            }
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "page_title": "Dashboard",
                "metrics": metrics,
            },
        )

    app.include_router(pages.router)

    @app.get("/media/{media_path:path}", include_in_schema=False)
    def legacy_local_media(media_path: str):
        """Keep the old local workspace usable without exposing it in pilot/auth mode."""

        current_settings = get_settings()
        if current_settings.public_pilot_mode or current_settings.auth_required:
            raise HTTPException(status_code=404, detail="media_not_found")
        source = current_settings.media_root / media_path
        resolved = authorized_media.resolve_media_file(source.as_posix())
        if resolved is None:
            raise HTTPException(status_code=404, detail="media_not_found")
        return FileResponse(resolved)

    return app


app = create_app()
