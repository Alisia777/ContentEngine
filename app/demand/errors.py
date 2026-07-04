class DemandError(RuntimeError):
    """Base error for product demand generation."""


class DemandDataError(DemandError):
    """Raised when demand generation input is missing or invalid."""


class DemandValidationError(DemandError):
    """Raised when a demand hypothesis cannot safely drive creative generation."""
