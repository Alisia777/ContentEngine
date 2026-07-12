from __future__ import annotations

import inspect

import pytest

from app.media_storage import factory
from app.media_storage.backend import StorageBackend, StoredObject
from app.routers.public_pilot import (
    _read_bounded_recipe_upload,
    product_ugc_recipe_draft,
)


class _TrackedBackend(StorageBackend):
    name = "tracked"
    bucket = "private"

    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1

    def put_bytes(self, key, content, *, mime_type, original_filename=None):
        return StoredObject(self.name, self.bucket, key, mime_type, len(content), "0" * 64)

    def head(self, key):
        return None

    def read_bytes(self, key):
        return b""

    def delete(self, key):
        return None

    def create_signed_get_url(self, key, *, expires_seconds, download_filename=None):
        return "https://storage.example.test/signed"


@pytest.fixture(autouse=True)
def reset_storage_cache():
    factory.close_storage_backends()
    yield
    factory.close_storage_backends()


def test_storage_backend_is_process_scoped_and_closed_once(monkeypatch):
    built: list[_TrackedBackend] = []

    def build(*, settings=None, environ=None):
        backend = _TrackedBackend()
        built.append(backend)
        return backend

    monkeypatch.setattr(factory, "build_storage_backend", build)
    first = factory.get_storage_backends()["tracked"]
    second = factory.get_storage_backends()["tracked"]

    assert first is second
    assert len(built) == 1
    factory.close_storage_backends()
    assert first.close_count == 1

    replacement = factory.get_storage_backends()["tracked"]
    assert replacement is not first
    assert len(built) == 2


def test_storage_configuration_change_gets_a_distinct_pool(monkeypatch):
    built: list[_TrackedBackend] = []

    def build(*, settings=None, environ=None):
        backend = _TrackedBackend()
        built.append(backend)
        return backend

    monkeypatch.setattr(factory, "build_storage_backend", build)
    first = factory.get_storage_backends()["tracked"]
    monkeypatch.setenv("QVF_STORAGE_BUCKET", "another-private-bucket")
    second = factory.get_storage_backends()["tracked"]

    assert first is not second
    assert len(built) == 2


def test_recipe_upload_route_runs_sync_storage_work_off_event_loop():
    assert not inspect.iscoroutinefunction(product_ugc_recipe_draft)
    assert inspect.iscoroutinefunction(_read_bounded_recipe_upload)
