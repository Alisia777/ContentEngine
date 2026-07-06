class LaunchOperationsError(Exception):
    """Base error for launch operations hub."""


class LaunchOperationsDataError(LaunchOperationsError):
    """Raised when launch operations state cannot be built."""
