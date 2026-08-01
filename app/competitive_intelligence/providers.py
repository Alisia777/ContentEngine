"""Provider-capability planning for public competitor discovery.

This module does not call third-party APIs. It makes the product boundary
explicit so an official owner-authorized API is never silently used as an
arbitrary-competitor scraper, and a research-only API is never selected for a
commercial production workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .schema import SocialPlatform


class DiscoveryProvider(StrEnum):
    YOUTUBE_DATA_API = "youtube_data_api"
    TIKTOK_DISPLAY_API = "tiktok_display_api"
    TIKTOK_RESEARCH_API = "tiktok_research_api"
    LICENSED_PUBLIC_DATA_VENDOR = "licensed_public_data_vendor"


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider: DiscoveryProvider
    platforms: tuple[SocialPlatform, ...]
    arbitrary_public_accounts: bool
    commercial_product_use: bool
    requires_subject_authorization: bool
    requires_special_approval: bool
    pricing_model: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.platforms:
            raise ValueError("provider_platforms_required")
        if not self.pricing_model or len(self.pricing_model) > 80:
            raise ValueError("pricing_model_invalid")


PROVIDER_CAPABILITIES: tuple[ProviderCapability, ...] = (
    ProviderCapability(
        provider=DiscoveryProvider.YOUTUBE_DATA_API,
        platforms=(SocialPlatform.YOUTUBE,),
        arbitrary_public_accounts=True,
        commercial_product_use=True,
        requires_subject_authorization=False,
        requires_special_approval=False,
        pricing_model="quota",
        reason_codes=(
            "official_public_channel_and_video_metadata",
            "quota_and_terms_apply",
        ),
    ),
    ProviderCapability(
        provider=DiscoveryProvider.TIKTOK_DISPLAY_API,
        platforms=(SocialPlatform.TIKTOK,),
        arbitrary_public_accounts=False,
        commercial_product_use=True,
        requires_subject_authorization=True,
        requires_special_approval=False,
        pricing_model="official_app_quota",
        reason_codes=(
            "authorized_subject_videos_only",
            "not_an_arbitrary_competitor_source",
        ),
    ),
    ProviderCapability(
        provider=DiscoveryProvider.TIKTOK_RESEARCH_API,
        platforms=(SocialPlatform.TIKTOK,),
        arbitrary_public_accounts=True,
        commercial_product_use=False,
        requires_subject_authorization=False,
        requires_special_approval=True,
        pricing_model="approved_research_access",
        reason_codes=(
            "public_research_dataset",
            "research_eligibility_required",
            "not_for_commercial_production_ingestion",
        ),
    ),
    ProviderCapability(
        provider=DiscoveryProvider.LICENSED_PUBLIC_DATA_VENDOR,
        platforms=(
            SocialPlatform.TIKTOK,
            SocialPlatform.INSTAGRAM,
            SocialPlatform.YOUTUBE,
            SocialPlatform.VK,
        ),
        arbitrary_public_accounts=True,
        commercial_product_use=True,
        requires_subject_authorization=False,
        requires_special_approval=False,
        pricing_model="records_or_compute",
        reason_codes=(
            "vendor_terms_and_public_data_only",
            "provider_keys_server_side",
            "hard_spend_cap_required",
        ),
    ),
)


class ProviderSelectionError(ValueError):
    """No provider satisfies the requested trust and product boundary."""


def provider_capability(provider: DiscoveryProvider) -> ProviderCapability:
    for capability in PROVIDER_CAPABILITIES:
        if capability.provider is provider:
            return capability
    raise ProviderSelectionError("provider_unknown")


def select_discovery_provider(
    *,
    platform: SocialPlatform,
    arbitrary_public_accounts: bool,
    commercial_product_use: bool = True,
    subject_authorized: bool = False,
    research_approved: bool = False,
) -> ProviderCapability:
    """Choose the narrowest compliant provider plan without making a request."""

    if platform is SocialPlatform.YOUTUBE:
        return provider_capability(DiscoveryProvider.YOUTUBE_DATA_API)

    if platform is SocialPlatform.TIKTOK:
        if not arbitrary_public_accounts and subject_authorized:
            return provider_capability(DiscoveryProvider.TIKTOK_DISPLAY_API)
        if arbitrary_public_accounts and not commercial_product_use and research_approved:
            return provider_capability(DiscoveryProvider.TIKTOK_RESEARCH_API)
        if arbitrary_public_accounts and commercial_product_use:
            return provider_capability(DiscoveryProvider.LICENSED_PUBLIC_DATA_VENDOR)
        raise ProviderSelectionError("tiktok_provider_boundary_unmet")

    if platform in {SocialPlatform.INSTAGRAM, SocialPlatform.VK}:
        if arbitrary_public_accounts and commercial_product_use:
            return provider_capability(DiscoveryProvider.LICENSED_PUBLIC_DATA_VENDOR)
        raise ProviderSelectionError("platform_provider_boundary_unmet")

    raise ProviderSelectionError("platform_not_supported")
