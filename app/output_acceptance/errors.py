class OutputAcceptanceError(Exception):
    """Base error for output acceptance workflows."""


class OutputAcceptanceDataError(OutputAcceptanceError):
    """Raised when required acceptance data is missing or invalid."""
