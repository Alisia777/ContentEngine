class ParticipantPortalError(Exception):
    """Base error for participant portal operations."""


class ParticipantPortalDataError(ParticipantPortalError):
    """Raised when participant portal input or state is invalid."""
