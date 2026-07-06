class DestinationControlTowerError(Exception):
    """Base error for destination control tower operations."""


class DestinationControlTowerDataError(DestinationControlTowerError):
    """Raised when tower input or state is invalid."""
