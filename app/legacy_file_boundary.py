from __future__ import annotations

from pathlib import Path


class LegacyFileBoundaryError(ValueError):
    """Raised when a legacy HTTP form tries to address a server-side path."""


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_FACTORY_MATRIX = _PROJECT_ROOT / "sample_data" / "product_matrix.csv"
_FACTORY_PERFORMANCE = _PROJECT_ROOT / "sample_data" / "campaign_performance.csv"
_BOMBAR_MATRIX = _PROJECT_ROOT / "sample_data" / "bombar_matrix.csv"
_REPORTS_DIRECTORY = _PROJECT_ROOT / "reports"


def _reference(value: str | Path | None) -> str:
    return str(value or "").strip().replace("\\", "/")


def factory_matrix_fixture(value: str | Path) -> Path:
    if _reference(value) not in {
        "sample_data/product_matrix.csv",
        "./sample_data/product_matrix.csv",
    }:
        raise LegacyFileBoundaryError(
            "The path-based Factory OS endpoint only accepts the bundled product matrix. "
            "Upload custom CSV data through the matrix import endpoint."
        )
    return _FACTORY_MATRIX


def factory_performance_fixture(value: str | Path | None) -> Path | None:
    reference = _reference(value)
    if not reference:
        return None
    if reference not in {
        "sample_data/campaign_performance.csv",
        "./sample_data/campaign_performance.csv",
    }:
        raise LegacyFileBoundaryError(
            "The path-based Factory OS endpoint only accepts the bundled performance fixture. "
            "Upload custom metrics through the campaign performance import endpoint."
        )
    return _FACTORY_PERFORMANCE


def bombar_matrix_fixture(value: str | Path) -> Path:
    if _reference(value) not in {
        "sample_data/bombar_matrix.csv",
        "./sample_data/bombar_matrix.csv",
    }:
        raise LegacyFileBoundaryError(
            "The path-based Bombar dry-run endpoint only accepts the bundled matrix. "
            "Upload custom matrix data through the matrix import endpoint."
        )
    return _BOMBAR_MATRIX


def legacy_reports_directory(value: str | Path) -> Path:
    if _reference(value) not in {"reports", "./reports"}:
        raise LegacyFileBoundaryError(
            "Legacy HTTP report exports are restricted to the application reports directory."
        )
    return _REPORTS_DIRECTORY
