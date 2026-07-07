class AIBriefContractError(Exception):
    """Base error for AI brief contract workflows."""


class AIBriefContractDataError(AIBriefContractError):
    """Raised when required source data for a production brief is missing."""
