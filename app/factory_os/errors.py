class FactoryOSError(Exception):
    """Base error for Factory OS workflows."""


class FactoryOSDataError(FactoryOSError):
    """Raised when a Factory OS workflow cannot find required local data."""
