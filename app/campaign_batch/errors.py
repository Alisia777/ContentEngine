class CampaignBatchError(Exception):
    """Base error for campaign batch execution."""


class CampaignBatchDataError(CampaignBatchError):
    """Raised when campaign batch input data is missing or invalid."""


class CampaignBatchSafetyError(CampaignBatchError):
    """Raised when a batch action violates execution safety rules."""
