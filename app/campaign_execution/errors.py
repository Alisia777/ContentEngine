class CampaignExecutionError(Exception):
    """Base error for campaign execution control center."""


class CampaignExecutionDataError(CampaignExecutionError):
    """Raised when campaign execution data cannot be found or is invalid."""


class CampaignExecutionSafetyError(CampaignExecutionError):
    """Raised when an unsafe or gated action is requested."""
