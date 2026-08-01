"""Rights-aware competitor discovery for ContentEngine."""

from .providers import (
    DiscoveryProvider,
    PROVIDER_CAPABILITIES,
    ProviderCapability,
    ProviderSelectionError,
    provider_capability,
    select_discovery_provider,
)
from .schema import (
    CompetitorActionPlan,
    CreativeAction,
    CtaStyle,
    DiscoveryCandidate,
    DiscoveryState,
    HookType,
    Pacing,
    ProofType,
    PublicContentKind,
    PublicCreativeObservation,
    SocialPlatform,
    SourceRelationship,
    StructuralProfile,
)
from .service import (
    CompetitiveIntelligenceError,
    build_competitor_action_plan,
    rank_public_creatives,
)

__all__ = [
    "CompetitorActionPlan",
    "CompetitiveIntelligenceError",
    "CreativeAction",
    "CtaStyle",
    "DiscoveryCandidate",
    "DiscoveryProvider",
    "DiscoveryState",
    "HookType",
    "PROVIDER_CAPABILITIES",
    "Pacing",
    "ProofType",
    "ProviderCapability",
    "ProviderSelectionError",
    "PublicContentKind",
    "PublicCreativeObservation",
    "SocialPlatform",
    "SourceRelationship",
    "StructuralProfile",
    "build_competitor_action_plan",
    "provider_capability",
    "rank_public_creatives",
    "select_discovery_provider",
]
