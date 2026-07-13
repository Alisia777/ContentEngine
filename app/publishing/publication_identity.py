from __future__ import annotations

import re
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


_SECRET_QUERY_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "expires",
    "key",
    "secret",
    "sig",
    "signature",
    "token",
    "x_amz_",
    "x_goog_",
)


PLATFORM_HOSTS = {
    "instagram": frozenset({"instagram.com", "www.instagram.com"}),
    "tiktok": frozenset({"tiktok.com", "www.tiktok.com", "m.tiktok.com"}),
    "youtube": frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}),
    "vk": frozenset({"vk.com", "www.vk.com", "m.vk.com"}),
    "vk_clips": frozenset({"vk.com", "www.vk.com", "m.vk.com"}),
    "rutube": frozenset({"rutube.ru", "www.rutube.ru"}),
    "facebook": frozenset({"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"}),
    "telegram": frozenset({"t.me", "telegram.me"}),
    "pinterest": frozenset({"pinterest.com", "www.pinterest.com", "pin.it"}),
    "x": frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"}),
    "twitter": frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"}),
}
CANONICAL_HOSTS = {
    "instagram": "www.instagram.com",
    "tiktok": "www.tiktok.com",
    "youtube": "www.youtube.com",
    "vk": "vk.com",
    "vk_clips": "vk.com",
    "rutube": "rutube.ru",
    "facebook": "www.facebook.com",
    "telegram": "t.me",
    "pinterest": "www.pinterest.com",
    "x": "x.com",
    "twitter": "x.com",
}


class PublicationIdentityError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_publication_platform(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "ig": "instagram",
        "instagram_reels": "instagram",
        "reels": "instagram",
        "youtube_shorts": "youtube",
        "shorts": "youtube",
        "vkontakte": "vk",
        "facebook_reels": "facebook",
        "rutube_shorts": "rutube",
    }.get(normalized, normalized)


def _safe_public_url(value: str, *, error_code: str) -> str:
    text = str(value or "").strip()
    try:
        parts = urlsplit(text)
        query = parse_qsl(parts.query, keep_blank_values=True)
        port = parts.port
    except ValueError as exc:
        raise PublicationIdentityError(error_code) from exc
    host = (parts.hostname or "").lower().rstrip(".")
    if (
        parts.scheme.lower() != "https"
        or not host
        or parts.username
        or parts.password
        or parts.fragment
        or port not in {None, 443}
        or any(
            any(
                marker in key.strip().lower().replace("-", "_")
                for marker in _SECRET_QUERY_MARKERS
            )
            for key, _item in query
        )
    ):
        raise PublicationIdentityError(error_code)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


