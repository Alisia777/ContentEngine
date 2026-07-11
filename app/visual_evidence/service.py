from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Protocol, Sequence
import unicodedata
import warnings

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.system_tools import resolve_tesseract
from app.visual_evidence.types import (
    FrameVisualEvidence,
    OCRVisualEvidence,
    ReferenceTextInput,
    VisualEvidencePolicy,
    VisualEvidenceReport,
)


TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)
FRAME_FIXES = {
    "visual_evidence_frames_missing": "extract_real_frames_from_decodable_video",
    "visual_evidence_frame_count_below_minimum": "extract_more_temporally_separated_real_frames",
    "visual_evidence_frame_not_decodable": "replace_corrupt_or_non_image_extracted_frames",
    "visual_evidence_resolution_below_minimum": "generate_or_attach_higher_resolution_video",
    "visual_evidence_duplicate_frames": "extract_temporally_diverse_frames_or_regenerate_frozen_video",
    "visual_evidence_freeze_detected": "regenerate_video_without_duplicate_frame_freeze",
}
OCR_FIXES = {
    "ocr_tool_unavailable": "install_local_tesseract_or_disable_only_when_ocr_is_not_required",
    "ocr_reference_evidence_missing": "provide_explicit_packaging_tokens_or_local_product_asset",
    "ocr_reference_extraction_failed": "provide_decodable_local_product_asset_or_explicit_packaging_tokens",
    "ocr_reference_evidence_too_large": "select_a_small_explicit_set_of_key_packaging_tokens",
    "ocr_frame_extraction_failed": "rerun_local_ocr_on_decodable_frames",
    "ocr_text_not_detected": "provide_frames_where_packaging_text_is_visible",
    "ocr_reference_tokens_missing_from_frames": "regenerate_or_review_product_packaging_identity",
}


