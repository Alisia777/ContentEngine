class ContentCycleError(ValueError):
    """Base error for canonical content-cycle operations."""


class ContentCycleOwnershipError(ContentCycleError):
    """The actor, product, destination, or cycle is outside the requested organization."""


class ContentCycleStateError(ContentCycleError):
    """The source or downstream artifact has not passed a required safety gate."""


class ContentCycleConflictError(ContentCycleError):
    """An idempotency key or canonical source is already bound to another cycle."""
