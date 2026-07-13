from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from app.media_storage.backend import StorageBackend, StoredObject
from app.media_storage.errors import StorageError, StorageNotFound, StorageSecurityError


class S3CompatibleStorage(StorageBackend):
    """Small dependency-free AWS Signature V4 adapter for private S3 buckets."""

    name = "s3"

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None = None,
        client: httpx.Client | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        parsed = urlsplit(endpoint_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise StorageSecurityError("S3 endpoint must be an absolute HTTP(S) URL.")
        if not bucket or "/" in bucket or "\\" in bucket:
            raise StorageSecurityError("Invalid S3 bucket.")
        if not access_key_id or not secret_access_key:
            raise StorageSecurityError("S3 credentials are required.")
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket = bucket
        self.region = region or "us-east-1"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token
        self._owns_client = client is None
        self.client = client or httpx.Client()
        self.clock = clock

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        sha256 = hashlib.sha256(content).hexdigest()
        headers = {"content-type": mime_type, "x-amz-meta-sha256": sha256}
        response = self._request("PUT", key, content=content, headers=headers)
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=sha256,
            etag=self._clean_etag(response.headers.get("etag")),
            version_id=response.headers.get("x-amz-version-id"),
        )

    def head(self, key: str) -> StoredObject | None:
        response = self._request("HEAD", key, allow_not_found=True)
        if response.status_code == 404:
            return None
        sha256 = response.headers.get("x-amz-meta-sha256") or ""
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=response.headers.get("content-type") or "application/octet-stream",
            size_bytes=int(response.headers.get("content-length") or 0),
            sha256=sha256,
            etag=self._clean_etag(response.headers.get("etag")),
            version_id=response.headers.get("x-amz-version-id"),
        )

    def put_file(
        self,
        key: str,
        source: Path,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        source = Path(source)
        if not source.is_file():
            raise StorageNotFound("Source file was not found.")
        sha256, size = self._file_fingerprint(source)

        def chunks():
            with source.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        response = self._request(
            "PUT",
            key,
            content=chunks(),
            payload_hash=sha256,
            headers={
                "content-type": mime_type,
                "content-length": str(size),
                "x-amz-meta-sha256": sha256,
            },
        )
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha256,
            etag=self._clean_etag(response.headers.get("etag")),
            version_id=response.headers.get("x-amz-version-id"),
        )

    def read_bytes(self, key: str) -> bytes:
        response = self._request("GET", key, allow_not_found=True)
        if response.status_code == 404:
            raise StorageNotFound("Object was not found.")
        return response.content

    def delete(self, key: str) -> None:
        self._request("DELETE", key, allow_not_found=True)

    def create_signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        if not 1 <= int(expires_seconds) <= 604800:
            raise StorageSecurityError("S3 signed URL lifetime must be from 1 to 604800 seconds.")
        now = self.clock().astimezone(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        url = self._object_url(key)
        parsed = urlsplit(url)
        query: list[tuple[str, str]] = [
            ("X-Amz-Algorithm", "AWS4-HMAC-SHA256"),
            ("X-Amz-Credential", f"{self.access_key_id}/{scope}"),
            ("X-Amz-Date", amz_date),
            ("X-Amz-Expires", str(int(expires_seconds))),
            ("X-Amz-SignedHeaders", "host"),
        ]
        if self.session_token:
            query.append(("X-Amz-Security-Token", self.session_token))
        if download_filename:
            safe_name = (
                Path(download_filename).name.replace('"', "").replace("\r", "").replace("\n", "")[:180]
                or "download"
            )
            query.append(("response-content-disposition", f'attachment; filename="{safe_name}"'))
        canonical_query = self._canonical_query(query)
        canonical_request = "\n".join(
            [
                "GET",
                self._canonical_uri(parsed.path),
                canonical_query,
                f"host:{parsed.netloc.lower()}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, f"{canonical_query}&X-Amz-Signature={signature}", "")
        )

    def _request(
        self,
        method: str,
        key: str,
        *,
        content: bytes | Iterable[bytes] | None = None,
        payload_hash: str | None = None,
        headers: dict[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        url = self._object_url(key)
        now = self.clock().astimezone(UTC)
        if payload_hash is None:
            if content is not None and not isinstance(content, bytes):
                raise StorageSecurityError("Streaming S3 uploads require a precomputed payload hash.")
            payload_hash = hashlib.sha256(content or b"").hexdigest()
        signed_headers = {str(k).lower(): str(v).strip() for k, v in (headers or {}).items()}
        signed_headers["host"] = urlsplit(url).netloc.lower()
        signed_headers["x-amz-content-sha256"] = payload_hash
        signed_headers["x-amz-date"] = now.strftime("%Y%m%dT%H%M%SZ")
        if self.session_token:
            signed_headers["x-amz-security-token"] = self.session_token
        authorization = self._authorization(method, url, signed_headers, payload_hash, now)
        request_headers = {**signed_headers, "authorization": authorization}
        try:
            response = self.client.request(method, url, headers=request_headers, content=content, timeout=180)
        except httpx.RequestError as exc:
            raise StorageError(f"S3 request failed: {exc}") from exc
        if allow_not_found and response.status_code == 404:
            return response
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"S3 request failed with HTTP {response.status_code}.") from exc
        return response

    def _authorization(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload_hash: str,
        now: datetime,
    ) -> str:
        parsed = urlsplit(url)
        canonical_names = sorted(headers)
        canonical_headers = "".join(f"{name}:{' '.join(headers[name].split())}\n" for name in canonical_names)
        signed_names = ";".join(canonical_names)
        canonical_query = self._canonical_query(parse_qsl(parsed.query, keep_blank_values=True))
        canonical_request = "\n".join(
            [
                method.upper(),
                self._canonical_uri(parsed.path),
                canonical_query,
                canonical_headers,
                signed_names,
                payload_hash,
            ]
        )
        date_stamp = now.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                now.strftime("%Y%m%dT%H%M%SZ"),
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp), string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return (
            f"AWS4-HMAC-SHA256 Credential={self.access_key_id}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        )

    def _signing_key(self, date_stamp: str) -> bytes:
        key_date = hmac.new(
            ("AWS4" + self.secret_access_key).encode("utf-8"),
            date_stamp.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        key_region = hmac.new(key_date, self.region.encode("utf-8"), hashlib.sha256).digest()
        key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
        return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()

    def _object_url(self, key: str) -> str:
        safe_key = self._safe_key(key)
        encoded = "/".join(quote(part, safe="-_.~") for part in safe_key.split("/"))
        return f"{self.endpoint_url}/{quote(self.bucket, safe='-_.~')}/{encoded}"

    @staticmethod
    def _safe_key(key: str) -> str:
        value = str(key or "").strip().replace("\\", "/")
        if (
            not value
            or value.startswith("/")
            or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise StorageSecurityError("Invalid object key.")
        return value

    @staticmethod
    def _canonical_uri(path: str) -> str:
        # ``_object_url`` has already percent-encoded path segments.  Preserve
        # those escapes in the canonical request instead of double-encoding %.
        return quote(path or "/", safe="/%-_.~")

    @staticmethod
    def _canonical_query(items) -> str:
        normalized = sorted((str(key), str(value)) for key, value in items)
        return urlencode(normalized, doseq=True, quote_via=quote, safe="-_.~")

    @staticmethod
    def _clean_etag(value: str | None) -> str | None:
        return value.strip('"') if value else None

    @staticmethod
    def _file_fingerprint(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size
