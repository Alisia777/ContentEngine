class GenerationCostError(Exception):
    """Base error for generation-cost accounting."""


class GenerationCostValidationError(GenerationCostError):
    """Raised when a cost record is malformed or unsafe to recognize."""


class GenerationCostOwnershipError(GenerationCostError):
    """Raised when an organization does not own the referenced generation."""


class GenerationCostConflictError(GenerationCostError):
    """Raised when immutable ledger history would become ambiguous."""
