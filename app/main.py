from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import altea_motion, api, pages, public_pilot
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
            public_prefixes = ("/login", "/logout", "/static", "/media", "/health", "/altea-motion")
            if not path.startswith(public_prefixes):
                token = request.cookies.get(current_settings.session_cookie_name)
                auth_header = request.headers.get("authorization", "")
                if not token and not auth_header.lower().startswith("bearer "):
                    if path.startswith("/api"):
                        return JSONResponse({"detail": "authentication_required"}, status_code=401)
                    return RedirectResponse("/login", status_code=303)
        return await call_next(request)

    app.include_router(api.router)
    app.include_router(altea_motion.router)
    app.include_router(public_pilot.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
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
