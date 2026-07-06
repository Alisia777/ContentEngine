class BombarProductionError(Exception):
    """Base error for Bombar production dry-run tooling."""


class BombarProductionDataError(BombarProductionError):
    """Raised when a Bombar production dry run cannot be completed."""
