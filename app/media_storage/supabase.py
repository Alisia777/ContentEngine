from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx

from app.media_storage.backend import StorageBackend, StoredObject
from app.media_storage.errors import StorageError, StorageNotFound, StorageSecurityError
from app.supabase_keys import server_api_key_headers


class SupabaseStorage(StorageBackend):
    """Private Supabase Storage REST adapter using a server-side service key."""

    name = "supabase"

    def __init__(
        self,
        *,
        project_url: str,
        bucket: str,
        service_role_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not project_url.startswith(("https://", "http://")):
            raise StorageSecurityError("Supabase project URL must be absolute.")
        if not bucket or "/" in bucket or "\\" in bucket:
            raise StorageSecurityError("Invalid Supabase bucket.")
        try:
            self._server_headers = server_api_key_headers(service_role_key)
        except ValueError as exc:
            raise StorageSecurityError("A valid Supabase server key is required.") from exc
        self.project_url = project_url.rstrip("/")
        self.bucket = bucket
        self.service_role_key = service_role_key
        self._owns_client = client is None
        self.client = client or httpx.Client()

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
        response = self._request(
            "POST",
            f"object/{self._encoded_bucket_key(key)}",
            content=content,
            headers={
                "content-type": mime_type,
                "x-upsert": "false",
                "x-metadata": self._metadata_header(sha256),
            },
        )
        payload = self._json(response)
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=sha256,
            etag=response.headers.get("etag"),
            version_id=str(payload.get("id") or payload.get("version") or "") or None,
        )

    def head(self, key: str) -> StoredObject | None:
        response = self._request(
            "GET",
            f"object/info/{self._encoded_bucket_key(key)}",
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        user_metadata = payload.get("user_metadata")
        if not isinstance(user_metadata, dict):
            user_metadata = payload.get("userMetadata")
        if not isinstance(user_metadata, dict):
            user_metadata = metadata.get("user_metadata") or metadata.get("metadata")
        if not isinstance(user_metadata, dict):
            user_metadata = {}
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=str(metadata.get("mimetype") or metadata.get("contentType") or "application/octet-stream"),
            size_bytes=int(metadata.get("size") or payload.get("size") or 0),
            sha256=str(user_metadata.get("sha256") or metadata.get("sha256") or ""),
            etag=str(metadata.get("eTag") or metadata.get("etag") or "") or None,
            version_id=str(payload.get("version") or payload.get("id") or "") or None,
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
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        sha256 = digest.hexdigest()

        def chunks():
            with source.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        response = self._request(
            "POST",
            f"object/{self._encoded_bucket_key(key)}",
            content=chunks(),
            headers={
                "content-type": mime_type,
                "content-length": str(size),
                "x-upsert": "false",
                "x-metadata": self._metadata_header(sha256),
            },
        )
        payload = self._json(response)
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha256,
            etag=response.headers.get("etag"),
            version_id=str(payload.get("id") or payload.get("version") or "") or None,
        )

    def read_bytes(self, key: str) -> bytes:
        response = self._request("GET", f"object/{self._encoded_bucket_key(key)}", allow_not_found=True)
        if response.status_code == 404:
            raise StorageNotFound("Object was not found.")
        return response.content

    def delete(self, key: str) -> None:
        self._request(
            "DELETE",
            f"object/{quote(self.bucket, safe='-_.~')}",
            json={"prefixes": [self._safe_key(key)]},
            allow_not_found=True,
        )

    def create_signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        if not 1 <= int(expires_seconds) <= 604800:
            raise StorageSecurityError("Signed URL lifetime must be from 1 to 604800 seconds.")
        response = self._request(
            "POST",
            f"object/sign/{self._encoded_bucket_key(key)}",
            json={"expiresIn": int(expires_seconds)},
        )
        payload = self._json(response)
        signed_path = payload.get("signedURL") or payload.get("signedUrl")
        if not isinstance(signed_path, str) or not signed_path:
            raise StorageError("Supabase did not return a signed URL.")
        signed_url = urljoin(f"{self.project_url}/", signed_path.lstrip("/"))
        if download_filename:
            safe_name = (
                Path(download_filename).name.replace('"', "").replace("\r", "").replace("\n", "")[:180]
                or "download"
            )
            separator = "&" if "?" in signed_url else "?"
            signed_url = f"{signed_url}{separator}download={quote(safe_name, safe='-_.~')}"
        return signed_url

    def _request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | Iterable[bytes] | None = None,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        request_headers = {**self._server_headers, **(headers or {})}
        url = f"{self.project_url}/storage/v1/{path.lstrip('/')}"
        try:
            response = self.client.request(
                method,
                url,
                headers=request_headers,
                content=content,
                json=json,
                timeout=180,
            )
        except httpx.RequestError as exc:
            raise StorageError(f"Supabase Storage request failed: {exc}") from exc
        if allow_not_found and response.status_code == 404:
            return response
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"Supabase Storage request failed with HTTP {response.status_code}.") from exc
        return response

    def _encoded_bucket_key(self, key: str) -> str:
        safe_key = self._safe_key(key)
        encoded_key = "/".join(quote(part, safe="-_.~") for part in safe_key.split("/"))
        return f"{quote(self.bucket, safe='-_.~')}/{encoded_key}"

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
    def _json(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise StorageError("Supabase Storage returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise StorageError("Supabase Storage returned an invalid response shape.")
        return payload

    @staticmethod
    def _metadata_header(sha256: str) -> str:
        encoded = json.dumps(
            {"sha256": str(sha256)},
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.b64encode(encoded).decode("ascii")
