class MetricsIntakeError(Exception):
    """Base exception for metrics intake failures."""


class MetricsIntakeDataError(MetricsIntakeError):
    """Raised when metrics intake data is missing, unsafe, or invalid."""
