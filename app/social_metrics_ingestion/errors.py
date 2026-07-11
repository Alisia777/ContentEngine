from __future__ import annotations


class SocialMetricIngestionError(Exception):
    """Base error for the safe social metric ingestion boundary."""

    code = "social_metric_ingestion_error"


class SocialMetricValidationError(SocialMetricIngestionError):
    code = "invalid_social_metric_observation"


class SocialMetricAccessError(SocialMetricIngestionError):
    code = "social_metric_access_denied"
