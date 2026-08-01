"""Strict public-content discovery contracts for ContentEngine.

Competitor observations are discovery evidence only. Raw captions, URLs,
faces, music, slogans and exact shot sequences never become reusable machine
instructions in this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


class SocialPlatform(StrEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    VK = "vk"
    OTHER = "other"


class SourceRelationship(StrEnum):
    OWNED = "owned"
    LICENSED = "licensed"
    PUBLIC_COMPETITOR = "public_competitor"
    UNKNOWN = "unknown"


class PublicContentKind(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    OTHER = "other"


class DiscoveryState(StrEnum):
    ELIGIBLE = "eligible"
    INSUFFICIENT_DATA = "insufficient_data"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class CreativeAction(StrEnum):
    LOCALIZE_OWNED = "localize_owned"
    RECREATE_STRUCTURE = "recreate_structure"
    MAKE_NEW = "make_new"
    DO_NOT_USE = "do_not_use"


class HookType(StrEnum):
    PROBLEM_FIRST = "problem_first"
    RESULT_FIRST = "result_first"
    DEMONSTRATION = "demonstration"
    CURIOSITY = "curiosity"
    COMPARISON = "comparison"
    REACTION = "reaction"
    UNKNOWN = "unknown"


class Pacing(StrEnum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ProofType(StrEnum):
    VISUAL_DEMO = "visual_demo"
    BEFORE_AFTER = "before_after"
    TESTIMONIAL = "testimonial"
    EXPERT = "expert"
    SPECIFICATION = "specification"
    SOCIAL_PROOF = "social_proof"
    NONE = "none"
    UNKNOWN = "unknown"


class CtaStyle(StrEnum):
    NONE = "none"
    SOFT_ACTION = "soft_action"
    DIRECT_ACTION = "direct_action"
    OFFER = "offer"
    COMMENT_KEYWORD = "comment_keyword"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StructuralProfile:
    """Allowlisted creative structure that may be reused safely."""

    hook_type: HookType = HookType.UNKNOWN
    pacing: Pacing = Pacing.UNKNOWN
    proof_type: ProofType = ProofType.UNKNOWN
    cta_style: CtaStyle = CtaStyle.UNKNOWN
    shot_count_bucket: str = "unknown"
    product_visibility: str = "unknown"

    def __post_init__(self) -> None:
        if self.shot_count_bucket not in {"1", "2_4", "5_8", "9_plus", "unknown"}:
            raise ValueError("shot_count_bucket_invalid")
        if self.product_visibility not in {
            "continuous",
            "early",
            "late",
            "intermittent",
            "unknown",
        }:
            raise ValueError("product_visibility_invalid")

    @property
    def is_informative(self) -> bool:
        return any(
            (
                self.hook_type is not HookType.UNKNOWN,
                self.pacing is not Pacing.UNKNOWN,
                self.proof_type is not ProofType.UNKNOWN,
                self.cta_style is not CtaStyle.UNKNOWN,
                self.shot_count_bucket != "unknown",
                self.product_visibility != "unknown",
            )
        )


@dataclass(frozen=True, slots=True)
class PublicCreativeObservation:
    """One public post used only to discover structural candidates."""

    observation_id: str
    account_key: str
    external_content_id: str
    platform: SocialPlatform
    category_key: str
    published_at: datetime
    fetched_at: datetime
    source_relationship: SourceRelationship
    content_kind: PublicContentKind
    source_locator_hash: str
    provider_key: str
    structural_profile: StructuralProfile = field(default_factory=StructuralProfile)
    duration_seconds: int | None = None
    follower_count: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    state: DiscoveryState = DiscoveryState.ELIGIBLE
    public_access_confirmed: bool = True
    rights_confirmed: bool = False

    def __post_init__(self) -> None:
        for value, limit, code in (
            (self.observation_id, 180, "observation_id_invalid"),
            (self.account_key, 180, "account_key_invalid"),
            (self.external_content_id, 180, "external_content_id_invalid"),
            (self.category_key, 80, "category_key_invalid"),
            (self.provider_key, 80, "provider_key_invalid"),
        ):
            if not value or len(value) > limit:
                raise ValueError(code)
        if not _SHA256.fullmatch(self.source_locator_hash):
            raise ValueError("source_locator_hash_invalid")
        if self.published_at.tzinfo is None or self.fetched_at.tzinfo is None:
            raise ValueError("timezone_required")
        published = self.published_at.astimezone(timezone.utc)
        fetched = self.fetched_at.astimezone(timezone.utc)
        if fetched < published:
            raise ValueError("fetched_before_published")
        if self.duration_seconds is not None and not 1 <= self.duration_seconds <= 3_600:
            raise ValueError("duration_invalid")
        for value, code in (
            (self.follower_count, "follower_count_invalid"),
            (self.views, "views_invalid"),
            (self.likes, "likes_invalid"),
            (self.comments, "comments_invalid"),
            (self.shares, "shares_invalid"),
        ):
            if value is not None and value < 0:
                raise ValueError(code)

    @property
    def age_hours(self) -> float:
        delta = self.fetched_at.astimezone(timezone.utc) - self.published_at.astimezone(timezone.utc)
        return max(1.0, delta.total_seconds() / 3_600)

    @property
    def discovery_eligible(self) -> bool:
        return (
            self.state is DiscoveryState.ELIGIBLE
            and self.public_access_confirmed
            and self.content_kind is PublicContentKind.VIDEO
            and self.views is not None
        )

    @property
    def can_be_localized_exactly(self) -> bool:
        return (
            self.source_relationship in {SourceRelationship.OWNED, SourceRelationship.LICENSED}
            and self.rights_confirmed
            and self.content_kind is PublicContentKind.VIDEO
        )


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    observation_id: str
    account_key: str
    action: CreativeAction
    discovery_score: float
    view_velocity: float
    engagement_rate: float
    share_rate: float
    structural_profile: StructuralProfile
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0 <= self.discovery_score <= 1:
            raise ValueError("discovery_score_invalid")
        for value, code in (
            (self.view_velocity, "view_velocity_invalid"),
            (self.engagement_rate, "engagement_rate_invalid"),
            (self.share_rate, "share_rate_invalid"),
        ):
            if value < 0:
                raise ValueError(code)


@dataclass(frozen=True, slots=True)
class CompetitorActionPlan:
    category_key: str
    platform: SocialPlatform
    candidates: tuple[DiscoveryCandidate, ...]
    fallback_action: CreativeAction
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        if len(self.candidates) > 100:
            raise ValueError("too_many_candidates")
