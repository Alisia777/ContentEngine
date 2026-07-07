class ProductStrategyError(Exception):
    """Base exception for product strategy generation."""


class ProductStrategyDataError(ProductStrategyError):
    """Raised when required product strategy inputs are missing."""
