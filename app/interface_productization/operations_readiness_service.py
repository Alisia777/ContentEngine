from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.customer_billing import CustomerBillingError, CustomerBillingService
from app.metrics_intake.official_connectors import (
    IMPLEMENTED_OFFICIAL_CONNECTORS,
    OfficialConnectorGateway,
)
from app.metrics_intake.platform_matrix import PlatformMetricsMatrix
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.system_tools import media_binary_readiness
from app.visual_evidence import LocalTesseractOCR
from app.wildberries_analytics import WildberriesSellerAnalyticsService


DISPLAY_PLATFORMS = (
    ("youtube", "YouTube"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("telegram", "Telegram"),
    ("vk", "VK"),
    ("wb", "Wildberries"),
)


class OperationsReadinessService:
    """Secret-free novice setup picture for every external capability."""

    def __init__(
        self,
        db: Session,
        *,
        connector_gateway: OfficialConnectorGateway | None = None,
        queue_service: ProductUGCGenerationQueueService | None = None,
        ocr_backend: LocalTesseractOCR | None = None,
        media_probe: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self.db = db
        self.connector_gateway = connector_gateway or OfficialConnectorGateway(db)
        self.queue_service = queue_service or ProductUGCGenerationQueueService(db)
        self.ocr_backend = ocr_backend or LocalTesseractOCR()
        self.media_probe = media_probe or media_binary_readiness

    def snapshot(self, *, organization_id: int) -> dict[str, object]:
        if isinstance(organization_id, bool) or organization_id <= 0:
            raise ValueError("organization_id must be a positive integer")
        cards = [
            self._media_quality_card(),
            self._worker_card(organization_id),
            self._connector_card(organization_id),
            self._billing_card(organization_id),
        ]
        recommended_action = next(
            (
                card["action"]
                for card in cards
                if card["status"] == "action_required" and card.get("action")
            ),
            None,
        )
        ready_count = sum(card["status"] == "ready" for card in cards)
        return {
            "schema_version": 1,
            "status": "ready" if ready_count == len(cards) else "action_required",
            "ready_count": ready_count,
            "total_count": len(cards),
            "summary": (
                "Все внешние контуры готовы к работе."
                if ready_count == len(cards)
                else f"Готово {ready_count} из {len(cards)} внешних контуров."
            ),
            "recommended_action": recommended_action,
            "cards": cards,
        }

    def _media_quality_card(self) -> dict[str, object]:
        media = self.media_probe()
        ocr = self.ocr_backend.readiness(required_languages=("rus", "eng"))
        checks = [
            self._check(
                "ffmpeg",
                "FFmpeg декодирует настоящее видео",
                bool(media.get("ffmpeg_ready")),
                (
                    "кадры можно извлекать из MP4 · источник: "
                    + str(media.get("ffmpeg_configuration", "path"))
                    if media.get("ffmpeg_ready")
                    else "задайте QVF_FFMPEG_PATH или добавьте ffmpeg в PATH"
                ),
            ),
            self._check(
                "ffprobe",
                "FFprobe читает длительность ролика",
                bool(media.get("ffprobe_ready")),
                (
                    "длительность проверяется до извлечения"
                    if media.get("ffprobe_ready")
                    else "задайте QVF_FFPROBE_PATH или положите ffprobe рядом с ffmpeg"
                ),
            ),
            self._check(
                "tesseract",
                "Tesseract запускается локально",
                bool(ocr.get("binary_ready")),
                (
                    "OCR работает локально · источник: "
                    + str(ocr.get("configuration", "path"))
                    if ocr.get("binary_ready")
                    else "задайте QVF_TESSERACT_PATH или добавьте tesseract в PATH"
                ),
            ),
            self._check(
                "ocr_languages",
                "Установлены языки упаковки rus + eng",
                bool(ocr.get("ready")),
                "языковые пакеты найдены"
                if ocr.get("ready")
                else self._missing_language_detail(ocr),
            ),
        ]
        ready = all(bool(check["ready"]) for check in checks)
        return {
            "key": "media_quality",
            "title": "Видео и OCR",
            "status": "ready" if ready else "action_required",
            "status_label": "готово" if ready else "нужна настройка",
            "summary": (
                "Настоящие кадры и надписи упаковки можно проверять локально."
                if ready
                else "Подключите локальные инструменты — без них качество остаётся закрыто."
            ),
            "checks": checks,
            "configuration": {
                "ffmpeg": media.get("ffmpeg_configuration", "path"),
                "ffprobe": media.get("ffprobe_configuration", "path"),
                "tesseract": ocr.get("configuration", "path"),
                "tessdata_configured_explicitly": bool(
                    ocr.get("tessdata_configured_explicitly")
                ),
                "tessdata_directory_ready": ocr.get("tessdata_directory_ready"),
            },
            "setup_steps": [
                "Установите FFmpeg вместе с FFprobe и Tesseract с языками rus + eng.",
                "Задайте QVF_FFMPEG_PATH, QVF_FFPROBE_PATH и QVF_TESSERACT_PATH, если сервис не видит системный PATH.",
                "Для своего каталога traineddata задайте QVF_TESSDATA_PREFIX.",
                "Перезапустите приложение и вернитесь к проверке качества.",
            ],
            "boundary": "Синтетические кадры и OCR без найденного Tesseract не открывают одобрение.",
            "action": self._media_action(media, ocr) if not ready else None,
        }

    def _worker_card(self, organization_id: int) -> dict[str, object]:
        health = self.queue_service.operational_health(
            organization_id=organization_id
        )
        checks = [
            self._check(
                "supervised_heartbeat",
                "Supervisor подтверждает живой worker",
                bool(health["worker_ready"]),
                (
                    "heartbeat: " + str(health["last_heartbeat_at"])
                    if health["worker_ready"]
                    else "запустите отдельный product-ugc-worker под supervisor"
                ),
            ),
            self._check(
                "stale_leases",
                "Нет зависших задач",
                int(health["stale_leases"]) == 0,
                f"просроченных lease: {health['stale_leases']}",
            ),
            self._check(
                "queue_lag",
                "Очередь не просрочена",
                int(health["queue_lag_seconds"])
                <= int(health["healthy_within_seconds"]),
                f"задержка: {health['queue_lag_seconds']} сек.",
            ),
        ]
        ready = all(bool(check["ready"]) for check in checks)
        return {
            "key": "generation_worker",
            "title": "Платная генерация",
            "status": "ready" if ready else "action_required",
            "status_label": "worker на связи" if ready else "worker не подтверждён",
            "summary": (
                "Очередь обслуживается отдельным supervised worker."
                if ready
                else "Задачи сохраняются, но обещать платный запуск пока нельзя."
            ),
            "checks": checks,
            "operations": health,
            "setup_steps": [
                "Запустите: docker compose up -d product-ugc-worker.",
                "Проверьте: docker compose ps.",
                "Дождитесь свежего heartbeat — статус обновится автоматически.",
            ],
            "boundary": "Веб-процесс не считается supervisor и не подменяет постоянный worker.",
            "action": {
                "key": "start_supervised_worker",
                "label": "Запустить worker генерации",
                "detail": "Поднимите product-ugc-worker и дождитесь свежего heartbeat.",
                "url": "/workbench?tab=video#operations-readiness",
            }
            if not ready
            else None,
        }

    def _connector_card(self, organization_id: int) -> dict[str, object]:
        catalog_by_platform = {
            str(item["platform"]): item for item in self.connector_gateway.catalog()
        }
        destinations = self.db.scalars(
            select(models.PublishingDestination).where(
                models.PublishingDestination.organization_id == organization_id
            )
        ).all()
        destinations_by_platform: dict[str, list[models.PublishingDestination]] = {}
        for destination in destinations:
            platform = PlatformMetricsMatrix.normalize_platform(destination.platform)
            destinations_by_platform.setdefault(platform, []).append(destination)

        published_platforms = self.db.scalars(
            select(models.PublishingDestination.platform)
            .join(
                models.ContentCycle,
                models.ContentCycle.destination_id == models.PublishingDestination.id,
            )
            .join(
                models.PublishingTask,
                models.PublishingTask.id == models.ContentCycle.publishing_task_id,
            )
            .where(
                models.ContentCycle.organization_id == organization_id,
                models.PublishingTask.final_url.is_not(None),
            )
        ).all()
        published_normalized = {
            PlatformMetricsMatrix.normalize_platform(platform)
            for platform in published_platforms
        }
        wb_readiness = WildberriesSellerAnalyticsService(self.db).readiness(
            organization_id=organization_id
        )

        platforms: list[dict[str, object]] = []
        official_cards: list[dict[str, object]] = []
        for platform, label in DISPLAY_PLATFORMS:
            if platform == "wb":
                setup_state = (
                    "ready"
                    if wb_readiness["ready"]
                    else "code_ready"
                    if not wb_readiness["connection_count"]
                    else "needs_credentials"
                    if wb_readiness["credential_reference_status"]
                    in {"missing", "configured_but_unavailable"}
                    else str(wb_readiness["status"])
                )
                wb_row = {
                    "key": "wb",
                    "label": "Wildberries",
                    "mode": "official_api",
                    "implemented_connector_types": wb_readiness[
                        "implemented_connector_types"
                    ],
                    "adapter_status": "code_ready",
                    "setup_status": setup_state,
                    "adapter": {
                        "display_name": wb_readiness["label"],
                        "endpoint": wb_readiness["endpoint"],
                        "auth_scheme": wb_readiness["auth_scheme"],
                    },
                    "status": "ready"
                    if wb_readiness["ready"]
                    else "action_required",
                    "status_label": wb_readiness["status_label"],
                    "destination_count": wb_readiness["connection_count"],
                    "ready_destination_count": sum(
                        bool(connection["ready"])
                        for connection in wb_readiness["connections"]
                    ),
                    "published_cycle_available": bool(
                        wb_readiness["verified_listing_count"]
                    ),
                    "credential_reference_status": wb_readiness[
                        "credential_reference_status"
                    ],
                    "last_sync_at": wb_readiness["last_sync_at"],
                    "fallbacks": PlatformMetricsMatrix.config("wb").fallback_source_types,
                    "destinations": wb_readiness["connections"],
                    "metric_snapshot_count": wb_readiness["metric_snapshot_count"],
                    "quarantine_count": wb_readiness["quarantine_count"],
                }
                platforms.append(wb_row)
                official_cards.append(wb_row)
                continue
            owned = destinations_by_platform.get(platform, [])
            implemented_types = sorted(
                IMPLEMENTED_OFFICIAL_CONNECTORS.get(platform, set())
            )
            config = PlatformMetricsMatrix.config(platform)
            readiness_rows = [
                {
                    **self.connector_gateway.readiness(
                        destination.id,
                        organization_id=organization_id,
                    ),
                    "destination_name": destination.name,
                }
                for destination in owned
            ]
            if implemented_types:
                ready_destination_count = sum(
                    bool(readiness.get("ready")) for readiness in readiness_rows
                )
                official_ready = bool(readiness_rows) and ready_destination_count == len(
                    readiness_rows
                )
                last_sync_at = max(
                    (
                        str(readiness["last_sync_at"])
                        for readiness in readiness_rows
                        if readiness.get("last_sync_at")
                    ),
                    default=None,
                )
                credential_status = self._credential_status(readiness_rows)
                setup_state = self._official_setup_state(
                    readiness_rows,
                    credential_status=credential_status,
                )
                state = "ready" if official_ready else "action_required"
                status_label = {
                    "ready": "официальный API готов",
                    "code_ready": "код готов · нужна площадка",
                    "needs_connection": "код готов · нужно подключение",
                    "needs_credentials": "нужны credentials",
                    "needs_verification": "нужно проверить OAuth",
                }.get(setup_state, "нужна настройка API")
                mode = "official_api"
            else:
                ready_destination_count = 0
                last_sync_at = None
                credential_status = "not_required"
                setup_state = "manual_ready"
                state = "manual_ready"
                status_label = "ручной/CSV импорт готов"
                mode = "manual_csv"
            row = {
                "key": platform,
                "label": label,
                "mode": mode,
                "implemented_connector_types": implemented_types,
                "adapter_status": "code_ready" if implemented_types else "manual_only",
                "setup_status": setup_state,
                "adapter": catalog_by_platform.get(platform),
                "status": state,
                "status_label": status_label,
                "destination_count": len(owned),
                "ready_destination_count": ready_destination_count,
                "published_cycle_available": platform in published_normalized,
                "credential_reference_status": credential_status,
                "last_sync_at": last_sync_at,
                "fallbacks": config.fallback_source_types,
                "destinations": readiness_rows,
            }
            platforms.append(row)
            if implemented_types:
                official_cards.append(row)

        official_ready = bool(official_cards) and all(
            card["status"] == "ready" for card in official_cards
        )
        official_labels = ", ".join(str(card["label"]) for card in official_cards)
        manual_labels = ", ".join(
            str(card["label"])
            for card in platforms
            if card["mode"] == "manual_csv"
        )
        return {
            "key": "social_connectors",
            "title": "Данные из сетей",
            "status": "ready" if official_ready else "action_required",
            "status_label": "API подключены" if official_ready else "есть шаг настройки",
            "summary": (
                f"Официальные API ({official_labels}) проверены; ручной/CSV путь остаётся доступным."
                if official_ready
                else f"Официальная настройка: {official_labels or 'нет доступных адаптеров'}. Ручной/CSV импорт: {manual_labels or 'не требуется'}."
            ),
            "checks": [
                self._check(
                    str(card["key"]),
                    f"{card['label']}: {card['status_label']}",
                    card["status"] in {"ready", "manual_ready"},
                    (
                        "последняя синхронизация: " + str(card["last_sync_at"])
                        if card["last_sync_at"]
                        else "данные ещё не синхронизировались"
                        if card["mode"] == "official_api"
                        else "доступны manual/CSV и tracking-ссылки"
                    ),
                )
                for card in platforms
            ],
            "platforms": platforms,
            "setup_steps": [
                "Добавьте свою площадку и сохраните final URL опубликованного ролика.",
                "Для официального API сохраните только имя credential reference, не токен.",
                "Запустите проверку OAuth; для manual/CSV внесите накопительный снимок.",
            ],
            "boundary": "Ручной импорт не выдаётся за официальный API; fake-метрики запрещены.",
            "action": self._connector_action(official_cards),
        }

    def _billing_card(self, organization_id: int) -> dict[str, object]:
        account = self.db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == organization_id
            )
        )
        subscription = self.db.scalar(
            select(models.CustomerBillingSubscriptionState)
            .where(
                models.CustomerBillingSubscriptionState.organization_id
                == organization_id
            )
            .order_by(
                models.CustomerBillingSubscriptionState.version.desc(),
                models.CustomerBillingSubscriptionState.id.desc(),
            )
        )
        integrity_errors = 0
        if account is not None:
            invoices = self.db.scalars(
                select(models.CustomerInvoice).where(
                    models.CustomerInvoice.organization_id == organization_id,
                    models.CustomerInvoice.billing_account_id == account.id,
                )
            ).all()
            service = CustomerBillingService(self.db)
            for invoice in invoices:
                try:
                    service.invoice_totals(
                        organization_id=organization_id,
                        billing_account_id=account.id,
                        invoice_id=invoice.id,
                    )
                except CustomerBillingError:
                    integrity_errors += 1
        checks = [
            self._check(
                "ledger_account",
                "Учётный счёт создан",
                account is not None,
                "валюта зафиксирована" if account else "создайте счёт организации",
            ),
            self._check(
                "subscription",
                "Тариф зафиксирован",
                subscription is not None,
                f"статус: {subscription.status}"
                if subscription
                else "задайте тариф и период",
            ),
            self._check(
                "ledger_integrity",
                "Журнал проходит проверку",
                integrity_errors == 0,
                "ошибок нет"
                if integrity_errors == 0
                else f"ошибок: {integrity_errors}",
            ),
            {
                "key": "acquiring_boundary",
                "label": "Банковский платёж",
                "ready": True,
                "status": "external",
                "detail": "принимается вне системы и затем сверяется по reference",
            },
        ]
        ready = account is not None and subscription is not None and not integrity_errors
        return {
            "key": "customer_billing",
            "title": "Счета и оплата",
            "status": "ready" if ready else "action_required",
            "status_label": "учёт готов" if ready else "завершите настройку",
            "summary": (
                "Счета, начисления и внешние оплаты сверяются по неизменяемому журналу."
                if ready
                else "Настройте счёт и тариф; банковские деньги останутся во внешнем провайдере."
            ),
            "checks": checks,
            "external_acquiring_enabled": False,
            "payment_recording_mode": "external_reconciliation",
            "setup_steps": [
                "Создайте учётный счёт и выберите валюту.",
                "Зафиксируйте тариф без банковского списания.",
                "После поступления денег добавьте внешний transaction reference.",
            ],
            "boundary": "Интерфейс не списывает, не переводит и не возвращает банковские деньги.",
            "action": {
                "key": "configure_billing",
                "label": "Настроить клиентский учёт",
                "detail": "Создайте счёт и тариф; эквайринг останется внешним контуром.",
                "url": "/workbench?tab=payments#operations-readiness",
            }
            if not ready
            else None,
        }

    @staticmethod
    def _check(key: str, label: str, ready: bool, detail: str) -> dict[str, object]:
        return {
            "key": key,
            "label": label,
            "ready": ready,
            "status": "ready" if ready else "action_required",
            "detail": detail,
        }

    @staticmethod
    def _missing_language_detail(ocr: dict[str, object]) -> str:
        missing = [str(item) for item in ocr.get("missing_languages", [])]
        if missing:
            prefix_hint = (
                "; каталог QVF_TESSDATA_PREFIX недоступен"
                if ocr.get("tessdata_configured_explicitly")
                and ocr.get("tessdata_directory_ready") is False
                else "; можно использовать QVF_TESSDATA_PREFIX"
            )
            return "добавьте языковые пакеты: " + ", ".join(missing) + prefix_hint
        return "не удалось проверить список языков Tesseract"

    @staticmethod
    def _media_action(
        media: dict[str, object],
        ocr: dict[str, object],
    ) -> dict[str, str]:
        if not media.get("ffmpeg_ready") or not media.get("ffprobe_ready"):
            label = "Подключить FFmpeg и FFprobe"
            detail = "Укажите QVF_FFMPEG_PATH и QVF_FFPROBE_PATH, затем перезапустите приложение."
        elif not ocr.get("binary_ready"):
            label = "Подключить Tesseract"
            detail = "Укажите QVF_TESSERACT_PATH и перезапустите приложение."
        else:
            missing = ", ".join(str(item) for item in ocr.get("missing_languages", []))
            label = "Добавить языки OCR"
            detail = (
                f"Добавьте traineddata ({missing or 'rus, eng'}) в каталог "
                "QVF_TESSDATA_PREFIX и повторите проверку."
            )
        return {
            "key": "configure_media_tools",
            "label": label,
            "detail": detail,
            "url": "/workbench?tab=video-quality#operations-readiness",
        }

    @staticmethod
    def _credential_status(rows: list[dict[str, object]]) -> str:
        statuses = {
            str(row.get("credential_reference_status") or "missing") for row in rows
        }
        if "available" in statuses:
            return "available"
        if "configured_but_unavailable" in statuses:
            return "configured_but_unavailable"
        return "missing"

    @staticmethod
    def _official_setup_state(
        rows: list[dict[str, object]],
        *,
        credential_status: str,
    ) -> str:
        if not rows:
            return "code_ready"
        if all(bool(row.get("ready")) for row in rows):
            return "ready"
        if all(str(row.get("status")) == "needs_connection" for row in rows):
            return "needs_connection"
        if credential_status in {"missing", "configured_but_unavailable"}:
            return "needs_credentials"
        if credential_status == "available":
            return "needs_verification"
        return "action_required"

    @staticmethod
    def _connector_action(
        official_cards: list[dict[str, object]],
    ) -> dict[str, str] | None:
        pending = next(
            (card for card in official_cards if card["status"] != "ready"), None
        )
        if pending is None:
            return None
        label = str(pending["label"])
        if pending["key"] == "wb":
            return {
                "key": "configure_official_connector",
                "label": "Настроить WB Seller Analytics",
                "detail": "Подтвердите nmID, сохраните ссылку на API-ключ и выполните первую синхронизацию.",
                "url": "/workbench?tab=wb#wb-seller-analytics",
            }
        if int(pending["destination_count"]) == 0:
            action_label = f"Подготовить площадку {label}"
            detail = f"Добавьте площадку {label}, опубликуйте ролик и сохраните final URL."
            url = "/workbench?tab=funnel#operations-readiness"
        elif not bool(pending["published_cycle_available"]):
            action_label = f"Завершить публикацию {label}"
            detail = f"Сохраните final URL реальной публикации {label}; затем настройте API."
            url = "/workbench?tab=funnel#operations-readiness"
        elif pending["credential_reference_status"] == "configured_but_unavailable":
            action_label = f"Активировать OAuth {label}"
            detail = "Добавьте OAuth-токен в указанную переменную окружения и перезапустите deployment."
            url = "/workbench?tab=sources#operations-readiness"
        elif pending["credential_reference_status"] == "available":
            action_label = f"Проверить OAuth {label}"
            detail = "Запустите официальный запрос: успешный ответ запишет last sync."
            url = "/workbench?tab=sources#operations-readiness"
        else:
            action_label = f"Подключить API {label}"
            detail = "Сохраните имя переменной окружения с OAuth-токеном; секрет в базу не попадёт."
            url = "/workbench?tab=sources#operations-readiness"
        return {
            "key": "configure_official_connector",
            "label": action_label,
            "detail": detail,
            "url": url,
        }
