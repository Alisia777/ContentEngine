from __future__ import annotations

import hashlib
import ipaddress
import json as jsonlib
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import ProviderVideoJob, ProviderVideoStatus
from app.runway_recipes.types import ProductUGCRecipeRequest
from app.system_tools import resolve_ffprobe


RUNWAY_OUTPUT_HOSTS = frozenset({"dnznrvs05pmza.cloudfront.net"})
RUNWAY_TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
RUNWAY_OUTPUT_MIME_TYPES = frozenset({"video/mp4", "application/mp4"})
RUNWAY_MAX_OUTPUTS = 4
RUNWAY_MAX_OUTPUT_BYTES = 256 * 1024 * 1024
RUNWAY_DOWNLOAD_CHUNK_BYTES = 64 * 1024
RUNWAY_MAX_REDIRECTS = 3
RUNWAY_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class RunwayRecipeProvider:
    provider_name = "runway_product_ugc_recipe"
    endpoint = "https://api.dev.runwayml.com/v1/recipes/product_ugc"
    api_version = "2024-11-06"

    def __init__(
        self,
        api_secret: str | None = None,
        *,
        client: httpx.Client | None = None,
        output_hosts: Iterable[str] | None = None,
        dns_resolver: Callable[[str], Iterable[str]] | None = None,
        ffprobe_path: str | None = None,
        max_output_bytes: int = RUNWAY_MAX_OUTPUT_BYTES,
    ):
        self.api_secret = api_secret or os.getenv("RUNWAYML_API_SECRET")
        self.client = client
        if not self.api_secret:
            raise ProviderConfigurationError("Runway Product UGC Recipe requires RUNWAYML_API_SECRET.")
        normalized_hosts = [
            self._normalized_host(item)
            for item in (output_hosts if output_hosts is not None else RUNWAY_OUTPUT_HOSTS)
        ]
        self.output_hosts = frozenset(item for item in normalized_hosts if item)
        if not self.output_hosts:
            raise ProviderConfigurationError("Runway output host allowlist is empty.")
        self.dns_resolver = dns_resolver or self._resolve_host_ips
        self.ffprobe_path = ffprobe_path or resolve_ffprobe(get_settings()).path
        try:
            self.max_output_bytes = int(max_output_bytes)
        except (TypeError, ValueError) as exc:
            raise ProviderConfigurationError("Runway output size limit is invalid.") from exc
        if self.max_output_bytes < 1:
            raise ProviderConfigurationError("Runway output size limit is invalid.")

    def create_product_ugc(self, request: ProductUGCRecipeRequest) -> ProviderVideoJob:
        settings = get_settings()
        if settings.generation_mode != "real":
            raise ProviderConfigurationError("Runway recipe call is blocked: QVF_GENERATION_MODE must be real.")
        if not settings.allow_real_spend:
            raise ProviderConfigurationError("Runway recipe call is blocked: QVF_ALLOW_REAL_SPEND must be true.")
        payload = request.model_dump(mode="json", by_alias=True)
        response = self._request("POST", self.endpoint, json=payload, timeout=120)
        data = self._response_json(response)
        provider_job_id = self._task_id(
            data.get("id") or data.get("task_id") or data.get("uuid")
        )
        return ProviderVideoJob(
            provider=self.provider_name,
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "queued"),
            raw_response=self._safe_task_metadata(data),
        )

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        task_id = self._task_id(provider_job_id)
        data = self._get_task_raw(task_id)
        return ProviderVideoStatus(
            provider_job_id=task_id,
            status=str(data.get("status") or "unknown"),
            raw_response=self._safe_task_metadata(data),
        )

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
        task_id = self._task_id(provider_job_id)
        data = self._get_task_raw(task_id)
        outputs = data.get("output") or data.get("outputs") or []
        if isinstance(outputs, str):
            outputs = [outputs]
        if not isinstance(outputs, list) or not outputs:
            raise ProviderConfigurationError("Runway Product UGC task has no output yet.")
        if len(outputs) > RUNWAY_MAX_OUTPUTS:
            raise ProviderConfigurationError("Runway Product UGC task returned too many outputs.")
        if any(not isinstance(url, str) or not url.strip() for url in outputs):
            raise ProviderConfigurationError("Runway Product UGC task returned an invalid output URL.")
        target_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        task_hash = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:32]
        for index, url in enumerate(outputs):
            path = target_dir / f"runway_{task_hash}_{index}.mp4"
            self._download_output(str(url), path)
            paths.append(path)
        return paths

    def _get_task_raw(self, provider_job_id: str) -> dict[str, Any]:
        task_id = self._task_id(provider_job_id)
        response = self._request(
            "GET",
            f"https://api.dev.runwayml.com/v1/tasks/{quote(task_id, safe='')}",
            timeout=60,
        )
        return self._response_json(response)

    def _download_output(self, output_url: str, final_path: Path) -> None:
        part_path = final_path.with_suffix(f"{final_path.suffix}.part")
        try:
            part_path.unlink(missing_ok=True)
            self._stream_output_to_part(output_url, part_path)
            self._validate_mp4_signature(part_path)
            self._validate_with_ffprobe(part_path)
            # Validation happens against the .part file; replace only after the
            # complete payload is known to be a bounded, decodable MP4.
            part_path.replace(final_path)
        except Exception:
            part_path.unlink(missing_ok=True)
            raise

    def _stream_output_to_part(self, output_url: str, part_path: Path) -> None:
        current_url = output_url.strip()
        for redirect_count in range(RUNWAY_MAX_REDIRECTS + 1):
            self._validate_output_url(current_url)
            try:
                stream = (
                    self.client.stream(
                        "GET",
                        current_url,
                        headers={"X-Runway-Version": self.api_version},
                        timeout=180,
                        follow_redirects=False,
                    )
                    if self.client
                    else httpx.stream(
                        "GET",
                        current_url,
                        headers={"X-Runway-Version": self.api_version},
                        timeout=180,
                        follow_redirects=False,
                    )
                )
                with stream as response:
                    if response.status_code in RUNWAY_REDIRECT_STATUSES:
                        if redirect_count >= RUNWAY_MAX_REDIRECTS:
                            raise ProviderConfigurationError(
                                "Runway output download exceeded the redirect limit."
                            )
                        location = str(response.headers.get("location") or "").strip()
                        if not location:
                            raise ProviderConfigurationError(
                                "Runway output redirect omitted its destination."
                            )
                        current_url = urljoin(current_url, location)
                        continue
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise ProviderConfigurationError(
                            f"Runway output download failed with HTTP {exc.response.status_code}."
                        ) from exc
                    self._validate_download_headers(response)
                    total = 0
                    with part_path.open("wb") as handle:
                        for chunk in response.iter_bytes(
                            chunk_size=RUNWAY_DOWNLOAD_CHUNK_BYTES
                        ):
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total > self.max_output_bytes:
                                raise ProviderConfigurationError(
                                    "Runway output exceeded the configured size limit."
                                )
                            handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())
                    if total < 12:
                        raise ProviderConfigurationError(
                            "Runway output download was empty or truncated."
                        )
                    return
            except ProviderConfigurationError:
                raise
            except httpx.RequestError as exc:
                raise ProviderConfigurationError(
                    "Runway output download failed at the provider boundary."
                ) from exc
            except OSError as exc:
                raise ProviderConfigurationError(
                    "Runway output could not be written safely."
                ) from exc
        raise ProviderConfigurationError("Runway output download exceeded the redirect limit.")

    def _validate_output_url(self, value: str) -> None:
        if len(value) > 4096:
            raise ProviderConfigurationError("Runway output URL is invalid.")
        try:
            parts = urlsplit(value)
            host = self._normalized_host(parts.hostname or "")
            port = parts.port
        except (ValueError, UnicodeError) as exc:
            raise ProviderConfigurationError("Runway output URL is invalid.") from exc
        if (
            parts.scheme.lower() != "https"
            or not host
            or parts.username
            or parts.password
            or parts.fragment
            or port not in {None, 443}
        ):
            raise ProviderConfigurationError("Runway output URL must be public HTTPS.")
        if host not in self.output_hosts:
            raise ProviderConfigurationError("Runway output host is not allowlisted.")
        try:
            addresses = list(self.dns_resolver(host))
        except (OSError, ValueError) as exc:
            raise ProviderConfigurationError("Runway output host could not be resolved safely.") from exc
        if not addresses:
            raise ProviderConfigurationError("Runway output host could not be resolved safely.")
        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(str(raw_address).split("%", 1)[0])
            except ValueError as exc:
                raise ProviderConfigurationError(
                    "Runway output host resolved to an invalid address."
                ) from exc
            if not address.is_global:
                raise ProviderConfigurationError(
                    "Runway output host resolved to a non-public address."
                )

    def _validate_download_headers(self, response: httpx.Response) -> None:
        mime_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if mime_type not in RUNWAY_OUTPUT_MIME_TYPES:
            raise ProviderConfigurationError("Runway output MIME type is not an accepted MP4 type.")
        raw_length = str(response.headers.get("content-length") or "").strip()
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ProviderConfigurationError("Runway output Content-Length is invalid.") from exc
            if length < 12 or length > self.max_output_bytes:
                raise ProviderConfigurationError(
                    "Runway output Content-Length is outside the allowed bounds."
                )

    @staticmethod
    def _validate_mp4_signature(path: Path) -> None:
        try:
            with path.open("rb") as handle:
                header = handle.read(32)
        except OSError as exc:
            raise ProviderConfigurationError("Runway output signature could not be checked.") from exc
        if len(header) < 12 or header[4:8] != b"ftyp":
            raise ProviderConfigurationError("Runway output signature is not MP4.")

    def _validate_with_ffprobe(self, path: Path) -> None:
        if not self.ffprobe_path:
            raise ProviderConfigurationError(
                "ffprobe is required before accepting a Runway master output."
            )
        try:
            completed = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_type,width,height:format=format_name,duration,size",
                    "-of",
                    "json",
                    str(path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            payload = jsonlib.loads(completed.stdout or "{}")
            streams = payload.get("streams") if isinstance(payload, dict) else None
            format_data = payload.get("format") if isinstance(payload, dict) else None
            stream = streams[0] if isinstance(streams, list) and streams else None
            format_name = str(format_data.get("format_name") or "") if isinstance(format_data, dict) else ""
            duration = float(format_data.get("duration") or 0) if isinstance(format_data, dict) else 0
            size = int(format_data.get("size") or 0) if isinstance(format_data, dict) else 0
            width = int(stream.get("width") or 0) if isinstance(stream, dict) else 0
            height = int(stream.get("height") or 0) if isinstance(stream, dict) else 0
            if (
                not isinstance(stream, dict)
                or stream.get("codec_type") != "video"
                or width < 1
                or height < 1
                or duration <= 0
                or size != path.stat().st_size
                or not {item.strip() for item in format_name.split(",")} & {"mov", "mp4"}
            ):
                raise ProviderConfigurationError(
                    "ffprobe rejected the Runway output as an invalid MP4 master."
                )
        except ProviderConfigurationError:
            raise
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            jsonlib.JSONDecodeError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise ProviderConfigurationError(
                "ffprobe could not validate the Runway MP4 master."
            ) from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: int,
        include_auth: bool = True,
    ) -> httpx.Response:
        headers = {"X-Runway-Version": self.api_version}
        if include_auth:
            headers["Authorization"] = f"Bearer {self.api_secret}"
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            if self.client:
                response = self.client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    timeout=timeout,
                    follow_redirects=False,
                )
            else:
                response = httpx.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    timeout=timeout,
                    follow_redirects=False,
                )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise ProviderConfigurationError(
                f"Runway Product UGC request failed with HTTP {exc.response.status_code}: "
                f"{self._safe_response_excerpt(exc.response)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConfigurationError(f"Runway Product UGC request failed: {exc}") from exc

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderConfigurationError("Runway Product UGC returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderConfigurationError("Runway Product UGC returned an invalid response.")
        return payload

    @staticmethod
    def _task_id(value: object) -> str:
        task_id = str(value or "").strip()
        if not RUNWAY_TASK_ID_PATTERN.fullmatch(task_id):
            raise ProviderConfigurationError("Runway Product UGC returned an invalid task id.")
        return task_id

    @staticmethod
    def _normalized_host(value: str) -> str:
        host = str(value or "").strip().lower().rstrip(".")
        if not host:
            return ""
        try:
            return host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ProviderConfigurationError("Runway output host is invalid.") from exc

    @staticmethod
    def _resolve_host_ips(host: str) -> list[str]:
        records = socket.getaddrinfo(
            host,
            443,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        return list(dict.fromkeys(str(record[4][0]) for record in records))

    @staticmethod
    def _safe_task_metadata(data: dict[str, Any]) -> dict[str, Any]:
        outputs = data.get("output") or data.get("outputs") or []
        output_count = 1 if isinstance(outputs, str) else len(outputs)
        return {
            "id": data.get("id") or data.get("task_id") or data.get("uuid"),
            "status": data.get("status"),
            "failure": data.get("failure") or data.get("failureCode"),
            "failure_code": data.get("failureCode"),
            "output_count": output_count,
        }

    @staticmethod
    def _safe_response_excerpt(response: httpx.Response) -> str:
        text = response.text.replace("\n", " ").strip()
        text = re.sub(r"(https?://[^\s\"']+)\?[^\s\"']+", r"\1?[redacted]", text)
        return text[:500] if text else "no response body"
