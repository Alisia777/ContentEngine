from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.pytest_shard_plugin import (
    SHARD_INDEX_ENV,
    SHARD_TOTAL_ENV,
    parse_shard_config,
    shard_for_nodeid,
)


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
SHARD_TOTAL = 6


def test_ci_runs_six_deterministic_python_shards_with_isolated_paths() -> None:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["test"]

    assert job["strategy"] == {
        "fail-fast": False,
        "max-parallel": SHARD_TOTAL,
        "matrix": {"shard": list(range(SHARD_TOTAL))},
    }
    assert job["timeout-minutes"] == 45
    assert job["env"][SHARD_INDEX_ENV] == "${{ matrix.shard }}"
    assert job["env"][SHARD_TOTAL_ENV] == str(SHARD_TOTAL)
    assert "${{ matrix.shard }}" in job["env"]["QVF_DATABASE_URL"]
    assert "${{ matrix.shard }}" in job["env"]["QVF_MEDIA_ROOT"]

    test_step = next(step for step in job["steps"] if step["name"] == "Run test suite")
    assert test_step["run"] == (
        "python -m pytest -q -p scripts.pytest_shard_plugin "
        "--durations=25 --durations-min=1.0"
    )


def test_hash_partition_assigns_every_test_file_representative_exactly_once() -> None:
    test_files = sorted((ROOT / "tests").glob("test_*.py"))
    assert test_files
    nodeids = [f"tests/{path.name}::__file_contract__" for path in test_files]

    assignments = {
        index: {
            nodeid
            for nodeid in nodeids
            if shard_for_nodeid(nodeid, SHARD_TOTAL) == index
        }
        for index in range(SHARD_TOTAL)
    }
    flattened = [nodeid for nodeids_for_shard in assignments.values() for nodeid in nodeids_for_shard]

    assert set(flattened) == set(nodeids)
    assert len(flattened) == len(nodeids)
    assert all(assignments.values())


def test_hash_partition_is_stable_and_normalizes_path_separators() -> None:
    nodeid = "tests/test_workflow.py::test_example[param-1]"

    first = shard_for_nodeid(nodeid, SHARD_TOTAL)
    assert first == shard_for_nodeid(nodeid, SHARD_TOTAL)
    assert first == shard_for_nodeid(nodeid.replace("/", "\\"), SHARD_TOTAL)


@pytest.mark.parametrize(
    "environment, message",
    [
        ({SHARD_INDEX_ENV: "0"}, "missing"),
        ({SHARD_TOTAL_ENV: "6"}, "missing"),
        ({SHARD_INDEX_ENV: "abc", SHARD_TOTAL_ENV: "6"}, "integers"),
        ({SHARD_INDEX_ENV: "0", SHARD_TOTAL_ENV: "0"}, "at least 1"),
        ({SHARD_INDEX_ENV: "6", SHARD_TOTAL_ENV: "6"}, "between 0 and 5"),
        ({SHARD_INDEX_ENV: "-1", SHARD_TOTAL_ENV: "6"}, "between 0 and 5"),
    ],
)
def test_malformed_shard_configuration_fails_closed(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_shard_config(environment)


def test_pytest_plugin_rejects_malformed_ci_environment() -> None:
    environment = dict(os.environ)
    environment[SHARD_INDEX_ENV] = "not-an-index"
    environment[SHARD_TOTAL_ENV] = str(SHARD_TOTAL)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "scripts.pytest_shard_plugin",
            "tests/test_ci_sharding_contract.py",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == pytest.ExitCode.USAGE_ERROR
    assert "pytest shard index and total must be integers" in output
