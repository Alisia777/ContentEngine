from __future__ import annotations

import os
import hashlib
import re
import calendar
from datetime import UTC, date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app import models
from app.config import get_settings
from app.content_cycles import ContentCycleError, ContentCycleService
from app.customer_billing import (
    CustomerBillingError,
    CustomerBillingService,
    UsageChargeInput,
)
from app.database import SessionLocal, get_db
from app.destination_connectors import (
    OFFICIAL_CONNECTOR_CATALOG,
    ConnectionRegistry,
    DestinationConnectorSyncService,
)
from app.destination_connectors.credential_status import public_settings
from app.destination_connectors.errors import DestinationConnectorError
from app.intelligence.errors import ProviderConfigurationError
from app.interface_productization import (
    FactoryDashboardService,
    InterfaceProductizationError,
    MVPLaunchWizardService,
    MVPWorkspaceService,
    OperationsReadinessService,
)
from app.generation_costs import GenerationCostError, GenerationCostLedgerService
from app.marketplace_listings import MarketplaceListingError, MarketplaceListingService
from app.metrics_intake import OfficialConnectorGateway, PlatformMetricsMatrix
from app.novice_learning_path import NoviceLearningPathError, NoviceLearningPathService
from app.output_acceptance import (
    AcceptanceReviewService,
    FrameExtractor,
    OutputAcceptanceError,
    OutputQualityChecker,
)
from app.product_asset_contract import ProductAssetClassifier
from app.product_asset_contract.reference_requirement_service import product_profile, product_variant_key
from app.product_telemetry import (
    ProductTelemetryService,
    TelemetryIdempotencyConflict,
    TelemetryValidationError,
)
from app.product_ugc_queue import (
    ProductUGCGenerationQueueService,
    ProductUGCGenerationWorker,
    ProductUGCQueueError,
)
from app.publishing import ManualUploadProvider
from app.publishing.errors import PublishingError
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import (
    PublicPilotUser,
    ensure_public_pilot_user,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.public_pilot.local_auth import authenticate_local_user, local_auth_configured
from app.public_pilot.control_room import PublicPilotControlRoomService
from app.public_pilot.gate_matrix import (
    ACTION_LABELS,
    CUSTOMER_BILLING_MANAGE,
    ONE_VIDEO_REAL_RUN,
    MARKETPLACE_LISTING_MANAGE,
    GENERATION_COST_MANAGE,
    METRICS_IMPORT,
    PUBLISHING_APPROVE,
    PublicPilotGateMatrix,
    TRAINING_ATTEMPT,
    VIDEO_APPROVE,
    VIDEO_REJECT,
)
from app.runway_recipes import (
    FORM_PROOF_REFERENCE_OPTIONS,
    ProductImageUpload,
    ProductUGCRecipeRunner,
    ProductUGCRecipeService,
    RunwayRecipeError,
)
from app.routers.authorized_media import (
    authorized_media_url,
    frame_contact_sheet_url,
    frame_image_urls,
    resolve_media_file,
    video_output_url,
)
from app.social_metrics_ingestion import (
    SocialMetricAccessError,
    SocialMetricIngestionService,
    SocialMetricObservation,
    SocialMetricValidationError,
)
from app.ui import templates
from app.visual_evidence import (
    VisualEvidenceSnapshotError,
    VisualEvidenceSnapshotService,
)
from app.wildberries_analytics import (
    WildberriesAnalyticsError,
    WildberriesSellerAnalyticsService,
)

router = APIRouter(tags=["public-pilot"])


def _require_ui_form_csrf(
    request: Request,
    csrf_token: str | None = Form(None),
) -> None:
    """Apply one session-bound CSRF rule to every authenticated HTML form write."""

    require_form_csrf(request, csrf_token)


try:
    BUSINESS_TIMEZONE = ZoneInfo("Europe/Moscow")
except ZoneInfoNotFoundError:
    # Moscow has observed fixed UTC+3 without DST since 2014.  The bundled
    # Windows runtime may omit the IANA tzdata package, so fail safely here.
    BUSINESS_TIMEZONE = timezone(timedelta(hours=3), name="Europe/Moscow")


def _record_factory_event(
    db: Session,
    *,
    event_name: str,
    organization_id: int,
    user_profile_id: int,
    role: str,
    idempotency_key: str,
    factory_run_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    product_id: int | None = None,
    sku: str | None = None,
    video_job_id: int | None = None,
    publishing_task_id: int | None = None,
    properties: dict | None = None,
) -> None:
    """Product telemetry must never interrupt the user's production task."""
    try:
        ProductTelemetryService(db).record_event(
            event_name=event_name,
            organization_id=organization_id,
            user_profile_id=user_profile_id,
            role=role,
            idempotency_key=idempotency_key,
            factory_run_id=factory_run_id,
            entity_type=entity_type,
            entity_id=entity_id,
            product_id=product_id,
            sku=sku,
            video_job_id=video_job_id,
            publishing_task_id=publishing_task_id,
            source="server",
            properties=properties or {},
        )
    except (TelemetryIdempotencyConflict, TelemetryValidationError):
        return
    except SQLAlchemyError:
        db.rollback()
        return


def _recipe_media_items(paths: list[str], *, draft_id: int) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for index, raw_path in enumerate(paths):
        path = resolve_media_file(raw_path)
        if path is None:
            continue
        media_url = authorized_media_url(
            raw_path,
            f"/media/product-ugc-drafts/{draft_id}/outputs/{index}",
        )
        if media_url:
            items.append(
                {
                    "name": path.name,
                    "url": media_url,
                    "size_bytes": path.stat().st_size,
                }
            )
    return items


def _amount_minor(value: str, *, allow_zero: bool = False) -> int:
    try:
        decimal_amount = Decimal(str(value or "").strip().replace(",", "."))
        if not decimal_amount.is_finite() or decimal_amount < 0 or (
            not allow_zero and decimal_amount == 0
        ):
            raise ValueError("invalid_amount")
        amount_minor = int(
            (decimal_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError("invalid_amount") from exc
    if amount_minor > 2_147_483_647:
        raise ValueError("invalid_amount")
    return amount_minor


def _generation_queue_view(
    service: ProductUGCGenerationQueueService,
    job: models.ProductUGCGenerationJob,
    *,
    can_retry_paid_generation: bool = False,
    can_reconcile_quarantine: bool = False,
) -> dict[str, object]:
    summary = service.summary(job)
    status_labels = {
        "queued": "ждёт воркер",
        "leased": "взята в работу",
        "provider_launching": "отправляется провайдеру",
        "provider_processing": "провайдер создаёт ролик",
        "downloading": "скачивается результат",
        "retry_wait": "безопасный повтор запланирован",
        "succeeded": "готово",
        "failed_terminal": "остановлено",
        "quarantined": "карантин",
    }
    ui_status = {
        "succeeded": "ready",
        "failed_terminal": "needs_review",
        "quarantined": "blocked",
        "queued": "in_progress",
        "leased": "in_progress",
        "provider_launching": "in_progress",
        "provider_processing": "in_progress",
        "downloading": "in_progress",
        "retry_wait": "needs_attention",
    }.get(job.status, "needs_review")
    reason = job.terminal_reason or job.last_error_message
    if not reason:
        if job.status == "retry_wait":
            reason = "Временная ошибка; задача продолжится без второго paid submit."
        elif job.status == "quarantined":
            reason = "Исход отправки провайдеру неизвестен."
        else:
            reason = "Остановок нет."
    provider_terminal = str(job.provider_status or "").upper() in {
        "FAILED",
        "FAILURE",
        "CANCELLED",
        "CANCELED",
        "ERROR",
    }
    return {
        **summary,
        "status_label": status_labels.get(job.status, job.status),
        "ui_status": ui_status,
        "reason_label": str(reason)[:400],
        "manual_retry_allowed": bool(
            can_retry_paid_generation
            and
            job.status == "failed_terminal"
            and not provider_terminal
            and not (job.spend_guarded_at and not job.provider_task_id)
        ),
        "quarantine_reconciliation_allowed": bool(
            can_reconcile_quarantine
            and summary["reconciliation_required"]
        ),
    }


def _visual_evidence_view(report) -> dict[str, object]:
    blocker_labels = {
        "visual_evidence_frames_missing": "Нет извлечённых кадров.",
        "visual_evidence_frame_count_below_minimum": "Нужно минимум два настоящих кадра.",
        "visual_evidence_frame_not_decodable": "Хотя бы один кадр не декодируется как изображение.",
        "visual_evidence_resolution_below_minimum": "Разрешение кадра ниже 720×1280.",
        "visual_evidence_duplicate_frames": "Слишком много визуально одинаковых кадров.",
        "visual_evidence_freeze_detected": "Обнаружена длинная заморозка изображения.",
        "ocr_tool_unavailable": "Обязательный локальный OCR недоступен.",
        "ocr_reference_evidence_missing": "Для OCR не задан доверенный текст упаковки.",
        "ocr_reference_extraction_failed": "Не удалось прочитать локальный эталон упаковки.",
        "ocr_reference_evidence_too_large": "Для OCR задано слишком много обязательных надписей.",
        "ocr_frame_extraction_failed": "OCR не смог обработать декодируемые кадры.",
        "ocr_text_not_detected": "OCR не смог прочитать текст на кадрах.",
        "ocr_reference_tokens_missing_from_frames": "На кадрах не найдены все обязательные надписи упаковки.",
    }
    ocr_labels = {
        "not_required": "не требуется",
        "passed": "надписи совпали",
        "blocked": "нужна проверка",
    }
    return {
        "status": report.status,
        "frame_count": report.frame_count,
        "decoded_frame_count": report.decoded_frame_count,
        "unique_percent": (
            round(float(report.unique_frame_ratio) * 100)
            if report.unique_frame_ratio is not None
            else None
        ),
        "freeze_percent": (
            round(float(report.freeze_run_ratio) * 100)
            if report.freeze_run_ratio is not None
            else None
        ),
        "minimum_short_side_observed_px": report.minimum_short_side_observed_px,
        "minimum_long_side_observed_px": report.minimum_long_side_observed_px,
        "ocr_label": ocr_labels.get(report.ocr.status, report.ocr.status),
        "missing_tokens": list(report.ocr.missing_tokens),
        "blockers": list(report.blockers),
        "blocker_labels": [
            blocker_labels.get(code, f"Проверка не пройдена: {code}")
            for code in report.blockers
        ],
    }


def _billing_error_label(exc: Exception) -> str:
    message = str(exc).lower()
    if "integrity" in message:
        return "Финансовая история не прошла проверку целостности; новые записи заблокированы."
    if "finance role" in message or "owner or admin" in message:
        return "Изменять биллинг могут только владелец или администратор."
    if "currency" in message:
        return "Валюта счёта, тарифа, расхода и инвойса должна совпадать."
    if "actual generation cost" in message or "confirmed actual" in message:
        return "Инвойс можно связать только с подтверждённой фактической стоимостью реальной генерации."
    if "content cycle" in message or "video job" in message:
        return "Не удалось подтвердить точную связь расхода с контент-циклом этой организации."
    if "outstanding balance" in message or "overpayment" in message or "exceed" in message:
        return "Сумма превышает непогашенный остаток инвойса."
    if "idempotency" in message or "already" in message or "conflict" in message:
        return "Такая неизменяемая запись уже существует или конфликтует с историей."
    return "Проверьте обязательные поля, период, статус тарифа и точную связь с подтверждённым расходом."


def _billing_period_end(start: datetime, interval: str) -> datetime:
    if interval == "year":
        target_year, target_month = start.year + 1, start.month
    elif interval == "month":
        target_year = start.year + (1 if start.month == 12 else 0)
        target_month = 1 if start.month == 12 else start.month + 1
    else:
        raise ValueError("invalid_billing_interval")
    target_day = min(start.day, calendar.monthrange(target_year, target_month)[1])
    return start.replace(year=target_year, month=target_month, day=target_day)


def _business_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()


def _business_time_utc(value: date, at: datetime_time) -> datetime:
    return datetime.combine(value, at, tzinfo=BUSINESS_TIMEZONE).astimezone(UTC)


def _require_customer_billing_integrity(
    db: Session,
    *,
    organization_id: int,
    billing_account_id: int,
) -> None:
    service = CustomerBillingService(db)
    invoice_ids = db.scalars(
        select(models.CustomerInvoice.id).where(
            models.CustomerInvoice.organization_id == organization_id,
            models.CustomerInvoice.billing_account_id == billing_account_id,
        )
    ).all()
    for invoice_id in invoice_ids:
        try:
            service.invoice_totals(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                invoice_id=invoice_id,
            )
        except CustomerBillingError as exc:
            raise ValueError("customer_billing_integrity_blocked") from exc


def _recipe_run_readiness(
    db: Session,
    user: PublicPilotUser,
    draft: models.ProductUGCRecipeDraft,
) -> dict[str, object]:
    settings = get_settings()
    role_decision = PublicPilotAccessService(db).evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=ONE_VIDEO_REAL_RUN,
        spend_gate_confirmed=True,
    )
    rows = [
        {
            "label": "ТЗ прошло Product UGC gates",
            "ready": draft.status == "ready_for_paid_preflight" and not draft.blockers_json,
            "detail": draft.status,
        },
        {
            "label": "Роль может запускать paid task",
            "ready": role_decision.allowed,
            "detail": user.role if role_decision.allowed else role_decision.reason,
        },
        {
            "label": "Real generation mode",
            "ready": settings.generation_mode == "real",
            "detail": f"QVF_GENERATION_MODE={settings.generation_mode}",
        },
        {
            "label": "Spend gate включён",
            "ready": settings.allow_real_spend,
            "detail": "QVF_ALLOW_REAL_SPEND=true" if settings.allow_real_spend else "QVF_ALLOW_REAL_SPEND не включён",
        },
        {
            "label": "Runway API key настроен",
            "ready": bool(os.getenv("RUNWAYML_API_SECRET")),
            "detail": "ключ найден" if os.getenv("RUNWAYML_API_SECRET") else "RUNWAYML_API_SECRET отсутствует",
        },
    ]
    return {
        "ready": all(bool(row["ready"]) for row in rows),
        "gates": rows,
        "role": user.role,
    }


def _run_product_ugc_background(
    generation_job_id: int,
    organization_id: int,
    user_profile_id: int,
    role: str,
) -> None:
    with SessionLocal() as db:
        ProductUGCGenerationWorker(db).process_job(generation_job_id)


@router.get("/login", response_class=HTMLResponse)
def public_login(request: Request, error: str | None = None) -> HTMLResponse:
    error_messages = {
        "invalid_credentials": "Проверьте логин и пароль.",
        "local_auth_not_configured": "Вход ещё не настроен. Обратитесь к владельцу пространства.",
        "password_required": "Введите пароль.",
        "oauth_exchange_not_configured_locally": "Внешний вход ещё не подключён.",
    }
    return templates.TemplateResponse(
        "public_login.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Вход",
            "error": error,
            "error_message": error_messages.get(error, "Не удалось войти. Повторите попытку.") if error else None,
        },
    )


@router.post("/login")
def public_login_submit(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    if not settings.auth_required:
        return RedirectResponse("/control-room", status_code=303)
    if local_auth_configured():
        token = authenticate_local_user(email, password)
        if not token:
            return RedirectResponse("/login?error=invalid_credentials", status_code=303)
        normalized_email = str(settings.local_auth_email).strip().casefold()
        ensure_public_pilot_user(
            db,
            email=normalized_email,
            display_name=None,
            role="owner",
            supabase_user_id=f"local:{normalized_email}",
            mark_login=True,
        )
        response = RedirectResponse("/control-room", status_code=303)
        response.set_cookie(
            settings.session_cookie_name,
            token,
            max_age=settings.local_session_ttl_seconds,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            path="/",
        )
        return response
    if not settings.supabase_url:
        return RedirectResponse("/login?error=local_auth_not_configured", status_code=303)
    if not password:
        return RedirectResponse("/login?error=password_required", status_code=303)
    # Real Supabase password exchange is intentionally not performed in tests/local acceptance.
    return RedirectResponse("/login?error=oauth_exchange_not_configured_locally", status_code=303)


@router.post("/logout", dependencies=[Depends(_require_ui_form_csrf)])
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
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Главная",
            "form_csrf_token": form_csrf_token(request),
            **context,
        },
    )


