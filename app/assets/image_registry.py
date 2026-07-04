from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from app.assets.types import ProductAssetDescriptor


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
SECRET_QUERY_KEYS = {"token", "signature", "sig", "expires", "x-amz-signature", "x-amz-credential", "x-amz-security-token"}


class ImageRegistry:
    def describe(self, raw_reference: str | dict) -> ProductAssetDescriptor:
        source = self._source(raw_reference)
        sanitized = self._sanitize(source)
        parsed = urlparse(sanitized)
        is_url = parsed.scheme in {"http", "https"}
        path = Path(parsed.path if is_url else sanitized)
        extension = path.suffix.lower() or None
        filename = path.name or None
        mime_type = mimetypes.guess_type(filename or sanitized)[0]
        exists = bool(is_url or path.exists())
        warnings = []
        width, height = (None, None)
        if not is_url and path.exists():
            width, height = self._local_dimensions(path)
            if width is None or height is None:
                warnings.append("Local image dimensions unavailable; no computer vision inspection was performed.")
        if source != sanitized:
            warnings.append("Private URL query parameters were stripped from stored asset reference.")
        return ProductAssetDescriptor(
            source_ref=sanitized,
            source_type="url" if is_url else "local",
            asset_type=self.classify(filename or sanitized),
            filename=filename,
            extension=extension,
            mime_type=mime_type,
            width=width,
            height=height,
            exists=exists,
            warnings=warnings,
            metadata={"raw_kind": type(raw_reference).__name__},
        )

    @staticmethod
    def classify(filename: str) -> str:
        value = filename.lower()
        if any(token in value for token in ["logo", "brandmark", "logotype"]):
            return "logo"
        if any(token in value for token in ["label", "closeup", "close-up", "detail", "ingredients", "back"]):
            return "label_closeup"
        if any(token in value for token in ["lifestyle", "usage", "use", "hand", "room", "model"]):
            return "lifestyle"
        if any(token in value for token in ["packshot", "main", "front", "hero", "product", "bottle"]):
            return "packshot"
        return "unknown"

    @staticmethod
    def _source(raw_reference: str | dict) -> str:
        if isinstance(raw_reference, dict):
            for key in ("url", "path", "src", "source", "source_ref"):
                value = raw_reference.get(key)
                if value:
                    return str(value)
            return ""
        return str(raw_reference or "")

    @staticmethod
    def _sanitize(source: str) -> str:
        parsed = urlparse(source)
        if parsed.scheme not in {"http", "https"}:
            return source
        query_keys = {part.split("=", 1)[0].lower() for part in parsed.query.split("&") if part}
        if query_keys.intersection(SECRET_QUERY_KEYS):
            return urlunparse(parsed._replace(query="", fragment=""))
        return urlunparse(parsed._replace(fragment=""))

    @staticmethod
    def _local_dimensions(path: Path) -> tuple[int | None, int | None]:
        try:
            from PIL import Image

            with Image.open(path) as image:
                return image.size
        except Exception:
            return None, None
