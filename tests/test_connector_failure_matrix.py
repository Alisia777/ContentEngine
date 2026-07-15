from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable

import httpx
import pytest

from app.destination_connectors import instagram_connector as instagram_module
from app.destination_connectors import tiktok_connector as tiktok_module
from app.destination_connectors import youtube_connector as youtube_module
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.instagram_connector import (
    HttpxInstagramInsightsTransport,
)
from app.destination_connectors.tiktok_connector import HttpxTikTokDisplayTransport
from app.destination_connectors.youtube_connector import (
    HttpxYouTubeAnalyticsTransport,
)
from app.wildberries_analytics.connector import (
    HttpxWildberriesSellerAnalyticsGateway,
)
from app.wildberries_analytics.errors import (
    WildberriesAnalyticsResponseError,
    WildberriesAnalyticsTransportError,
)


SECRET = "connector-secret-that-must-not-leak"


@dataclass(frozen=True)
class SocialTransportCase:
    name: str
    module: ModuleType
    transport_type: type
    invoke: Callable[[Any, str], dict[str, Any]]


def _query_youtube(transport: Any, token: str) -> dict[str, Any]:
    return transport.query_report(
        access_token=token,
        params={
            "ids": "channel==MINE",
            "startDate": "2026-07-01",
            "endDate": "2026-07-07",
            "metrics": "views",
        },
    )


def _query_tiktok(transport: Any, token: str) -> dict[str, Any]:
    return transport.query_videos(
        access_token=token,
        fields=("id", "view_count"),
        video_ids=["1234567890123456789"],
    )


def _query_instagram(transport: Any, token: str) -> dict[str, Any]:
    return transport.query_media_insights(
        access_token=token,
        api_version="v22.0",
        media_id="1234567890123456789",
        metrics=("views", "reach"),
    )


SOCIAL_TRANSPORTS = (
    SocialTransportCase(
        name="youtube",
        module=youtube_module,
        transport_type=HttpxYouTubeAnalyticsTransport,
        invoke=_query_youtube,
    ),
    SocialTransportCase(
        name="tiktok",
        module=tiktok_module,
        transport_type=HttpxTikTokDisplayTransport,
        invoke=_query_tiktok,
    ),
    SocialTransportCase(
        name="instagram",
        module=instagram_module,
        transport_type=HttpxInstagramInsightsTransport,
        invoke=_query_instagram,
    ),
)


FAILURES = (
    pytest.param("timeout", None, "transport_failed", id="timeout"),
    pytest.param("status", 401, "authorization_failed", id="401"),
    pytest.param("status", 403, "authorization_failed", id="403"),
    pytest.param("status", 429, "request_failed_status_429", id="429"),
    pytest.param("status", 503, "request_failed_status_503", id="503"),
    pytest.param("invalid_json", 200, "invalid_json", id="invalid-json"),
)


def _response_or_timeout(
    request: httpx.Request,
    *,
    mode: str,
    status_code: int | None,
) -> httpx.Response:
    if mode == "timeout":
        raise httpx.ConnectTimeout(
            f"untrusted upstream error containing {SECRET}",
            request=request,
        )
    if mode == "invalid_json":
        return httpx.Response(
            200,
            content=f'{{"upstream_secret":"{SECRET}"'.encode(),
            headers={"Content-Type": "application/json"},
        )
    assert status_code is not None
    return httpx.Response(status_code, json={"upstream_error": SECRET})


def _assert_public_exception_is_sanitized(error: Exception, expected_code: str) -> None:
    assert str(error) == expected_code
    assert error.args == (expected_code,)
    assert SECRET not in str(error)
    assert SECRET not in repr(error)


def _exception_chain_text(error: BaseException) -> str:
    rendered: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        rendered.append(f"{type(current).__name__}: {current!s} {current!r}")
        current = current.__cause__ or current.__context__
    return "\n".join(rendered)


