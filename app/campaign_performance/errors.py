class CampaignPerformanceError(Exception):
    """Base error for campaign performance loop."""


class CampaignPerformanceDataError(CampaignPerformanceError):
    """Raised when campaign performance input data is missing or invalid."""
