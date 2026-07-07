class CreativeQualityError(Exception):
    """Base exception for creative-quality checks."""


class CreativeQualityDataError(CreativeQualityError):
    """Raised when a score, script, or rewrite request cannot be resolved."""
