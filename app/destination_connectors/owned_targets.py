from __future__ import annotations

import math
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from app import models
from app.destination_connectors.errors import DestinationConnectorDataError


PUBLISHED_TASK_STATUSES = {"published", "published_manual", "published_api", "done"}
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


def normalize_platform(value: str | None) -> str:
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


def safe_public_url(value: str, *, error_code: str) -> str:
    text = str(value or "").strip()
    try:
        parts = urlsplit(text)
        query = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError as exc:
        raise DestinationConnectorDataError(error_code) from exc
    host = (parts.hostname or "").lower().rstrip(".")
    if (
        parts.scheme.lower() != "https"
        or not host
        or parts.username
        or parts.password
        or parts.fragment
        or any(
            any(
                marker in key.strip().lower().replace("-", "_")
                for marker in _SECRET_QUERY_MARKERS
            )
            for key, _item in query
        )
    ):
        raise DestinationConnectorDataError(error_code)
    try:
        port = parts.port
    except ValueError as exc:
        raise DestinationConnectorDataError(error_code) from exc
    if port not in {None, 443}:
        raise DestinationConnectorDataError(error_code)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


def require_owned_published_target(
    connection: models.DestinationConnection,
    *,
    organization_id: int,
    publishing_task_id: int,
    final_url: str,
    expected_platform: str,
    error_prefix: str,
) -> models.PublishingTask:
    destination = connection.destination
    if (
        destination is None
        or destination.id != connection.destination_id
        or destination.organization_id != organization_id
        or normalize_platform(destination.platform) != expected_platform
        or normalize_platform(connection.platform) != expected_platform
    ):
        raise DestinationConnectorDataError("destination_connection_not_found_in_organization")

    matches = [task for task in destination.publishing_tasks if task.id == publishing_task_id]
    if len(matches) != 1:
        raise DestinationConnectorDataError(f"{error_prefix}_target_not_owned_by_destination")
    task = matches[0]
    package = task.publishing_package
    product = package.product if package is not None else None
    if (
        task.status not in PUBLISHED_TASK_STATUSES
        or normalize_platform(task.platform) != expected_platform
        or package is None
        or normalize_platform(package.target_platform) != expected_platform
        or product is None
        or product.organization_id != organization_id
        or not task.final_url
    ):
        raise DestinationConnectorDataError(f"{error_prefix}_target_not_owned_by_destination")
    # Import lazily: publication identity is infrastructure-neutral, while the
    # destination_connectors package eagerly registers connector modules.
    from app.publishing.publication_identity import (
        PublicationIdentityError,
        canonical_publication_url,
    )

    try:
        mapped_url = canonical_publication_url(final_url, destination)
        task_url = canonical_publication_url(task.final_url, destination)
    except PublicationIdentityError as exc:
        raise DestinationConnectorDataError(
            f"{error_prefix}_final_url_is_invalid"
        ) from exc
    if mapped_url != task_url:
        raise DestinationConnectorDataError(f"{error_prefix}_target_final_url_mismatch")
    return task


def positive_task_id(value: object, *, error_code: str) -> int:
    if isinstance(value, bool):
        raise DestinationConnectorDataError(error_code)
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise DestinationConnectorDataError(error_code) from exc
    if result <= 0:
        raise DestinationConnectorDataError(error_code)
    return result


def non_negative_integer(value: object, *, error_code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DestinationConnectorDataError(error_code)
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise DestinationConnectorDataError(error_code) from exc
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise DestinationConnectorDataError(error_code)
    return int(numeric)
