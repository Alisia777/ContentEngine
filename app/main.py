from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.public_pilot.auth import SupabaseJWTValidator, active_public_pilot_user_from_payload
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.routers import (
    altea_motion,
    api,
    authorized_media,
    marketplace_listings,
    pages,
    product_events,
    public_pilot,
    public_pilot_api,
    social_metrics,
)
from app.ui import templates

settings = get_settings()


PUBLIC_UNAUTHENTICATED_PATHS = frozenset({"/login", "/logout", "/health"})
PUBLIC_UNAUTHENTICATED_PREFIXES = ("/static/", "/r/")
PUBLIC_PILOT_SCOPED_PATHS = frozenset(
    {
        "/",
        "/control-room",
        "/workbench",
        "/mvp-launch",
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
    init_db()
    # Reclaim expired leases and quarantine any ambiguous paid submission
    # before web traffic can enqueue another attempt after a restart.
    with SessionLocal() as db:
        ProductUGCGenerationQueueService(db).reconcile_stale()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
        auth_header = request.headers.get("authorization", "")
        if not token and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if current_settings.auth_required and not token:
            if path.startswith("/api"):
                return JSONResponse({"detail": "authentication_required"}, status_code=401)
            response = RedirectResponse("/login", status_code=303)
            response.delete_cookie(current_settings.session_cookie_name, path="/")
            return response
        if token and pilot_boundary:
            try:
                payload = SupabaseJWTValidator().validate(token)
                with SessionLocal() as db:
                    active_public_pilot_user_from_payload(db, payload)
                request.state.public_pilot_auth_payload = payload
            except HTTPException as exc:
                if exc.status_code == 403:
                    return JSONResponse({"detail": exc.detail}, status_code=403)
                if path.startswith("/api"):
                    return JSONResponse({"detail": "authentication_required"}, status_code=401)
                response = RedirectResponse("/login", status_code=303)
                response.delete_cookie(current_settings.session_cookie_name, path="/")
                return response
            except (ValueError, TypeError, json.JSONDecodeError):
                if path.startswith("/api"):
                    return JSONResponse({"detail": "authentication_required"}, status_code=401)
                response = RedirectResponse("/login", status_code=303)
                response.delete_cookie(current_settings.session_cookie_name, path="/")
                return response
        return await call_next(request)

    app.include_router(api.router)
    app.include_router(product_events.router)
    app.include_router(marketplace_listings.router)
    app.include_router(social_metrics.router)
    app.include_router(altea_motion.router)
    # Entity-scoped routes must be registered before the legacy catch-all.
    app.include_router(authorized_media.router)
    app.include_router(public_pilot_api.router)
    app.include_router(public_pilot.router)

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
