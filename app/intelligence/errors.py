class IntelligenceError(RuntimeError):
    """Base error for data-driven generation."""


class MissingGeneratorDataError(IntelligenceError):
    """Raised when required generator input is missing."""


class ProviderConfigurationError(IntelligenceError):
    """Raised when a selected real provider is missing required configuration."""


class ClaimValidationError(IntelligenceError):
    """Raised when generated claims are not backed by allowed source refs."""

