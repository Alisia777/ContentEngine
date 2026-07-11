from __future__ import annotations


class WildberriesAnalyticsError(ValueError):
    code = "wildberries_analytics_error"

    def __init__(self, code: str | None = None):
        self.code = code or self.code
        super().__init__(self.code)


class WildberriesAnalyticsScopeError(WildberriesAnalyticsError):
    code = "wildberries_analytics_scope_rejected"


class WildberriesAnalyticsConfigurationError(WildberriesAnalyticsError):
    code = "wildberries_analytics_configuration_rejected"


class WildberriesAnalyticsPeriodError(WildberriesAnalyticsError):
    code = "wildberries_analytics_period_rejected"


class WildberriesAnalyticsTransportError(WildberriesAnalyticsError):
    code = "wildberries_analytics_transport_failed"


class WildberriesAnalyticsResponseError(WildberriesAnalyticsError):
    code = "wildberries_analytics_response_rejected"


class WildberriesAnalyticsIdempotencyError(WildberriesAnalyticsError):
    code = "wildberries_analytics_idempotency_conflict"
