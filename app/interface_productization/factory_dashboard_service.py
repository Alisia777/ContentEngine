from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.models import utcnow


class FactoryDashboardService:
    """Builds a novice-facing, honest view of the whole content factory."""

    def __init__(self, db: Session):
        self.db = db

    def snapshot(self, *, user_profile_id: int | None = None) -> dict[str, object]:
        window_start = utcnow() - timedelta(days=7)
        products = self._count(models.Product)
        videos = self._count(models.VideoJob)
        videos_7d = self._count(models.VideoJob, models.VideoJob.created_at >= window_start)
        approved_videos = self._distinct_count(
            models.VideoOutputAcceptance.video_job_id,
            models.VideoOutputAcceptance.status == "approved",
        )
        reviews_waiting = self._count(
            models.VideoOutputAcceptance,
            models.VideoOutputAcceptance.status.in_(["needs_human_review", "needs_review"]),
        )
        recipe_reviews_waiting = self._count(
            models.ProductUGCRecipeDraft,
            models.ProductUGCRecipeDraft.human_review_status.in_(["needs_human_review", "needs_review"]),
        )
        reviews_waiting += recipe_reviews_waiting

        publishing_tasks = self._count(models.PublishingTask)
        published_tasks = self._count(models.PublishingTask, models.PublishingTask.final_url.is_not(None))
        tracking_links = self._count(models.TrackingLink)
        metric_rows = self._count(models.DestinationPostMetric)
        connections = self._count(models.DestinationConnection)
        synced_connections = self._count(
            models.DestinationConnection,
            models.DestinationConnection.last_sync_at.is_not(None),
        )
        payout_entries = self._count(models.PayoutLedgerEntry)
        payouts_paid = self._count(models.PayoutLedgerEntry, models.PayoutLedgerEntry.status == "paid")
        payout_pending_amount = self._sum(
            models.PayoutLedgerEntry.amount,
            models.PayoutLedgerEntry.status.in_(["pending", "approved", "payable"]),
        )
        certifications = 0
        if user_profile_id:
            certifications = self._count(
                models.TrainingCertification,
                models.TrainingCertification.user_profile_id == user_profile_id,
                models.TrainingCertification.status == "passed",
            )

        latest_draft = self.db.scalar(
            select(models.ProductUGCRecipeDraft).order_by(models.ProductUGCRecipeDraft.id.desc())
        )
        latest_draft_status = latest_draft.status if latest_draft else "not_started"
        funnel = self._funnel_totals()
        measurable_cycles_7d = self._measurable_cycles(window_start)

        metrics = {
            "products": products,
            "videos": videos,
            "videos_7d": videos_7d,
            "approved_videos": approved_videos,
            "reviews_waiting": reviews_waiting,
            "publishing_tasks": publishing_tasks,
            "published_tasks": published_tasks,
            "tracking_links": tracking_links,
            "metric_rows": metric_rows,
            "connections": connections,
            "synced_connections": synced_connections,
            "payout_entries": payout_entries,
            "payouts_paid": payouts_paid,
            "payout_pending_amount": round(payout_pending_amount, 2),
            "certifications": certifications,
            "latest_draft_status": latest_draft_status,
            "measurable_cycles_7d": measurable_cycles_7d,
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
            "modules": self._modules(metrics),
        }

    def _measurable_cycles(self, window_start) -> int:
        statement = (
            select(func.count(func.distinct(models.PublishingTask.id)))
            .select_from(models.PublishingTask)
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
            )
            .join(
                models.VideoOutputAcceptance,
                models.VideoOutputAcceptance.video_job_id == models.PublishingPackage.video_job_id,
            )
            .join(
                models.DestinationPostMetric,
                models.DestinationPostMetric.publishing_task_id == models.PublishingTask.id,
            )
            .where(
                models.PublishingTask.final_url.is_not(None),
                models.PublishingTask.updated_at >= window_start,
                models.VideoOutputAcceptance.status == "approved",
            )
        )
        return int(self.db.scalar(statement) or 0)

    def _funnel_totals(self) -> dict[str, float | int]:
        metric_rows = self._count(models.DestinationPostMetric)
        source = models.DestinationPostMetric if metric_rows else models.FunnelSnapshot
        return {
            "views": int(self._sum(source.views)),
            "clicks": int(self._sum(source.clicks)),
            "orders": int(self._sum(source.orders)),
            "revenue": round(self._sum(source.revenue), 2),
        }

    @staticmethod
    def _modules(metrics: dict[str, object]) -> list[dict[str, object]]:
        draft_status = str(metrics["latest_draft_status"])
        if draft_status in {"ready_for_paid_preflight", "completed", "approved"}:
            video_status, video_label = "ready", "Готово"
        elif draft_status in {"provider_launching", "processing", "generating"}:
            video_status, video_label = "in_progress", "Создаётся"
        elif draft_status in {"provider_failed", "blocked", "failed"}:
            video_status, video_label = "blocked", "Нужна помощь"
        else:
            video_status, video_label = "not_started", "Не начато"

        review_count = int(metrics["reviews_waiting"])
        if review_count:
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
        payout_status = "manual" if payout_entries else "planned"
        payout_label = "Ручной расчёт" if payout_entries else "Нужно настроить"
        analytics_status = "ready" if metric_rows else "needs_data"
        analytics_label = "Есть данные" if metric_rows else "Ждёт данных"
        training_status = "ready" if int(metrics["certifications"]) else "not_started"
        training_label = "Пройдено" if int(metrics["certifications"]) else "Начать обучение"

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
                "status": "planned",
                "status_label": "Нужно настроить",
                "url": "/workbench?tab=wb",
                "cta_label": "Посмотреть правила",
                "metric_value": 0,
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

    def _count(self, model, *conditions) -> int:
        statement = select(func.count()).select_from(model)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.db.scalar(statement) or 0)

    def _distinct_count(self, column, *conditions) -> int:
        statement = select(func.count(func.distinct(column)))
        if conditions:
            statement = statement.where(*conditions)
        return int(self.db.scalar(statement) or 0)

    def _sum(self, column, *conditions) -> float:
        statement = select(func.coalesce(func.sum(column), 0))
        if conditions:
            statement = statement.where(*conditions)
        return float(self.db.scalar(statement) or 0)
