class PublishingError(ValueError):
    """Raised when the safe publishing workflow blocks an operation."""


class PublishingAuthorizationError(PublishingError):
    """Raised when an organization member cannot perform publishing approval."""


class PublishingSourceNotFound(PublishingError):
    """Raised without revealing whether a media artifact exists in another tenant."""


class PublishingSourceStateError(PublishingError):
    """Raised when a tenant-owned source is not eligible for publishing."""