@router.get("/workbench", response_class=HTMLResponse)
def mvp_workbench(
    request: Request,
    tab: str = "product",
    role: str | None = None,
    module: str | None = None,
    training_result: str | None = None,
    training_score: int | None = None,
    wb_error: str | None = None,
    wb_notice: str | None = None,
    wb_analytics_error: str | None = None,
    wb_analytics_notice: str | None = None,
    quality_error: str | None = None,
    quality_notice: str | None = None,
    funnel_error: str | None = None,
    funnel_notice: str | None = None,
    metrics_error: str | None = None,
    metrics_notice: str | None = None,
    connector_error: str | None = None,
    connector_notice: str | None = None,
    cost_error: str | None = None,
    cost_notice: str | None = None,
    queue_error: str | None = None,
    queue_notice: str | None = None,
    billing_error: str | None = None,
    billing_notice: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    selected_role = role or (
        user.role if user.role in {"owner", "admin", "reviewer", "operator"} else "creator_publisher"
    )
    service = MVPWorkspaceService(db)
    snapshot = service.output(
        service.build(
            role=selected_role,
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
        )
    )
    allowed_tabs = {item.key for item in snapshot.module_links}
    tab_aliases = {
        "creative": "video",
        "publishing": "funnel",
        "metrics": "analytics",
        "access": "product",
    }
    requested_tab = tab_aliases.get(tab, tab)
    selected_tab = requested_tab if requested_tab in allowed_tabs else "product"
    access_service = PublicPilotAccessService(db)
    access_service.ensure_training_catalog()
    learning_service = NoviceLearningPathService(db)
    learning_path = learning_service.build(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
    )
    training_modules = db.scalars(
        select(models.TrainingModule)
        .where(models.TrainingModule.is_active.is_(True))
        .order_by(models.TrainingModule.order_index, models.TrainingModule.id)
    ).all()
    preferred_module_code = module or learning_path.next_move.module_code
    selected_training_module = next(
        (item for item in training_modules if item.code == preferred_module_code),
        training_modules[0] if training_modules else None,
    )
    verified_certifications = learning_service.verified_certification_codes(
        user_profile_id=user.profile.id
    )
    wb_products = db.scalars(
        select(models.Product)
        .where(models.Product.organization_id == user.organization.id)
        .order_by(models.Product.title, models.Product.id)
    ).all()
    wb_listings = MarketplaceListingService(db).list_listings(
        organization_id=user.organization.id,
        include_inactive=True,
    )
    wb_aliases = db.scalars(
        select(models.ListingAlias)
        .where(models.ListingAlias.organization_id == user.organization.id)
        .order_by(models.ListingAlias.created_at.desc(), models.ListingAlias.id.desc())
    ).all()
    wildberries_analytics_readiness = WildberriesSellerAnalyticsService(db).readiness(
        organization_id=user.organization.id
    )
    verified_wb_seller_refs = sorted(
        {
            str(listing.seller_account_ref)
            for listing in wb_listings
            if listing.status == "verified"
            and listing.nm_id
            and listing.seller_account_ref
        }
    )
    wb_manage_decision = access_service.evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=MARKETPLACE_LISTING_MANAGE,
    )
    cost_manage_decision = access_service.evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=GENERATION_COST_MANAGE,
    )
    billing_manage_decision = access_service.evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=CUSTOMER_BILLING_MANAGE,
    )
    metrics_manage_decision = access_service.evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=METRICS_IMPORT,
    )
    generation_retry_decision = access_service.evaluate_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=ONE_VIDEO_REAL_RUN,
        spend_gate_confirmed=True,
    )
    generation_queue_service = ProductUGCGenerationQueueService(db)
    generation_queue_health = generation_queue_service.operational_health(
        organization_id=user.organization.id,
    )
    generation_jobs = db.scalars(
        select(models.ProductUGCGenerationJob)
        .where(models.ProductUGCGenerationJob.organization_id == user.organization.id)
        .order_by(models.ProductUGCGenerationJob.created_at.desc(), models.ProductUGCGenerationJob.id.desc())
        .limit(50)
    ).all()
    generation_queue_views = [
        _generation_queue_view(
            generation_queue_service,
            job,
            can_retry_paid_generation=generation_retry_decision.allowed,
            can_reconcile_quarantine=(
                generation_retry_decision.allowed and user.role in {"owner", "admin"}
            ),
        )
        for job in generation_jobs
    ]
    content_cycles = db.scalars(
        select(models.ContentCycle)
        .where(models.ContentCycle.organization_id == user.organization.id)
        .order_by(models.ContentCycle.updated_at.desc(), models.ContentCycle.id.desc())
        .limit(50)
    ).all()
    content_cycle_views = []
    frame_service = FrameExtractor(db)
    evidence_snapshot_service = VisualEvidenceSnapshotService(db)
    for cycle in content_cycles:
        frame_result = frame_service.latest_for_video_job(cycle.video_job_id)
        visual_evidence = None
        if selected_tab == "video-quality" and frame_result is not None:
            evidence_snapshot = evidence_snapshot_service.latest_for_frame_result(
                frame_result.id
            )
            try:
                if evidence_snapshot is not None:
                    evidence_snapshot_service.verify_current(evidence_snapshot)
                    visual_evidence = _visual_evidence_view(
                        evidence_snapshot_service.report(evidence_snapshot)
                    )
            except (VisualEvidenceSnapshotError, ValueError):
                evidence_snapshot = None
            if evidence_snapshot is None:
                visual_evidence = {
                    "status": "blocked",
                    "frame_count": len(frame_result.frame_paths_json or []),
                    "decoded_frame_count": 0,
                    "unique_percent": None,
                    "freeze_percent": None,
                    "minimum_short_side_observed_px": None,
                    "minimum_long_side_observed_px": None,
                    "ocr_label": "ещё не зафиксирован",
                    "missing_tokens": [],
                    "blockers": ["visual_evidence_snapshot_missing"],
                    "blocker_labels": [
                        "Для этих кадров ещё нет неизменяемого CV/OCR-снимка; повторите извлечение."
                    ],
                }
        content_cycle_views.append(
            {
                "cycle": cycle,
                "video_url": video_output_url(cycle.video_job),
                "frame_status": frame_result.status if frame_result else "not_started",
                "contact_sheet_url": frame_contact_sheet_url(frame_result) if frame_result else None,
                "frame_urls": frame_image_urls(frame_result) if frame_result else [],
                "frame_warnings": list(frame_result.warnings_json or []) if frame_result else [],
                "visual_evidence": visual_evidence,
            }
        )
    publishing_destinations = db.scalars(
        select(models.PublishingDestination)
        .where(models.PublishingDestination.organization_id == user.organization.id)
        .order_by(models.PublishingDestination.name, models.PublishingDestination.id)
    ).all()
    social_metric_service = SocialMetricIngestionService(db)
    social_metric_rows = social_metric_service.list_metrics(
        organization_id=user.organization.id,
        limit=50,
    )
    social_metric_quarantine = social_metric_service.list_quarantine(
        organization_id=user.organization.id,
        limit=20,
    )
    published_content_cycles = [
        cycle for cycle in content_cycles if cycle.publishing_task is not None and cycle.publishing_task.final_url
    ]
    connector_gateway = OfficialConnectorGateway(db)
    official_connector_views: list[dict[str, object]] = []
    for destination in publishing_destinations:
        readiness = connector_gateway.readiness(
            destination.id,
            organization_id=user.organization.id,
        )
        official_connector_views.append(
            {
                **readiness,
                "destination_name": destination.name,
                "destination_platform": destination.platform,
                "status_label": {
                    "ready": "официальный API проверен",
                    "needs_verification": "нужно проверить OAuth",
                    "needs_connection": "нужно настроить",
                    "manual_or_csv_only": "только ручной/CSV импорт",
                    "blocked": "заблокировано безопасно",
                }.get(str(readiness.get("status")), str(readiness.get("status"))),
            }
        )
    official_connector_setup_views: list[dict[str, object]] = []
    target_patterns = {
        "youtube": "[A-Za-z0-9_-]{6,64}",
        "tiktok": "[0-9]{6,32}",
        "instagram": "[0-9]{6,40}",
    }
    credential_defaults = {
        "youtube": "env:YOUTUBE_ANALYTICS_ACCESS_TOKEN",
        "tiktok": "env:TIKTOK_OFFICIAL_ACCESS_TOKEN",
        "instagram": "env:INSTAGRAM_OFFICIAL_ACCESS_TOKEN",
    }
    for definition in OFFICIAL_CONNECTOR_CATALOG.values():
        matching_cycles = [
            cycle
            for cycle in published_content_cycles
            if cycle.destination is not None
            and PlatformMetricsMatrix.normalize_platform(cycle.destination.platform)
            == definition.platform
        ]
        official_connector_setup_views.append(
            {
                **definition.public_metadata(),
                "published_cycles": matching_cycles,
                "target_pattern": target_patterns.get(definition.platform, ".{3,80}"),
                "credential_default": credential_defaults.get(
                    definition.platform,
                    f"env:{definition.platform.upper()}_METRICS_ACCESS_TOKEN",
                ),
            }
        )
    generation_cost_entries = db.scalars(
        select(models.GenerationCostLedgerEntry)
        .where(models.GenerationCostLedgerEntry.organization_id == user.organization.id)
        .order_by(models.GenerationCostLedgerEntry.occurred_at.desc(), models.GenerationCostLedgerEntry.id.desc())
    ).all()
    customer_billing_service = CustomerBillingService(db)
    customer_billing_account = db.scalar(
        select(models.CustomerBillingAccount).where(
            models.CustomerBillingAccount.organization_id == user.organization.id
        )
    )
    customer_billing_subscription = None
    customer_invoice_views: list[dict[str, object]] = []
    eligible_billing_usage: list[dict[str, object]] = []
    customer_billing_balance_minor = 0
    customer_billing_integrity_errors = 0
    if customer_billing_account is not None:
        customer_billing_subscription = db.scalar(
            select(models.CustomerBillingSubscriptionState)
            .where(
                models.CustomerBillingSubscriptionState.organization_id == user.organization.id,
                models.CustomerBillingSubscriptionState.billing_account_id == customer_billing_account.id,
            )
            .order_by(
                models.CustomerBillingSubscriptionState.version.desc(),
                models.CustomerBillingSubscriptionState.id.desc(),
            )
        )
        invoices = db.scalars(
            select(models.CustomerInvoice)
            .where(
                models.CustomerInvoice.organization_id == user.organization.id,
                models.CustomerInvoice.billing_account_id == customer_billing_account.id,
            )
            .order_by(models.CustomerInvoice.issued_at.desc(), models.CustomerInvoice.id.desc())
        ).all()
        for invoice_index, invoice in enumerate(invoices):
            try:
                totals = customer_billing_service.invoice_totals(
                    organization_id=user.organization.id,
                    billing_account_id=customer_billing_account.id,
                    invoice_id=invoice.id,
                )
            except CustomerBillingError:
                customer_billing_integrity_errors += 1
                if invoice_index < 50:
                    customer_invoice_views.append(
                        {
                            "invoice": invoice,
                            "totals": {
                                "status": "integrity_error",
                                "currency": invoice.currency,
                                "balance_minor": None,
                            },
                            "status_label": "ошибка целостности",
                            "total_major": "неизвестно",
                            "paid_major": "неизвестно",
                            "balance_major": "неизвестно",
                            "payment_allowed": False,
                        }
                    )
                continue
            customer_billing_balance_minor += totals.balance_minor
            if invoice_index >= 50:
                continue
            ledger_entries = db.scalars(
                select(models.CustomerBillingLedgerEntry)
                .where(
                    models.CustomerBillingLedgerEntry.organization_id
                    == user.organization.id,
                    models.CustomerBillingLedgerEntry.billing_account_id
                    == customer_billing_account.id,
                    models.CustomerBillingLedgerEntry.invoice_id == invoice.id,
                )
                .order_by(models.CustomerBillingLedgerEntry.id)
            ).all()
            credited_charge_ids = {
                entry.related_entry_id
                for entry in ledger_entries
                if entry.entry_kind == "credit" and entry.related_entry_id is not None
            }
            creditable_charges = [
                {
                    "id": entry.id,
                    "description": entry.description,
                    "amount_major": round(entry.amount_minor / 100, 2),
                    "max_credit_major": round(
                        min(entry.amount_minor, totals.balance_minor) / 100,
                        2,
                    ),
                }
                for entry in ledger_entries
                if entry.entry_kind == "charge"
                and entry.id not in credited_charge_ids
                and totals.balance_minor > 0
            ]
            customer_invoice_views.append(
                {
                    "invoice": invoice,
                    "totals": {
                        "status": totals.status,
                        "currency": totals.currency,
                        "balance_minor": totals.balance_minor,
                    },
                    "status_label": {
                        "paid": "оплачен",
                        "partially_paid": "оплачен частично",
                        "issued": "ожидает оплаты",
                        "open": "ожидает оплаты",
                        "credited": "закрыт кредитом",
                    }.get(totals.status, totals.status),
                    "total_major": round(totals.total_minor / 100, 2),
                    "paid_major": round(totals.paid_minor / 100, 2),
                    "balance_major": round(totals.balance_minor / 100, 2),
                    "payment_allowed": totals.balance_minor > 0,
                    "creditable_charges": creditable_charges,
                    "ledger_entries": [
                        {
                            "id": entry.id,
                            "entry_kind": entry.entry_kind,
                            "source": entry.source,
                            "amount_major": round(entry.amount_minor / 100, 2),
                            "description": entry.description,
                            "related_entry_id": entry.related_entry_id,
                            "occurred_at": entry.occurred_at,
                        }
                        for entry in ledger_entries
                    ],
                }
            )
        billed_cost_ids = select(models.CustomerBillingLedgerEntry.generation_cost_ledger_entry_id).where(
            models.CustomerBillingLedgerEntry.organization_id == user.organization.id,
            models.CustomerBillingLedgerEntry.generation_cost_ledger_entry_id.is_not(None),
        )
        cycle_by_video_job = {cycle.video_job_id: cycle for cycle in content_cycles}
        successor_cost = aliased(models.GenerationCostLedgerEntry)
        eligible_cost_entries = db.scalars(
            select(models.GenerationCostLedgerEntry)
            .where(
                models.GenerationCostLedgerEntry.organization_id == user.organization.id,
                models.GenerationCostLedgerEntry.entry_kind == "actual",
                models.GenerationCostLedgerEntry.status == "confirmed",
                models.GenerationCostLedgerEntry.currency == customer_billing_account.currency,
                ~models.GenerationCostLedgerEntry.id.in_(billed_cost_ids),
                ~exists(
                    select(successor_cost.id).where(
                        successor_cost.supersedes_entry_id
                        == models.GenerationCostLedgerEntry.id
                    )
                ),
            )
            .order_by(models.GenerationCostLedgerEntry.recorded_at.desc())
            .limit(50)
        ).all()
        for cost_entry in eligible_cost_entries:
            cycle = cycle_by_video_job.get(cost_entry.video_job_id)
            if cycle is None:
                continue
            eligible_billing_usage.append(
                {
                    "cost_entry_id": cost_entry.id,
                    "content_cycle_id": cycle.id,
                    "sku": cycle.product.sku,
                    "cost_major": round(cost_entry.amount_minor / 100, 2),
                    "currency": cost_entry.currency,
                }
            )
    business_today = _business_today()
    tomorrow = business_today + timedelta(days=1)
    billing_due_date = business_today + timedelta(days=14)
    operations_readiness = OperationsReadinessService(db).snapshot(
        organization_id=user.organization.id
    )
    return templates.TemplateResponse(
        "public_workbench.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Рабочая область",
            "user": user,
            "role": selected_role,
            "workspace": snapshot,
            "selected_tab": selected_tab,
            "learning_path": learning_path,
            "training_modules": training_modules,
            "selected_training_module": selected_training_module,
            "verified_certifications": verified_certifications,
            "training_result": training_result if training_result in {"passed", "failed"} else None,
            "training_score": training_score,
            "wb_products": wb_products,
            "wb_listings": wb_listings,
            "wb_aliases": wb_aliases,
            "can_manage_wb": wb_manage_decision.allowed,
            "wb_error": wb_error,
            "wb_notice": wb_notice,
            "wb_analytics_error": wb_analytics_error,
            "wb_analytics_notice": wb_analytics_notice,
            "wildberries_analytics_readiness": wildberries_analytics_readiness,
            "verified_wb_seller_refs": verified_wb_seller_refs,
            "content_cycles": content_cycles,
            "content_cycle_views": content_cycle_views,
            "publishing_destinations": publishing_destinations,
            "quality_error": quality_error,
            "quality_notice": quality_notice,
            "funnel_error": funnel_error,
            "funnel_notice": funnel_notice,
            "social_metric_rows": social_metric_rows,
            "social_metric_quarantine": social_metric_quarantine,
            "published_content_cycles": published_content_cycles,
            "metrics_error": metrics_error,
            "metrics_notice": metrics_notice,
            "connector_error": connector_error,
            "connector_notice": connector_notice,
            "official_connector_views": official_connector_views,
            "official_connector_setup_views": official_connector_setup_views,
            "can_manage_connectors": metrics_manage_decision.allowed,
            "today": business_today.isoformat(),
            "cost_error": cost_error,
            "cost_notice": cost_notice,
            "generation_cost_entries": generation_cost_entries,
            "can_manage_costs": cost_manage_decision.allowed,
            "generation_queue_views": generation_queue_views,
            "generation_queue_health": generation_queue_health,
            "queue_error": queue_error,
            "queue_notice": queue_notice,
            "customer_billing_account": customer_billing_account,
            "customer_billing_subscription": customer_billing_subscription,
            "customer_invoice_views": customer_invoice_views,
            "eligible_billing_usage": eligible_billing_usage,
            "customer_billing_balance_major": (
                None
                if customer_billing_integrity_errors
                else round(customer_billing_balance_minor / 100, 2)
            ),
            "customer_billing_integrity_errors": customer_billing_integrity_errors,
            "can_manage_billing": billing_manage_decision.allowed,
            "billing_error": billing_error,
            "billing_notice": billing_notice,
            "tomorrow": tomorrow.isoformat(),
            "billing_due_date": billing_due_date.isoformat(),
            "operations_readiness": operations_readiness,
            "operations_cards": {
                str(card["key"]): card for card in operations_readiness["cards"]
            },
            "form_csrf_token": form_csrf_token(request),
        },
    )


