class CampaignAutopilotError(Exception):
    """Base exception for campaign autopilot failures."""


class CampaignAutopilotDataError(CampaignAutopilotError):
    """Raised when required campaign data is missing or invalid."""
