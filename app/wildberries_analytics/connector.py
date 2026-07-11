from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any, Protocol

import httpx

from app.destination_connectors.credential_status import (
    CredentialResolver,
    EnvironmentCredentialResolver,
)
from app.wildberries_analytics.errors import (
    WildberriesAnalyticsConfigurationError,
    WildberriesAnalyticsPeriodError,
    WildberriesAnalyticsResponseError,
    WildberriesAnalyticsTransportError,
)
from app.wildberries_analytics.types import (
    WildberriesCollection,
    WildberriesHistoryMetric,
)


WILDBERRIES_HISTORY_ENDPOINT = (
    "https://seller-analytics-api.wildberries.ru/api/analytics/v3/"
    "sales-funnel/products/history"
)
WILDBERRIES_AUTH_SCHEME = "HeaderApiKey"
MAX_PERIOD_DAYS = 7
MAX_NM_IDS_PER_PAGE = 20
MAX_NM_IDS_TOTAL = 1000
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DATABASE_INTEGER = 9_223_372_036_854_775_807

_HISTORY_KEYS = {
    "date",
    "openCount",
    "cartCount",
    "orderCount",
    "orderSum",
    "buyoutCount",
    "buyoutSum",
    "buyoutPercent",
    "addToCartPercent",
    "cartToOrderPercent",
}


class WildberriesSellerAnalyticsHttpGateway(Protocol):
    def post_product_history(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
    ) -> dict[str, Any]: ...


