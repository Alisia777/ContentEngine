"""Deterministically partition collected pytest items across CI jobs.

The plugin is opt-in (``-p scripts.pytest_shard_plugin``), so a normal local
``pytest`` invocation remains a single, unsharded run.  All workers still
collect the complete suite before deselection.  That preserves import-time
contract checks while assigning every fully expanded pytest node id to one and
only one worker.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Final

import pytest


SHARD_INDEX_ENV: Final = "QVF_PYTEST_SHARD_INDEX"
SHARD_TOTAL_ENV: Final = "QVF_PYTEST_SHARD_TOTAL"
_CONFIG_ATTRIBUTE: Final = "_qvf_pytest_shard"


def parse_shard_config(environment: Mapping[str, str]) -> tuple[int, int] | None:
    """Return ``(index, total)`` or fail closed for an invalid partial config."""

    raw_index = environment.get(SHARD_INDEX_ENV)
    raw_total = environment.get(SHARD_TOTAL_ENV)
    if raw_index is None and raw_total is None:
        return None
    if raw_index is None or raw_total is None:
        missing = SHARD_INDEX_ENV if raw_index is None else SHARD_TOTAL_ENV
        raise ValueError(f"pytest shard configuration is incomplete: missing {missing}")

    try:
        index = int(raw_index.strip())
        total = int(raw_total.strip())
    except (AttributeError, ValueError) as exc:
        raise ValueError("pytest shard index and total must be integers") from exc

    if total < 1:
        raise ValueError("pytest shard total must be at least 1")
    if index < 0 or index >= total:
        raise ValueError(
            f"pytest shard index must be between 0 and {total - 1}, got {index}"
        )
    return index, total


def shard_for_nodeid(nodeid: str, total: int) -> int:
    """Map one normalized pytest node id to a stable zero-based shard."""

    if total < 1:
        raise ValueError("pytest shard total must be at least 1")
    normalized = nodeid.replace("\\", "/")
    digest = sha256(normalized.encode("utf-8")).digest()
    return int.from_bytes(digest, byteorder="big", signed=False) % total


def pytest_configure(config: pytest.Config) -> None:
    import os

    try:
        shard = parse_shard_config(os.environ)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    setattr(config, _CONFIG_ATTRIBUTE, shard)


def pytest_report_header(config: pytest.Config) -> str | None:
    shard = getattr(config, _CONFIG_ATTRIBUTE, None)
    if shard is None:
        return None
    index, total = shard
    return f"QVF deterministic test shard {index + 1}/{total}"


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    shard = getattr(config, _CONFIG_ATTRIBUTE, None)
    if shard is None:
        return

    index, total = shard
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        target = selected if shard_for_nodeid(item.nodeid, total) == index else deselected
        target.append(item)

    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
