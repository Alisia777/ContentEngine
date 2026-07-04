class EngineError(RuntimeError):
    """Base error for the core video factory engine."""


class EngineNotFoundError(EngineError):
    """Raised when a required workflow entity is missing."""


class EnginePreconditionError(EngineError):
    """Raised when the workflow cannot safely continue."""

