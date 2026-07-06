class DestinationCRMError(Exception):
    """Base error for destination readiness CRM."""


class DestinationCRMDataError(DestinationCRMError):
    """Raised when destination CRM data is missing or invalid."""
