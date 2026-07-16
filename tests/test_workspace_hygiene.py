from __future__ import annotations

import subprocess
import sys
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def git_binary() -> str:
    configured = os.environ.get("GIT_BINARY")
    if configured:
        return configured
    discovered = shutil.which("git")
    if discovered:
        return discovered
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe"
    if bundled.exists():
        return str(bundled)
    raise AssertionError("git binary is required for workspace hygiene tests")


def run_git(*args: str) -> str:
    result = subprocess.run(
        [git_binary(), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_workspace_hygiene_gitignore_covers_runtime_artifacts():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    required_entries = {
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "media/",
        "media/**",
        "logs/",
        "logs/**",
        "*.log",
        ".env",
        ".env.*",
        "!.env.example",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".coverage",
        "htmlcov/",
        ".DS_Store",
        "Thumbs.db",
        "*.mp4",
        "*.mov",
        "*.webm",
        "*.avi",
        "*.tmp",
    }
    assert required_entries.issubset(set(gitignore))
    assert "!web/app/assets/training/*.mp4" in gitignore


def test_clean_local_artifacts_dry_run_is_safe():
    result = subprocess.run(
        [sys.executable, "scripts/clean_local_artifacts.py", "--dry-run"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Workspace cleanup mode: dry-run" in result.stdout
    assert "Would remove: app/main.py" not in result.stdout
    assert "Would remove: tests/test_workspace_hygiene.py" not in result.stdout
    assert "Would remove: docs/WORKSPACE_HYGIENE.md" not in result.stdout
    assert "Would remove: scripts/clean_local_artifacts.py" not in result.stdout


def test_no_runtime_artifacts_tracked_in_repository():
    tracked_files = run_git("ls-files").splitlines()
    forbidden_suffixes = (".db", ".sqlite", ".sqlite3", ".mp4", ".mov", ".webm", ".avi")
    forbidden_exact = {".env"}
    forbidden_prefixes = ("media/", "logs/")
    curated_training_prefix = "web/app/assets/training/"
    curated_training_suffixes = (".mp4", ".webm")
    curated_training_max_bytes = 20 * 1024 * 1024

    offenders = []
    for file_path in tracked_files:
        normalized = file_path.replace("\\", "/")
        if normalized in forbidden_exact:
            offenders.append(normalized)
        elif normalized.startswith(forbidden_prefixes):
            offenders.append(normalized)
        elif normalized.endswith(forbidden_suffixes):
            is_curated_training_asset = (
                normalized.startswith(curated_training_prefix)
                and normalized.endswith(curated_training_suffixes)
            )
            if not is_curated_training_asset:
                offenders.append(normalized)
                continue
            asset = REPO_ROOT / normalized
            assert 0 < asset.stat().st_size <= curated_training_max_bytes

    assert offenders == []