@router.get("/api/factory-dashboard")
def factory_dashboard_snapshot(
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> dict[str, object]:
    factory = FactoryDashboardService(db).snapshot(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
    )
    learning = NoviceLearningPathService(db).build(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
    )
    cycles = db.scalars(
        select(models.ContentCycle)
        .where(models.ContentCycle.organization_id == user.organization.id)
        .order_by(models.ContentCycle.id.desc())
        .limit(50)
    ).all()
    quarantine_count = int(
        db.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(
                models.AuditLog.organization_id == user.organization.id,
                models.AuditLog.action == "social_metric_quarantined",
                models.AuditLog.status == "blocked",
            )
        )
        or 0
    )
    queue_service = ProductUGCGenerationQueueService(db)
    queue_jobs = db.scalars(
        select(models.ProductUGCGenerationJob)
        .where(models.ProductUGCGenerationJob.organization_id == user.organization.id)
        .order_by(models.ProductUGCGenerationJob.created_at.desc(), models.ProductUGCGenerationJob.id.desc())
        .limit(50)
    ).all()
    generation_queue = [queue_service.summary(job) for job in queue_jobs]
    generation_queue_operations = queue_service.operational_health(
        organization_id=user.organization.id,
    )
    quality_evidence: list[dict[str, object]] = []
    frame_service = FrameExtractor(db)
    evidence_snapshot_service = VisualEvidenceSnapshotService(db)
    for cycle in cycles[:20]:
        frame_result = frame_service.latest_for_video_job(cycle.video_job_id)
        secure_media = {
            "video_url": video_output_url(cycle.video_job),
            "contact_sheet_url": (
                frame_contact_sheet_url(frame_result) if frame_result else None
            ),
            "frame_urls": frame_image_urls(frame_result) if frame_result else [],
        }
        if frame_result is None:
            quality_evidence.append(
                {
                    "content_cycle_id": cycle.id,
                    "video_job_id": cycle.video_job_id,
                    **secure_media,
                    "status": "blocked",
                    "frame_count": 0,
                    "decoded_frame_count": 0,
                    "unique_percent": None,
                    "freeze_percent": None,
                    "minimum_short_side_observed_px": None,
                    "minimum_long_side_observed_px": None,
                    "ocr_label": "не начат",
                    "missing_tokens": [],
                    "blockers": ["visual_evidence_frames_missing"],
                    "blocker_labels": ["Нет извлечённых кадров."],
                }
            )
            continue
        snapshot = evidence_snapshot_service.latest_for_frame_result(frame_result.id)
        if snapshot is None:
            quality_evidence.append(
                {
                    "content_cycle_id": cycle.id,
                    "video_job_id": cycle.video_job_id,
                    **secure_media,
                    "status": "blocked",
                    "frame_count": len(frame_result.frame_paths_json or []),
                    "decoded_frame_count": 0,
                    "unique_percent": None,
                    "freeze_percent": None,
                    "minimum_short_side_observed_px": None,
                    "minimum_long_side_observed_px": None,
                    "ocr_label": "не зафиксирован",
                    "missing_tokens": [],
                    "blockers": ["visual_evidence_snapshot_missing"],
                    "blocker_labels": ["Нет неизменяемого CV/OCR-снимка для последнего извлечения."],
                }
            )
            continue
        try:
            evidence_snapshot_service.verify_current(snapshot)
            evidence_view = _visual_evidence_view(
                evidence_snapshot_service.report(snapshot)
            )
        except (VisualEvidenceSnapshotError, ValueError):
            evidence_view = {
                "status": "blocked",
                "frame_count": len(frame_result.frame_paths_json or []),
                "decoded_frame_count": 0,
                "unique_percent": None,
                "freeze_percent": None,
                "minimum_short_side_observed_px": None,
                "minimum_long_side_observed_px": None,
                "ocr_label": "повреждён",
                "missing_tokens": [],
                "blockers": ["visual_evidence_snapshot_invalid"],
                "blocker_labels": ["Сохранённый CV/OCR-снимок не прошёл проверку схемы."],
            }
        quality_evidence.append(
            {
                "content_cycle_id": cycle.id,
                "video_job_id": cycle.video_job_id,
                **secure_media,
                **evidence_view,
            }
        )
    connector_gateway = OfficialConnectorGateway(db)
    owned_destinations = db.scalars(
        select(models.PublishingDestination)
        .where(models.PublishingDestination.organization_id == user.organization.id)
        .order_by(models.PublishingDestination.id)
    ).all()
    official_connectors = [
        connector_gateway.readiness(
            destination.id,
            organization_id=user.organization.id,
        )
        for destination in owned_destinations
    ]
    verified_official_connectors = sum(
        1 for item in official_connectors if bool(item.get("ready"))
    )
    operations_readiness = OperationsReadinessService(db).snapshot(
        organization_id=user.organization.id
    )
    return {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "organization": {"id": user.organization.id, "name": user.organization.name},
        "north_star": factory["north_star"],
        "metrics": factory["metrics"],
        "journey_funnel": factory["journey_funnel"],
        "generation_costs": factory["generation_costs"],
        "customer_billing": factory["customer_billing"],
        "wildberries_seller_analytics": factory["wildberries_seller_analytics"],
        "generation_queue": generation_queue,
        "generation_queue_operations": generation_queue_operations,
        "quality_evidence": quality_evidence,
        "official_connectors": official_connectors,
        "operations_readiness": operations_readiness,
        "modules": [
            {
                "number": item["number"],
                "key": item["key"],
                "label": item["label"],
                "status": item["status"],
                "status_label": item["status_label"],
                "metric_value": item["metric_value"],
                "metric_label": item["metric_label"],
            }
            for item in factory["modules"]
        ],
        "learning": learning.model_dump(mode="json"),
        "content_cycles": [
            {
                "id": cycle.id,
                "product_id": cycle.product_id,
                "sku": cycle.product.sku,
                "status": cycle.status,
                "video_job_id": cycle.video_job_id,
                "output_acceptance_id": cycle.output_acceptance_id,
                "publishing_task_id": cycle.publishing_task_id,
                "tracking_link_id": cycle.tracking_link_id,
                "has_final_url": bool(cycle.publishing_task and cycle.publishing_task.final_url),
            }
            for cycle in cycles
        ],
        "data_quality": {
            "social_metric_quarantine": quarantine_count,
            "generation_queue_quarantine": int(factory["metrics"]["generation_queue_quarantined"]),
            "visual_evidence_blocked": sum(
                1 for item in quality_evidence if item["status"] == "blocked"
            ),
            "legacy_global_workspaces_enabled": False,
            "automatic_social_connectors_verified": verified_official_connectors,
        },
    }


