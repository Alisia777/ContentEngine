class ProductUGCQueueError(Exception):
    """Base error for durable Product UGC generation work."""


class ProductUGCQueueOwnershipError(ProductUGCQueueError):
    """Raised when a job, draft, user, and organization do not share scope."""


class ProductUGCQueueConflict(ProductUGCQueueError):
    """Raised when an idempotency or state transition conflicts."""


class ProductUGCQueueLeaseError(ProductUGCQueueError):
    """Raised when a worker does not own a live lease."""


class ProductUGCSubmissionAmbiguous(ProductUGCQueueError):
    """Raised when provider submission may have spent but returned no task id."""
