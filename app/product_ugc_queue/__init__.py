from app.product_ugc_queue.errors import (
    ProductUGCQueueConflict,
    ProductUGCQueueError,
    ProductUGCQueueLeaseError,
    ProductUGCQueueOwnershipError,
    ProductUGCSpendValidationError,
    ProductUGCSubmissionAmbiguous,
)
from app.product_ugc_queue.service import ProductUGCGenerationQueueService
from app.product_ugc_queue.types import (
    EnqueueResult,
    FailureDisposition,
    QuarantineReconciliationResult,
    ReconciliationResult,
)

__all__ = [
    "EnqueueResult",
    "FailureDisposition",
    "ProductUGCGenerationQueueService",
    "ProductUGCGenerationWorker",
    "ProductUGCQueueConflict",
    "ProductUGCQueueError",
    "ProductUGCQueueLeaseError",
    "ProductUGCQueueOwnershipError",
    "ProductUGCSpendValidationError",
    "ProductUGCSubmissionAmbiguous",
    "QuarantineReconciliationResult",
    "ReconciliationResult",
]


def __getattr__(name: str):
    # Lazy export avoids a runner -> package -> worker -> runner import cycle.
    if name == "ProductUGCGenerationWorker":
        from app.product_ugc_queue.worker import ProductUGCGenerationWorker

        return ProductUGCGenerationWorker
    raise AttributeError(name)