def _wb_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&wb_notice={quote(notice)}" if notice else f"&wb_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=wb{suffix}", status_code=303)


def _wb_analytics_redirect(
    *, notice: str | None = None, error: str | None = None
) -> RedirectResponse:
    suffix = (
        f"&wb_analytics_notice={quote(notice)}"
        if notice
        else f"&wb_analytics_error={quote(error or 'unknown')}"
    )
    return RedirectResponse(f"/workbench?tab=wb{suffix}", status_code=303)


@router.post(
    "/workbench/wb-analytics/setup",
    dependencies=[Depends(_require_ui_form_csrf)],
)
def setup_wildberries_analytics_from_workbench(
    request: Request,
    seller_account_ref: str = Form(...),
    credential_ref: str = Form(...),
    confirm_secret_reference_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_secret_reference_only:
        return _wb_analytics_redirect(error="secret_reference_confirmation_required")
    try:
        WildberriesSellerAnalyticsService(db).configure_connection(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            seller_account_ref=seller_account_ref,
            credential_ref=credential_ref,
        )
    except WildberriesAnalyticsError as exc:
        return _wb_analytics_redirect(error=str(exc))
    return _wb_analytics_redirect(notice="connection_configured")


@router.post(
    "/workbench/wb-analytics/{connection_id}/sync",
    dependencies=[Depends(_require_ui_form_csrf)],
)
def sync_wildberries_analytics_from_workbench(
    connection_id: int,
    request: Request,
    period_start: str = Form(...),
    period_end: str = Form(...),
    confirm_official_api_call: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_official_api_call:
        return _wb_analytics_redirect(error="official_api_confirmation_required")
    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        observed_at = datetime.now(UTC)
        WildberriesSellerAnalyticsService(db).sync(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            connection_id=connection_id,
            period_start=start,
            period_end=end,
            idempotency_key=(
                f"novice-ui-wb:{connection_id}:{start.isoformat()}:"
                f"{end.isoformat()}:{observed_at.isoformat(timespec='minutes')}"
            ),
        )
    except (WildberriesAnalyticsError, ValueError) as exc:
        return _wb_analytics_redirect(error=str(exc))
    return _wb_analytics_redirect(notice="sync_completed")


def _require_wb_manage(db: Session, user: PublicPilotUser, *, operation: str, payload: dict) -> None:
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=MARKETPLACE_LISTING_MANAGE,
        payload={"operation": operation, **payload},
    )


@router.post("/workbench/wb/listings/create", dependencies=[Depends(_require_ui_form_csrf)])
def create_wb_listing_from_workbench(
    product_id: int = Form(...),
    seller_account_ref: str = Form(...),
    nm_id: str = Form(""),
    vendor_code: str = Form(""),
    barcode: str = Form(""),
    listing_url: str = Form(""),
    confirm_owned_card: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    _require_wb_manage(db, user, operation="create_listing", payload={"product_id": product_id})
    if not confirm_owned_card:
        return _wb_redirect(error="ownership_confirmation_required")
    try:
        MarketplaceListingService(db).create_listing(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            product_id=product_id,
            seller_account_ref=seller_account_ref,
            nm_id=nm_id or None,
            vendor_code=vendor_code or None,
            barcode=barcode or None,
            listing_url=listing_url or None,
        )
    except MarketplaceListingError as exc:
        return _wb_redirect(error=exc.code)
    return _wb_redirect(notice="listing_created")


@router.post("/workbench/wb/listings/{listing_id}/verify", dependencies=[Depends(_require_ui_form_csrf)])
def verify_wb_listing_from_workbench(
    listing_id: int,
    confirm_identifiers: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    _require_wb_manage(db, user, operation="verify_listing", payload={"listing_id": listing_id})
    if not confirm_identifiers:
        return _wb_redirect(error="identifier_confirmation_required")
    try:
        MarketplaceListingService(db).verify_listing(
            organization_id=user.organization.id,
            listing_id=listing_id,
            verified_by=user.profile.id,
        )
    except MarketplaceListingError as exc:
        return _wb_redirect(error=exc.code)
    return _wb_redirect(notice="listing_verified")


@router.post("/workbench/wb/aliases/create", dependencies=[Depends(_require_ui_form_csrf)])
def create_wb_alias_from_workbench(
    canonical_listing_id: int = Form(...),
    current_listing_id: int = Form(...),
    alias_type: str = Form(...),
    alias_value: str = Form(...),
    reason: str = Form(...),
    confirm_replacement: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    _require_wb_manage(
        db,
        user,
        operation="create_alias",
        payload={
            "canonical_listing_id": canonical_listing_id,
            "current_listing_id": current_listing_id,
            "alias_type": alias_type,
        },
    )
    if not confirm_replacement:
        return _wb_redirect(error="replacement_confirmation_required")
    try:
        MarketplaceListingService(db).create_alias(
            organization_id=user.organization.id,
            approved_by=user.profile.id,
            canonical_listing_id=canonical_listing_id,
            current_listing_id=current_listing_id,
            alias_type=alias_type,
            alias_value=alias_value,
            reason=reason,
        )
    except MarketplaceListingError as exc:
        return _wb_redirect(error=exc.code)
    return _wb_redirect(notice="alias_created")


def _quality_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&quality_notice={quote(notice)}" if notice else f"&quality_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=video-quality{suffix}", status_code=303)


def _funnel_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&funnel_notice={quote(notice)}" if notice else f"&funnel_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=funnel{suffix}", status_code=303)


def _owned_content_cycle(db: Session, user: PublicPilotUser, cycle_id: int) -> models.ContentCycle:
    cycle = db.scalar(
        select(models.ContentCycle).where(
            models.ContentCycle.id == cycle_id,
            models.ContentCycle.organization_id == user.organization.id,
        )
    )
    if cycle is None:
        raise HTTPException(status_code=404, detail="Content cycle not found in organization.")
    return cycle


@router.post("/workbench/content-cycles/{cycle_id}/extract-frames", dependencies=[Depends(_require_ui_form_csrf)])
def extract_content_cycle_frames(
    cycle_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cycle = _owned_content_cycle(db, user, cycle_id)
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=OUTPUT_REVIEW,
        payload={"content_cycle_id": cycle.id, "video_job_id": cycle.video_job_id},
    )
    try:
        result = FrameExtractor(db).extract(cycle.video_job_id)
        quality_probe = OutputQualityChecker().check(
            video_job=cycle.video_job,
            brief=cycle.ai_production_brief,
            frame_result=result,
        )
        if quality_probe.visual_evidence is None:
            raise VisualEvidenceSnapshotError("visual_evidence_missing")
        VisualEvidenceSnapshotService(db).record(
            video_job=cycle.video_job,
            frame_result=result,
            report=quality_probe.visual_evidence,
        )
    except (OutputAcceptanceError, VisualEvidenceSnapshotError, OSError, ValueError):
        return _quality_redirect(error="frame_extraction_failed")
    blocking_frame_warning = any(
        marker in str(warning).casefold()
        for warning in (result.warnings_json or [])
        for marker in ("synthetic", "missing", "failed", "incomplete")
    )
    if result.status != "created" or not result.contact_sheet_path or blocking_frame_warning:
        return _quality_redirect(error="frame_extraction_incomplete")
    if quality_probe.visual_evidence.status != "passed":
        return _quality_redirect(error="visual_evidence_blocked")
    return _quality_redirect(notice="frames_ready")


@router.post("/workbench/content-cycles/{cycle_id}/review-output", dependencies=[Depends(_require_ui_form_csrf)])
def review_content_cycle_output(
    cycle_id: int,
    decision: str = Form(...),
    reviewer_notes: str = Form(...),
    confirm_video_watched: bool = Form(False),
    product_identity_ok: bool = Form(False),
    packaging_ok: bool = Form(False),
    geometry_ok: bool = Form(False),
    blogger_ok: bool = Form(False),
    scene_match_ok: bool = Form(False),
    proof_moment_ok: bool = Form(False),
    cta_ok: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cycle = _owned_content_cycle(db, user, cycle_id)
    action = VIDEO_APPROVE if decision == "approved" else VIDEO_REJECT
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=action,
        payload={"content_cycle_id": cycle.id, "decision": decision},
    )
    if decision not in {"approved", "needs_regeneration"}:
        return _quality_redirect(error="invalid_review_decision")
    if not confirm_video_watched:
        return _quality_redirect(error="visual_review_required")
    if len(reviewer_notes.strip()) < 10:
        return _quality_redirect(error="review_notes_required")
    status = lambda ready: "pass" if ready else "fail"
    try:
        acceptance = AcceptanceReviewService(db).review(
            video_job_id=cycle.video_job_id,
            ai_production_brief_id=cycle.ai_production_brief_id,
            decision="approve" if decision == "approved" else "reject",
            product_identity_status=status(product_identity_ok),
            packaging_status=status(packaging_ok),
            geometry_status=status(geometry_ok),
            blogger_authenticity_status=status(blogger_ok),
            scene_match_status=status(scene_match_ok),
            proof_moment_status=status(proof_moment_ok),
            cta_status=status(cta_ok),
            reviewer_notes=reviewer_notes.strip(),
            commit=False,
        )
        if acceptance.status == "approved":
            ContentCycleService(db).bind_approved_output(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                content_cycle_id=cycle.id,
                output_acceptance_id=acceptance.id,
            )
            return _quality_redirect(notice="output_approved")
        db.commit()
        return _quality_redirect(error="output_needs_regeneration")
    except (OutputAcceptanceError, ContentCycleError):
        db.rollback()
        return _quality_redirect(error="output_review_blocked")


@router.post("/workbench/publishing-destinations/create", dependencies=[Depends(_require_ui_form_csrf)])
def create_owned_publishing_destination(
    brand: str = Form(...),
    platform: str = Form(...),
    name: str = Form(...),
    handle: str = Form(""),
    url: str = Form(""),
    confirm_owned_destination: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=PUBLISHING_APPROVE,
        payload={"operation": "create_manual_destination", "platform": platform},
    )
    if not confirm_owned_destination:
        return _funnel_redirect(error="destination_ownership_required")
    owned_brand = db.scalar(
        select(models.Product.id).where(
            models.Product.organization_id == user.organization.id,
            models.Product.brand == brand.strip(),
        )
    )
    if owned_brand is None or not platform.strip() or not name.strip():
        return _funnel_redirect(error="invalid_destination")
    safe_url = None
    if url.strip():
        try:
            safe_url = _canonical_https_url(url)
        except ValueError:
            return _funnel_redirect(error="invalid_destination_url")
    destination = models.PublishingDestination(
        organization_id=user.organization.id,
        brand=brand.strip(),
        platform=platform.strip(),
        name=name.strip()[:160],
        handle=handle.strip()[:160] or None,
        url=safe_url,
        owner_name=user.profile.display_name or user.profile.email,
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=1,
        weekly_limit=3,
        notes="Created in novice-first manual publishing flow.",
    )
    db.add(destination)
    db.commit()
    return _funnel_redirect(notice="destination_created")


@router.post("/workbench/content-cycles/{cycle_id}/prepare-distribution", dependencies=[Depends(_require_ui_form_csrf)])
def prepare_content_cycle_distribution(
    cycle_id: int,
    destination_id: int = Form(...),
    target_url: str = Form(""),
    confirm_manual_distribution: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cycle = _owned_content_cycle(db, user, cycle_id)
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=PUBLISHING_APPROVE,
        payload={"content_cycle_id": cycle.id, "destination_id": destination_id},
    )
    if not confirm_manual_distribution or cycle.output_acceptance_id is None:
        return _funnel_redirect(error="distribution_confirmation_required")
    try:
        prepared = ContentCycleService(db).prepare_manual_distribution(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            content_cycle_id=cycle.id,
            output_acceptance_id=cycle.output_acceptance_id,
            destination_id=destination_id,
            target_url=target_url.strip() or None,
        )
    except ContentCycleError:
        return _funnel_redirect(error="distribution_blocked")
    _record_factory_event(
        db,
        event_name="publishing_package_approved",
        organization_id=user.organization.id,
        user_profile_id=user.profile.id,
        role=user.role,
        idempotency_key=f"publishing_package_approved:c{prepared.id}",
        factory_run_id=f"product_ugc:{prepared.product_ugc_recipe_draft_id}",
        entity_type="content_cycle",
        entity_id=str(prepared.id),
        product_id=prepared.product_id,
        video_job_id=prepared.video_job_id,
        publishing_task_id=prepared.publishing_task_id,
    )
    return _funnel_redirect(notice="distribution_ready")


@router.post("/workbench/content-cycles/{cycle_id}/mark-published", dependencies=[Depends(_require_ui_form_csrf)])
def mark_content_cycle_published(
    cycle_id: int,
    final_url: str = Form(...),
    confirm_uploaded: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cycle = _owned_content_cycle(db, user, cycle_id)
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=PUBLISHING_APPROVE,
        payload={"content_cycle_id": cycle.id, "operation": "mark_manual_published"},
    )
    if not confirm_uploaded or cycle.publishing_task_id is None or cycle.destination_id is None:
        return _funnel_redirect(error="publication_confirmation_required")
    task = db.get(models.PublishingTask, cycle.publishing_task_id)
    destination = db.get(models.PublishingDestination, cycle.destination_id)
    if task is None or destination is None or destination.organization_id != user.organization.id:
        return _funnel_redirect(error="publication_not_found")
    try:
        safe_final_url = _canonical_final_post_url(final_url, destination)
        ManualUploadProvider(db).mark_published(
            task,
            safe_final_url,
            user.profile.display_name or user.profile.email,
        )
    except (ValueError, PublishingError):
        return _funnel_redirect(error="invalid_final_url")
    _record_factory_event(
        db,
        event_name="publication_completed",
        organization_id=user.organization.id,
        user_profile_id=user.profile.id,
        role=user.role,
        idempotency_key=f"publication_completed:c{cycle.id}",
        factory_run_id=f"product_ugc:{cycle.product_ugc_recipe_draft_id}",
        entity_type="content_cycle",
        entity_id=str(cycle.id),
        product_id=cycle.product_id,
        video_job_id=cycle.video_job_id,
        publishing_task_id=task.id,
        properties={"platform": destination.platform},
    )
    return _funnel_redirect(notice="publication_completed")


def _canonical_https_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTPS URL without credentials is required.")
    return urlunsplit(("https", parsed.netloc.casefold(), parsed.path or "/", "", ""))


def _canonical_final_post_url(value: str, destination: models.PublishingDestination) -> str:
    canonical = _canonical_https_url(value)
    hostname = (urlsplit(canonical).hostname or "").casefold()
    platform_domains = {
        "instagram": ("instagram.com",),
        "instagram reels": ("instagram.com",),
        "tiktok": ("tiktok.com",),
        "youtube": ("youtube.com", "youtu.be"),
        "youtube shorts": ("youtube.com", "youtu.be"),
        "facebook": ("facebook.com", "fb.watch"),
        "vk": ("vk.com",),
        "telegram": ("t.me", "telegram.me"),
    }
    allowed = platform_domains.get(destination.platform.strip().casefold(), ())
    if not allowed and destination.url:
        allowed = ((urlsplit(destination.url).hostname or "").casefold(),)
    if not allowed or not any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed if domain):
        raise ValueError("Final URL host does not match the owned destination.")
    return canonical


def _metrics_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&metrics_notice={quote(notice)}" if notice else f"&metrics_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=sources{suffix}", status_code=303)


def _connector_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = (
        f"&connector_notice={quote(notice)}"
        if notice
        else f"&connector_error={quote(error or 'unknown')}"
    )
    return RedirectResponse(f"/workbench?tab=sources{suffix}", status_code=303)


def _connector_error_label(exc: Exception) -> str:
    code = str(exc).strip().lower()
    if "credential_reference_unresolved" in code or "credential reference is set" in code:
        return "Переменная окружения с OAuth-токеном не настроена в процессе приложения."
    if "authorization_failed" in code:
        return "Площадка отклонила OAuth-токен или ему не хватает обязательных прав."
    if any(marker in code for marker in ("video_id", "media_id", "video_map", "media_map", "final_url")):
        return "Проверьте ID публикации и final URL опубликованного ролика."
    if "not_found_in_organization" in code or "organization" in code:
        return "Площадка или подключение не принадлежит текущей организации."
    if "official_adapter_unavailable" in code:
        return "Для этой сети production-адаптер не реализован; используйте ручной или CSV импорт."
    return "Официальный API не подтвердил настройку. Секреты не сохранены; проверьте период, OAuth и опубликованный ролик."


@router.post("/workbench/official-connectors/{platform}/setup", dependencies=[Depends(_require_ui_form_csrf)])
def setup_official_connector_from_workbench(
    platform: str,
    request: Request,
    cycle_id: int = Form(...),
    target_id: str | None = Form(None),
    video_id: str | None = Form(None),
    credential_ref: str = Form(...),
    confirm_secret_reference_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_secret_reference_only:
        return _connector_redirect(
            error="Подтвердите, что указываете только имя переменной окружения, а не сам OAuth-токен."
        )
    try:
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=METRICS_IMPORT,
            payload={
                "operation": "setup_official_connector",
                "platform": platform,
                "content_cycle_id": cycle_id,
            },
        )
        cycle = _owned_content_cycle(db, user, cycle_id)
        destination = cycle.destination
        task = cycle.publishing_task
        platform_name = PlatformMetricsMatrix.normalize_platform(platform)
        definitions = [
            definition
            for definition in OFFICIAL_CONNECTOR_CATALOG.values()
            if definition.platform == platform_name
        ]
        if len(definitions) != 1:
            raise ValueError("official_adapter_unavailable")
        definition = definitions[0]
        normalized_target_id = str(target_id or video_id or "").strip()
        target_patterns = {
            "youtube": r"[A-Za-z0-9_-]{6,64}",
            "tiktok": r"[0-9]{6,32}",
            "instagram": r"[0-9]{6,40}",
        }
        target_pattern = target_patterns.get(platform_name, r"[^\s]{3,80}")
        if (
            destination is None
            or PlatformMetricsMatrix.normalize_platform(destination.platform)
            != platform_name
            or task is None
            or not task.final_url
            or not re.fullmatch(target_pattern, normalized_target_id)
        ):
            raise ValueError(f"{platform_name}_target_id_or_final_url_invalid")
        existing = db.scalars(
            select(models.DestinationConnection).where(
                models.DestinationConnection.destination_id == destination.id,
                models.DestinationConnection.connection_type == definition.connection_type,
            )
        ).all()
        if len(existing) > 1:
            raise ValueError("ambiguous_official_connections")
        safe_settings: dict[str, object] = {}
        if existing:
            safe_settings = public_settings(existing[0].settings_json or {})
        previous_map = safe_settings.get(definition.target_map_key)
        safe_settings[definition.target_map_key] = (
            dict(previous_map) if isinstance(previous_map, dict) else {}
        )
        target_map = safe_settings[definition.target_map_key]
        if (
            normalized_target_id not in target_map
            and len(target_map) >= definition.max_targets_per_request
        ):
            raise ValueError(f"{platform_name}_target_map_limit_exceeded")
        target_map[normalized_target_id] = {
            "final_url": task.final_url,
            "publishing_task_id": task.id,
        }
        registry = ConnectionRegistry(db)
        if existing:
            registry.update(
                existing[0].id,
                credential_ref=credential_ref,
                settings_json=safe_settings,
                status="needs_verification",
                auth_status="credential_reference_configured",
            )
        else:
            registry.create(
                destination.id,
                definition.connection_type,
                credential_ref=credential_ref,
                settings_json=safe_settings,
            )
    except HTTPException:
        return _connector_redirect(error="У вашей роли нет права подключать источники метрик.")
    except (DestinationConnectorError, ValueError) as exc:
        return _connector_redirect(error=_connector_error_label(exc))
    return _connector_redirect(notice=f"{platform_name}_configured")


@router.post("/workbench/official-connectors/{connection_id}/sync", dependencies=[Depends(_require_ui_form_csrf)])
def sync_official_connector_from_workbench(
    connection_id: int,
    request: Request,
    destination_id: int = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    confirm_official_api_call: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_official_api_call:
        return _connector_redirect(error="Подтвердите запрос фактических метрик из официального API.")
    try:
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=METRICS_IMPORT,
            payload={
                "operation": "official_metric_sync",
                "connection_id": connection_id,
                "destination_id": destination_id,
            },
        )
        observed_at = datetime.now(UTC)
        period_start_value = date.fromisoformat(period_start)
        period_end_value = date.fromisoformat(period_end)
        sync_key = (
            f"novice-ui:{connection_id}:{period_start_value.isoformat()}:"
            f"{period_end_value.isoformat()}:{observed_at.isoformat(timespec='minutes')}"
        )
        DestinationConnectorSyncService(db).sync(
            connection_id,
            organization_id=user.organization.id,
            destination_id=destination_id,
            actor_user_profile_id=user.profile.id,
            period_start=period_start_value,
            period_end=period_end_value,
            observed_at=observed_at,
            sync_key=sync_key,
        )
    except HTTPException:
        return _connector_redirect(error="У вашей роли нет права синхронизировать метрики.")
    except (DestinationConnectorError, ValueError) as exc:
        return _connector_redirect(error=_connector_error_label(exc))
    return _connector_redirect(notice="sync_completed")


def _optional_metric_number(value: str, *, integer: bool) -> int | float | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    number = int(cleaned) if integer else float(cleaned.replace(",", "."))
    if number < 0:
        raise ValueError("Metric values cannot be negative.")
    return number


@router.post("/workbench/social-metrics/ingest", dependencies=[Depends(_require_ui_form_csrf)])
def ingest_social_metrics_from_workbench(
    request: Request,
    cycle_id: int = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    external_post_id: str = Form(""),
    views: str = Form(""),
    likes: str = Form(""),
    comments: str = Form(""),
    shares: str = Form(""),
    saves: str = Form(""),
    clicks: str = Form(""),
    orders: str = Form(""),
    revenue: str = Form(""),
    spend: str = Form(""),
    confirm_cumulative_snapshot: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    cycle = _owned_content_cycle(db, user, cycle_id)
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=METRICS_IMPORT,
        payload={"content_cycle_id": cycle.id, "operation": "manual_metric_snapshot"},
    )
    if not confirm_cumulative_snapshot or cycle.publishing_task_id is None:
        return _metrics_redirect(error="snapshot_confirmation_required")
    task = db.get(models.PublishingTask, cycle.publishing_task_id)
    if task is None or not task.final_url:
        return _metrics_redirect(error="final_url_required")
    try:
        metrics = {
            "views": _optional_metric_number(views, integer=True),
            "likes": _optional_metric_number(likes, integer=True),
            "comments": _optional_metric_number(comments, integer=True),
            "shares": _optional_metric_number(shares, integer=True),
            "saves": _optional_metric_number(saves, integer=True),
            "clicks": _optional_metric_number(clicks, integer=True),
            "orders": _optional_metric_number(orders, integer=True),
            "revenue": _optional_metric_number(revenue, integer=False),
            "spend": _optional_metric_number(spend, integer=False),
        }
        if all(value is None for value in metrics.values()):
            raise ValueError("At least one metric is required.")
        observed_at = datetime.now(UTC)
        result = SocialMetricIngestionService(db).ingest(
            SocialMetricObservation(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                source_type="manual_entry",
                source_ref="novice-ui",
                platform=task.platform,
                external_post_id=external_post_id.strip() or None,
                final_url=task.final_url,
                publishing_task_id=task.id,
                observed_at=observed_at,
                period_start=date.fromisoformat(period_start),
                period_end=date.fromisoformat(period_end),
                metrics=metrics,
            )
        )
    except (ValueError, SocialMetricAccessError, SocialMetricValidationError):
        return _metrics_redirect(error="invalid_metric_snapshot")
    if result.disposition == "quarantine":
        return _metrics_redirect(error="metric_quarantined")
    _record_factory_event(
        db,
        event_name="first_metric_attributed",
        organization_id=user.organization.id,
        user_profile_id=user.profile.id,
        role=user.role,
        idempotency_key=f"first_metric_attributed:c{cycle.id}",
        factory_run_id=f"product_ugc:{cycle.product_ugc_recipe_draft_id}",
        entity_type="content_cycle",
        entity_id=str(cycle.id),
        product_id=cycle.product_id,
        video_job_id=cycle.video_job_id,
        publishing_task_id=task.id,
        properties={"source_type": "manual_entry"},
    )
    if int(metrics.get("orders") or 0) > 0:
        _record_factory_event(
            db,
            event_name="first_order_attributed",
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            role=user.role,
            idempotency_key=f"first_order_attributed:c{cycle.id}",
            factory_run_id=f"product_ugc:{cycle.product_ugc_recipe_draft_id}",
            entity_type="content_cycle",
            entity_id=str(cycle.id),
            product_id=cycle.product_id,
            video_job_id=cycle.video_job_id,
            publishing_task_id=task.id,
        )
    return _metrics_redirect(notice=result.status)


def _cost_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&cost_notice={quote(notice)}" if notice else f"&cost_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=payments{suffix}", status_code=303)


def _queue_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&queue_notice={quote(notice)}" if notice else f"&queue_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=video{suffix}", status_code=303)


def _billing_redirect(*, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    suffix = f"&billing_notice={quote(notice)}" if notice else f"&billing_error={quote(error or 'unknown')}"
    return RedirectResponse(f"/workbench?tab=payments{suffix}", status_code=303)


@router.post("/workbench/generation-costs/record", dependencies=[Depends(_require_ui_form_csrf)])
def record_generation_cost_from_workbench(
    cycle_id: int = Form(...),
    amount: str = Form(...),
    currency: str = Form("RUB"),
    entry_kind: str = Form(...),
    external_reference: str = Form(...),
    confirm_accounting_fact: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cycle = _owned_content_cycle(db, user, cycle_id)
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=GENERATION_COST_MANAGE,
        payload={"content_cycle_id": cycle.id, "entry_kind": entry_kind, "currency": currency},
    )
    if not confirm_accounting_fact or entry_kind not in {"estimated", "actual"}:
        return _cost_redirect(error="confirmation_required")
    try:
        decimal_amount = Decimal(amount.strip().replace(",", "."))
        if not decimal_amount.is_finite() or decimal_amount < 0:
            raise InvalidOperation
        amount_minor = int((decimal_amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        reference = external_reference.strip()
        if not reference:
            raise InvalidOperation
        key_digest = hashlib.sha256(
            f"{user.organization.id}:{cycle.video_job_id}:{entry_kind}:{currency}:{reference}".encode("utf-8")
        ).hexdigest()[:32]
        provider_job_id = cycle.product_ugc_recipe_draft.provider_task_id or None
        result = GenerationCostLedgerService(db).record(
            organization_id=user.organization.id,
            video_job_id=cycle.video_job_id,
            provider_job_id=provider_job_id,
            amount_minor=amount_minor,
            currency=currency,
            entry_kind=entry_kind,
            status="confirmed" if entry_kind == "actual" else "pending",
            source="manual_reconciliation",
            external_reference=reference,
            idempotency_key=f"manual-cost:{key_digest}",
            recorded_by_user_profile_id=user.profile.id,
        )
    except (InvalidOperation, ValueError, GenerationCostError):
        return _cost_redirect(error="invalid_cost_fact")
    return _cost_redirect(notice="created" if result.created else "unchanged")


@router.post("/workbench/generation-jobs/{job_id}/retry", dependencies=[Depends(_require_ui_form_csrf)])
def retry_product_ugc_generation_from_workbench(
    job_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    confirm_safe_retry: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_safe_retry:
        return _queue_redirect(error="Подтвердите безопасное продолжение одной существующей задачи.")
    try:
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=ONE_VIDEO_REAL_RUN,
            spend_gate_confirmed=True,
            payload={"generation_job_id": job_id, "operation": "safe_manual_retry"},
        )
        job = ProductUGCGenerationQueueService(db).manual_retry(
            job_id,
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
        )
        background_tasks.add_task(
            _run_product_ugc_background,
            job.id,
            user.organization.id,
            user.profile.id,
            user.role,
        )
    except HTTPException:
        return _queue_redirect(error="У вашей роли нет права продолжать paid generation.")
    except ProductUGCQueueError as exc:
        message = str(exc).lower()
        if "unknown provider-submit" in message or "outcome" in message or "quarantine" in message:
            label = "Исход первой отправки неизвестен: повтор запрещён до ручной сверки у провайдера."
        elif "terminal provider" in message:
            label = "Провайдер завершил task терминальной ошибкой. Новый paid submit из этой задачи запрещён."
        elif "outside this organization" in message or "not an active member" in message:
            label = "Задача не принадлежит текущей организации."
        else:
            label = "Эту задачу нельзя продолжить автоматически; проверьте её статус и причину остановки."
        return _queue_redirect(error=label)
    return _queue_redirect(notice="requeued")


@router.post("/workbench/generation-jobs/{job_id}/reconcile-quarantine", dependencies=[Depends(_require_ui_form_csrf)])
def reconcile_product_ugc_quarantine_from_workbench(
    job_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    resolution: str = Form(...),
    provider_task_id: str = Form(""),
    evidence_reference: str = Form(...),
    reason: str = Form(...),
    confirm_provider_check: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if resolution not in {"attach_existing_task", "confirm_no_submission"}:
        return _queue_redirect(error="Выберите один безопасный результат сверки.")
    if not confirm_provider_check:
        return _queue_redirect(
            error="Подтвердите, что сверили задачу в кабинете провайдера."
        )
    digest = hashlib.sha256(
        "\0".join(
            [
                str(user.organization.id),
                str(job_id),
                resolution,
                provider_task_id.strip(),
                evidence_reference.strip(),
                " ".join(reason.strip().split()),
            ]
        ).encode("utf-8")
    ).hexdigest()[:32]
    idempotency_key = f"queue-reconcile:{job_id}:{resolution}:{digest}"
    try:
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=ONE_VIDEO_REAL_RUN,
            spend_gate_confirmed=True,
            payload={
                "generation_job_id": job_id,
                "operation": "quarantine_reconciliation",
                "resolution": resolution,
            },
        )
        queue = ProductUGCGenerationQueueService(db)
        if resolution == "attach_existing_task":
            result = queue.reconcile_attach_existing_provider_task(
                job_id,
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                provider_task_id=provider_task_id,
                evidence_reference=evidence_reference,
                reason=reason,
                idempotency_key=idempotency_key,
                confirmed_provider_task=True,
            )
            notice = "reconciled_existing_task"
        else:
            result = queue.reconcile_confirm_no_provider_submission(
                job_id,
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                evidence_reference=evidence_reference,
                reason=reason,
                idempotency_key=idempotency_key,
                confirmed_no_submission=True,
            )
            notice = "reconciled_no_submission"
        if result.job.status in {"queued", "retry_wait"}:
            background_tasks.add_task(
                _run_product_ugc_background,
                result.job.id,
                user.organization.id,
                user.profile.id,
                user.role,
            )
    except HTTPException:
        return _queue_redirect(
            error="Только активный владелец или администратор может снять карантин."
        )
    except ProductUGCQueueError as exc:
        message = str(exc).lower()
        if "outside this organization" in message or "owner or admin" in message:
            label = "Задача недоступна этой организации или роли."
        elif "credentials" in message or "signed urls" in message:
            label = "Не вставляйте токены или подписанные URL: укажите только номер проверки."
        elif "already in use" in message or "idempotency" in message:
            label = "Эта сверка уже относится к другой задаче или решению."
        elif "ambiguous provider submission" in message:
            label = "Карантин уже снят либо задача больше не ждёт сверки."
        else:
            label = "Проверьте task ID, номер сверки и причину; секреты сюда не вводятся."
        return _queue_redirect(error=label)
    return _queue_redirect(notice=notice)


def _require_billing_manage(
    db: Session,
    user: PublicPilotUser,
    *,
    operation: str,
    payload: dict | None = None,
) -> None:
    PublicPilotAccessService(db).require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=CUSTOMER_BILLING_MANAGE,
        payload={"operation": operation, **(payload or {})},
    )


@router.post("/workbench/customer-billing/account", dependencies=[Depends(_require_ui_form_csrf)])
def create_customer_billing_account_from_workbench(
    request: Request,
    currency: str = Form("RUB"),
    confirm_ledger_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_ledger_only:
        return _billing_redirect(error="Подтвердите создание только учётного счёта без банковской операции.")
    try:
        _require_billing_manage(db, user, operation="create_account", payload={"currency": currency})
        result = CustomerBillingService(db).create_account(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            currency=currency,
            idempotency_key=f"customer-billing-account:o{user.organization.id}:v1",
        )
    except HTTPException:
        return _billing_redirect(error="Изменять клиентский биллинг могут только владелец или администратор.")
    except CustomerBillingError as exc:
        return _billing_redirect(error=_billing_error_label(exc))
    return _billing_redirect(notice="account_created" if result.created else "account_exists")


@router.post("/workbench/customer-billing/subscription", dependencies=[Depends(_require_ui_form_csrf)])
def create_customer_billing_subscription_from_workbench(
    request: Request,
    plan_code: str = Form(...),
    status: str = Form("active"),
    billing_interval: str = Form("month"),
    recurring_amount: str = Form("0"),
    included_content_cycles: int = Form(0),
    expected_previous_state_id: int | None = Form(None),
    confirm_ledger_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_ledger_only:
        return _billing_redirect(error="Подтвердите, что состояние тарифа не списывает деньги.")
    try:
        _require_billing_manage(db, user, operation="transition_subscription")
        account = db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == user.organization.id
            )
        )
        if account is None:
            raise ValueError("billing_account_missing")
        amount_minor = _amount_minor(recurring_amount, allow_zero=True)
        period_start = _business_time_utc(_business_today(), datetime_time.min)
        period_end = _billing_period_end(period_start, billing_interval)
        key_material = ":".join(
            [
                str(user.organization.id),
                plan_code.strip(),
                status.strip(),
                billing_interval.strip(),
                str(amount_minor),
                str(included_content_cycles),
                str(expected_previous_state_id or "initial"),
                period_start.date().isoformat(),
            ]
        )
        key_digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:32]
        result = CustomerBillingService(db).transition_subscription(
            organization_id=user.organization.id,
            billing_account_id=account.id,
            actor_user_profile_id=user.profile.id,
            plan_code=plan_code,
            status=status,
            billing_interval=billing_interval,
            recurring_amount_minor=amount_minor,
            included_content_cycles=included_content_cycles,
            currency=account.currency,
            current_period_start=period_start,
            current_period_end=period_end,
            expected_previous_state_id=expected_previous_state_id,
            idempotency_key=f"customer-subscription:{key_digest}",
        )
    except HTTPException:
        return _billing_redirect(error="Изменять клиентский биллинг могут только владелец или администратор.")
    except (CustomerBillingError, ValueError) as exc:
        return _billing_redirect(error=_billing_error_label(exc))
    return _billing_redirect(notice="subscription_created" if result.created else "subscription_exists")


@router.post("/workbench/customer-billing/invoices", dependencies=[Depends(_require_ui_form_csrf)])
def issue_customer_invoice_from_workbench(
    request: Request,
    generation_cost_entry_id: int = Form(...),
    invoice_number: str = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    due_date: str = Form(...),
    charge_amount: str = Form(...),
    description: str = Form(...),
    confirm_invoice_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_invoice_only:
        return _billing_redirect(error="Подтвердите выпуск инвойса без автоматического списания.")
    try:
        _require_billing_manage(
            db,
            user,
            operation="issue_usage_invoice",
            payload={"generation_cost_entry_id": generation_cost_entry_id},
        )
        account = db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == user.organization.id
            )
        )
        subscription = db.scalar(
            select(models.CustomerBillingSubscriptionState)
            .where(models.CustomerBillingSubscriptionState.organization_id == user.organization.id)
            .order_by(
                models.CustomerBillingSubscriptionState.version.desc(),
                models.CustomerBillingSubscriptionState.id.desc(),
            )
        )
        cost_entry = db.get(models.GenerationCostLedgerEntry, generation_cost_entry_id)
        if account is None or subscription is None or cost_entry is None:
            raise ValueError("billing_lineage_missing")
        _require_customer_billing_integrity(
            db,
            organization_id=user.organization.id,
            billing_account_id=account.id,
        )
        if cost_entry.organization_id != user.organization.id:
            raise ValueError("billing_lineage_missing")
        cycle = db.scalar(
            select(models.ContentCycle).where(
                models.ContentCycle.organization_id == user.organization.id,
                models.ContentCycle.video_job_id == cost_entry.video_job_id,
            )
        )
        if cycle is None:
            raise ValueError("billing_lineage_missing")
        amount_minor = _amount_minor(charge_amount)
        invoice_key = hashlib.sha256(
            f"{user.organization.id}:{invoice_number.strip()}".encode("utf-8")
        ).hexdigest()[:32]
        result = CustomerBillingService(db).issue_usage_invoice(
            organization_id=user.organization.id,
            billing_account_id=account.id,
            actor_user_profile_id=user.profile.id,
            subscription_state_id=subscription.id,
            invoice_number=invoice_number,
            currency=account.currency,
            period_start=date.fromisoformat(period_start),
            period_end=date.fromisoformat(period_end),
            due_at=_business_time_utc(
                date.fromisoformat(due_date),
                datetime_time(23, 59, 59),
            ),
            usage_charges=[
                UsageChargeInput(
                    content_cycle_id=cycle.id,
                    generation_cost_ledger_entry_id=cost_entry.id,
                    amount_minor=amount_minor,
                    description=description,
                )
            ],
            idempotency_key=f"customer-invoice:{invoice_key}",
        )
    except HTTPException:
        return _billing_redirect(error="Изменять клиентский биллинг могут только владелец или администратор.")
    except (CustomerBillingError, ValueError, InvalidOperation) as exc:
        return _billing_redirect(error=_billing_error_label(exc))
    return _billing_redirect(notice="invoice_created" if result.created else "invoice_exists")


@router.post("/workbench/customer-billing/invoices/{invoice_id}/payments", dependencies=[Depends(_require_ui_form_csrf)])
def record_customer_payment_from_workbench(
    invoice_id: int,
    request: Request,
    amount: str = Form(...),
    transaction_reference: str = Form(...),
    occurred_date: str = Form(...),
    confirm_external_payment: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_external_payment:
        return _billing_redirect(error="Подтвердите, что платёж уже получен во внешней системе.")
    try:
        _require_billing_manage(db, user, operation="record_manual_payment", payload={"invoice_id": invoice_id})
        account = db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == user.organization.id
            )
        )
        if account is None:
            raise ValueError("billing_account_missing")
        _require_customer_billing_integrity(
            db,
            organization_id=user.organization.id,
            billing_account_id=account.id,
        )
        amount_minor = _amount_minor(amount)
        reference = transaction_reference.strip()
        selected_occurred_date = date.fromisoformat(occurred_date)
        now_utc = datetime.now(UTC)
        today_business = now_utc.astimezone(BUSINESS_TIMEZONE).date()
        occurred_at = (
            now_utc
            if selected_occurred_date >= today_business
            else _business_time_utc(selected_occurred_date, datetime_time(12, 0))
        )
        reference_digest = hashlib.sha256(
            f"{user.organization.id}:{reference}".encode("utf-8")
        ).hexdigest()[:32]
        result = CustomerBillingService(db).record_manual_payment(
            organization_id=user.organization.id,
            billing_account_id=account.id,
            invoice_id=invoice_id,
            actor_user_profile_id=user.profile.id,
            amount_minor=amount_minor,
            transaction_reference=reference,
            idempotency_key=f"customer-payment:{reference_digest}",
            occurred_at=occurred_at,
        )
    except HTTPException:
        return _billing_redirect(error="Изменять клиентский биллинг могут только владелец или администратор.")
    except (CustomerBillingError, ValueError, InvalidOperation) as exc:
        return _billing_redirect(error=_billing_error_label(exc))
    return _billing_redirect(notice="payment_recorded" if result.created else "payment_exists")


@router.post("/workbench/customer-billing/invoices/{invoice_id}/credits", dependencies=[Depends(_require_ui_form_csrf)])
def record_customer_credit_from_workbench(
    invoice_id: int,
    request: Request,
    target_charge_entry_id: int = Form(...),
    amount: str = Form(...),
    reason: str = Form(...),
    correction_reference: str = Form(...),
    confirm_ledger_only: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    if not confirm_ledger_only:
        return _billing_redirect(
            error="Подтвердите, что кредит исправляет только журнал и не выполняет возврат денег."
        )
    try:
        _require_billing_manage(
            db,
            user,
            operation="record_invoice_credit",
            payload={
                "invoice_id": invoice_id,
                "target_charge_entry_id": target_charge_entry_id,
            },
        )
        account = db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == user.organization.id
            )
        )
        if account is None:
            raise ValueError("billing_account_missing")
        _require_customer_billing_integrity(
            db,
            organization_id=user.organization.id,
            billing_account_id=account.id,
        )
        reference = correction_reference.strip()
        cleaned_reason = reason.strip()
        if not 3 <= len(reference) <= 80 or "\n" in reference or "\r" in reference:
            raise ValueError("invalid_correction_reference")
        if len(cleaned_reason) < 10:
            raise ValueError("invalid_credit_reason")
        amount_minor = _amount_minor(amount)
        key_digest = hashlib.sha256(
            (
                f"{user.organization.id}:{invoice_id}:{target_charge_entry_id}:"
                f"{reference.casefold()}"
            ).encode("utf-8")
        ).hexdigest()[:32]
        result = CustomerBillingService(db).add_credit(
            organization_id=user.organization.id,
            billing_account_id=account.id,
            invoice_id=invoice_id,
            target_charge_entry_id=target_charge_entry_id,
            actor_user_profile_id=user.profile.id,
            amount_minor=amount_minor,
            reason=f"{cleaned_reason} · корректировка {reference}",
            idempotency_key=f"customer-credit:{key_digest}",
            occurred_at=datetime.now(UTC),
        )
    except HTTPException:
        return _billing_redirect(
            error="Изменять клиентский биллинг могут только владелец или администратор."
        )
    except (CustomerBillingError, ValueError, InvalidOperation) as exc:
        return _billing_redirect(error=_billing_error_label(exc))
    return _billing_redirect(
        notice="credit_recorded" if result.created else "credit_exists"
    )


@router.get("/mvp-launch", response_class=HTMLResponse)
def mvp_launch(
    request: Request,
    run_id: int | None = None,
    product_id: int | None = None,
    recipe_draft_id: int | None = None,
    error: str | None = None,
    notice: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    strict_org_scope = bool(get_settings().public_pilot_mode or get_settings().auth_required)
    service = MVPLaunchWizardService(db)
    run_output = None
    if run_id and not strict_org_scope:
        try:
            run_output = service.output(service.get(run_id))
        except InterfaceProductizationError as exc:
            error = str(exc)
    product_query = select(models.Product)
    if strict_org_scope:
        product_query = product_query.where(models.Product.organization_id == user.organization.id)
    products = list(db.scalars(product_query.order_by(models.Product.id.desc()).limit(50)))
    legacy_products: list[models.Product] = []
    if strict_org_scope and user.role in {"owner", "admin"}:
        legacy_products = list(
            db.scalars(
                select(models.Product)
                .where(models.Product.organization_id.is_(None))
                .order_by(models.Product.id.desc())
                .limit(20)
            )
        )
    recipe_service = ProductUGCRecipeService(db)
    recipe_draft = None
    recipe_record = None
    recipe_run_readiness = None
    recipe_output_media: list[dict[str, object]] = []
    recipe_report_url = None
    recipe_character_url = None
    recipe_provider_product_url = None
    selected_product = db.get(models.Product, product_id) if product_id else None
    if strict_org_scope and selected_product and selected_product.organization_id != user.organization.id:
        selected_product = None
        error = error or "Товар не принадлежит текущему рабочему пространству."
    if recipe_draft_id:
        try:
            recipe_record = recipe_service.get(recipe_draft_id)
            if strict_org_scope and recipe_record.product.organization_id != user.organization.id:
                raise RunwayRecipeError("Черновик не принадлежит текущему рабочему пространству.")
            recipe_draft = recipe_service.output(recipe_record)
            selected_product = recipe_record.product
            recipe_run_readiness = _recipe_run_readiness(db, user, recipe_record)
            recipe_output_media = _recipe_media_items(
                recipe_draft.local_output_paths,
                draft_id=recipe_record.id,
            )
            recipe_character_url = authorized_media_url(
                recipe_record.character_image_path,
                f"/media/product-ugc-drafts/{recipe_record.id}/character",
            )
            provider_asset = recipe_record.primary_product_asset
            if provider_asset:
                recipe_provider_product_url = (
                    authorized_media_url(
                        provider_asset.source_ref,
                        f"/media/product-assets/{provider_asset.id}/source",
                    )
                    if provider_asset.source_type == "local"
                    else provider_asset.source_ref
                )
            if recipe_draft.generation_report_path:
                recipe_report_url = authorized_media_url(
                    recipe_draft.generation_report_path,
                    f"/media/product-ugc-drafts/{recipe_record.id}/generation-report",
                )
        except RunwayRecipeError as exc:
            error = str(exc)
    assets = []
    if selected_product:
        classifier = ProductAssetClassifier()
        expected_variant = product_variant_key(selected_product)
        for asset in db.scalars(
            select(models.ProductAsset)
            .where(models.ProductAsset.product_id == selected_product.id)
            .order_by(models.ProductAsset.is_primary_reference.desc(), models.ProductAsset.id.desc())
        ):
            classification = classifier.classify(asset, expected_variant_key=expected_variant)
            assets.append(
                {
                    "id": asset.id,
                    "filename": asset.filename or Path(asset.source_ref).name,
                    "contract_type": classification.contract_type,
                    "review_status": asset.review_status,
                    "variant_status": classification.variant_status,
                    "is_primary": asset.is_primary_reference,
                    "media_url": (
                        authorized_media_url(
                            asset.source_ref,
                            f"/media/product-assets/{asset.id}/source",
                        )
                        if asset.source_type == "local"
                        else asset.source_ref
                    ),
                }
            )
    selected_profile = product_profile(selected_product) if selected_product else None
    selected_variant = product_variant_key(selected_product) if selected_product else None
    if selected_product:
        _record_factory_event(
            db,
            event_name="product_selected",
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            role=user.role,
            idempotency_key=f"product_selected:u{user.profile.id}:p{selected_product.id}",
            entity_type="product",
            entity_id=str(selected_product.id),
            product_id=selected_product.id,
            sku=selected_product.sku,
        )
    return templates.TemplateResponse(
        "public_mvp_launch.html",
        {
            "request": request,
            "page_title": "ContentEngine · Product UGC",
            "user": user,
            "role": user.role,
            "run": run_output,
            "products": products,
            "legacy_products": legacy_products,
            "strict_org_scope": strict_org_scope,
            "selected_product": selected_product,
            "selected_profile": selected_profile,
            "selected_variant": selected_variant,
            "proof_reference_options": list(FORM_PROOF_REFERENCE_OPTIONS.get(selected_profile, {}).items()),
            "product_assets": assets,
            "recipe_draft": recipe_draft,
            "recipe_run_readiness": recipe_run_readiness,
            "recipe_output_media": recipe_output_media,
            "recipe_report_url": recipe_report_url,
            "recipe_character_url": recipe_character_url,
            "recipe_provider_product_url": recipe_provider_product_url,
            "default_product_info": recipe_service.default_product_info(selected_product, selected_variant) if selected_product else "",
            "error": error,
            "notice": notice,
            "form_csrf_token": form_csrf_token(request),
        },
    )


@router.post("/mvp-launch/products/create", dependencies=[Depends(_require_ui_form_csrf)])
def create_scoped_product_from_ui(
    sku: str = Form(...),
    brand: str = Form(...),
    title: str = Form(...),
    marketplace: str = Form("wildberries"),
    category: str = Form(""),
    product_url: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    cleaned = {
        "sku": sku.strip(),
        "brand": brand.strip(),
        "title": title.strip(),
        "marketplace": marketplace.strip(),
        "category": category.strip(),
        "product_url": product_url.strip(),
    }
    if not cleaned["sku"] or not cleaned["brand"] or not cleaned["title"]:
        return RedirectResponse(
            f"/mvp-launch?error={quote('Заполните SKU, бренд и название товара.')}",
            status_code=303,
        )
    if len(cleaned["sku"]) > 120 or len(cleaned["brand"]) > 120 or len(cleaned["title"]) > 255:
        return RedirectResponse(
            f"/mvp-launch?error={quote('SKU, бренд или название слишком длинные.')}",
            status_code=303,
        )
    if cleaned["product_url"] and not cleaned["product_url"].startswith("https://"):
        return RedirectResponse(
            f"/mvp-launch?error={quote('Ссылка на товар должна начинаться с https://')}",
            status_code=303,
        )
    if db.scalar(select(models.Product.id).where(models.Product.sku == cleaned["sku"])) is not None:
        return RedirectResponse(
            f"/mvp-launch?error={quote('Такой SKU уже существует. Выберите его или попросите владельца принять старую запись.')}",
            status_code=303,
        )
    product = models.Product(
        organization_id=user.organization.id,
        sku=cleaned["sku"],
        brand=cleaned["brand"],
        title=cleaned["title"],
        marketplace=cleaned["marketplace"] or None,
        category=cleaned["category"] or None,
        product_url=cleaned["product_url"] or None,
        attributes_json={},
        benefits_json=[],
        images_json=[],
        reviews_json=[],
        restrictions_json=[],
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            f"/mvp-launch?error={quote('Не удалось создать товар: проверьте уникальность SKU.')}",
            status_code=303,
        )
    db.refresh(product)
    _record_factory_event(
        db,
        event_name="product_created",
        organization_id=user.organization.id,
        user_profile_id=user.profile.id,
        role=user.role,
        idempotency_key=f"product_created:p{product.id}",
        entity_type="product",
        entity_id=str(product.id),
        product_id=product.id,
        sku=product.sku,
        properties={"marketplace": product.marketplace or "not_set"},
    )
    return RedirectResponse(f"/mvp-launch?product_id={product.id}", status_code=303)


@router.post("/mvp-launch/products/{product_id}/claim", dependencies=[Depends(_require_ui_form_csrf)])
def claim_legacy_product_from_ui(
    product_id: int,
    confirm_ownership: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    if user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="role_cannot_claim_legacy_product")
    product = db.get(models.Product, product_id)
    if not product or (product.organization_id is not None and product.organization_id != user.organization.id):
        return RedirectResponse(
            f"/mvp-launch?error={quote('Товар не найден в доступных legacy-записях.')}",
            status_code=303,
        )
    if not confirm_ownership:
        return RedirectResponse(
            f"/mvp-launch?error={quote('Подтвердите, что товар принадлежит вашей организации.')}",
            status_code=303,
        )
    if product.organization_id is None:
        product.organization_id = user.organization.id
        db.add(
            models.AuditLog(
                user_profile_id=user.profile.id,
                organization_id=user.organization.id,
                action="claim_legacy_product",
                status="allowed",
                reason="explicit_owner_confirmation",
                entity_type="product",
                entity_id=str(product.id),
                metadata_json={"sku": product.sku, "role": user.role},
            )
        )
        db.commit()
        db.refresh(product)
    return RedirectResponse(f"/mvp-launch?product_id={product.id}", status_code=303)


@router.post("/mvp-launch/product-ugc-draft", dependencies=[Depends(_require_ui_form_csrf)])
async def product_ugc_recipe_draft(
    product_id: int = Form(...),
    variant_key: str = Form(...),
    existing_asset_ids: list[int] = Form([]),
    primary_asset_id: int | None = Form(None),
    provider_image_slot: str = Form("front"),
    scale_reference_type: str = Form("product_in_hand"),
    proof_reference_type: str = Form(""),
    front_image: UploadFile | None = File(None),
    angle_image: UploadFile | None = File(None),
    scale_image: UploadFile | None = File(None),
    proof_image: UploadFile | None = File(None),
    character_image: UploadFile = File(...),
    product_info: str = Form(""),
    required_packaging_tokens: str = Form(...),
    task: str = Form(...),
    creator_profile: str = Form(...),
    setting: str = Form(...),
    hook: str = Form(...),
    product_action: str = Form(...),
    proof_moment: str = Form(...),
    spoken_message: str = Form(""),
    cta: str = Form(...),
    forbidden_visuals: str = Form(""),
    interaction_mode: str = Form("presentation"),
    platform: str = Form("Instagram Reels"),
    duration: int = Form(15),
    ratio: str = Form("720:1280"),
    audio_enabled: bool = Form(False),
    likeness_consent: bool = Form(False),
    character_product_free_confirmed: bool = Form(False),
    exact_variant_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    product = db.get(models.Product, product_id)
    if not product:
        return RedirectResponse(f"/mvp-launch?error={quote('Товар не найден')}", status_code=303)
    settings = get_settings()
    if (settings.public_pilot_mode or settings.auth_required) and product.organization_id != user.organization.id:
        return RedirectResponse(
            f"/mvp-launch?error={quote('Товар не принадлежит текущему рабочему пространству.')}",
            status_code=303,
        )
    profile = product_profile(product)
    proof_options = FORM_PROOF_REFERENCE_OPTIONS[profile]
    proof_type = proof_reference_type or next(iter(proof_options))
    if proof_type not in proof_options:
        return RedirectResponse(
            f"/mvp-launch?product_id={product_id}&error={quote('Неверный тип proof reference для категории товара.')}",
            status_code=303,
        )
    if scale_reference_type not in {"product_in_hand", "product_on_surface", "scale_context"}:
        return RedirectResponse(
            f"/mvp-launch?product_id={product_id}&error={quote('Неверный тип scale reference.')}",
            status_code=303,
        )
    upload_specs = [
        ("front", "Главный вид", front_image, "front_packshot"),
        ("angle", "Второй ракурс", angle_image, "angled_product"),
        ("scale", "Масштаб / в руке", scale_image, scale_reference_type),
        ("proof", "Доказательство применения", proof_image, proof_type),
    ]
    uploads: list[ProductImageUpload] = []
    for slot_key, slot, upload, contract_type in upload_specs:
        if upload and upload.filename:
            uploads.append(
                ProductImageUpload(
                    slot=slot,
                    filename=upload.filename,
                    content=await upload.read(),
                    contract_type=contract_type,
                    primary=primary_asset_id is None and provider_image_slot == slot_key,
                )
            )
    try:
        draft = ProductUGCRecipeService(db).create_draft(
            product_id=product_id,
            variant_key=variant_key,
            character_filename=character_image.filename or "creator.png",
            character_content=await character_image.read(),
            existing_asset_ids=existing_asset_ids,
            primary_asset_id=primary_asset_id,
            product_uploads=uploads,
            product_info=product_info,
            required_packaging_tokens=required_packaging_tokens,
            task=task,
            creator_profile=creator_profile,
            setting=setting,
            hook=hook,
            product_action=product_action,
            proof_moment=proof_moment,
            spoken_message=spoken_message,
            cta=cta,
            forbidden_visuals=forbidden_visuals,
            interaction_mode=interaction_mode,
            platform=platform,
            duration=duration,
            ratio=ratio,
            audio=audio_enabled,
            likeness_consent=likeness_consent,
            character_product_free_confirmed=character_product_free_confirmed,
            exact_variant_confirmed=exact_variant_confirmed,
        )
    except RunwayRecipeError as exc:
        return RedirectResponse(
            f"/mvp-launch?product_id={product_id}&error={quote(str(exc))}",
            status_code=303,
        )
    if draft.status == "ready_for_paid_preflight" and not draft.blockers_json:
        common_event = {
            "organization_id": user.organization.id,
            "user_profile_id": user.profile.id,
            "role": user.role,
            "factory_run_id": f"product_ugc:{draft.id}",
            "entity_type": "product_ugc_recipe_draft",
            "entity_id": str(draft.id),
            "product_id": draft.product_id,
            "sku": draft.sku,
        }
        _record_factory_event(
            db,
            event_name="asset_gate_passed",
            idempotency_key=f"asset_gate_passed:d{draft.id}",
            properties={"reference_count": len(draft.product_asset_ids_json or [])},
            **common_event,
        )
        _record_factory_event(
            db,
            event_name="prompt_ready",
            idempotency_key=f"prompt_ready:d{draft.id}",
            properties={"provider_calls": 0, "estimated_credits": draft.estimated_credits},
            **common_event,
        )
    return RedirectResponse(
        f"/mvp-launch?product_id={product_id}&recipe_draft_id={draft.id}",
        status_code=303,
    )


@router.post("/mvp-launch/product-ugc/{draft_id}/run", dependencies=[Depends(_require_ui_form_csrf)])
def run_product_ugc_recipe_from_ui(
    draft_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    confirm_single_paid_run: bool = Form(False),
    confirmed_credits: int = Form(0),
    confirm_human_review: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    service = ProductUGCRecipeService(db)
    try:
        draft = service.get(draft_id)
        settings = get_settings()
        if (settings.public_pilot_mode or settings.auth_required) and draft.product.organization_id != user.organization.id:
            raise RunwayRecipeError("Черновик не принадлежит текущему рабочему пространству.")
        if draft.status != "ready_for_paid_preflight" or draft.blockers_json:
            raise RunwayRecipeError("Paid run доступен только для полностью готового Product UGC draft.")
        if not confirm_single_paid_run or not confirm_human_review:
            raise RunwayRecipeError("Подтвердите один paid task и обязательный human review.")
        if confirmed_credits != draft.estimated_credits:
            raise RunwayRecipeError(
                f"Подтверждение стоимости должно точно совпадать с оценкой: {draft.estimated_credits} credits."
            )
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=ONE_VIDEO_REAL_RUN,
            spend_gate_confirmed=True,
            payload={"draft_id": draft.id, "estimated_credits": draft.estimated_credits, "recipe": "product_ugc"},
        )
        ProductUGCRecipeRunner(db).validate_preflight(draft.id, real_run=True)
        strict_org_scope = settings.public_pilot_mode or settings.auth_required
        enqueue_result = ProductUGCGenerationQueueService(db).enqueue(
            draft_id=draft.id,
            organization_id=user.organization.id,
            requested_by_user_profile_id=user.profile.id,
            idempotency_key=f"product-ugc-paid:d{draft.id}:v1",
            allow_unscoped_product=not strict_org_scope,
        )
        _record_factory_event(
            db,
            event_name="generation_requested",
            organization_id=user.organization.id,
            user_profile_id=user.profile.id,
            role=user.role,
            idempotency_key=f"generation_requested:d{draft.id}",
            factory_run_id=f"product_ugc:{draft.id}",
            entity_type="product_ugc_recipe_draft",
            entity_id=str(draft.id),
            product_id=draft.product_id,
            sku=draft.sku,
            properties={"estimated_credits": draft.estimated_credits, "provider": "runway"},
        )
        background_tasks.add_task(
            _run_product_ugc_background,
            enqueue_result.job.id,
            user.organization.id,
            user.profile.id,
            user.role,
        )
    except HTTPException as exc:
        return RedirectResponse(
            f"/mvp-launch?product_id={draft.product_id if 'draft' in locals() else ''}&recipe_draft_id={draft_id}&error={quote(str(exc.detail))}",
            status_code=303,
        )
    except (ProviderConfigurationError, RunwayRecipeError, ProductUGCQueueError) as exc:
        return RedirectResponse(
            f"/mvp-launch?product_id={draft.product_id if 'draft' in locals() else ''}&recipe_draft_id={draft_id}&error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        f"/mvp-launch?product_id={draft.product_id}&recipe_draft_id={draft.id}&notice={quote('Paid task отправляется в Runway. Страница обновит статус автоматически.')}",
        status_code=303,
    )


@router.post("/mvp-launch/product-ugc/{draft_id}/review", dependencies=[Depends(_require_ui_form_csrf)])
def review_product_ugc_recipe_from_ui(
    draft_id: int,
    review_status: str = Form(...),
    review_notes: str = Form(...),
    confirm_visual_review: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    service = ProductUGCRecipeService(db)
    try:
        draft = service.get(draft_id)
        settings = get_settings()
        if (settings.public_pilot_mode or settings.auth_required) and draft.product.organization_id != user.organization.id:
            raise RunwayRecipeError("Черновик не принадлежит текущему рабочему пространству.")
        if not confirm_visual_review:
            raise RunwayRecipeError("Подтвердите, что MP4 действительно просмотрен глазами.")
        action = VIDEO_APPROVE if review_status == "approved" else VIDEO_REJECT
        PublicPilotAccessService(db).require_action(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            role=user.role,
            action=action,
            payload={"draft_id": draft.id, "review_status": review_status},
        )
        reviewed = service.record_human_review(draft.id, status=review_status, notes=review_notes)
        common_event = {
            "organization_id": user.organization.id,
            "user_profile_id": user.profile.id,
            "role": user.role,
            "factory_run_id": f"product_ugc:{draft.id}",
            "entity_type": "product_ugc_recipe_draft",
            "entity_id": str(draft.id),
            "product_id": reviewed.product_id,
            "sku": reviewed.sku,
        }
        _record_factory_event(
            db,
            event_name="human_review_completed",
            idempotency_key=f"human_review_completed:d{draft.id}:{review_status}",
            properties={"decision": review_status},
            **common_event,
        )
        decision_event = "video_approved" if review_status == "approved" else "video_rejected"
        _record_factory_event(
            db,
            event_name=decision_event,
            idempotency_key=f"{decision_event}:d{draft.id}",
            properties={"decision": review_status},
            **common_event,
        )
        content_cycle = None
        if review_status == "approved" and reviewed.product.organization_id == user.organization.id:
            content_cycle = ContentCycleService(db).start_from_product_ugc(
                organization_id=user.organization.id,
                actor_user_profile_id=user.profile.id,
                product_ugc_recipe_draft_id=reviewed.id,
                idempotency_key=f"product-ugc:{reviewed.id}",
            )
    except HTTPException as exc:
        return RedirectResponse(
            f"/mvp-launch?recipe_draft_id={draft_id}&error={quote(str(exc.detail))}",
            status_code=303,
        )
    except (RunwayRecipeError, ContentCycleError) as exc:
        return RedirectResponse(
            f"/mvp-launch?recipe_draft_id={draft_id}&error={quote(str(exc))}",
            status_code=303,
        )
    notice = (
        "Human review сохранён. Создан канонический цикл; следующий шаг — покадровая проверка качества."
        if content_cycle is not None
        else "Human review сохранён. Публикация зависит от решения."
    )
    return RedirectResponse(
        f"/mvp-launch?product_id={reviewed.product_id}&recipe_draft_id={reviewed.id}&notice={quote(notice)}",
        status_code=303,
    )


@router.post("/mvp-launch/start", dependencies=[Depends(_require_ui_form_csrf)])
def mvp_launch_start(
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    if get_settings().public_pilot_mode or get_settings().auth_required:
        raise HTTPException(status_code=404, detail="not_found")
    del user
    run = MVPLaunchWizardService(db).start(product_id=product_id, sku=sku or None)
    return RedirectResponse(f"/mvp-launch?run_id={run.id}", status_code=303)


@router.post("/mvp-launch/{run_id}/next", dependencies=[Depends(_require_ui_form_csrf)])
def mvp_launch_next(
    run_id: int,
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    runway_credits_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    if get_settings().public_pilot_mode or get_settings().auth_required:
        raise HTTPException(status_code=404, detail="not_found")
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
            "role": user.role,
            "roles": matrix_service.matrix().get("settings_view", {}).keys(),
            "matrix": matrix_service.matrix(),
            "summary": matrix_service.summary(),
            "action_labels": ACTION_LABELS,
            "form_csrf_token": form_csrf_token(request),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_redirect() -> RedirectResponse:
    return RedirectResponse("/settings/access", status_code=302)


@router.post("/control-room/training/{module_code}/submit", dependencies=[Depends(_require_ui_form_csrf)])
async def complete_training(
    module_code: str,
    request: Request,
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
    form = await request.form()
    answers: dict[str, object] = {}
    for key in form:
        if not key.startswith("answer_"):
            continue
        question_id = key.removeprefix("answer_")
        values = form.getlist(key)
        answers[question_id] = values if len(values) > 1 else values[0]
    try:
        result = NoviceLearningPathService(db).submit_quiz(
            user_profile_id=user.profile.id,
            organization_id=user.organization.id,
            module_code=module_code,
            answers=answers,
        )
    except NoviceLearningPathError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    score_percent = round(result.score * 100)
    status_label = "passed" if result.passed else "failed"
    return RedirectResponse(
        f"/workbench?tab=people&module={quote(module_code)}&training_result={status_label}&training_score={score_percent}",
        status_code=303,
    )

