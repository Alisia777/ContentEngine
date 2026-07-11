from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import models
from app.customer_billing import CustomerBillingError, CustomerBillingService
from app.models import utcnow
from app.generation_costs import GenerationCostLedgerService
from app.novice_learning_path import NoviceLearningPathService
from app.visual_evidence import VisualEvidenceSnapshotError, VisualEvidenceSnapshotService
from app.wildberries_analytics import WildberriesSellerAnalyticsService


class FactoryDashboardService:
    """Builds a novice-facing, honest view of the whole content factory."""

    def __init__(self, db: Session):
        self.db = db

    def snapshot(
        self,
        *,
        user_profile_id: int | None = None,
        organization_id: int | None = None,
    ) -> dict[str, object]:
        window_start = utcnow() - timedelta(days=7)
        products = self._count(models.Product, organization_id=organization_id)
        real_video = func.lower(models.VideoJob.provider) != "mock"
        videos = self._count(models.VideoJob, real_video, organization_id=organization_id)
        videos_7d = self._count(
            models.VideoJob,
            real_video,
            models.VideoJob.created_at >= window_start,
            organization_id=organization_id,
        )
        approved_statement = (
            select(
                models.ContentCycle.video_job_id,
                models.VisualEvidenceSnapshot,
            )
            .select_from(models.ContentCycle)
            .join(
                models.VideoOutputAcceptance,
                models.VideoOutputAcceptance.id == models.ContentCycle.output_acceptance_id,
            )
            .join(
                models.VisualEvidenceSnapshot,
                models.VisualEvidenceSnapshot.id
                == models.VideoOutputAcceptance.visual_evidence_snapshot_id,
            )
            .where(
                models.VideoOutputAcceptance.status == "approved",
                models.VisualEvidenceSnapshot.status == "passed",
            )
        )
        waiting_statement = select(func.count()).select_from(models.ContentCycle).where(
            models.ContentCycle.output_acceptance_id.is_(None)
        )
        if organization_id is not None:
            approved_statement = approved_statement.where(
                models.ContentCycle.organization_id == organization_id
            )
            waiting_statement = waiting_statement.where(
                models.ContentCycle.organization_id == organization_id
            )
        approved_videos = 0
        stale_approved_evidence = 0
        evidence_service = VisualEvidenceSnapshotService(self.db)
        seen_approved_video_ids: set[int] = set()
        for video_job_id, evidence_snapshot in self.db.execute(approved_statement):
            if video_job_id in seen_approved_video_ids:
                continue
            try:
                evidence_service.verify_current(evidence_snapshot)
            except (VisualEvidenceSnapshotError, OSError, ValueError):
                stale_approved_evidence += 1
                continue
            seen_approved_video_ids.add(video_job_id)
            approved_videos += 1
        reviews_waiting = int(self.db.scalar(waiting_statement) or 0)

        latest_recipe_ids = select(
            func.max(models.ProductUGCRecipeDraft.id).label("draft_id")
        ).group_by(models.ProductUGCRecipeDraft.product_id)
        if organization_id is not None:
            latest_recipe_ids = latest_recipe_ids.join(
                models.Product,
                models.Product.id == models.ProductUGCRecipeDraft.product_id,
            ).where(models.Product.organization_id == organization_id)
        latest_recipe_ids = latest_recipe_ids.subquery()
        recipe_reviews_waiting = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.ProductUGCRecipeDraft)
                .where(
                    models.ProductUGCRecipeDraft.id.in_(
                        select(latest_recipe_ids.c.draft_id)
                    ),
                    models.ProductUGCRecipeDraft.human_review_status.in_(
                        ["needs_human_review", "needs_review", "needs_regeneration"]
                    ),
                )
            )
            or 0
        )
        reviews_waiting += recipe_reviews_waiting

        queue_active_statuses = (
            "queued",
            "leased",
            "provider_launching",
            "provider_processing",
            "downloading",
            "retry_wait",
        )
        generation_queue_jobs = self._count(
            models.ProductUGCGenerationJob,
            organization_id=organization_id,
        )
        generation_queue_active = self._count(
            models.ProductUGCGenerationJob,
            models.ProductUGCGenerationJob.status.in_(queue_active_statuses),
            organization_id=organization_id,
        )
        generation_queue_retry_wait = self._count(
            models.ProductUGCGenerationJob,
            models.ProductUGCGenerationJob.status == "retry_wait",
            organization_id=organization_id,
        )
        generation_queue_quarantined = self._count(
            models.ProductUGCGenerationJob,
            models.ProductUGCGenerationJob.status == "quarantined",
            organization_id=organization_id,
        )
        generation_queue_failed = self._count(
            models.ProductUGCGenerationJob,
            models.ProductUGCGenerationJob.status == "failed_terminal",
            organization_id=organization_id,
        )
        latest_queue_ids = (
            select(func.max(models.ProductUGCGenerationJob.id).label("job_id"))
            .join(
                models.ProductUGCRecipeDraft,
                models.ProductUGCRecipeDraft.id == models.ProductUGCGenerationJob.draft_id,
            )
            .group_by(models.ProductUGCRecipeDraft.product_id)
        )
        if organization_id is not None:
            latest_queue_ids = latest_queue_ids.where(
                models.ProductUGCGenerationJob.organization_id == organization_id
            )
        latest_queue_ids = latest_queue_ids.subquery()
        current_queue_filter = models.ProductUGCGenerationJob.id.in_(
            select(latest_queue_ids.c.job_id)
        )
        generation_queue_current_active = self._count(
            models.ProductUGCGenerationJob,
            current_queue_filter,
            models.ProductUGCGenerationJob.status.in_(queue_active_statuses),
            organization_id=organization_id,
        )
        generation_queue_current_quarantined = self._count(
            models.ProductUGCGenerationJob,
            current_queue_filter,
            models.ProductUGCGenerationJob.status == "quarantined",
            organization_id=organization_id,
        )
        generation_queue_current_failed = self._count(
            models.ProductUGCGenerationJob,
            current_queue_filter,
            models.ProductUGCGenerationJob.status == "failed_terminal",
            organization_id=organization_id,
        )

        publishing_tasks = self._count(models.PublishingTask, organization_id=organization_id)
        published_tasks = self._count(
            models.PublishingTask,
            models.PublishingTask.final_url.is_not(None),
            organization_id=organization_id,
        )
        tracking_links = self._count(models.TrackingLink, organization_id=organization_id)
        metric_rows = self._count(models.DestinationPostMetric, organization_id=organization_id)
        connections = self._count(models.DestinationConnection, organization_id=organization_id)
        synced_connections = self._count(
            models.DestinationConnection,
            models.DestinationConnection.last_sync_at.is_not(None),
            models.DestinationConnection.connection_type == "youtube_oauth",
            models.DestinationConnection.status == "connected",
            models.DestinationConnection.auth_status == "oauth_verified",
            organization_id=organization_id,
        )
        payout_entries = self._count(models.PayoutLedgerEntry, organization_id=organization_id)
        payouts_paid = self._count(
            models.PayoutLedgerEntry,
            models.PayoutLedgerEntry.status == "paid",
            organization_id=organization_id,
        )
        payouts_blocked = self._count(
            models.PayoutLedgerEntry,
            or_(
                models.PayoutLedgerEntry.amount <= 0,
                models.PayoutLedgerEntry.reason.like("%\\_blocked:%", escape="\\"),
            ),
            organization_id=organization_id,
        )
        payout_pending_amount = self._sum(
            models.PayoutLedgerEntry.amount,
            models.PayoutLedgerEntry.status.in_(["pending", "approved", "payable"]),
            organization_id=organization_id,
        )
        billing_account = None
        latest_subscription = None
        billing_invoices = 0
        billing_ledger_entries = 0
        billing_charged_minor = 0
        billing_credits_minor = 0
        billing_paid_minor = 0
        billing_balance_minor: int | None = 0
        billing_integrity_errors = 0
        if organization_id is not None:
            billing_account = self.db.scalar(
                select(models.CustomerBillingAccount).where(
                    models.CustomerBillingAccount.organization_id == organization_id
                )
            )
            latest_subscription = self.db.scalar(
                select(models.CustomerBillingSubscriptionState)
                .where(models.CustomerBillingSubscriptionState.organization_id == organization_id)
                .order_by(
                    models.CustomerBillingSubscriptionState.version.desc(),
                    models.CustomerBillingSubscriptionState.id.desc(),
                )
            )
            owned_invoices = self.db.scalars(
                select(models.CustomerInvoice)
                .where(models.CustomerInvoice.organization_id == organization_id)
                .order_by(models.CustomerInvoice.id)
            ).all()
            billing_invoices = len(owned_invoices)
            billing_ledger_entries = self._count(
                models.CustomerBillingLedgerEntry,
                organization_id=organization_id,
            )
            billing_charged_minor = int(
                self._sum(
                    models.CustomerBillingLedgerEntry.amount_minor,
                    models.CustomerBillingLedgerEntry.entry_kind == "charge",
                    organization_id=organization_id,
                )
            )
            billing_credits_minor = int(
                self._sum(
                    models.CustomerBillingLedgerEntry.amount_minor,
                    models.CustomerBillingLedgerEntry.entry_kind == "credit",
                    organization_id=organization_id,
                )
            )
            billing_paid_minor = int(
                self._sum(
                    models.CustomerBillingLedgerEntry.amount_minor,
                    models.CustomerBillingLedgerEntry.entry_kind == "payment",
                    organization_id=organization_id,
                )
            )
            if billing_account is not None:
                validated_balance = 0
                billing_service = CustomerBillingService(self.db)
                for invoice in owned_invoices:
                    try:
                        totals = billing_service.invoice_totals(
                            organization_id=organization_id,
                            billing_account_id=billing_account.id,
                            invoice_id=invoice.id,
                        )
                    except CustomerBillingError:
                        billing_integrity_errors += 1
                        continue
                    validated_balance += totals.balance_minor
                billing_balance_minor = (
                    validated_balance if billing_integrity_errors == 0 else None
                )
        certifications = 0
        if user_profile_id:
            certifications = len(
                NoviceLearningPathService(self.db).verified_certification_codes(
                    user_profile_id=user_profile_id
                )
            )
        listing_scope = (
            (models.MarketplaceListing.organization_id == organization_id,)
            if organization_id
            else ()
        )
        marketplace_listings = self._count(models.MarketplaceListing, *listing_scope)
        verified_listings = self._count(
            models.MarketplaceListing,
            *listing_scope,
            models.MarketplaceListing.status == "verified",
        )
        alias_scope = (
            (models.ListingAlias.organization_id == organization_id,)
            if organization_id
            else ()
        )
        listing_aliases = self._count(models.ListingAlias, *alias_scope)
        wildberries_seller_analytics = WildberriesSellerAnalyticsService(
            self.db
        ).readiness(organization_id=organization_id)

        latest_draft_statement = select(models.ProductUGCRecipeDraft)
        latest_draft_statement = self._scope_statement(
            latest_draft_statement,
            models.ProductUGCRecipeDraft,
            organization_id,
        )
        latest_draft = self.db.scalar(latest_draft_statement.order_by(models.ProductUGCRecipeDraft.id.desc()))
        latest_draft_status = latest_draft.status if latest_draft else "not_started"
        funnel = self._funnel_totals(organization_id=organization_id)
        measurable_cycles_7d = self._measurable_cycles(window_start, organization_id=organization_id)
        journey = self._journey_funnel(window_start, organization_id=organization_id)
        generation_costs = []
        if organization_id is not None:
            generation_costs = [
                {
                    "currency": item.currency,
                    "recognized": round(item.recognized_cost_minor / 100, 2),
                    "estimated": round(item.estimated_cost_minor / 100, 2),
                    "actual_confirmed": round(item.confirmed_actual_cost_minor / 100, 2),
                    "cost_per_generated": (
                        round(float(item.cost_per_generated_video_minor) / 100, 2)
                        if item.cost_per_generated_video_minor is not None
                        else None
                    ),
                    "cost_per_approved": (
                        round(float(item.cost_per_approved_video_minor) / 100, 2)
                        if item.cost_per_approved_video_minor is not None
                        else None
                    ),
                    "priced_videos": item.priced_video_count,
                    "unpriced_generated": item.unpriced_generated_video_count,
                    "unpriced_approved": item.unpriced_approved_video_count,
                    "entry_count": item.effective_entry_count,
                }
                for item in GenerationCostLedgerService(self.db).aggregate(
                    organization_id=organization_id
                )
            ]

        metrics = {
            "products": products,
            "videos": videos,
            "videos_7d": videos_7d,
            "approved_videos": approved_videos,
            "stale_approved_evidence": stale_approved_evidence,
            "reviews_waiting": reviews_waiting,
            "publishing_tasks": publishing_tasks,
            "published_tasks": published_tasks,
            "tracking_links": tracking_links,
            "metric_rows": metric_rows,
            "connections": connections,
            "synced_connections": synced_connections,
            "payout_entries": payout_entries,
            "payouts_paid": payouts_paid,
            "payouts_blocked": payouts_blocked,
            "payout_pending_amount": round(payout_pending_amount, 2),
            "certifications": certifications,
            "marketplace_listings": marketplace_listings,
            "verified_listings": verified_listings,
            "listing_aliases": listing_aliases,
            "wildberries_metric_snapshots": int(
                wildberries_seller_analytics.get("metric_snapshot_count", 0)
            ),
            "wildberries_metric_quarantine": int(
                wildberries_seller_analytics.get("quarantine_count", 0)
            ),
            "latest_draft_status": latest_draft_status,
            "generation_queue_jobs": generation_queue_jobs,
            "generation_queue_active": generation_queue_active,
            "generation_queue_retry_wait": generation_queue_retry_wait,
            "generation_queue_quarantined": generation_queue_quarantined,
            "generation_queue_failed": generation_queue_failed,
            "generation_queue_current_active": generation_queue_current_active,
            "generation_queue_current_quarantined": generation_queue_current_quarantined,
            "generation_queue_current_failed": generation_queue_current_failed,
            "billing_accounts": 1 if billing_account else 0,
            "billing_invoices": billing_invoices,
            "billing_ledger_entries": billing_ledger_entries,
            "billing_balance_minor": billing_balance_minor,
            "billing_integrity_errors": billing_integrity_errors,
            "measurable_cycles_7d": measurable_cycles_7d,
            "events_7d": journey["events_7d"],
            "active_users_7d": journey["active_users_7d"],
            "sessions_7d": journey["sessions_7d"],
            "generation_cost_entries": sum(item["entry_count"] for item in generation_costs),
            **funnel,
        }
        return {
            "north_star": {
                "label": "Измеримые контент-циклы",
                "value": measurable_cycles_7d,
                "period": "за 7 дней",
                "definition": "Одобренный ролик опубликован и получил атрибутированные метрики.",
            },
            "metrics": metrics,
            "journey_funnel": journey["steps"],
            "generation_costs": generation_costs,
            "customer_billing": {
                "configured": billing_account is not None,
                "account_status": billing_account.status if billing_account else "not_configured",
                "currency": billing_account.currency if billing_account else None,
                "subscription_status": latest_subscription.status if latest_subscription else "not_configured",
                "plan_code": latest_subscription.plan_code if latest_subscription else None,
                "invoice_count": billing_invoices,
                "ledger_entry_count": billing_ledger_entries,
                "charged_minor": billing_charged_minor,
                "credits_minor": billing_credits_minor,
                "paid_minor": billing_paid_minor,
                "balance_minor": billing_balance_minor,
                "integrity_status": (
                    "blocked" if billing_integrity_errors else "verified"
                ),
                "integrity_error_count": billing_integrity_errors,
                "external_charges_enabled": False,
            },
            "wildberries_seller_analytics": wildberries_seller_analytics,
            "modules": self._modules(metrics),
        }

    def _measurable_cycles(self, window_start, *, organization_id: int | None) -> int:
        statement = (
            select(models.ContentCycle.id, models.VisualEvidenceSnapshot)
            .select_from(models.ContentCycle)
            .join(
                models.PublishingTask,
                models.PublishingTask.id == models.ContentCycle.publishing_task_id,
            )
            .join(
                models.VideoOutputAcceptance,
                models.VideoOutputAcceptance.id == models.ContentCycle.output_acceptance_id,
            )
            .join(
                models.VisualEvidenceSnapshot,
                models.VisualEvidenceSnapshot.id
                == models.VideoOutputAcceptance.visual_evidence_snapshot_id,
            )
            .join(
                models.TrackingLink,
                (models.TrackingLink.id == models.ContentCycle.tracking_link_id)
                & (models.TrackingLink.publishing_task_id == models.PublishingTask.id),
            )
            .join(
                models.DestinationPostMetric,
                models.DestinationPostMetric.publishing_task_id == models.PublishingTask.id,
            )
            .where(
                models.PublishingTask.final_url.is_not(None),
                models.PublishingTask.updated_at >= window_start,
                models.VideoOutputAcceptance.status == "approved",
                models.VisualEvidenceSnapshot.status == "passed",
                models.DestinationPostMetric.created_at >= window_start,
            )
        )
        if organization_id is not None:
            statement = statement.where(
                models.ContentCycle.organization_id == organization_id
            )

        evidence_service = VisualEvidenceSnapshotService(self.db)
        verified_cycle_ids: set[int] = set()
        for cycle_id, evidence_snapshot in self.db.execute(statement):
            if cycle_id in verified_cycle_ids:
                continue
            try:
                evidence_service.verify_current(evidence_snapshot)
            except (VisualEvidenceSnapshotError, OSError, ValueError):
                continue
            verified_cycle_ids.add(cycle_id)
        return len(verified_cycle_ids)

    def _funnel_totals(self, *, organization_id: int | None) -> dict[str, float | int]:
        metric_rows = self._count(models.DestinationPostMetric, organization_id=organization_id)
        source = models.DestinationPostMetric if metric_rows else models.FunnelSnapshot
        return {
            "views": int(self._sum(source.views, organization_id=organization_id)),
            "clicks": int(self._sum(source.clicks, organization_id=organization_id)),
            "orders": int(self._sum(source.orders, organization_id=organization_id)),
            "revenue": round(self._sum(source.revenue, organization_id=organization_id), 2),
        }

    def _journey_funnel(self, window_start, *, organization_id: int | None) -> dict[str, object]:
        steps = (
            ("product_created", "Товар создан"),
            ("asset_gate_passed", "Фото проверены"),
            ("prompt_ready", "Задание готово"),
            ("generation_succeeded", "Видео создано"),
            ("video_approved", "Видео одобрено"),
            ("publication_completed", "Опубликовано"),
            ("first_metric_attributed", "Получены метрики"),
            ("first_order_attributed", "Получен заказ"),
        )
        base_conditions = [models.FactoryEvent.occurred_at >= window_start]
        if organization_id is not None:
            base_conditions.append(models.FactoryEvent.organization_id == organization_id)
        rows = []
        for event_name, label in steps:
            count = self._count(
                models.FactoryEvent,
                *base_conditions,
                models.FactoryEvent.event_name == event_name,
            )
            rows.append({"event_name": event_name, "label": label, "value": count})
        events_7d = self._count(models.FactoryEvent, *base_conditions)
        active_users_7d = self._distinct_count(
            models.FactoryEvent.user_profile_id,
            *base_conditions,
            model=models.FactoryEvent,
        )
        sessions_7d = self._distinct_count(
            models.FactoryEvent.session_id,
            *base_conditions,
            models.FactoryEvent.session_id.is_not(None),
            model=models.FactoryEvent,
        )
        return {
            "steps": rows,
            "events_7d": events_7d,
            "active_users_7d": active_users_7d,
            "sessions_7d": sessions_7d,
        }

    @staticmethod
    def _modules(metrics: dict[str, object]) -> list[dict[str, object]]:
        draft_status = str(metrics["latest_draft_status"])
        if int(metrics["generation_queue_current_quarantined"]) or int(
            metrics["generation_queue_current_failed"]
        ):
            video_status, video_label = "blocked", "Нужна проверка"
        elif int(metrics["generation_queue_current_active"]):
            video_status, video_label = "in_progress", "В очереди"
        elif draft_status in {"ready_for_paid_preflight", "completed", "approved"}:
            video_status, video_label = "ready", "Готово"
        elif draft_status in {"provider_launching", "processing", "generating"}:
            video_status, video_label = "in_progress", "Создаётся"
        elif draft_status in {"provider_failed", "blocked", "failed"}:
            video_status, video_label = "blocked", "Нужна помощь"
        else:
            video_status, video_label = "not_started", "Не начато"

        review_count = int(metrics["reviews_waiting"])
        if int(metrics["stale_approved_evidence"]):
            quality_status, quality_label = "needs_review", "Доказательства устарели"
        elif review_count:
            quality_status, quality_label = "needs_review", "Ждёт решения"
        elif int(metrics["approved_videos"]):
            quality_status, quality_label = "ready", "Проверено"
        else:
            quality_status, quality_label = "not_started", "Нет роликов"

        published = int(metrics["published_tasks"])
        measured = int(metrics["measurable_cycles_7d"])
        if measured:
            funnel_status, funnel_label = "ready", "Измеряется"
        elif published:
            funnel_status, funnel_label = "needs_attention", "Нужны метрики"
        else:
            funnel_status, funnel_label = "not_started", "Не запущена"

        synced = int(metrics["synced_connections"])
        metric_rows = int(metrics["metric_rows"])
        if synced:
            source_status, source_label = "ready", "Синхронизация есть"
        elif metric_rows:
            source_status, source_label = "manual", "Данные загружены"
        else:
            source_status, source_label = "not_started", "Не подключено"

        payout_entries = int(metrics["payout_entries"])
        cost_entries = int(metrics["generation_cost_entries"])
        billing_entries = int(metrics["billing_ledger_entries"])
        payout_status = "manual" if payout_entries or cost_entries or billing_entries else "planned"
        payout_label = "Учёт ведётся" if payout_entries or cost_entries or billing_entries else "Нужно настроить"
        analytics_status = "ready" if metric_rows else "needs_data"
        analytics_label = "Есть данные" if metric_rows else "Ждёт данных"
        training_status = "ready" if int(metrics["certifications"]) else "not_started"
        training_label = "Пройдено" if int(metrics["certifications"]) else "Начать обучение"
        listing_count = int(metrics["marketplace_listings"])
        alias_count = int(metrics["listing_aliases"])
        if alias_count:
            wb_status, wb_label = "ready", "Связи подтверждены"
        elif listing_count:
            wb_status, wb_label = "in_progress", "Карточки добавлены"
        else:
            wb_status, wb_label = "planned", "Нужно настроить"

        return [
            {
                "number": 1,
                "key": "product",
                "label": "Старт и интерфейс",
                "summary": "Один следующий шаг вместо десятков технических экранов.",
                "status": "ready",
                "status_label": "Работает",
                "url": "/control-room",
                "cta_label": "На главную",
                "metric_value": int(metrics["products"]),
                "metric_label": "товаров в работе",
                "note": "Система ведёт от товара до измеримого результата.",
            },
            {
                "number": 2,
                "key": "video",
                "label": "Генерация видео",
                "summary": "Товар, референсы, идея и безопасный запуск генератора.",
                "status": video_status,
                "status_label": video_label,
                "url": "/mvp-launch",
                "cta_label": "Создать ролик",
                "metric_value": int(metrics["videos"]),
                "metric_label": "роликов создано",
                "note": "Платный запуск всегда требует отдельного подтверждения.",
            },
            {
                "number": 3,
                "key": "video-quality",
                "label": "Качество",
                "summary": "Точный товар, упаковка, сцены и обязательное решение человека.",
                "status": quality_status,
                "status_label": quality_label,
                "url": "/workbench?tab=video-quality",
                "cta_label": "Проверить качество",
                "metric_value": review_count,
                "metric_label": "ждут проверки",
                "note": "Автоматическая оценка не заменяет просмотр готового видео.",
            },
            {
                "number": 4,
                "key": "funnel",
                "label": "Воронка",
                "summary": "Просмотры → переходы → заказы → выручка.",
                "status": funnel_status,
                "status_label": funnel_label,
                "url": "/workbench?tab=funnel",
                "cta_label": "Открыть воронку",
                "metric_value": measured,
                "metric_label": "измеримых циклов за 7 дней",
                "note": "Публикация считается завершённой только с final URL и метриками.",
            },
            {
                "number": 5,
                "key": "sources",
                "label": "Данные из сетей",
                "summary": "Подключения площадок, CSV и контроль свежести данных.",
                "status": source_status,
                "status_label": source_label,
                "url": "/workbench?tab=sources",
                "cta_label": "Подключить данные",
                "metric_value": int(metrics["connections"]),
                "metric_label": "подключений",
                "note": "Неподключённые API честно помечаются и не подменяются fake-данными.",
            },
            {
                "number": 6,
                "key": "payments",
                "label": "Оплата и расходы",
                "summary": "Расходы на генерацию и выплаты участникам раздельно.",
                "status": payout_status,
                "status_label": payout_label,
                "url": "/workbench?tab=payments",
                "cta_label": "Посмотреть расчёты",
                "metric_value": float(metrics["payout_pending_amount"]),
                "metric_label": "₽ ожидают подтверждения",
                "note": "Фактический перевод денег пока выполняется вручную.",
            },
            {
                "number": 7,
                "key": "wb",
                "label": "Артикулы Wildberries",
                "summary": "Основные и подменные артикулы только для ваших карточек.",
                "status": wb_status,
                "status_label": wb_label,
                "url": "/workbench?tab=wb",
                "cta_label": "Посмотреть правила",
                "metric_value": alias_count,
                "metric_label": "связей артикулов",
                "note": "До появления точной модели система не угадывает соответствия SKU.",
            },
            {
                "number": 8,
                "key": "analytics",
                "label": "Аналитика",
                "summary": "Что сработало по товару, ролику, площадке и продажам.",
                "status": analytics_status,
                "status_label": analytics_label,
                "url": "/workbench?tab=analytics",
                "cta_label": "Открыть аналитику",
                "metric_value": int(metrics["orders"]),
                "metric_label": "атрибутированных заказов",
                "note": "Главный показатель — не количество роликов, а измеримый цикл.",
            },
            {
                "number": 9,
                "key": "people",
                "label": "Обучение",
                "summary": "Короткие уроки по ходу работы и проверка навыков.",
                "status": training_status,
                "status_label": training_label,
                "url": "/workbench?tab=people",
                "cta_label": "Перейти к обучению",
                "metric_value": int(metrics["certifications"]),
                "metric_label": "сертификатов",
                "note": "Подсказка появляется там, где пользователь выполняет действие.",
            },
        ]

    def _scope_statement(self, statement, model, organization_id: int | None):
        """Apply the strictest ownership path available for novice-facing metrics.

        Legacy rows without an explicit path to an owned product or destination are
        intentionally invisible in organization mode. They can be claimed or
        migrated explicitly, but are never guessed into a customer's dashboard.
        """

        if organization_id is None:
            return statement
        if model is models.Product:
            return statement.where(models.Product.organization_id == organization_id)
        if model is models.VideoJob:
            return statement.where(models.VideoJob.organization_id == organization_id)
        if model is models.VideoOutputAcceptance:
            return statement.join(
                models.VideoJob,
                models.VideoJob.id == models.VideoOutputAcceptance.video_job_id,
            ).where(models.VideoJob.organization_id == organization_id)
        if model is models.ProductUGCRecipeDraft:
            return statement.join(
                models.Product,
                models.Product.id == models.ProductUGCRecipeDraft.product_id,
            ).where(models.Product.organization_id == organization_id)
        if model is models.ProductUGCGenerationJob:
            return statement.where(
                models.ProductUGCGenerationJob.organization_id == organization_id
            )
        if model is models.PublishingTask:
            return (
                statement.join(
                    models.PublishingPackage,
                    models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
                )
                .join(models.Product, models.Product.id == models.PublishingPackage.product_id)
                .where(models.Product.organization_id == organization_id)
            )
        if model is models.TrackingLink:
            return statement.join(
                models.Product,
                models.Product.id == models.TrackingLink.product_id,
            ).where(models.Product.organization_id == organization_id)
        if model is models.DestinationPostMetric:
            return statement.join(
                models.Product,
                models.Product.id == models.DestinationPostMetric.product_id,
            ).where(models.Product.organization_id == organization_id)
        if model is models.FunnelSnapshot:
            return statement.join(
                models.Product,
                models.Product.id == models.FunnelSnapshot.product_id,
            ).where(models.Product.organization_id == organization_id)
        if model is models.DestinationConnection:
            return statement.join(
                models.PublishingDestination,
                models.PublishingDestination.id == models.DestinationConnection.destination_id,
            ).where(models.PublishingDestination.organization_id == organization_id)
        if model is models.PayoutLedgerEntry:
            return (
                statement.join(
                    models.PublishingTask,
                    models.PublishingTask.id == models.PayoutLedgerEntry.publishing_task_id,
                )
                .join(
                    models.PublishingPackage,
                    models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
                )
                .join(models.Product, models.Product.id == models.PublishingPackage.product_id)
                .where(models.Product.organization_id == organization_id)
            )
        if model is models.MarketplaceListing:
            return statement.where(models.MarketplaceListing.organization_id == organization_id)
        if model is models.ListingAlias:
            return statement.where(models.ListingAlias.organization_id == organization_id)
        if model is models.FactoryEvent:
            return statement.where(models.FactoryEvent.organization_id == organization_id)
        if model is models.CustomerBillingAccount:
            return statement.where(models.CustomerBillingAccount.organization_id == organization_id)
        if model is models.CustomerBillingSubscriptionState:
            return statement.where(
                models.CustomerBillingSubscriptionState.organization_id == organization_id
            )
        if model is models.CustomerInvoice:
            return statement.where(models.CustomerInvoice.organization_id == organization_id)
        if model is models.CustomerBillingLedgerEntry:
            return statement.where(
                models.CustomerBillingLedgerEntry.organization_id == organization_id
            )
        return statement

    def _count(self, model, *conditions, organization_id: int | None = None) -> int:
        statement = select(func.count()).select_from(model)
        statement = self._scope_statement(statement, model, organization_id)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.db.scalar(statement) or 0)

    def _distinct_count(
        self,
        column,
        *conditions,
        model=None,
        organization_id: int | None = None,
    ) -> int:
        source_model = model or column.class_
        statement = select(func.count(func.distinct(column))).select_from(source_model)
        statement = self._scope_statement(statement, source_model, organization_id)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.db.scalar(statement) or 0)

    def _sum(self, column, *conditions, organization_id: int | None = None) -> float:
        source_model = column.class_
        statement = select(func.coalesce(func.sum(column), 0)).select_from(source_model)
        statement = self._scope_statement(statement, source_model, organization_id)
        if conditions:
            statement = statement.where(*conditions)
        return float(self.db.scalar(statement) or 0)
