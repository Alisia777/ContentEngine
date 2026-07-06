class DestinationConnectorError(Exception):
    """Base error for destination connector operations."""


class DestinationConnectorDataError(DestinationConnectorError):
    """Raised when connector input or state is invalid."""
