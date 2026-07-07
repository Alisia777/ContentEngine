class CreativeWorkbenchError(Exception):
    """Base error for creative workbench workflows."""


class CreativeWorkbenchDataError(CreativeWorkbenchError):
    """Raised when required workbench data is missing or invalid."""


class CreativeWorkbenchGuardrailError(CreativeWorkbenchError):
    """Raised when an operator action would bypass a quality or spend gate."""
