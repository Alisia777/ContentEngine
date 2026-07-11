class CustomerBillingError(Exception):
    """Base error for customer billing accounting."""


class CustomerBillingValidationError(CustomerBillingError):
    """Raised when a billing command is malformed or financially unsafe."""


class CustomerBillingOwnershipError(CustomerBillingError):
    """Raised when an actor or record is outside the requested organization."""


class CustomerBillingConflictError(CustomerBillingError):
    """Raised when immutable history or idempotency would become ambiguous."""


class CustomerBillingStateError(CustomerBillingError):
    """Raised when a subscription or invoice is not in a billable state."""
