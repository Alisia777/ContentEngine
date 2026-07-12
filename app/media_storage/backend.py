from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    backend_name: str
    bucket: str
    key: str
    mime_type: str
    size_bytes: int
    sha256: str
    etag: str | None = None
    version_id: str | None = None


class StorageBackend(ABC):
    """Private object-store contract.

    Implementations return stable object coordinates and integrity metadata.
    A signed URL is an ephemeral capability and must never be returned from a
    persistence method or stored in ``MediaArtifact``.
    """

    name: str
    bucket: str

    def close(self) -> None:
        """Release process-scoped transport resources, if any."""

        return None

    @abstractmethod
    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    def put_file(
        self,
        key: str,
        source: Path,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        """Portable fallback; remote backends may override with streaming IO."""

        return self.put_bytes(
            key,
            source.read_bytes(),
            mime_type=mime_type,
            original_filename=original_filename or source.name,
        )

    @abstractmethod
    def head(self, key: str) -> StoredObject | None:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        raise NotImplementedError
