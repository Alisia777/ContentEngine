from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.public_pilot.auth import (
    PublicPilotUser,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.team import (
    TEAM_ROLE_ALLOWLIST,
    SupabaseAdminError,
    TeamError,
    TeamPermissionError,
    TeamService,
)
from app.ui import templates


router = APIRouter(prefix="/team", tags=["team"])

TEAM_ROLE_DISPLAY_ORDER = (
    "producer",
    "operator",
    "reviewer",
    "trainee",
    "viewer",
    "admin",
    "owner",
)
TEAM_ROLE_LABELS = {
    "owner": "Владелец — полный контроль",
    "admin": "Администратор — команда и настройки",
    "producer": "Продюсер — создание контента",
    "reviewer": "Проверяющий — контроль качества",
    "operator": "Оператор — выполнение задач",
    "trainee": "Стажёр — обучение с ограничениями",
    "viewer": "Наблюдатель — только просмотр",
}


def get_team_service(db: Session = Depends(get_db)) -> TeamService:
    return TeamService(db)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def team_roster_page(
    request: Request,
    q: str | None = None,
    notice: str | None = None,
    error: str | None = None,
    user: PublicPilotUser = Depends(get_current_public_user),
    service: TeamService = Depends(get_team_service),
) -> HTMLResponse:
    public_app_url = (get_settings().public_app_url or "").rstrip("/")
    try:
        complete_roster = service.roster(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
        )
    except TeamPermissionError as exc:
        raise HTTPException(status_code=403, detail="team_manager_required") from exc
    search_query = " ".join(str(q or "").strip().split())[:120]
    roster = complete_roster
    if search_query:
        needle = search_query.casefold()
        roster = [
            member
            for member in complete_roster
            if needle
            in " ".join(
                (
                    member.display_name or "",
                    member.email,
                    member.role,
                    member.status,
                    str(member.user_profile_id),
                )
            ).casefold()
        ]
    available_roles = [
        role for role in TEAM_ROLE_DISPLAY_ORDER if role in TEAM_ROLE_ALLOWLIST
    ]
    available_roles.extend(sorted(TEAM_ROLE_ALLOWLIST.difference(available_roles)))
    if user.role == "admin":
        available_roles = [role for role in available_roles if role not in {"owner", "admin"}]
    return templates.TemplateResponse(
        request,
        "team_roster.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Команда",
            "active_page": "team",
            "user": user,
            "role": user.role,
            "form_csrf_token": form_csrf_token(request),
            "roster": roster,
            "roster_total": len(complete_roster),
            "search_query": search_query,
            "roles": available_roles,
            "role_labels": TEAM_ROLE_LABELS,
            "default_redirect_to": f"{public_app_url}/login" if public_app_url else "",
            "notice": notice if notice in {"invited", "added", "suspended", "reactivated"} else None,
            "error": error
            if error
            in {
                "invalid_input",
                "permission_denied",
                "provider_unavailable",
                "state_conflict",
                "confirmation_required",
            }
            else None,
        },
    )


@router.post("/invite")
def invite_team_member(
    request: Request,
    email: str = Form(...),
    role: str = Form(...),
    display_name: str = Form(""),
    redirect_to: str = Form(""),
    csrf_token: str = Form(""),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: TeamService = Depends(get_team_service),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    public_app_url = (get_settings().public_app_url or "").rstrip("/")
    invite_redirect = f"{public_app_url}/login" if public_app_url else (redirect_to or None)
    try:
        result = service.invite_or_add(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            email=email,
            role=role,
            display_name=display_name or None,
            redirect_to=invite_redirect,
        )
    except TeamPermissionError:
        return _redirect(error="permission_denied")
    except SupabaseAdminError:
        return _redirect(error="provider_unavailable")
    except TeamError as exc:
        return _redirect(error="state_conflict" if exc.code == "team_state_conflict" else "invalid_input")
    return _redirect(notice="invited" if result.invited else "added")


@router.post("/memberships/{membership_id}/suspend")
def suspend_team_membership(
    membership_id: int,
    request: Request,
    confirm_action: bool = Form(False),
    csrf_token: str = Form(""),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: TeamService = Depends(get_team_service),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_action:
        return _redirect(error="confirmation_required")
    try:
        service.suspend_membership(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            membership_id=membership_id,
        )
    except TeamPermissionError:
        return _redirect(error="permission_denied")
    except TeamError:
        return _redirect(error="state_conflict")
    return _redirect(notice="suspended")


@router.post("/memberships/{membership_id}/reactivate")
def reactivate_team_membership(
    membership_id: int,
    request: Request,
    confirm_action: bool = Form(False),
    csrf_token: str = Form(""),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: TeamService = Depends(get_team_service),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_action:
        return _redirect(error="confirmation_required")
    try:
        service.reactivate_membership(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            membership_id=membership_id,
        )
    except TeamPermissionError:
        return _redirect(error="permission_denied")
    except TeamError:
        return _redirect(error="state_conflict")
    return _redirect(notice="reactivated")


def _redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    query = f"notice={quote(notice)}" if notice else f"error={quote(error or 'invalid_input')}"
    return RedirectResponse(f"/team?{query}", status_code=303)
