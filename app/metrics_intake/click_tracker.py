from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import re
from typing import Any, Callable, Literal
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.tracking_link_service import TrackingLinkService


TRACKING_EVENT_SCHEMA_VERSION = 1
TRACKING_DEDUPE_WINDOW_SECONDS = 10
TRACKING_RATE_WINDOW_SECONDS = 60
TRACKING_MAX_EVENTS_PER_WINDOW = 120

TrackingClassification = Literal["human", "bot", "unknown"]
TrackingDisposition = Literal[
    "recorded",
    "duplicate",
    "rate_limited",
    "telemetry_skipped",
]

_SOCIAL_PREVIEW_MARKERS = (
    "facebookexternalhit",
    "facebot",
    "twitterbot",
    "telegrambot",
    "linkedinbot",
    "pinterestbot",
    "discordbot",
    "slackbot",
    "vkshare",
    "whatsapp",
)
_CRAWLER_MARKERS = (
    "bot/",
    "googlebot",
    "bingbot",
    "yandexbot",
    "duckduckbot",
    "baiduspider",
    "crawler",
    "spider",
    "slurp",
)
_AUTOMATION_MARKERS = (
    "curl/",
    "wget/",
    "python-requests",
    "python-httpx",
    "aiohttp",
    "go-http-client",
    "headlesschrome",
    "phantomjs",
)
_VISITOR_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{16,128}")


@dataclass(frozen=True)
class ClickTrackingResult:
    """Result of one bounded tracking attempt.

    Only ``recorded`` creates a ``TrackingClick`` row. Duplicate and capped
    requests still redirect, but cannot grow the database. ``classification``
    is returned even when no row is stored so callers can add secret-free
    operational telemetry later without reprocessing the User-Agent.
    """

    link: models.TrackingLink
    click: models.TrackingClick | None
    disposition: TrackingDisposition
    classification: TrackingClassification
    accepted_for_human_kpi: bool
    duplicate_of_click_id: int | None = None

    def __iter__(self) -> Iterator[models.TrackingLink | models.TrackingClick | None]:
        """Retain the legacy ``link, click = record(...)`` read contract."""

        yield self.link
        yield self.click


