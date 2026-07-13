from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import os
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, joinedload

from app import models
from app.creator_operations import CreatorOperationsError, CreatorOperationsService
from app.database import get_db
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.publishing.scheduler import PublishingScheduler
from app.public_pilot.auth import (
    PublicPilotUser,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.ui import templates


router = APIRouter(prefix="/creator-operations", tags=["creator-operations"])
TABS = frozenset({"generation", "placement", "stats", "payouts", "tasks", "needs"})
OPERATIONS_PAGE_SIZE = 50
ASSIGNABLE_CREATOR_ROLES = frozenset(
    {"owner", "admin", "producer", "reviewer", "operator", "trainee"}
)
OPERATION_MESSAGES = {
    "review_video_identity_mismatch": "Видео в задаче уже обновилось. Обновите страницу, откройте новый MP4 и проверьте его перед решением.",
    "tracking_target_url_required": "Добавьте в пакет безопасную HTTPS-ссылку на карточку товара, чтобы система создала отслеживаемую ссылку.",
    "tracking_target_url_invalid": "Ссылка на товар должна быть публичной HTTPS-ссылкой без секретных параметров.",
    "placement_final_url_invalid": "Вставьте публичную HTTPS-ссылку на опубликованный пост.",
    "placement_final_url_host_mismatch": "Ссылка ведёт не на ту площадку, которая указана в задаче.",
    "placement_final_url_post_path_required": "Нужна ссылка именно на опубликованный пост или ролик, а не на главную страницу аккаунта.",
    "placement_final_url_short_link_not_supported": "Короткую ссылку нельзя надёжно проверить. Откройте публикацию и вставьте её полный канонический HTTPS-адрес.",
    "placement_final_url_already_used": "Эта публикация уже подтверждена в другой задаче команды.",
    "placement_task_assignee_required": "Подтвердить результат может назначенный креатор либо owner/admin.",
    "payout_rate_owner_admin_required": "Ставку выплаты может задавать только owner или admin.",
    "payout_manager_role_required": "Согласовывать и отмечать выплаты может только owner или admin.",
    "payout_must_be_approved_first": "Сначала согласуйте начисление, затем отметьте внешний платёж.",
    "external_payment_reference_invalid": "Укажите внешний номер платежа длиной от 3 до 180 знаков, без банковских реквизитов.",
    "manual_metrics_publication_required": "Метрики можно сохранить только после подтверждённой публикации.",
    "manual_metric_revenue_invalid": "Выручка должна быть неотрицательной суммой с точностью до копеек.",
    "manual_metrics_cumulative_decrease_requires_correction": "Накопительные метрики не могут уменьшаться. Owner/admin может оформить отдельную коррекцию с причиной.",
    "manual_metrics_correction_manager_required": "Уменьшение накопительных метрик может подтвердить только owner/admin.",
    "manual_metrics_correction_reason_too_short": "Для коррекции укажите причину не короче 10 знаков.",
    "real_spend_gate_required": "Платная генерация выключена. Owner должен отдельно включить реальный режим и подтвердить лимит.",
    "real_spend_owner_admin_required": "Платную генерацию может запустить только owner или admin.",
    "template_draft_not_ready": "Шаблон ещё не прошёл подготовку к генерации. Откройте «Что добавить» и устраните препятствия.",
    "compatible_destination_required": "Для пакета нет выбранной площадки с той же платформой и брендом.",
    "compatible_destination_unavailable": "Все совместимые площадки сейчас заблокированы настройками или лимитами.",
    "publishing_package_already_scheduled": "Этот пакет уже поставлен в расписание и повторно не показывается как свободный.",
    "publishing_package_not_approved": "Пакет ещё не одобрен для размещения.",
    "publishing_package_review_required": "Пакет должен пройти человеческую проверку перед размещением.",
    "package_platform_mismatch": "Платформа пакета не совпадает с площадкой.",
    "package_brand_mismatch": "Бренд пакета не совпадает с брендом площадки.",
    "package_destination_organization_mismatch": "Пакет и площадка принадлежат разным организациям.",
    "destination_posting_disabled": "Для площадки выключен режим публикации.",
    "destination_api_credentials_required": "Для API-публикации площадки нужно настроить действующие реквизиты подключения.",
    "destination_daily_limit_invalid": "У площадки должен быть дневной лимит не меньше 1.",
    "destination_weekly_limit_invalid": "У площадки должен быть недельный лимит не меньше 1.",
    "destination_not_active": "Площадка неактивна.",
    "daily_publishing_limit_reached": "Дневной лимит площадки уже исчерпан.",
    "weekly_publishing_limit_reached": "Недельный лимит площадки уже исчерпан.",
    "daily_publishing_limit_reached_in_batch": "В этой партии исчерпывается дневной лимит площадки.",
    "weekly_publishing_limit_reached_in_batch": "В этой партии исчерпывается недельный лимит площадки.",
    "publishing_video_missing": "У пакета нет доступного готового видео.",
    "publishing_media_review_required": "Видео из библиотеки требует подтверждённой человеческой проверки.",
    "publishing_media_artifact_invalid": "Приватный видеофайл не прошёл проверку целостности или принадлежности.",
    "invalid_start_timezone": "Не удалось определить часовой пояс браузера. Обновите страницу и повторите.",
    "start_at_does_not_exist_in_timezone": "Выбранного местного времени не существует из-за перевода часов. Выберите другое время.",
    "start_at_is_ambiguous_in_timezone": "Это местное время встречается дважды при переводе часов. Выберите время до или после перехода.",
    "dry_run_batch_not_found": "Проверенная партия не найдена в этой организации.",
    "dry_run_batch_must_be_clean_before_launch": "Запустить можно только dry-run без ошибок. Исправьте препятствия и выполните новую проверку.",
    "dry_run_start_at_invalid": "В проверенной партии повреждено время старта. Создайте новый dry-run.",
    "start_at_is_in_the_past": "Время старта проверенной партии уже прошло. Создайте новый dry-run с актуальным временем.",
    "review_rejected_artifact_requires_regeneration": "Этот файл уже был отклонён. Сначала создайте новую генерацию, затем проверяйте новый ролик.",
    "video_review_watch_confirmation_required": "Перед решением подтвердите, что полностью посмотрели именно этот ролик.",
    "approval_review_notes_too_short": "Для одобрения оставьте комментарий не короче 10 знаков: что именно вы проверили.",
    "active_membership_required": "Аккаунт или членство в команде неактивно. Обратитесь к owner/admin.",
}


def _redirect(tab: str, *, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&notice={quote(notice)}" if notice else f"&error={quote(error or 'operation_failed')}"
    return RedirectResponse(f"/creator-operations?tab={tab}{suffix}", status_code=303)


def _flash(value: str | None) -> str | None:
    normalized = " ".join(str(value or "").split())[:160]
    if not normalized:
        return None
    base_code = normalized.split(":", 1)[0]
    if base_code in OPERATION_MESSAGES:
        return OPERATION_MESSAGES[base_code]
    if normalized.startswith("batch_"):
        status = normalized.split("_", 2)[-1]
        return {
            "validated": "Партия проверена без расходов. Исправьте показанные препятствия или запускайте рабочий режим.",
            "queued": "Партия принята и поставлена в общую очередь.",
            "running": "Партия выполняется; прогресс сохраняется в общей базе.",
            "completed": "Партия полностью завершена.",
            "completed_with_errors": "Партия завершена не полностью. Откройте задачи и исправьте отмеченные причины.",
            "blocked": "Партия не создана: dry-run обнаружил препятствия.",
        }.get(status, "Партия сохранена.")
    if normalized.startswith("task_"):
        return "Результат задачи сохранён."
    if normalized.startswith("payout_"):
        return "Статус начисления обновлён."
    if normalized.startswith("metrics_"):
        return "Метрики публикации сохранены и пересчитаны."
    return normalized.replace("_", " ")


def _rubles_to_minor(value: str) -> int:
    try:
        amount = Decimal(str(value or "0").strip().replace(",", "."))
        rounded = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise CreatorOperationsError("payout_per_post_invalid") from exc
    if not amount.is_finite() or amount != rounded or amount < 0:
        raise CreatorOperationsError("payout_per_post_invalid")
    return int(rounded * 100)


def _revenue_to_minor(value: str) -> int:
    try:
        amount = Decimal(str(value or "0").strip().replace(",", "."))
        rounded = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise CreatorOperationsError("manual_metric_revenue_invalid") from exc
    if not amount.is_finite() or amount != rounded or amount < 0:
        raise CreatorOperationsError("manual_metric_revenue_invalid")
    return int(rounded * 100)


@router.get("", response_class=HTMLResponse)
def creator_operations(
    request: Request,
    tab: str = "generation",
    notice: str | None = None,
    error: str | None = None,
    task_page: int = Query(1, ge=1, le=10_000),
    payout_page: int = Query(1, ge=1, le=10_000),
    task_view: str = Query("active", pattern="^(active|completed)$"),
    task_creator_id: int | None = Query(None, ge=1),
    task_batch_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    selected_tab = tab if tab in TABS else "generation"
    service = CreatorOperationsService(db)
    paid_generation_enabled = (
        service.settings.allow_real_spend
        and service.settings.generation_mode == "real"
        and service.settings.video_provider != "mock"
        and bool(os.getenv("RUNWAYML_API_SECRET"))
    )
    owner_view = user.role in {"owner", "admin"}
    if not owner_view:
        task_creator_id = None
    memberships = db.scalars(
        select(models.Membership)
        .join(models.UserProfile)
        .options(joinedload(models.Membership.user_profile))
        .where(
            models.Membership.organization_id == user.organization.id,
            models.Membership.status == "active",
            models.UserProfile.status == "active",
            models.UserProfile.is_active.is_(True),
        )
        .order_by(models.Membership.role, models.Membership.id)
    ).all()
    final_certified_ids = service.final_exam_passed_user_ids(
        membership.user_profile_id for membership in memberships
    )
    team_open_tasks = dict(
        db.execute(
            select(
                models.CreatorTask.assignee_user_profile_id,
                func.count(models.CreatorTask.id),
            )
            .where(
                models.CreatorTask.organization_id == user.organization.id,
                models.CreatorTask.status.not_in(["done", "cancelled"]),
                models.CreatorTask.assignee_user_profile_id.in_(
                    [membership.user_profile_id for membership in memberships]
                ),
            )
            .group_by(models.CreatorTask.assignee_user_profile_id)
        ).all()
    )
    team = [
        {
            "membership": membership,
            "profile": membership.user_profile,
            "final_exam_passed": membership.user_profile_id in final_certified_ids,
            "open_tasks": int(team_open_tasks.get(membership.user_profile_id, 0)),
        }
        for membership in memberships
    ]
    assignable_team = [
        item
        for item in team
        if item["final_exam_passed"]
        and item["membership"].role in ASSIGNABLE_CREATOR_ROLES
    ]
    assignable_team.sort(
        key=lambda item: (
            int(item["open_tasks"]),
            str(item["profile"].display_name or item["profile"].email).casefold(),
        )
    )
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
        .options(joinedload(models.PublishingPackage.product))
        .where(
            models.Product.organization_id == user.organization.id,
            models.PublishingPackage.organization_id == user.organization.id,
            models.PublishingPackage.status == "approved",
            models.PublishingPackage.review_status == "approved",
            ~exists(
                select(models.PublishingTask.id).where(
                    models.PublishingTask.publishing_package_id
                    == models.PublishingPackage.id,
                    models.PublishingTask.status.in_(
                        PublishingScheduler.COUNTED_STATUSES
                    ),
                )
            ),
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
    task_page_rows = service.task_inbox(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
        status_group=task_view,
        assignee_user_profile_id=task_creator_id,
        mass_operation_batch_id=task_batch_id,
        limit=OPERATIONS_PAGE_SIZE + 1,
        offset=(task_page - 1) * OPERATIONS_PAGE_SIZE,
    )
    has_next_task_page = len(task_page_rows) > OPERATIONS_PAGE_SIZE
    tasks = task_page_rows[:OPERATIONS_PAGE_SIZE]
    task_profiles = {
        item["profile"].id: item["profile"]
        for item in team
    }
    task_filter_suffix = (
        f"&task_creator_id={task_creator_id}" if task_creator_id else ""
    ) + (f"&task_batch_id={task_batch_id}" if task_batch_id else "")
    payout_page_rows = service.payout_ledger(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
        limit=OPERATIONS_PAGE_SIZE + 1,
        offset=(payout_page - 1) * OPERATIONS_PAGE_SIZE,
    )
    has_next_payout_page = len(payout_page_rows) > OPERATIONS_PAGE_SIZE
    payouts = payout_page_rows[:OPERATIONS_PAGE_SIZE]
    performance = service.performance_snapshot(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
    )
    workload = service.workload_snapshot(
        organization_id=user.organization.id,
        viewer_user_profile_id=user.profile.id,
    )
    payout_profiles = {
        profile.id: profile
        for profile in (
            db.scalars(
                select(models.UserProfile).where(
                    models.UserProfile.id.in_([item.user_profile_id for item in payouts])
                )
            ).all()
            if payouts
            else []
        )
    }
    task_artifacts = {
        artifact.id: artifact
        for artifact in db.scalars(
            select(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == user.organization.id,
                models.MediaArtifact.id.in_(
                    [task.media_artifact_id for task in tasks if task.media_artifact_id]
                ),
            )
        ).all()
    }
    task_ids_by_publishing_task = {
        int(task.publishing_task_id): task.id
        for task in tasks
        if task.publishing_task_id is not None
    }
    task_latest_metrics: dict[int, models.DestinationPostMetric] = {}
    if task_ids_by_publishing_task:
        for metric in db.scalars(
            select(models.DestinationPostMetric)
            .where(
                models.DestinationPostMetric.publishing_task_id.in_(
                    list(task_ids_by_publishing_task)
                ),
                models.DestinationPostMetric.period_start.is_(None),
                models.DestinationPostMetric.period_end.is_(None),
            )
            .order_by(
                models.DestinationPostMetric.publishing_task_id,
                models.DestinationPostMetric.id.desc(),
            )
        ):
            if dict(metric.raw_json or {}).get("source") != "manual_creator_cumulative_snapshot":
                continue
            creator_task_id = task_ids_by_publishing_task.get(
                int(metric.publishing_task_id)
            )
            if creator_task_id is not None and creator_task_id not in task_latest_metrics:
                task_latest_metrics[creator_task_id] = metric
    queue_health = ProductUGCGenerationQueueService(db).operational_health(
        organization_id=user.organization.id
    )
    stats = {
        **performance,
        **workload,
        "team_members": len(team),
        "certified_creators": len({item["profile"].id for item in team if item["final_exam_passed"]}),
        "videos_ready": db.scalar(
            select(func.count()).select_from(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == user.organization.id,
                models.MediaArtifact.kind.in_(["provider_output", "master_video"]),
                models.MediaArtifact.status == "ready",
                models.MediaArtifact.deleted_at.is_(None),
            )
        ) or 0,
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
    if not packages:
        needs.append({"title": "Одобрить видео для размещения", "detail": "Создайте publishing package из проверенного видео; без него партия размещения закрыта."})
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
            "public_app_url": str(
                service.settings.public_app_url or request.base_url
            ).rstrip("/"),
            "generation_idempotency_key": f"ui-generation:{user.organization.id}:{uuid4().hex}",
            "placement_idempotency_key": f"ui-placement:{user.organization.id}:{uuid4().hex}",
            "team": team,
            "assignable_team": assignable_team,
            "ready_drafts": ready_drafts,
            "mass_generation_credit_limit": service.settings.mass_generation_credit_limit,
            "packages": packages,
            "destinations": destinations,
            "batches": batches,
            "tasks": tasks,
            "task_view": task_view,
            "task_creator_id": task_creator_id,
            "task_batch_id": task_batch_id,
            "task_profiles": task_profiles,
            "task_page": task_page,
            "previous_task_page_url": (
                f"/creator-operations?tab=tasks&task_view={task_view}&task_page={task_page - 1}{task_filter_suffix}"
                if task_page > 1
                else None
            ),
            "next_task_page_url": (
                f"/creator-operations?tab=tasks&task_view={task_view}&task_page={task_page + 1}{task_filter_suffix}"
                if has_next_task_page
                else None
            ),
            "task_artifacts": task_artifacts,
            "task_latest_metrics": task_latest_metrics,
            "payouts": payouts,
            "payout_page": payout_page,
            "previous_payout_page_url": (
                f"/creator-operations?tab=payouts&payout_page={payout_page - 1}"
                if payout_page > 1
                else None
            ),
            "next_payout_page_url": (
                f"/creator-operations?tab=payouts&payout_page={payout_page + 1}"
                if has_next_payout_page
                else None
            ),
            "payout_profiles": payout_profiles,
            "payout_status_labels": {
                "pending": "Ожидает проверки",
                "approved": "Согласовано",
                "paid": "Оплачено",
                "rejected": "Отклонено",
                "cancelled": "Отменено",
            },
            "operation_messages": OPERATION_MESSAGES,
            "queue_health": queue_health,
            "stats": stats,
            "needs": needs,
            "notice": _flash(notice),
            "error": _flash(error),
            "default_start_at": (
                datetime.now(UTC).astimezone(ZoneInfo("Europe/Moscow"))
                + timedelta(hours=1)
            ).strftime("%Y-%m-%dT%H:%M"),
            "default_start_timezone": "Europe/Moscow",
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
    payout_per_post_rub: str = Form("0"),
    start_timezone: str = Form("Europe/Moscow"),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if mode not in {"dry_run", "schedule"}:
        return _redirect("placement", error="invalid_placement_mode")
    try:
        payout_per_post_minor = _rubles_to_minor(payout_per_post_rub)
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
            payout_per_post_minor=payout_per_post_minor,
            start_timezone=start_timezone,
        )
    except CreatorOperationsError as exc:
        return _redirect("placement", error=str(exc))
    return _redirect("placement", notice=f"batch_{batch.id}_{batch.status}")


@router.post("/batches/{batch_id}/promote")
def promote_dry_run_batch(
    batch_id: int,
    request: Request,
    csrf_token: str = Form(...),
    confirm_real_spend: bool = Form(False),
    confirmed_total_credits: int = Form(0),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    preview = db.scalar(
        select(models.MassOperationBatch).where(
            models.MassOperationBatch.id == int(batch_id),
            models.MassOperationBatch.organization_id == user.organization.id,
            models.MassOperationBatch.dry_run.is_(True),
        )
    )
    tab = (
        "generation"
        if preview is not None and preview.operation_type == "generation"
        else "placement"
    )
    try:
        promoted = CreatorOperationsService(db).promote_dry_run_batch(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            batch_id=batch_id,
            confirm_real_spend=confirm_real_spend,
            confirmed_total_credits=confirmed_total_credits,
        )
    except CreatorOperationsError as exc:
        return _redirect(tab, error=str(exc))
    return _redirect(tab, notice=f"batch_{promoted.id}_{promoted.status}")


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


@router.post("/tasks/{task_id}/metrics")
def record_manual_metrics(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    views: int = Form(0),
    clicks: int = Form(0),
    orders: int = Form(0),
    revenue_rub: str = Form("0"),
    allow_correction: bool = Form(False),
    correction_reason: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        metric = CreatorOperationsService(db).record_manual_metrics(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            task_id=task_id,
            views=views,
            clicks=clicks,
            orders=orders,
            revenue_minor=_revenue_to_minor(revenue_rub),
            allow_correction=allow_correction,
            correction_reason=correction_reason,
        )
    except CreatorOperationsError as exc:
        return _redirect("tasks", error=str(exc))
    return _redirect("stats", notice=f"metrics_{metric.id}_saved")


@router.post("/payouts/{payout_id}/decision")
def decide_payout(
    payout_id: int,
    request: Request,
    csrf_token: str = Form(...),
    decision: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        payout = CreatorOperationsService(db).decide_payout(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            payout_id=payout_id,
            decision=decision,
            notes=notes,
        )
    except CreatorOperationsError as exc:
        return _redirect("payouts", error=str(exc))
    return _redirect("payouts", notice=f"payout_{payout.id}_{payout.status}")


@router.post("/payouts/{payout_id}/paid")
def mark_payout_paid(
    payout_id: int,
    request: Request,
    csrf_token: str = Form(...),
    external_payment_reference: str = Form(...),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        payout = CreatorOperationsService(db).mark_payout_paid(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            payout_id=payout_id,
            external_payment_reference=external_payment_reference,
        )
    except CreatorOperationsError as exc:
        return _redirect("payouts", error=str(exc))
    return _redirect("payouts", notice=f"payout_{payout.id}_{payout.status}")


@router.post("/tasks/{task_id}/review")
def review_generated_task(
    task_id: int,
    request: Request,
    csrf_token: str = Form(...),
    expected_media_artifact_id: int = Form(..., ge=1),
    expected_media_artifact_public_id: str = Form(..., min_length=1, max_length=64),
    expected_media_artifact_sha256: str = Form(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
    decision: str = Form(...),
    notes: str = Form(""),
    confirm_video_watched: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        task = CreatorOperationsService(db).review_generated_task(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            task_id=task_id,
            expected_media_artifact_id=expected_media_artifact_id,
            expected_media_artifact_public_id=expected_media_artifact_public_id,
            expected_media_artifact_sha256=expected_media_artifact_sha256,
            decision=decision,
            notes=notes,
            confirm_video_watched=confirm_video_watched,
        )
    except CreatorOperationsError as exc:
        return _redirect("tasks", error=str(exc))
    return _redirect("tasks", notice=f"task_{task.id}_{task.status}")
