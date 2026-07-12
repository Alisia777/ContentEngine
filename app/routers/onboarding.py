from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.novice_learning_path import NoviceLearningPathError, NoviceLearningPathService
from app.public_pilot.auth import (
    PublicPilotUser,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.public_pilot.onboarding import CloudOnboardingService, safe_workspace_next
from app.public_pilot.training_catalog import ONBOARDING_EXAM_CODE
from app.ui import templates


router = APIRouter(tags=["cloud-onboarding"])


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(
    request: Request,
    module: str | None = None,
    result: str | None = None,
    score: int | None = None,
    next: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    context = CloudOnboardingService(db).context(user, selected_code=module)
    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Обучение",
            "user": user,
            "result": result if result in {"passed", "failed"} else None,
            "score": score,
            "next_url": safe_workspace_next(next),
            "form_csrf_token": form_csrf_token(request),
            **context,
        },
    )


@router.post("/onboarding/modules/{module_code}/submit")
async def submit_onboarding_module(
    module_code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    form = await request.form()
    require_form_csrf(request, str(form.get("csrf_token") or ""))
    next_url = safe_workspace_next(str(form.get("next") or ""))
    service = CloudOnboardingService(db)
    context = service.context(user, selected_code=module_code)
    active_codes = {str(item["code"]) for item in context["modules"]}
    if module_code not in active_codes:
        raise HTTPException(status_code=404, detail="onboarding_module_not_found")
    if module_code == ONBOARDING_EXAM_CODE:
        try:
            service.require_exam_prerequisites(user_profile_id=user.profile.id)
        except HTTPException:
            return RedirectResponse(
                f"/onboarding?module={quote(module_code)}&result=failed&score=0&next={quote(next_url, safe='')}",
                status_code=303,
            )

    answers: dict[str, object] = {}
    for key in form:
        if not key.startswith("answer_"):
            continue
        question_id = key.removeprefix("answer_")
        values = form.getlist(key)
        answers[question_id] = values if len(values) > 1 else values[0]
    try:
        submission = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code=module_code,
            answers=answers,
        )
    except NoviceLearningPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if module_code == ONBOARDING_EXAM_CODE and submission.passed:
        return RedirectResponse(next_url, status_code=303)
    result = "passed" if submission.passed else "failed"
    return RedirectResponse(
        f"/onboarding?module={quote(module_code)}&result={result}"
        f"&score={round(submission.score * 100)}&next={quote(next_url, safe='')}",
        status_code=303,
    )