@pytest.mark.parametrize("case", SOCIAL_TRANSPORTS, ids=lambda case: case.name)
@pytest.mark.parametrize("mode,status_code,expected_suffix", FAILURES)
def test_social_http_transport_failure_matrix_is_bounded_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    case: SocialTransportCase,
    mode: str,
    status_code: int | None,
    expected_suffix: str,
) -> None:
    requests: list[httpx.Request] = []
    constructor_calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {SECRET}"
        assert SECRET not in str(request.url)
        assert SECRET.encode() not in request.content
        return _response_or_timeout(
            request,
            mode=mode,
            status_code=status_code,
        )

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )

    def client_factory(*_args: Any, **kwargs: Any) -> httpx.Client:
        constructor_calls.append(kwargs)
        return mock_client

    monkeypatch.setattr(case.module.httpx, "Client", client_factory)

    with pytest.raises(DestinationConnectorDataError) as caught:
        case.invoke(case.transport_type(), SECRET)

    expected_code = f"{case.name}_official_api_{expected_suffix}"
    _assert_public_exception_is_sanitized(caught.value, expected_code)
    assert len(requests) == 1
    assert constructor_calls == [{"timeout": 20.0, "follow_redirects": False}]


WB_FAILURES = (
    pytest.param(
        "timeout",
        None,
        WildberriesAnalyticsTransportError,
        "wildberries_official_api_transport_failed",
        id="timeout",
    ),
    pytest.param(
        "status",
        401,
        WildberriesAnalyticsTransportError,
        "wildberries_official_api_auth_rejected",
        id="401",
    ),
    pytest.param(
        "status",
        403,
        WildberriesAnalyticsTransportError,
        "wildberries_official_api_auth_rejected",
        id="403",
    ),
    pytest.param(
        "status",
        429,
        WildberriesAnalyticsTransportError,
        "wildberries_official_api_rate_limited",
        id="429",
    ),
    pytest.param(
        "status",
        503,
        WildberriesAnalyticsTransportError,
        "wildberries_official_api_http_error",
        id="503",
    ),
    pytest.param(
        "invalid_json",
        200,
        WildberriesAnalyticsResponseError,
        "wildberries_official_api_json_invalid",
        id="invalid-json",
    ),
)


@pytest.mark.parametrize(
    "mode,status_code,error_type,expected_code",
    WB_FAILURES,
)
def test_wildberries_http_gateway_failure_matrix_is_bounded_and_sanitized(
    mode: str,
    status_code: int | None,
    error_type: type[Exception],
    expected_code: str,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == SECRET
        assert SECRET not in str(request.url)
        assert SECRET.encode() not in request.content
        return _response_or_timeout(
            request,
            mode=mode,
            status_code=status_code,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    ) as client:
        gateway = HttpxWildberriesSellerAnalyticsGateway(client=client)
        with pytest.raises(error_type) as caught:
            gateway.post_product_history(
                api_key=SECRET,
                body={
                    "selectedPeriod": {
                        "start": "2026-07-01",
                        "end": "2026-07-07",
                    },
                    "nmIds": [123456789],
                    "skipDeletedNm": True,
                },
            )

    _assert_public_exception_is_sanitized(caught.value, expected_code)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "case_name",
    ["youtube", "tiktok", "instagram", "wildberries"],
)
def test_transport_exception_chain_does_not_expose_untrusted_secret(
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout(
            f"untrusted upstream error containing {SECRET}",
            request=request,
        )

    mock_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    if case_name == "wildberries":
        gateway = HttpxWildberriesSellerAnalyticsGateway(client=mock_client)
        with pytest.raises(WildberriesAnalyticsTransportError) as caught:
            gateway.post_product_history(
                api_key=SECRET,
                body={"selectedPeriod": {}, "nmIds": [1], "skipDeletedNm": True},
            )
    else:
        case = next(item for item in SOCIAL_TRANSPORTS if item.name == case_name)

        def client_factory(*_args: Any, **_kwargs: Any) -> httpx.Client:
            return mock_client

        monkeypatch.setattr(case.module.httpx, "Client", client_factory)
        with pytest.raises(DestinationConnectorDataError) as caught:
            case.invoke(case.transport_type(), SECRET)

    assert SECRET not in _exception_chain_text(caught.value)