def canonical_publication_url(
    value: str,
    destination: models.PublishingDestination,
) -> str:
    """Return one platform-specific identity URL without tracking variants."""

    try:
        canonical = _safe_public_url(
            value,
            error_code="placement_final_url_invalid",
        )
    except PublicationIdentityError:
        raise
    if len(canonical) > 500:
        raise PublicationIdentityError("placement_final_url_invalid")
    platform = normalize_publication_platform(destination.platform)
    allowed_hosts = set(PLATFORM_HOSTS.get(platform, ()))
    if not allowed_hosts and destination.url:
        try:
            destination_url = _safe_public_url(
                destination.url,
                error_code="placement_destination_url_invalid",
            )
        except PublicationIdentityError:
            raise
        destination_host = (urlsplit(destination_url).hostname or "").lower().rstrip(".")
        if destination_host:
            allowed_hosts.add(destination_host)
    if not allowed_hosts:
        raise PublicationIdentityError("placement_destination_domain_required")
    parts = urlsplit(canonical)
    host = (parts.hostname or "").lower().rstrip(".")
    if host not in allowed_hosts:
        raise PublicationIdentityError("placement_final_url_host_mismatch")
    path = parts.path.rstrip("/") or "/"
    canonical_host = CANONICAL_HOSTS.get(platform, host)
    canonical_query = ""
    if platform == "youtube":
        video_id = ""
        if host == "youtu.be":
            video_id = path.strip("/").split("/", 1)[0]
        elif path.casefold().startswith("/shorts/"):
            video_id = path.split("/", 3)[2]
        elif path.casefold() == "/watch":
            video_id = (parse_qs(parts.query).get("v") or [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", video_id):
            raise PublicationIdentityError("placement_final_url_post_path_required")
        path = f"/shorts/{video_id}"
    elif platform == "instagram":
        if not re.fullmatch(r"/(?:reel|p|tv)/[A-Za-z0-9._-]{3,120}", path):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform == "tiktok":
        if not re.fullmatch(r"/@[^/]{2,80}/video/[0-9]{5,40}", path):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform in {"x", "twitter"}:
        if not re.fullmatch(r"/[^/]{1,80}/status/[0-9]{5,40}", path):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform == "facebook":
        if host == "fb.watch":
            raise PublicationIdentityError("placement_final_url_short_link_not_supported")
        if path.casefold() == "/watch":
            video_id = (parse_qs(parts.query).get("v") or [""])[0]
            if not re.fullmatch(r"[A-Za-z0-9._-]{3,120}", video_id):
                raise PublicationIdentityError("placement_final_url_post_path_required")
            canonical_query = urlencode({"v": video_id})
        elif not re.search(
            r"/(?:reel|reels|videos|posts)/[A-Za-z0-9._-]{3,120}(?:/|$)",
            path,
            flags=re.IGNORECASE,
        ):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform in {"vk", "vk_clips"}:
        if not re.fullmatch(r"/(?:clip|video|wall)-?[0-9]+_[0-9]+", path):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform == "rutube":
        if not re.fullmatch(
            r"/(?:video|shorts)/[A-Za-z0-9_-]{5,120}",
            path,
        ):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform == "telegram":
        if not (
            re.fullmatch(r"/[A-Za-z0-9_]{3,64}/[0-9]{1,20}", path)
            or re.fullmatch(r"/c/[0-9]{1,20}/[0-9]{1,20}", path)
        ):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif platform == "pinterest":
        if host == "pin.it":
            raise PublicationIdentityError("placement_final_url_short_link_not_supported")
        if not re.fullmatch(r"/pin/[0-9]{3,40}", path):
            raise PublicationIdentityError("placement_final_url_post_path_required")
    elif path == "/":
        raise PublicationIdentityError("placement_final_url_post_path_required")
    return urlunsplit(("https", canonical_host, path, canonical_query, ""))


def claim_publication_identity(
    db: Session,
    *,
    task: models.PublishingTask,
    final_url: str,
) -> str:
    """Serialize and deduplicate a final post URL within its organization."""

    package = task.publishing_package or db.get(
        models.PublishingPackage,
        task.publishing_package_id,
    )
    destination = task.destination or db.get(
        models.PublishingDestination,
        task.destination_id,
    )
    if package is None or destination is None:
        raise PublicationIdentityError("placement_task_lineage_invalid")
    organization_id = package.organization_id
    if organization_id is None:
        try:
            return _safe_public_url(
                final_url,
                error_code="placement_final_url_invalid",
            )
        except PublicationIdentityError:
            raise
    if organization_id is not None:
        organization_lock = db.scalar(
            select(models.Organization.id)
            .where(models.Organization.id == int(organization_id))
            .with_for_update()
        )
        if organization_lock is None or destination.organization_id != organization_id:
            raise PublicationIdentityError("placement_task_lineage_invalid")
    canonical = canonical_publication_url(final_url, destination)

    if task.final_url:
        existing_self = canonical_publication_url(task.final_url, destination)
        if existing_self != canonical:
            raise PublicationIdentityError("placement_final_url_mismatch")

    if organization_id is not None:
        existing_rows = db.execute(
            select(models.PublishingTask, models.PublishingDestination)
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id
                == models.PublishingTask.publishing_package_id,
            )
            .join(
                models.PublishingDestination,
                models.PublishingDestination.id
                == models.PublishingTask.destination_id,
            )
            .where(
                models.PublishingPackage.organization_id == int(organization_id),
                models.PublishingTask.id != task.id,
                models.PublishingTask.final_url.is_not(None),
                models.PublishingTask.final_url != "",
            )
            .with_for_update()
        ).all()
        for other_task, other_destination in existing_rows:
            try:
                other_identity = canonical_publication_url(
                    str(other_task.final_url),
                    other_destination,
                )
            except PublicationIdentityError:
                # Legacy malformed rows do not gain authority over a new valid
                # publication, but remain visible for data cleanup.
                continue
            if other_identity == canonical:
                raise PublicationIdentityError("placement_final_url_already_used")
    return canonical


def find_task_by_publication_url(
    db: Session,
    value: str | None,
    *,
    destination_id: int | None = None,
    platform: str | None = None,
    organization_id: int | None = None,
) -> models.PublishingTask | None:
    """Match metrics/connector URLs through the same post identity contract."""

    text = str(value or "").strip()
    if not text:
        return None
    normalized_platform = (
        normalize_publication_platform(platform) if platform else None
    )
    platform_destination_ids: list[int] | None = None
    if destination_id is None and normalized_platform is not None:
        platform_destination_ids = [
            int(row.id)
            for row in db.execute(
                select(
                    models.PublishingDestination.id,
                    models.PublishingDestination.platform,
                )
            )
            if normalize_publication_platform(row.platform) == normalized_platform
        ]
        if not platform_destination_ids:
            return None
    base_query = (
        select(models.PublishingTask, models.PublishingDestination)
        .join(
            models.PublishingPackage,
            models.PublishingPackage.id
            == models.PublishingTask.publishing_package_id,
        )
        .join(
            models.PublishingDestination,
            models.PublishingDestination.id == models.PublishingTask.destination_id,
        )
        .where(
            models.PublishingTask.final_url.is_not(None),
            models.PublishingTask.final_url != "",
        )
    )
    if destination_id is not None:
        base_query = base_query.where(
            models.PublishingTask.destination_id == int(destination_id)
        )
    elif platform_destination_ids is not None:
        base_query = base_query.where(
            models.PublishingTask.destination_id.in_(platform_destination_ids)
        )
    if organization_id is not None:
        base_query = base_query.where(
            models.PublishingPackage.organization_id == int(organization_id)
        )
    exact = db.execute(
        base_query.where(models.PublishingTask.final_url == text).limit(2)
    ).all()
    exact = [
        row
        for row in exact
        if normalized_platform is None
        or normalize_publication_platform(row[1].platform) == normalized_platform
    ]
    if len(exact) == 1:
        return exact[0][0]
    if len(exact) > 1:
        raise PublicationIdentityError("publication_final_url_match_ambiguous")

    matched: list[models.PublishingTask] = []
    for task, destination in db.execute(
        base_query.order_by(models.PublishingTask.id.desc()).execution_options(
            yield_per=500
        )
    ):
        if (
            normalized_platform is not None
            and normalize_publication_platform(destination.platform)
            != normalized_platform
        ):
            continue
        try:
            submitted_identity = canonical_publication_url(text, destination)
            stored_identity = canonical_publication_url(
                str(task.final_url),
                destination,
            )
        except PublicationIdentityError:
            continue
        if submitted_identity == stored_identity:
            matched.append(task)
            if len(matched) > 1:
                raise PublicationIdentityError(
                    "publication_final_url_match_ambiguous"
                )
    return matched[0] if matched else None
