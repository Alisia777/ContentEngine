class CreativeSpecError(RuntimeError):
    """Base error for hook-driven creative specs."""


class CreativeSpecValidationError(CreativeSpecError):
    """Raised when a creative spec cannot satisfy required safety checks."""
