from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.creator_operations import CreatorOperationsError, CreatorOperationsService
from app.database import get_db
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.public_pilot.auth import (
    PublicPilotUser,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.ui import templates


router = APIRouter(prefix="/creator-operations", tags=["creator-operations"])
TABS = frozenset({"generation", "placement", "stats", "payouts", "tasks", "needs"})


def _redirect(tab: str, *, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&notice={quote(notice)}" if notice else f"&error={quote(error or 'operation_failed')}"
    return RedirectResponse(f"/creator-operations?tab={tab}{suffix}", status_code=303)


def _flash(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split())[:160]
    return normalized or None


@router.get("", response_class=HTMLResponse)
def creator_operations(
    request: Request,
    tab: str = "tasks",
    notice: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    selected_tab = tab if tab in TABS else "tasks"
    service = CreatorOperationsService(db)
    paid_generation_enabled = (
        service.settings.allow_real_spend
        and service.settings.generation_mode == "real"
        and service.settings.video_provider != "mock"
        and bool(os.getenv("RUNWAYML_API_SECRET"))
    )
    owner_view = user.role in {"owner", "admin"}
    memberships = db.scalars(
        select(models.Membership)
        .join(models.UserProfile)
        .where(
            models.Membership.organization_id == user.organization.id,
            models.Membership.status == "active",
            models.UserProfile.status == "active",
            models.UserProfile.is_active.is_(True),
        )
        .order_by(models.Membership.role, models.Membership.id)
    ).all()
    final_certified_ids = {
        membership.user_profile_id
        for membership in memberships
        if service.final_exam_passed(membership.user_profile_id)
    }
    team = [
        {
            "membership": membership,
            "profile": membership.user_profile,
            "final_exam_passed": membership.user_profile_id in final_certified_ids,
        }
        for membership in memberships
    ]
    ready_drafts = db.scalars(
        select(models.ProductUGCRecipeDraft)
        .join(models.Product)
        .where(
            models.Product.organization_id == user.organization.id,
            models.ProductUGCRecipeDraft.status == "ready_for_paid_preflight",
        )
        .order_by(models.ProductUGCRecipeDraft.created_at.desc(), models.ProductUGCRecipeDraft.id.desc())
        .limit(100)
    ).all()
    packages = db.scalars(
        select(models.PublishingPackage)
        .join(models.Product)
        .where(
            models.Product.organization_id == user.organization.id,
            models.PublishingPackage.organization_id == user.organization.id,
            models.PublishingPackage.status == "approved",
            models.PublishingPackage.review_status == "approved",
        )
        .order_by(models.PublishingPackage.created_at.desc(), models.PublishingPackage.id.desc())
        .limit(250)
    ).all()
    destinations = db.scalars(
        select(models.PublishingDestination)
        .where(
            models.PublishingDestination.organization_id == user.organization.id,
            models.PublishingDestination.status == "active",
        )
        .order_by(models.PublishingDestination.platform, models.PublishingDestination.name)
    ).all()
    batches = db.scalars(
        select(models.MassOperationBatch)
        .where(models.MassOperationBatch.organization_id == user.organization.id)
        .order_by(models.MassOperationBatch.created_at.desc(), models.MassOperationBatch.id.desc())
        .limit(50)
    ).all()
    tasks = service.task_inbox(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
        limit=200,
    )
    payouts = service.payout_ledger(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
        limit=200,
    )
    task_artifacts = {
        artifact.id: artifact.public_id
        for artifact in db.scalars(
            select(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == user.organization.id,
                models.MediaArtifact.id.in_(
                    [task.media_artifact_id for task in tasks if task.media_artifact_id]
                ),
            )
        ).all()
    }
    queue_health = ProductUGCGenerationQueueService(db).operational_health(
        organization_id=user.organization.id
    )
    stats = {
        "team_members": len(team),
        "certified_creators": len({item["profile"].id for item in team if item["final_exam_passed"]}),
        "tasks_open": sum(item.status not in {"done", "cancelled"} for item in tasks),
        "tasks_done": sum(item.status == "done" for item in tasks),
        "videos_ready": db.scalar(
            select(func.count()).select_from(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == user.organization.id,
                models.MediaArtifact.kind.in_(["provider_output", "master_video"]),
                models.MediaArtifact.status == "ready",
                models.MediaArtifact.deleted_at.is_(None),
            )
        ) or 0,
        "payout_pending_minor": sum(item.amount_minor for item in payouts if item.status in {"pending", "approved"}),
        "payout_paid_minor": sum(item.amount_minor for item in payouts if item.status == "paid"),
    }
    needs = []
    if not queue_health["worker_ready"]:
        needs.append({"title": "Запустить supervised worker", "detail": "Массовая очередь сохранит задачи, но не должна обещать обработку без heartbeat."})
    if not paid_generation_enabled:
        needs.append({"title": "Подключить реального видеопровайдера", "detail": "Сейчас доступны безопасные dry-run проверки. Для платной очереди владелец должен настроить Runway, real mode и отдельный spend gate."})
    if not ready_drafts:
        needs.append({"title": "Подготовить шаблон генерации", "detail": "Нужен хотя бы один draft со всеми фото и пройденным preflight."})
    if not destinations:
        needs.append({"title": "Добавить площадки", "detail": "Подключите принадлежащие команде аккаунты или ручные направления размещения."})
    if any(not item["final_exam_passed"] for item in team):
        needs.append({"title": "Завершить обучение команды", "detail": "В массовую работу попадают только креаторы, прошедшие итоговый сценарный экзамен."})
    if not needs:
        needs.append({"title": "Критичных разрывов нет", "detail": "Можно запускать dry-run новой партии и проверять лимиты до расходов."})

    return templates.TemplateResponse(
        request,
        "creator_operations.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Командная работа",
            "active_page": "creator-operations",
            "selected_tab": selected_tab,
            "user": user,
            "role": user.role,
            "owner_view": owner_view,
            "can_create_generation": user.role in {"owner", "admin", "producer"},
            "can_enqueue_generation": user.role in {"owner", "admin"} and paid_generation_enabled,
            "can_create_placement": user.role in {"owner", "admin", "operator"},
            "form_csrf_token": form_csrf_token(request),
            "generation_idempotency_key": f"ui-generation:{user.organization.id}:{uuid4().hex}",
            "placement_idempotency_key": f"ui-placement:{user.organization.id}:{uuid4().hex}",
            "team": team,
            "ready_drafts": ready_drafts,
            "packages": packages,
            "destinations": destinations,
            "batches": batches,
            "tasks": tasks,
            "task_artifacts": task_artifacts,
            "payouts": payouts,
            "queue_health": queue_health,
            "stats": stats,
            "needs": needs,
            "notice": _flash(notice),
            "error": _flash(error),
            "default_start_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        },
    )


@router.post("/generation-batches")
def create_generation_batch(
    request: Request,
    csrf_token: str = Form(...),
    template_draft_id: int = Form(...),
    assignee_user_profile_ids: list[int] = Form(...),
    quantity: int = Form(...),
    name: str = Form(...),
    idempotency_key: str = Form(...),
    mode: str = Form("dry_run"),
    confirm_real_spend: bool = Form(False),
    confirmed_total_credits: int = Form(0),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if mode not in {"dry_run", "enqueue"}:
        return _redirect("generation", error="invalid_generation_mode")
    dry_run = mode == "dry_run"
    try:
        batch = CreatorOperationsService(db).generation_batch(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            template_draft_id=template_draft_id,
            assignee_user_profile_ids=assignee_user_profile_ids,
            quantity=quantity,
            name=name,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
            confirm_real_spend=confirm_real_spend,
            confirmed_total_credits=confirmed_total_credits,
        )
    except CreatorOperationsError as exc:
        return _redirect("generation", error=str(exc))
    notice = f"batch_{batch.id}_{batch.status}"
    return _redirect("generation", notice=notice)


@router.post("/placement-batches")
def create_placement_batch(
    request: Request,
    csrf_token: str = Form(...),
    package_ids: list[int] = Form(...),
    destination_ids: list[int] = Form(...),
    assignee_user_profile_ids: list[int] = Form(...),
    start_at: datetime = Form(...),
    interval_minutes: int = Form(60),
    name: str = Form(...),
    idempotency_key: str = Form(...),
    mode: str = Form("dry_run"),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if mode not in {"dry_run", "schedule"}:
        return _redirect("placement", error="invalid_placement_mode")
    try:
        batch = CreatorOperationsService(db).placement_batch(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            package_ids=package_ids,
            destination_ids=destination_ids,
            assignee_user_profile_ids=assignee_user_profile_ids,
            start_at=start_at,
            interval_minutes=interval_minutes,
            name=name,
            idempotency_key=idempotency_key,
            dry_run=mode == "dry_run",
        )
    except CreatorOperationsError as exc:
        return _redirect("placement", error=str(exc))
    return _redirect("placement", notice=f"batch_{batch.id}_{batch.status}")


@router.post("/tasks/{task_id}/complete-placement")
def complete_manual_placement(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    final_url: str = Form(...),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        task = CreatorOperationsService(db).complete_manual_placement(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            task_id=task_id,
            final_url=final_url,
        )
    except CreatorOperationsError as exc:
        return _redirect("tasks", error=str(exc))
    return _redirect("tasks", notice=f"task_{task.id}_{task.status}")


@router.post("/tasks/{task_id}/review")
def review_generated_task(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    decision: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        task = CreatorOperationsService(db).review_generated_task(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            task_id=task_id,
            decision=decision,
            notes=notes,
        )
    except CreatorOperationsError as exc:
        return _redirect("tasks", error=str(exc))
    return _redirect("tasks", notice=f"task_{task.id}_{task.status}")
