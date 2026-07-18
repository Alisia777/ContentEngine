from pathlib import Path

import pytest

from app.assets.asset_storage import ProductAssetStorage
from app.assets.errors import AssetKitDataError
from app.assets.image_registry import ImageRegistry
from app.legacy_file_boundary import (
    LegacyFileBoundaryError,
    bombar_matrix_fixture,
    factory_matrix_fixture,
    factory_performance_fixture,
    legacy_reports_directory,
)


@pytest.mark.parametrize(
    ("resolver", "safe_value", "suffix"),
    [
        (factory_matrix_fixture, "sample_data/product_matrix.csv", "sample_data/product_matrix.csv"),
        (
            factory_performance_fixture,
            "sample_data/campaign_performance.csv",
            "sample_data/campaign_performance.csv",
        ),
        (bombar_matrix_fixture, "sample_data/bombar_matrix.csv", "sample_data/bombar_matrix.csv"),
        (legacy_reports_directory, "reports", "reports"),
    ],
)
def test_legacy_http_file_boundary_returns_only_server_owned_constants(
    resolver,
    safe_value: str,
    suffix: str,
) -> None:
    resolved = resolver(safe_value)

    assert isinstance(resolved, Path)
    assert resolved.is_absolute()
    assert resolved.as_posix().endswith(suffix)


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "../.env",
        "../../etc/passwd",
        "/etc/passwd",
        r"C:\\Windows\\win.ini",
        "sample_data/../.env",
        "reports/../../outside",
    ],
)
def test_legacy_http_file_boundary_rejects_traversal_and_absolute_paths(
    unsafe_value: str,
) -> None:
    for resolver in (
        factory_matrix_fixture,
        factory_performance_fixture,
        bombar_matrix_fixture,
        legacy_reports_directory,
    ):
        with pytest.raises(LegacyFileBoundaryError):
            resolver(unsafe_value)


def test_empty_performance_fixture_disables_optional_import() -> None:
    assert factory_performance_fixture("") is None
    assert factory_performance_fixture(None) is None


def test_image_registry_never_probes_a_local_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_probed(*_args, **_kwargs):
        raise AssertionError("untrusted local path was probed")

    monkeypatch.setattr(Path, "exists", fail_if_probed)

    descriptor = ImageRegistry().describe("../../private/secret-product.png")

    assert descriptor.source_type == "local"
    assert descriptor.exists is False
    assert descriptor.width is None
    assert descriptor.height is None
    assert "metadata-only" in descriptor.warnings[0]


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "../../private/image.png",
        "file:///etc/passwd",
        "https://user:password@example.com/image.png",
        "https:///missing-host.png",
    ],
)
def test_asset_url_boundary_rejects_local_paths_and_credentials(unsafe_url: str) -> None:
    with pytest.raises(AssetKitDataError):
        ProductAssetStorage.remote_asset_url(unsafe_url)


def test_asset_url_boundary_accepts_remote_http_assets() -> None:
    url = "https://cdn.example.test/products/image.png?signature=secret"

    assert ProductAssetStorage.remote_asset_url(url) == url