class ClickTracker:
    """Persist privacy-minimized, bot-classified tracking events.

    Persisted rows use this stable JSON contract under ``metadata_json``::

        {
          "tracking_v1": {
            "schema_version": 1,
            "classification": "human" | "bot" | "unknown",
            "bot_reason": str | null,
            "accepted_for_raw_kpi": true,
            "accepted_for_human_kpi": bool,
            "visitor_fingerprint": str | null
          },
          ...caller metadata
        }

    The fingerprint is a SHA-256 digest of a short-lived random first-party
    visitor token. Direct callers without that token fall back to normalized
    request headers. Raw IP addresses are neither accepted nor persisted.
    """

    def __init__(
        self,
        db: Session,
        *,
        clock: Callable[[], datetime] = models.utcnow,
        dedupe_window_seconds: int = TRACKING_DEDUPE_WINDOW_SECONDS,
        rate_window_seconds: int = TRACKING_RATE_WINDOW_SECONDS,
        max_events_per_window: int = TRACKING_MAX_EVENTS_PER_WINDOW,
    ):
        self.db = db
        self.clock = clock
        self.dedupe_window_seconds = min(max(int(dedupe_window_seconds), 1), 300)
        self.rate_window_seconds = min(max(int(rate_window_seconds), 1), 3600)
        self.max_events_per_window = min(max(int(max_events_per_window), 1), 10_000)

    def resolve(self, slug: str) -> models.TrackingLink:
        """Resolve an active link before starting best-effort telemetry."""

        return TrackingLinkService(self.db).get_by_slug(slug)

    def record(
        self,
        slug: str,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None,
        visitor_token: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClickTrackingResult:
        link = self.resolve(slug)
        return self.record_resolved(
            link,
            referrer=referrer,
            user_agent=user_agent,
            accept_language=accept_language,
            visitor_token=visitor_token,
            metadata=metadata,
        )

    def record_resolved(
        self,
        link: models.TrackingLink,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
        accept_language: str | None = None,
        visitor_token: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClickTrackingResult:
        """Record one event after the redirect target has been safely resolved.

        The active link row is locked while the recent-window count and insert
        are evaluated. PostgreSQL web workers therefore cannot race past the
        per-slug cap. SQLite ignores ``FOR UPDATE`` but remains deterministic in
        the single-process test/development profile.
        """

        now = self._naive_utc(self.clock())
        classification, bot_reason = self.classify_user_agent(user_agent)
        referrer_origin = self.sanitize_referrer_origin(referrer)
        visitor_fingerprint = self._visitor_fingerprint(
            visitor_token=visitor_token,
            user_agent=user_agent,
            accept_language=accept_language,
            referrer_origin=referrer_origin,
        )
        accepted_for_human_kpi = classification == "human"

        locked_link = self.db.scalar(
            select(models.TrackingLink)
            .where(
                models.TrackingLink.id == int(link.id),
                models.TrackingLink.status == "active",
            )
            .with_for_update()
        )
        if locked_link is None:
            # The target was active when resolved. If an operator disabled it
            # concurrently, telemetry is skipped but the already resolved
            # redirect remains available to the router.
            self.db.rollback()
            return ClickTrackingResult(
                link=link,
                click=None,
                disposition="telemetry_skipped",
                classification=classification,
                accepted_for_human_kpi=accepted_for_human_kpi,
            )

        rate_cutoff = now - timedelta(seconds=self.rate_window_seconds)
        recent = list(
            self.db.scalars(
                select(models.TrackingClick)
                .where(
                    models.TrackingClick.tracking_link_id == locked_link.id,
                    models.TrackingClick.clicked_at >= rate_cutoff,
                )
                .order_by(
                    models.TrackingClick.clicked_at.desc(),
                    models.TrackingClick.id.desc(),
                )
                .limit(self.max_events_per_window)
            )
        )

        if visitor_fingerprint:
            dedupe_cutoff = now - timedelta(seconds=self.dedupe_window_seconds)
            duplicate = next(
                (
                    item
                    for item in recent
                    if item.clicked_at >= dedupe_cutoff
                    and self._stored_visitor_fingerprint(item) == visitor_fingerprint
                ),
                None,
            )
            if duplicate is not None:
                self.db.commit()
                return ClickTrackingResult(
                    link=locked_link,
                    click=None,
                    disposition="duplicate",
                    classification=classification,
                    accepted_for_human_kpi=accepted_for_human_kpi,
                    duplicate_of_click_id=duplicate.id,
                )

        if len(recent) >= self.max_events_per_window:
            self.db.commit()
            return ClickTrackingResult(
                link=locked_link,
                click=None,
                disposition="rate_limited",
                classification=classification,
                accepted_for_human_kpi=accepted_for_human_kpi,
            )

        event_metadata = dict(metadata or {})
        # Caller data cannot spoof the classification contract used by KPI.
        event_metadata["tracking_v1"] = {
            "schema_version": TRACKING_EVENT_SCHEMA_VERSION,
            "classification": classification,
            "bot_reason": bot_reason,
            "accepted_for_raw_kpi": True,
            "accepted_for_human_kpi": accepted_for_human_kpi,
            "visitor_fingerprint": visitor_fingerprint,
        }
        click = models.TrackingClick(
            tracking_link_id=locked_link.id,
            clicked_at=now,
            campaign_id=locked_link.campaign_id,
            publishing_task_id=locked_link.publishing_task_id,
            destination_id=locked_link.destination_id,
            sku=locked_link.sku,
            creative_variant_id=locked_link.creative_variant_id,
            participant_id=locked_link.participant_id,
            referrer=referrer_origin,
            user_agent_hash=self._hash(user_agent),
            metadata_json=event_metadata,
        )
        self.db.add(click)
        self.db.commit()
        self.db.refresh(click)
        return ClickTrackingResult(
            link=locked_link,
            click=click,
            disposition="recorded",
            classification=classification,
            accepted_for_human_kpi=accepted_for_human_kpi,
        )

    @staticmethod
    def classify_user_agent(
        user_agent: str | None,
    ) -> tuple[TrackingClassification, str | None]:
        normalized = " ".join(str(user_agent or "").strip().lower().split())[:1000]
        if not normalized:
            return "unknown", "missing_user_agent"
        if any(marker in normalized for marker in _SOCIAL_PREVIEW_MARKERS):
            return "bot", "social_preview"
        if any(marker in normalized for marker in _CRAWLER_MARKERS):
            return "bot", "crawler"
        if any(marker in normalized for marker in _AUTOMATION_MARKERS):
            return "bot", "automation"
        return "human", None

    @staticmethod
    def sanitize_referrer_origin(referrer: str | None) -> str | None:
        """Retain an HTTP(S) origin only; discard credentials, path and query."""

        value = str(referrer or "").strip()
        if not value or any(ord(char) < 32 for char in value):
            return None
        try:
            parsed = urlsplit(value)
            scheme = parsed.scheme.lower()
            hostname = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except (UnicodeError, ValueError):
            return None
        if scheme not in {"http", "https"} or not hostname:
            return None
        if parsed.username or parsed.password:
            return None
        try:
            normalized_host = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            return None
        if ":" in normalized_host and not normalized_host.startswith("["):
            normalized_host = f"[{normalized_host}]"
        default_port = 443 if scheme == "https" else 80
        netloc = normalized_host if port in {None, default_port} else f"{normalized_host}:{port}"
        origin = urlunsplit((scheme, netloc, "", "", ""))
        return origin[:500]

    @classmethod
    def _visitor_fingerprint(
        cls,
        *,
        visitor_token: str | None,
        user_agent: str | None,
        accept_language: str | None,
        referrer_origin: str | None,
    ) -> str | None:
        token = str(visitor_token or "").strip()
        if _VISITOR_TOKEN_RE.fullmatch(token):
            material = f"visitor-token\0{token}"
        else:
            normalized_user_agent = " ".join(
                str(user_agent or "").strip().lower().split()
            )[:1000]
            if not normalized_user_agent:
                return None
            normalized_language = " ".join(
                str(accept_language or "").strip().lower().split()
            )[:200]
            material = (
                f"request-headers\0{normalized_user_agent}\0"
                f"{normalized_language}\0{referrer_origin or ''}"
            )
        return hashlib.sha256(
            f"qvf-tracking-visitor-v1\0{material}".encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _stored_visitor_fingerprint(click: models.TrackingClick) -> str | None:
        metadata = click.metadata_json if isinstance(click.metadata_json, dict) else {}
        contract = metadata.get("tracking_v1")
        if not isinstance(contract, dict):
            return None
        value = contract.get("visitor_fingerprint")
        return str(value) if value else None

    @staticmethod
    def _hash(user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        value = str(user_agent)[:1000]
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _naive_utc(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise ValueError("tracking clock must return datetime")
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value
