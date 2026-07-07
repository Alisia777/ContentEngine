class OneVideoAcceptanceError(Exception):
    """Base error for one-video render acceptance workflows."""


class OneVideoAcceptanceDataError(OneVideoAcceptanceError):
    """Raised when required one-video render data is missing or invalid."""
