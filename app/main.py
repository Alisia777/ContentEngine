from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.public_pilot.auth import SupabaseJWTValidator
from app.routers import altea_motion, api, pages, product_events, public_pilot
from app.ui import templates

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")

    @app.middleware("http")
    async def public_pilot_auth_wall(request: Request, call_next):
        current_settings = get_settings()
        if current_settings.auth_required:
            path = request.url.path
            public_path = path in {"/login", "/logout", "/health"} or path.startswith("/static/")
            if not public_path:
                token = request.cookies.get(current_settings.session_cookie_name)
                auth_header = request.headers.get("authorization", "")
                if not token and auth_header.lower().startswith("bearer "):
                    token = auth_header.split(" ", 1)[1].strip()
                authenticated = False
                if token:
                    try:
                        SupabaseJWTValidator().validate(token)
                        authenticated = True
                    except (HTTPException, ValueError, TypeError, json.JSONDecodeError):
                        authenticated = False
                if not authenticated:
                    if path.startswith("/api"):
                        return JSONResponse({"detail": "authentication_required"}, status_code=401)
                    response = RedirectResponse("/login", status_code=303)
                    response.delete_cookie(current_settings.session_cookie_name, path="/")
                    return response
        return await call_next(request)

    app.include_router(api.router)
    app.include_router(product_events.router)
    app.include_router(altea_motion.router)
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
    return app


app = create_app()
