class DestinationSetupError(Exception):
    """Base error for destination setup workflows."""


class DestinationSetupDataError(DestinationSetupError):
    """Raised when destination setup data is missing or invalid."""
