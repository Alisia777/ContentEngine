from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.interface_productization import InterfaceProductizationError, MVPLaunchWizardService, MVPWorkspaceService
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.public_pilot.control_room import PublicPilotControlRoomService
from app.public_pilot.gate_matrix import ACTION_LABELS, PublicPilotGateMatrix, TRAINING_ATTEMPT
from app.ui import templates

router = APIRouter(tags=["public-pilot"])


@router.get("/login", response_class=HTMLResponse)
def public_login(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        "public_login.html",
        {"request": request, "page_title": "ALTEA Public Pilot Login", "error": error},
    )


@router.post("/login")
def public_login_submit(email: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    settings = get_settings()
    if not settings.auth_required:
        return RedirectResponse("/control-room", status_code=303)
    if not settings.supabase_url:
        return RedirectResponse("/login?error=supabase_not_configured", status_code=303)
    if not password:
        return RedirectResponse("/login?error=password_required", status_code=303)
    # Real Supabase password exchange is intentionally not performed in tests/local acceptance.
    return RedirectResponse("/login?error=oauth_exchange_not_configured_locally", status_code=303)


@router.post("/logout")
def public_logout() -> RedirectResponse:
    settings = get_settings()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


@router.get("/control-room", response_class=HTMLResponse)
def control_room(
    request: Request,
    role: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    context = PublicPilotControlRoomService(db).context(user, role=role)
    return templates.TemplateResponse(
        "public_control_room.html",
        {"request": request, "page_title": "ALTEA Control Room", **context},
    )


@router.get("/workbench", response_class=HTMLResponse)
def mvp_workbench(
    request: Request,
    tab: str = "product",
    role: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    selected_role = role or (user.role if user.role in {"owner", "admin", "reviewer", "operator"} else "owner")
    service = MVPWorkspaceService(db)
    snapshot = service.output(service.build(role=selected_role))
    allowed_tabs = {item.key for item in snapshot.module_links}
    selected_tab = tab if tab in allowed_tabs else "product"
    return templates.TemplateResponse(
        "public_workbench.html",
        {
            "request": request,
            "page_title": "ALTEA Рабочая область",
            "user": user,
            "role": selected_role,
            "workspace": snapshot,
            "selected_tab": selected_tab,
        },
    )


@router.get("/mvp-launch", response_class=HTMLResponse)
def mvp_launch(
    request: Request,
    run_id: int | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    service = MVPLaunchWizardService(db)
    run_output = None
    error = None
    if run_id:
        try:
            run_output = service.output(service.get(run_id))
        except InterfaceProductizationError as exc:
            error = str(exc)
    products = list(db.scalars(select(models.Product).order_by(models.Product.id.desc()).limit(50)))
    return templates.TemplateResponse(
        "public_mvp_launch.html",
        {
            "request": request,
            "page_title": "ALTEA Запуск MVP",
            "user": user,
            "role": user.role,
            "run": run_output,
            "products": products,
            "error": error,
        },
    )


@router.post("/mvp-launch/start")
def mvp_launch_start(
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user
    run = MVPLaunchWizardService(db).start(product_id=product_id, sku=sku or None)
    return RedirectResponse(f"/mvp-launch?run_id={run.id}", status_code=303)


@router.post("/mvp-launch/{run_id}/next")
def mvp_launch_next(
    run_id: int,
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    runway_credits_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user
    try:
        MVPLaunchWizardService(db).advance(
            run_id,
            product_id=product_id,
            sku=sku or None,
            runway_credits_confirmed=runway_credits_confirmed,
        )
    except InterfaceProductizationError:
        return RedirectResponse("/mvp-launch?error=run_not_found", status_code=303)
    return RedirectResponse(f"/mvp-launch?run_id={run_id}", status_code=303)


@router.get("/settings/access", response_class=HTMLResponse)
def settings_access(
    request: Request,
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    settings = get_settings()
    matrix_service = PublicPilotGateMatrix(strict_training=settings.public_pilot_strict_training_gates)
    return templates.TemplateResponse(
        "settings_access.html",
        {
            "request": request,
            "page_title": "Access Gates",
            "user": user,
            "roles": matrix_service.matrix().get("settings_view", {}).keys(),
            "matrix": matrix_service.matrix(),
            "summary": matrix_service.summary(),
            "action_labels": ACTION_LABELS,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_redirect() -> RedirectResponse:
    return RedirectResponse("/settings/access", status_code=302)


@router.post("/control-room/training/{module_code}/submit")
def complete_training(
    module_code: str,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
):
    service = PublicPilotAccessService(db)
    service.require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=TRAINING_ATTEMPT,
        payload={"module_code": module_code},
    )
    try:
        cert = service.grant_certification(user.profile.id, module_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"module_code": module_code, "certification_id": cert.id, "status": cert.status}

