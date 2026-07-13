from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.runway_recipes.provider import RunwayRecipeProvider
from app.runway_recipes.types import (
    ProductUGCRecipeRequest,
    RecipeImageInput,
)


TASK_ID = "recipe-task-opaque_123"
TASK_URL = f"https://api.dev.runwayml.com/v1/tasks/{TASK_ID}"
OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net"
OUTPUT_URL = f"https://{OUTPUT_HOST}/outputs/master.mp4?_jwt=signed"
PUBLIC_IP = "8.8.8.8"


class _ChunkedStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks

    def __iter__(self):
        yield from self.chunks


def _mp4_bytes(payload_size: int = 64) -> bytes:
    header = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isommp41"
    return header + b"v" * payload_size


def _ffprobe_success(monkeypatch):
    def run(args, **_kwargs):
        path = Path(args[-1])
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 720,
                            "height": 1280,
                        }
                    ],
                    "format": {
                        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                        "duration": "8.0",
                        "size": str(path.stat().st_size),
                    },
                }
            )
        )

    monkeypatch.setattr("app.runway_recipes.provider.subprocess.run", run)


def _provider(handler, **kwargs) -> RunwayRecipeProvider:
    return RunwayRecipeProvider(
        api_secret="test-secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        dns_resolver=lambda _host: [PUBLIC_IP],
        ffprobe_path="ffprobe",
        **kwargs,
    )


def test_download_streams_to_hashed_filename_then_atomically_accepts_mp4(
    monkeypatch,
    tmp_path,
):
    body = _mp4_bytes()
    seen: list[dict[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
            }
        )
        if str(request.url) == TASK_URL:
            return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})
        assert request.url.host == OUTPUT_HOST
        return httpx.Response(200, headers={"content-type": "video/mp4"}, content=body)

    _ffprobe_success(monkeypatch)
    paths = _provider(handler).download_outputs(TASK_ID, tmp_path)

    digest = hashlib.sha256(TASK_ID.encode("utf-8")).hexdigest()[:32]
    assert paths == [tmp_path / f"runway_{digest}_0.mp4"]
    assert paths[0].read_bytes() == body
    assert TASK_ID not in paths[0].name
    assert list(tmp_path.glob("*.part")) == []
    assert seen[0]["authorization"] == "Bearer test-secret"
    assert seen[1]["authorization"] is None


def test_task_id_is_opaque_and_rejected_before_building_provider_path(tmp_path):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(500)

    provider = _provider(handler)
    with pytest.raises(ProviderConfigurationError, match="invalid task id"):
        provider.download_outputs("../../tasks/admin?token=secret", tmp_path)
    assert calls == []


def test_provider_supplied_traversal_task_id_is_rejected(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    get_settings.cache_clear()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "../../provider-output", "status": "PENDING"})

    request = ProductUGCRecipeRequest(
        character_image=RecipeImageInput(uri="data:image/png;base64,AA=="),
        product_image=RecipeImageInput(uri="data:image/png;base64,BB=="),
        product_info="Exact product information",
        user_concept="Creator presents the exact product.",
    )
    try:
        with pytest.raises(ProviderConfigurationError, match="invalid task id"):
            _provider(handler).create_product_ugc(request)
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("output_url", "expected_error"),
    [
        (f"http://{OUTPUT_HOST}/output.mp4", "public HTTPS"),
        ("https://evil.example/output.mp4", "not allowlisted"),
    ],
)
def test_output_url_requires_https_and_allowlisted_provider_host(
    tmp_path,
    output_url,
    expected_error,
):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={"id": TASK_ID, "status": "SUCCEEDED", "output": [output_url]},
        )

    with pytest.raises(ProviderConfigurationError, match=expected_error):
        _provider(handler).download_outputs(TASK_ID, tmp_path)
    assert seen == [TASK_URL]
    assert list(tmp_path.iterdir()) == []


def test_cross_host_redirect_is_rejected_before_following_it(tmp_path):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url) == TASK_URL:
            return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})
        if request.url.host == OUTPUT_HOST:
            return httpx.Response(302, headers={"location": "https://127.0.0.1/private.mp4"})
        raise AssertionError("redirect target must be rejected before a request")

    with pytest.raises(ProviderConfigurationError, match="not allowlisted"):
        _provider(handler).download_outputs(TASK_ID, tmp_path)
    assert len(seen) == 2
    assert list(tmp_path.iterdir()) == []


def test_allowlisted_host_resolving_to_private_ip_is_rejected(tmp_path):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})

    provider = RunwayRecipeProvider(
        api_secret="test-secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        dns_resolver=lambda _host: ["127.0.0.1"],
        ffprobe_path="ffprobe",
    )
    with pytest.raises(ProviderConfigurationError, match="non-public address"):
        provider.download_outputs(TASK_ID, tmp_path)
    assert seen == [TASK_URL]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("mime_type", "body", "expected_error"),
    [
        ("text/html", _mp4_bytes(), "MIME type"),
        ("video/mp4", b"<html>provider error</html>", "signature is not MP4"),
    ],
)
def test_mime_or_signature_failure_never_promotes_part_file(
    tmp_path,
    mime_type,
    body,
    expected_error,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TASK_URL:
            return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})
        return httpx.Response(200, headers={"content-type": mime_type}, content=body)

    with pytest.raises(ProviderConfigurationError, match=expected_error):
        _provider(handler).download_outputs(TASK_ID, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_size_limit_is_enforced_before_master_acceptance(tmp_path):
    body = _mp4_bytes(128)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TASK_URL:
            return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})
        return httpx.Response(
            200,
            headers={"content-type": "video/mp4"},
            stream=_ChunkedStream([body[:40], body[40:80], body[80:]]),
        )

    with pytest.raises(ProviderConfigurationError, match="configured size limit"):
        _provider(handler, max_output_bytes=64).download_outputs(TASK_ID, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_ffprobe_failure_keeps_output_unaccepted(monkeypatch, tmp_path):
    body = _mp4_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TASK_URL:
            return httpx.Response(200, json={"id": TASK_ID, "status": "SUCCEEDED", "output": [OUTPUT_URL]})
        return httpx.Response(200, headers={"content-type": "video/mp4"}, content=body)

    monkeypatch.setattr(
        "app.runway_recipes.provider.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps({"streams": [], "format": {}})
        ),
    )
    with pytest.raises(ProviderConfigurationError, match="ffprobe rejected"):
        _provider(handler).download_outputs(TASK_ID, tmp_path)
    assert list(tmp_path.iterdir()) == []