class HttpxWildberriesSellerAnalyticsGateway:
    """Production HTTP gateway; tests inject a fake and never call the network."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ):
        self.client = client
        self.timeout_seconds = timeout_seconds

    def post_product_history(
        self,
        *,
        api_key: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(api_key, str) or not api_key.strip():
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_credential_reference_unresolved"
            )
        try:
            if self.client is not None:
                response = self.client.post(
                    WILDBERRIES_HISTORY_ENDPOINT,
                    headers={"Authorization": api_key, "Content-Type": "application/json"},
                    json=body,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = client.post(
                        WILDBERRIES_HISTORY_ENDPOINT,
                        headers={"Authorization": api_key, "Content-Type": "application/json"},
                        json=body,
                    )
        except httpx.HTTPError as exc:
            raise WildberriesAnalyticsTransportError(
                "wildberries_official_api_transport_failed"
            ) from exc

        if response.status_code in {401, 403}:
            raise WildberriesAnalyticsTransportError(
                "wildberries_official_api_auth_rejected"
            )
        if response.status_code == 429:
            raise WildberriesAnalyticsTransportError(
                "wildberries_official_api_rate_limited"
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise WildberriesAnalyticsTransportError(
                "wildberries_official_api_http_error"
            )
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise WildberriesAnalyticsResponseError(
                "wildberries_official_api_response_too_large"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise WildberriesAnalyticsResponseError(
                "wildberries_official_api_json_invalid"
            ) from exc
        if not isinstance(payload, dict):
            raise WildberriesAnalyticsResponseError(
                "wildberries_official_api_payload_invalid"
            )
        return payload


class WildberriesSellerAnalyticsConnector:
    def __init__(
        self,
        *,
        credential_resolver: CredentialResolver | None = None,
        http_gateway: WildberriesSellerAnalyticsHttpGateway | None = None,
    ):
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.http_gateway = http_gateway or HttpxWildberriesSellerAnalyticsGateway()

    @staticmethod
    def validate_period(period_start: date, period_end: date) -> None:
        if type(period_start) is not date or type(period_end) is not date:
            raise WildberriesAnalyticsPeriodError("wildberries_period_dates_required")
        if period_end < period_start:
            raise WildberriesAnalyticsPeriodError(
                "wildberries_period_end_precedes_start"
            )
        if (period_end - period_start).days + 1 > MAX_PERIOD_DAYS:
            raise WildberriesAnalyticsPeriodError(
                "wildberries_period_exceeds_seven_days"
            )

    @classmethod
    def request_bodies(
        cls,
        *,
        period_start: date,
        period_end: date,
        nm_ids: list[str],
    ) -> tuple[dict[str, Any], ...]:
        cls.validate_period(period_start, period_end)
        normalized: list[int] = []
        for raw_nm_id in nm_ids:
            value = str(raw_nm_id or "").strip()
            if not value.isdigit() or len(value) > 64 or int(value) <= 0:
                raise WildberriesAnalyticsConfigurationError(
                    "wildberries_owned_nm_id_invalid"
                )
            normalized.append(int(value))
        normalized = sorted(set(normalized))
        if not normalized:
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_verified_owned_nm_ids_required"
            )
        if len(normalized) > MAX_NM_IDS_TOTAL:
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_owned_nm_id_limit_exceeded"
            )
        bodies: list[dict[str, Any]] = []
        for offset in range(0, len(normalized), MAX_NM_IDS_PER_PAGE):
            page = normalized[offset : offset + MAX_NM_IDS_PER_PAGE]
            bodies.append(
                {
                    "selectedPeriod": {
                        "start": period_start.isoformat(),
                        "end": period_end.isoformat(),
                    },
                    "nmIds": page,
                    "skipDeletedNm": True,
                }
            )
        return tuple(bodies)

    def collect(
        self,
        *,
        credential_ref: str,
        period_start: date,
        period_end: date,
        nm_ids: list[str],
    ) -> WildberriesCollection:
        bodies = self.request_bodies(
            period_start=period_start,
            period_end=period_end,
            nm_ids=nm_ids,
        )
        try:
            api_key = self.credential_resolver.resolve(credential_ref)
        except Exception as exc:
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_credential_resolution_failed"
            ) from exc
        if not api_key:
            raise WildberriesAnalyticsConfigurationError(
                "wildberries_credential_reference_unresolved"
            )

        responses: list[dict[str, Any]] = []
        metrics: list[WildberriesHistoryMetric] = []
        response_product_count = 0
        for body in bodies:
            payload = self.http_gateway.post_product_history(
                api_key=api_key,
                body=body,
            )
            page_metrics, product_count = self._normalize_response(
                payload,
                period_start=period_start,
                period_end=period_end,
            )
            responses.append(payload)
            metrics.extend(page_metrics)
            response_product_count += product_count
        return WildberriesCollection(
            request_bodies=bodies,
            response_payloads=tuple(responses),
            metrics=tuple(metrics),
            response_product_count=response_product_count,
        )

    @classmethod
    def _normalize_response(
        cls,
        payload: dict[str, Any],
        *,
        period_start: date,
        period_end: date,
    ) -> tuple[list[WildberriesHistoryMetric], int]:
        if not isinstance(payload, dict) or set(payload) != {"data"}:
            raise WildberriesAnalyticsResponseError(
                "wildberries_official_api_envelope_invalid"
            )
        products = payload.get("data")
        if not isinstance(products, list):
            raise WildberriesAnalyticsResponseError(
                "wildberries_official_api_data_invalid"
            )

        seen_products: set[str] = set()
        metrics: list[WildberriesHistoryMetric] = []
        for product_row in products:
            if not isinstance(product_row, dict) or set(product_row) != {"product", "history"}:
                raise WildberriesAnalyticsResponseError(
                    "wildberries_official_api_product_row_invalid"
                )
            product = product_row.get("product")
            history = product_row.get("history")
            if not isinstance(product, dict) or not isinstance(history, list):
                raise WildberriesAnalyticsResponseError(
                    "wildberries_official_api_product_history_invalid"
                )
            nm_id_value = product.get("nmId")
            if (
                isinstance(nm_id_value, bool)
                or not isinstance(nm_id_value, int)
                or nm_id_value <= 0
                or len(str(nm_id_value)) > 64
            ):
                raise WildberriesAnalyticsResponseError(
                    "wildberries_official_api_nm_id_invalid"
                )
            nm_id = str(nm_id_value)
            if nm_id in seen_products:
                raise WildberriesAnalyticsResponseError(
                    "wildberries_official_api_duplicate_nm_id"
                )
            seen_products.add(nm_id)

            seen_dates: set[date] = set()
            for history_row in history:
                if not isinstance(history_row, dict) or set(history_row) != _HISTORY_KEYS:
                    raise WildberriesAnalyticsResponseError(
                        "wildberries_official_api_history_row_invalid"
                    )
                raw_date = history_row.get("date")
                if not isinstance(raw_date, str):
                    raise WildberriesAnalyticsResponseError(
                        "wildberries_official_api_history_date_invalid"
                    )
                try:
                    metric_date = date.fromisoformat(raw_date)
                except ValueError as exc:
                    raise WildberriesAnalyticsResponseError(
                        "wildberries_official_api_history_date_invalid"
                    ) from exc
                if (
                    metric_date < period_start
                    or metric_date > period_end
                    or metric_date in seen_dates
                ):
                    raise WildberriesAnalyticsResponseError(
                        "wildberries_official_api_history_period_invalid"
                    )
                seen_dates.add(metric_date)
                metrics.append(
                    WildberriesHistoryMetric(
                        nm_id=nm_id,
                        metric_date=metric_date,
                        open_count=cls._integer(history_row["openCount"], "openCount"),
                        cart_count=cls._integer(history_row["cartCount"], "cartCount"),
                        order_count=cls._integer(history_row["orderCount"], "orderCount"),
                        order_sum_minor=cls._money_minor(history_row["orderSum"], "orderSum"),
                        buyout_count=cls._integer(history_row["buyoutCount"], "buyoutCount"),
                        buyout_sum_minor=cls._money_minor(history_row["buyoutSum"], "buyoutSum"),
                        buyout_percent=cls._percentage(history_row["buyoutPercent"], "buyoutPercent"),
                        add_to_cart_percent=cls._percentage(
                            history_row["addToCartPercent"], "addToCartPercent"
                        ),
                        cart_to_order_percent=cls._percentage(
                            history_row["cartToOrderPercent"], "cartToOrderPercent"
                        ),
                        product_json=dict(product),
                        history_json=dict(history_row),
                    )
                )
        return metrics, len(products)

    @staticmethod
    def _field_code(field: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", field).lower()

    @staticmethod
    def _number(value: Any, field: str) -> float:
        field_code = WildberriesSellerAnalyticsConnector._field_code(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            )
        try:
            number = float(value)
        except (OverflowError, ValueError) as exc:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            ) from exc
        if not math.isfinite(number) or number < 0:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            )
        return number

    @classmethod
    def _integer(cls, value: Any, field: str) -> int:
        number = cls._number(value, field)
        if int(number) != number:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{cls._field_code(field)}_invalid"
            )
        result = int(number)
        if result > MAX_DATABASE_INTEGER:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{cls._field_code(field)}_invalid"
            )
        return result

    @classmethod
    def _percentage(cls, value: Any, field: str) -> float:
        number = cls._number(value, field)
        if number > 100:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{cls._field_code(field)}_invalid"
            )
        return number

    @staticmethod
    def _money_minor(value: Any, field: str) -> int:
        field_code = WildberriesSellerAnalyticsConnector._field_code(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            )
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            ) from exc
        if not decimal_value.is_finite() or decimal_value < 0:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            )
        minor = decimal_value * 100
        if minor != minor.to_integral_value():
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_precision_invalid"
            )
        result = int(minor)
        if result > MAX_DATABASE_INTEGER:
            raise WildberriesAnalyticsResponseError(
                f"wildberries_official_api_{field_code}_invalid"
            )
        return result
