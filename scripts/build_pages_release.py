#!/usr/bin/env python3
"""Build and verify the browser-only GitHub Pages release artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


PROJECT_REF_PATTERN = re.compile(r"[a-z0-9]{20}")
PUBLISHABLE_KEY_PATTERN = re.compile(r"sb_publishable_[A-Za-z0-9._-]{16,}")
APP_SCRIPT_PATTERN = re.compile(
    r'<script\s+type="module"\s+src="(?P<src>\./app\.js\?v=[A-Za-z0-9][A-Za-z0-9._-]*)"'
)
LEARNING_GATE_PATTERN = re.compile(
    r'const GENERATION_LEARNING_GATE_VERSION = "(?P<version>[0-9]{4}-[0-9]{2}-[0-9]{2}\.v[0-9]+)";'
)
HTML_ASSET_PATTERN = re.compile(r'(?:src|href)="(?P<path>\./[^"#]+)"')
CSS_ASSET_PATTERN = re.compile(r"url\(\s*[\"']?(?P<path>\./[^\"')]+)")
JS_IMPORT_PATTERN = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*)["'](?P<path>\./[^"']+)["']"""
)
SECRET_SHAPE_PATTERNS = (
    re.compile(r"sb_secret_[A-Za-z0-9._-]{16,}"),
    re.compile(r"sbp_[A-Za-z0-9._-]{16,}"),
    re.compile(r"postgres(?:ql)?://[^\s\"']+@", re.IGNORECASE),
)
LOCAL_ONLY_PATTERN = re.compile(r"__SET_SUPABASE_|127\.0\.0\.1|localhost")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _without_query(value: str) -> str:
    return value.split("?", 1)[0]


def _resolve_relative(base: Path, value: str, root: Path) -> Path:
    relative = _without_query(value)
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"asset escapes release root: {value}") from error
    return candidate


def _require_asset(base: Path, value: str, root: Path) -> Path:
    candidate = _resolve_relative(base, value, root)
    if not candidate.is_file():
        raise ValueError(f"missing release asset: {value}")
    return candidate


def _extract_learning_gate(path: Path) -> str:
    match = LEARNING_GATE_PATTERN.search(_read_text(path))
    if match is None:
        raise ValueError(f"learning gate version is missing in {path}")
    return match.group("version")


def _validate_asset_graph(site_root: Path) -> str:
    index_path = site_root / "index.html"
    index = _read_text(index_path)
    app_match = APP_SCRIPT_PATTERN.search(index)
    if app_match is None:
        raise ValueError("index.html must load a versioned ./app.js module")
    app_script = app_match.group("src")

    for match in HTML_ASSET_PATTERN.finditer(index):
        _require_asset(site_root, match.group("path"), site_root)

    for stylesheet in site_root.glob("*.css"):
        for match in CSS_ASSET_PATTERN.finditer(_read_text(stylesheet)):
            _require_asset(stylesheet.parent, match.group("path"), site_root)

    entrypoint = _require_asset(site_root, app_script, site_root)
    pending = [entrypoint]
    visited: set[Path] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        for match in JS_IMPORT_PATTERN.finditer(_read_text(module)):
            dependency = _require_asset(
                module.parent,
                match.group("path"),
                site_root,
            )
            if dependency.suffix == ".js":
                pending.append(dependency)
    return app_script


def _validate_public_artifact(site_root: Path) -> None:
    for path in site_root.rglob("*"):
        if not path.is_file() or path.name == "release-manifest.json":
            continue
        try:
            text = _read_text(path)
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_SHAPE_PATTERNS:
            if pattern.search(text):
                raise ValueError(f"server credential shape entered artifact: {path}")
        if LOCAL_ONLY_PATTERN.search(text):
            raise ValueError(f"local-only coordinate entered artifact: {path}")


def _artifact_hashes(site_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(site_root.rglob("*")):
        if not path.is_file() or path.name == "release-manifest.json":
            continue
        relative = path.relative_to(site_root).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _safe_output(source_dir: Path, output_dir: Path) -> None:
    source = source_dir.resolve()
    output = output_dir.resolve()
    if (
        output == source
        or source in output.parents
        or output in source.parents
        or output == Path("/")
    ):
        raise ValueError("output directory must be separate from the source")
    if output.name in {"", ".", ".."}:
        raise ValueError("output directory is too broad")


def build_release(
    *,
    source_dir: Path,
    output_dir: Path,
    edge_function: Path,
    project_ref: str,
    expected_project_ref: str,
    publishable_key: str,
) -> dict[str, object]:
    if PROJECT_REF_PATTERN.fullmatch(project_ref) is None:
        raise ValueError("SUPABASE_PROJECT_REF has an invalid format")
    if project_ref != expected_project_ref:
        raise ValueError("SUPABASE_PROJECT_REF does not match production")
    if PUBLISHABLE_KEY_PATTERN.fullmatch(publishable_key) is None:
        raise ValueError("Only a browser-safe Supabase publishable key is allowed")
    if not source_dir.is_dir() or not (source_dir / "index.html").is_file():
        raise ValueError("browser source directory is incomplete")
    if not edge_function.is_file():
        raise ValueError("creator-generate Edge source is missing")

    _safe_output(source_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir)
    (output_dir / "config.example.js").unlink(missing_ok=True)
    (output_dir / ".nojekyll").touch()

    config = {
        "APP_NAME": "Контент ИИ Завод",
        "SUPABASE_URL": f"https://{project_ref}.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": publishable_key,
        "RPC_SCHEMA": "public",
        "STORAGE_BUCKET": "contentengine-private",
        "MOCK_ENABLED": True,
        "REAL_GENERATION_ENABLED": True,
        "REAL_PROVIDER": "runway",
        "REAL_MODEL": "gen4_turbo",
        "REAL_DURATION_SECONDS": 5,
        "REAL_ESTIMATED_CREDITS": 25,
        "REAL_ESTIMATED_COST_USD": 0.25,
        "MAX_BATCH_SIZE": 50,
        "MAX_UPLOAD_BYTES": 52_428_800,
    }
    (output_dir / "config.js").write_text(
        "window.CONTENTENGINE_CONFIG = Object.freeze("
        + json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        + ");\n",
        encoding="utf-8",
    )

    app_script = _validate_asset_graph(output_dir)
    client_gate = _extract_learning_gate(output_dir / "app.js")
    edge_gate = _extract_learning_gate(edge_function)
    if client_gate != edge_gate:
        raise ValueError(
            "client and creator-generate learning gate versions differ"
        )
    _validate_public_artifact(output_dir)

    hashes = _artifact_hashes(output_dir)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "app_script": app_script,
        "learning_gate_version": client_gate,
        "artifact_file_count": len(hashes),
        "sha256": hashes,
    }
    (output_dir / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--edge-function", type=Path, required=True)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--expected-project-ref", required=True)
    parser.add_argument("--publishable-key", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = build_release(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        edge_function=args.edge_function,
        project_ref=args.project_ref,
        expected_project_ref=args.expected_project_ref,
        publishable_key=args.publishable_key,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "app_script": manifest["app_script"],
                "learning_gate_version": manifest["learning_gate_version"],
                "artifact_file_count": manifest["artifact_file_count"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
