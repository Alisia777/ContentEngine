class AssetKitError(Exception):
    """Base error for product asset kit workflows."""


class AssetKitDataError(AssetKitError):
    """Raised when required asset kit inputs are missing."""
