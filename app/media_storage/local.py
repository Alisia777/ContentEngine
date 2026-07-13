from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import os
from pathlib import Path
from urllib.parse import quote, urlencode
from uuid import uuid4

from app.media_storage.backend import StorageBackend, StoredObject
from app.media_storage.errors import StorageNotFound, StorageSecurityError


class LocalStorage(StorageBackend):
    """Filesystem adapter for development and hermetic tests.

    It keeps the same tenant object keys and signed-capability semantics as a
    remote backend.  Writes use an atomic rename so readers never observe a
    partially written object.
    """

    name = "local"

    def __init__(
        self,
        root: Path,
        *,
        bucket: str = "media",
        signing_secret: str,
        public_base_url: str = "/api/local-media",
        clock=lambda: datetime.now(UTC),
    ) -> None:
        if len(signing_secret.encode("utf-8")) < 16:
            raise StorageSecurityError("Local storage signing secret must be at least 16 bytes.")
        self.root = Path(root)
        self.bucket = self._safe_bucket(bucket)
        self.signing_secret = signing_secret.encode("utf-8")
        self.public_base_url = public_base_url.rstrip("/")
        self.clock = clock
        (self.root / self.bucket).mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.part"
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return self._metadata(key, target, mime_type=mime_type)

    def head(self, key: str) -> StoredObject | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return self._metadata(key, path, mime_type="application/octet-stream")

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
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as input_file, temporary.open("wb") as output_file:
                while True:
                    chunk = input_file.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                    output_file.write(chunk)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=size,
            sha256=digest.hexdigest(),
        )

    def read_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageNotFound("Object was not found.")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists() and not path.is_file():
            raise StorageSecurityError("Object key does not resolve to a regular file.")
        if path.is_file():
            path.unlink()

    def create_signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        self._path(key)
        expires_at = int(self.clock().timestamp()) + int(expires_seconds)
        disposition = self._disposition(download_filename)
        signature = self._signature(key, expires_at, disposition)
        query = urlencode(
            {
                "expires": str(expires_at),
                "disposition": disposition,
                "signature": signature,
            }
        )
        encoded_key = "/".join(quote(part, safe="-_.~") for part in key.split("/"))
        return f"{self.public_base_url}/{quote(self.bucket, safe='-_.~')}/{encoded_key}?{query}"

    def validate_signed_get(
        self,
        key: str,
        *,
        expires_at: int,
        disposition: str,
        signature: str,
    ) -> bool:
        self._path(key)
        if int(expires_at) < int(self.clock().timestamp()):
            return False
        expected = self._signature(key, int(expires_at), disposition)
        return hmac.compare_digest(expected, str(signature))

    def _signature(self, key: str, expires_at: int, disposition: str) -> str:
        payload = f"GET\n{self.bucket}\n{key}\n{expires_at}\n{disposition}".encode("utf-8")
        return hmac.new(self.signing_secret, payload, hashlib.sha256).hexdigest()

    def _path(self, key: str) -> Path:
        normalized = str(key or "").strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or "\x00" in normalized:
            raise StorageSecurityError("Invalid object key.")
        root = (self.root / self.bucket).resolve()
        candidate = (root / normalized).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise StorageSecurityError("Object key escapes the storage bucket.") from exc
        return candidate

    def path_for_key(self, key: str) -> Path:
        """Resolve a key for the signed local-development response only."""

        path = self._path(key)
        if not path.is_file():
            raise StorageNotFound("Object was not found.")
        return path

    def _metadata(self, key: str, path: Path, *, mime_type: str) -> StoredObject:
        content = path.read_bytes()
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    @staticmethod
    def _safe_bucket(value: str) -> str:
        bucket = str(value or "").strip()
        if not bucket or "/" in bucket or "\\" in bucket or bucket in {".", ".."}:
            raise StorageSecurityError("Invalid storage bucket.")
        return bucket

    @staticmethod
    def _disposition(filename: str | None) -> str:
        if not filename:
            return "inline"
        safe = Path(filename).name.replace('"', "").replace("\r", "").replace("\n", "")[:180]
        return f'attachment; filename="{safe or "download"}"'
