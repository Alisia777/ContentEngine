from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

PROTECTED_ROOTS = {
    "app",
    "tests",
    "docs",
    "scripts",
    "sample_data",
    "templates",
    "static",
}

SAFE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}
SAFE_TOP_LEVEL_DIRS = {"logs"}
SAFE_FILE_NAMES = {".coverage"}
SAFE_FILE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".tmp", ".log"}

MEDIA_DIRS = {
    Path("media/output"),
    Path("media/provider"),
    Path("media/generation_reports"),
}
MEDIA_FILE_SUFFIXES = {".mp4", ".mov", ".webm", ".avi"}


@dataclass(frozen=True)
class CleanupTarget:
    path: Path
    reason: str


def relative(path: Path) -> Path:
    return path.resolve().relative_to(REPO_ROOT)


def is_under_protected_source(path: Path) -> bool:
    rel = relative(path)
    return bool(rel.parts and rel.parts[0] in PROTECTED_ROOTS)


def add_target(targets: list[CleanupTarget], path: Path, reason: str) -> None:
    resolved = path.resolve()
    if not resolved.exists():
        return
    if REPO_ROOT not in (resolved, *resolved.parents):
        return
    if any(existing.path.resolve() == resolved for existing in targets):
        return
    targets.append(CleanupTarget(resolved, reason))


def collect_safe_targets() -> list[CleanupTarget]:
    targets: list[CleanupTarget] = []

    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_dir() and path.name in SAFE_DIR_NAMES:
            add_target(targets, path, f"cache directory {path.name}")

    for dirname in SAFE_TOP_LEVEL_DIRS:
        add_target(targets, REPO_ROOT / dirname, f"runtime directory {dirname}")

    for path in REPO_ROOT.iterdir():
        if path.is_file() and path.name in SAFE_FILE_NAMES:
            add_target(targets, path, f"runtime file {path.name}")

    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if is_under_protected_source(path):
            continue
        if path.suffix.lower() in SAFE_FILE_SUFFIXES:
            add_target(targets, path, f"runtime file *{path.suffix.lower()}")

    return targets


def collect_media_targets() -> list[CleanupTarget]:
    targets: list[CleanupTarget] = []
    for rel_path in MEDIA_DIRS:
        add_target(targets, REPO_ROOT / rel_path, f"generated media directory {rel_path.as_posix()}")

    media_root = REPO_ROOT / "media"
    if media_root.exists():
        for path in media_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in MEDIA_FILE_SUFFIXES:
                add_target(targets, path, f"generated media file *{path.suffix.lower()}")

    for path in REPO_ROOT.iterdir():
        if path.is_file() and path.suffix.lower() in MEDIA_FILE_SUFFIXES:
            add_target(targets, path, f"top-level temporary media file *{path.suffix.lower()}")

    return targets


def remove_target(target: CleanupTarget) -> None:
    if target.path.is_dir():
        shutil.rmtree(target.path)
    else:
        target.path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or remove safe local runtime artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Preview cleanup. This is the default.")
    parser.add_argument("--apply", action="store_true", help="Remove safe cleanup targets.")
    parser.add_argument("--include-media", action="store_true", help="Also include generated media outputs.")
    args = parser.parse_args()

    apply = bool(args.apply)
    targets = collect_safe_targets()
    if args.include_media:
        targets.extend(collect_media_targets())

    unique_targets = sorted({target.path.resolve(): target for target in targets}.values(), key=lambda item: str(item.path))

    mode = "apply" if apply else "dry-run"
    print(f"Workspace cleanup mode: {mode}")
    print(f"Repository: {REPO_ROOT}")

    if not unique_targets:
        print("No local artifacts found.")
        return 0

    for target in unique_targets:
        rel = relative(target.path).as_posix()
        prefix = "Removing" if apply else "Would remove"
        print(f"{prefix}: {rel} ({target.reason})")
        if apply:
            remove_target(target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
