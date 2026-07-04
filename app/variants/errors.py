class VariantError(Exception):
    """Base error for first-frame and creative-variant workflows."""


class VariantDataError(VariantError):
    """Raised when variant inputs are missing."""