class OCRBackend(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    def extract_text(self, image_path: Path, *, language: str, timeout_seconds: float) -> str: ...


class OCRExecutionError(RuntimeError):
    pass


class LocalTesseractOCR:
    """Small no-network adapter around an optional local Tesseract executable."""

    name = "local_tesseract"

    def __init__(
        self,
        executable_path: str | None = None,
        tessdata_prefix: str | Path | None = None,
    ):
        settings = get_settings()
        resolution = resolve_tesseract(settings) if executable_path is None else None
        candidate = executable_path if executable_path is not None else resolution.path
        if candidate and not Path(candidate).is_file():
            candidate = shutil.which(candidate)
        self.executable_path = candidate
        self.configuration_source = resolution.source if resolution else "injected"
        self.configured_explicitly = (
            resolution.configured_explicitly if resolution else bool(executable_path)
        )
        configured_tessdata = (
            tessdata_prefix if tessdata_prefix is not None else settings.tessdata_prefix
        )
        self.tessdata_prefix = (
            Path(str(configured_tessdata)).expanduser().resolve()
            if str(configured_tessdata or "").strip()
            else None
        )

    @property
    def available(self) -> bool:
        return bool(self.executable_path and Path(self.executable_path).is_file())

    def extract_text(self, image_path: Path, *, language: str, timeout_seconds: float) -> str:
        if not self.available:
            raise OCRExecutionError("local_tesseract_unavailable")
        try:
            completed = subprocess.run(
                [
                    str(self.executable_path),
                    str(image_path),
                    "stdout",
                    "-l",
                    language,
                    "--psm",
                    "6",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=self._subprocess_environment(),
            )
        except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
            raise OCRExecutionError("local_tesseract_execution_failed") from exc
        if completed.returncode != 0:
            raise OCRExecutionError("local_tesseract_execution_failed")
        return (completed.stdout or "")[:16_000]

    def readiness(self, *, required_languages: tuple[str, ...] = ("rus", "eng")) -> dict[str, object]:
        """Probe the executable and language packs without exposing its path."""

        required = [item.strip().lower() for item in required_languages if item.strip()]
        result: dict[str, object] = {
            "ready": False,
            "binary_ready": self.available,
            "configuration": self.configuration_source,
            "configured_explicitly": self.configured_explicitly,
            "tessdata_configured_explicitly": self.tessdata_prefix is not None,
            "tessdata_directory_ready": (
                self.tessdata_prefix.is_dir() if self.tessdata_prefix is not None else None
            ),
            "required_languages": required,
            "missing_languages": required,
            "language_check": "not_run",
        }
        if not self.available:
            result["language_check"] = "binary_missing"
            return result
        try:
            completed = subprocess.run(
                [str(self.executable_path), "--list-langs"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=self._subprocess_environment(),
            )
        except (OSError, UnicodeError, subprocess.SubprocessError):
            result["language_check"] = "probe_failed"
            return result
        if completed.returncode != 0:
            result["language_check"] = "probe_failed"
            return result
        installed = {
            line.strip().lower()
            for line in (completed.stdout or "").splitlines()
            if line.strip() and not line.lower().startswith("list of available")
        }
        missing = [language for language in required if language not in installed]
        result.update(
            {
                "ready": not missing,
                "missing_languages": missing,
                "language_check": "ready" if not missing else "languages_missing",
            }
        )
        return result

    def _subprocess_environment(self) -> dict[str, str] | None:
        if self.tessdata_prefix is None:
            return None
        return {**os.environ, "TESSDATA_PREFIX": str(self.tessdata_prefix)}


class VisualEvidenceService:
    def __init__(self, ocr_backend: OCRBackend | None = None):
        self.ocr_backend = ocr_backend or LocalTesseractOCR()

    def evaluate(
        self,
        frame_paths: Sequence[str | Path],
        *,
        references: Sequence[ReferenceTextInput | dict] | None = None,
        policy: VisualEvidencePolicy | dict | None = None,
    ) -> VisualEvidenceReport:
        resolved_policy = self._policy(policy)
        resolved_references = [
            item if isinstance(item, ReferenceTextInput) else ReferenceTextInput.model_validate(item)
            for item in (references or [])
        ]
        frames = [self._inspect_frame(index, Path(path), resolved_policy) for index, path in enumerate(frame_paths, 1)]
        blockers: list[str] = []
        if not frames:
            blockers.append("visual_evidence_frames_missing")
        if len(frames) < resolved_policy.min_frame_count:
            blockers.append("visual_evidence_frame_count_below_minimum")
        if any(not frame.decoded for frame in frames):
            blockers.append("visual_evidence_frame_not_decodable")
        if any("visual_evidence_resolution_below_minimum" in frame.blockers for frame in frames):
            blockers.append("visual_evidence_resolution_below_minimum")

        decoded_frames = [frame for frame in frames if frame.decoded and frame.perceptual_hash]
        unique_count, longest_run = self._diversity(decoded_frames, resolved_policy)
        unique_ratio = unique_count / len(decoded_frames) if decoded_frames else None
        freeze_ratio = longest_run / len(decoded_frames) if decoded_frames else None
        if len(decoded_frames) >= resolved_policy.min_frame_count:
            if unique_ratio is None or unique_ratio < resolved_policy.min_unique_frame_ratio:
                blockers.append("visual_evidence_duplicate_frames")
            if (
                longest_run >= resolved_policy.min_freeze_run_frames
                and freeze_ratio is not None
                and freeze_ratio >= resolved_policy.max_freeze_run_ratio
            ):
                blockers.append("visual_evidence_freeze_detected")

        ocr = self._evaluate_ocr(
            decoded_frames,
            references=resolved_references,
            policy=resolved_policy,
        )
        blockers.extend(ocr.blockers)
        blockers = list(dict.fromkeys(blockers))
        required_fixes = list(
            dict.fromkeys(
                fix
                for blocker in blockers
                if (fix := FRAME_FIXES.get(blocker) or OCR_FIXES.get(blocker))
            )
        )
        short_sides = [frame.short_side_px for frame in decoded_frames if frame.short_side_px is not None]
        long_sides = [frame.long_side_px for frame in decoded_frames if frame.long_side_px is not None]
        return VisualEvidenceReport(
            status="blocked" if blockers else "passed",
            frame_count=len(frames),
            decoded_frame_count=len(decoded_frames),
            unique_frame_count=unique_count,
            unique_frame_ratio=round(unique_ratio, 4) if unique_ratio is not None else None,
            longest_duplicate_run=longest_run,
            freeze_run_ratio=round(freeze_ratio, 4) if freeze_ratio is not None else None,
            minimum_short_side_observed_px=min(short_sides) if short_sides else None,
            minimum_long_side_observed_px=min(long_sides) if long_sides else None,
            policy=resolved_policy,
            frames=frames,
            ocr=ocr,
            blockers=blockers,
            required_fixes=required_fixes,
        )

    def evaluate_frame_result(
        self,
        frame_result: models.FrameExtractionResult | object | None,
        *,
        references: Sequence[ReferenceTextInput | dict] | None = None,
        policy: VisualEvidencePolicy | dict | None = None,
    ) -> VisualEvidenceReport:
        paths = list(getattr(frame_result, "frame_paths_json", None) or []) if frame_result else []
        return self.evaluate(paths, references=references, policy=policy)

    def evaluate_latest(
        self,
        db: Session,
        video_job_id: int,
        *,
        references: Sequence[ReferenceTextInput | dict] | None = None,
        policy: VisualEvidencePolicy | dict | None = None,
    ) -> VisualEvidenceReport:
        frame_result = db.scalar(
            select(models.FrameExtractionResult)
            .where(models.FrameExtractionResult.video_job_id == video_job_id)
            .order_by(models.FrameExtractionResult.id.desc())
        )
        return self.evaluate_frame_result(frame_result, references=references, policy=policy)

    @staticmethod
    def reference_from_product_asset(
        asset: models.ProductAsset | object,
        *,
        required_tokens: Sequence[str] | None = None,
        declared_text: str | None = None,
    ) -> ReferenceTextInput:
        """Adapt explicit ProductAsset evidence without guessing from names/URLs."""

        metadata = getattr(asset, "metadata_json", None) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        metadata_tokens = metadata.get("required_packaging_tokens") or metadata.get("packaging_tokens") or []
        if isinstance(metadata_tokens, str):
            metadata_tokens = [metadata_tokens]
        trusted_text = declared_text
        if trusted_text is None:
            trusted_text = metadata.get("packaging_text") or metadata.get("label_text") or metadata.get("ocr_text")
        source_path = None
        if str(getattr(asset, "source_type", "") or "").lower() == "local":
            candidate = str(getattr(asset, "source_ref", "") or "").strip()
            source_path = candidate or None
        return ReferenceTextInput(
            source_kind="product_asset",
            source_ref=f"product_asset:{getattr(asset, 'id', 'unknown')}",
            required_tokens=list(required_tokens or metadata_tokens),
            declared_text=str(trusted_text) if trusted_text else None,
            asset_path=source_path,
        )

    @staticmethod
    def _policy(policy: VisualEvidencePolicy | dict | None) -> VisualEvidencePolicy:
        if policy is None:
            return VisualEvidencePolicy()
        if isinstance(policy, VisualEvidencePolicy):
            return policy
        return VisualEvidencePolicy.model_validate(policy)

    @staticmethod
    def _inspect_frame(index: int, path: Path, policy: VisualEvidencePolicy) -> FrameVisualEvidence:
        blockers: list[str] = []
        if not path.is_file():
            return FrameVisualEvidence(
                index=index,
                path=path.as_posix(),
                blockers=["visual_evidence_frame_not_decodable"],
            )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as candidate:
                    image_format = candidate.format
                    candidate.verify()
                with Image.open(path) as candidate:
                    candidate.load()
                    width, height = candidate.size
                    image = candidate.convert("RGB")
                    perceptual_hash = VisualEvidenceService._perceptual_hash(image)
            short_side, long_side = sorted((width, height))
            if short_side < policy.min_short_side_px or long_side < policy.min_long_side_px:
                blockers.append("visual_evidence_resolution_below_minimum")
            return FrameVisualEvidence(
                index=index,
                path=path.as_posix(),
                decoded=True,
                image_format=image_format,
                width=width,
                height=height,
                short_side_px=short_side,
                long_side_px=long_side,
                sha256=VisualEvidenceService._sha256(path),
                perceptual_hash=perceptual_hash,
                blockers=blockers,
            )
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return FrameVisualEvidence(
                index=index,
                path=path.as_posix(),
                blockers=["visual_evidence_frame_not_decodable"],
            )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _perceptual_hash(image: Image.Image) -> str:
        grayscale = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(grayscale.getdata())
        bits = 0
        for row in range(8):
            offset = row * 9
            for column in range(8):
                bits = (bits << 1) | int(pixels[offset + column] > pixels[offset + column + 1])
        color_sample = image.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        color_signature = "".join(f"{channel // 16:x}" for channel in color_sample)
        return f"{bits:016x}{color_signature}"

    @staticmethod
    def _hash_distance(left: str, right: str) -> int:
        left_bits, left_color = left[:16], left[16:]
        right_bits, right_color = right[:16], right[16:]
        bit_distance = (int(left_bits, 16) ^ int(right_bits, 16)).bit_count()
        color_distance = sum(abs(int(a, 16) - int(b, 16)) for a, b in zip(left_color, right_color))
        return bit_distance + (color_distance // 3)

    @classmethod
    def _diversity(
        cls,
        frames: Sequence[FrameVisualEvidence],
        policy: VisualEvidencePolicy,
    ) -> tuple[int, int]:
        hashes = [frame.perceptual_hash for frame in frames if frame.perceptual_hash]
        if not hashes:
            return 0, 0
        representatives: list[str] = []
        for value in hashes:
            if not any(cls._hash_distance(value, representative) <= policy.perceptual_duplicate_distance for representative in representatives):
                representatives.append(value)
        longest_run = 1
        current_run = 1
        for previous, current in zip(hashes, hashes[1:]):
            if cls._hash_distance(previous, current) <= policy.perceptual_duplicate_distance:
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 1
        return len(representatives), longest_run

    def _evaluate_ocr(
        self,
        frames: Sequence[FrameVisualEvidence],
        *,
        references: Sequence[ReferenceTextInput],
        policy: VisualEvidencePolicy,
    ) -> OCRVisualEvidence:
        required = policy.ocr_required or bool(references)
        if not required:
            return OCRVisualEvidence(required=False, status="not_required")
        evidence = OCRVisualEvidence(
            required=True,
            status="blocked",
            backend=self.ocr_backend.name,
            tool_available=self.ocr_backend.available,
            reference_source_refs=[reference.source_ref for reference in references],
        )
        if not self.ocr_backend.available:
            evidence.blockers = ["ocr_tool_unavailable"]
            return evidence

        expected_tokens, reference_error = self._expected_tokens(references, policy)
        evidence.expected_tokens = expected_tokens
        if reference_error:
            evidence.blockers = [reference_error]
            return evidence
        if not expected_tokens:
            evidence.blockers = ["ocr_reference_evidence_missing"]
            return evidence
        if not frames:
            evidence.blockers = ["ocr_text_not_detected"]
            return evidence

        observed: list[str] = []
        try:
            for frame in frames:
                text = self.ocr_backend.extract_text(
                    Path(frame.path),
                    language=policy.ocr_language,
                    timeout_seconds=policy.ocr_timeout_seconds,
                )
                observed.extend(self._tokens(text, policy))
                evidence.processed_frame_count += 1
        except OCRExecutionError:
            evidence.blockers = ["ocr_frame_extraction_failed"]
            return evidence
        observed_tokens = list(dict.fromkeys(observed))[: policy.max_ocr_tokens]
        evidence.observed_tokens = observed_tokens
        if not observed_tokens:
            evidence.blockers = ["ocr_text_not_detected"]
            return evidence
        observed_set = set(observed_tokens)
        evidence.matched_tokens = [token for token in expected_tokens if token in observed_set]
        evidence.missing_tokens = [token for token in expected_tokens if token not in observed_set]
        evidence.token_match_ratio = round(len(evidence.matched_tokens) / len(expected_tokens), 4)
        if evidence.token_match_ratio < policy.required_token_match_ratio:
            evidence.blockers = ["ocr_reference_tokens_missing_from_frames"]
            return evidence
        evidence.status = "passed"
        return evidence

    def _expected_tokens(
        self,
        references: Sequence[ReferenceTextInput],
        policy: VisualEvidencePolicy,
    ) -> tuple[list[str], str | None]:
        tokens: list[str] = []
        try:
            for reference in references:
                if reference.required_tokens:
                    for value in reference.required_tokens:
                        tokens.extend(self._tokens(value, policy))
                elif reference.declared_text:
                    tokens.extend(self._tokens(reference.declared_text, policy))
                elif reference.asset_path:
                    tokens.extend(
                        self._tokens(
                            self.ocr_backend.extract_text(
                                Path(reference.asset_path),
                                language=policy.ocr_language,
                                timeout_seconds=policy.ocr_timeout_seconds,
                            ),
                            policy,
                        )
                    )
        except OCRExecutionError:
            return [], "ocr_reference_extraction_failed"
        unique_tokens = list(dict.fromkeys(tokens))
        if len(unique_tokens) > policy.max_ocr_tokens:
            return [], "ocr_reference_evidence_too_large"
        return unique_tokens, None

    @staticmethod
    def _tokens(text: str, policy: VisualEvidencePolicy) -> list[str]:
        normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
        return [
            token
            for token in TOKEN_PATTERN.findall(normalized)
            if len(token) >= policy.min_ocr_token_length
        ]
