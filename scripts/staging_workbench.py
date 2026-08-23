#!/usr/bin/env python3
"""Fail-closed static staging preview for ContentEngine.

This workbench never creates, links, migrates, or deploys a Supabase project.
It only builds the browser application with public coordinates for an already
provisioned, separate staging project and serves that artifact on loopback.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SITE = ROOT / "web" / "app"
STAGING_ROOT = ROOT / ".local" / "staging"
STAGING_SITE = STAGING_ROOT / "site"
STAGING_CONFIG = STAGING_SITE / "config.js"
STAGING_ENV = ROOT / ".env.staging"
COMPOSE_FILE = ROOT / "docker-compose.staging.yml"
COMPOSE_PROJECT = "contentengine-staging-workbench"
PRODUCTION_PROJECT_REF = "iyckwryrucqrxwlowxow"
PROJECT_REF_PATTERN = re.compile(r"[a-z0-9]{20}")
PUBLISHABLE_KEY_PATTERN = re.compile(r"sb_publishable_[A-Za-z0-9._-]{16,}")
JWT_PATTERN = re.compile(
    r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
)
ALLOWED_ENV_KEYS = frozenset(
    {
        "STAGING_SUPABASE_URL",
        "STAGING_SUPABASE_PROJECT_REF",
        "STAGING_SUPABASE_PUBLISHABLE_KEY",
    }
)
FORBIDDEN_ENV_NAME_MARKERS = (
    "API_KEY",
    "JWT",
    "PASSWORD",
    "PRIVATE",
    "SECRET",
    "SERVICE_ROLE",
    "TOKEN",
)
FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"sb_secret_", re.IGNORECASE),
    re.compile(r"service[_-]?role", re.IGNORECASE),
    re.compile(r"postgres(?:ql)?://", re.IGNORECASE),
)
PLACEHOLDER_MARKERS = (
    "<",
    ">",
    "changeme",
    "example",
    "placeholder",
    "replace",
    "your_",
)
CONFIG_PREFIX = "window.CONTENTENGINE_CONFIG = Object.freeze("


class StagingSettings(NamedTuple):
    supabase_url: str
    project_ref: str
    publishable_key: str


def _strip_env_value(value: str, *, line_number: int) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean[0] in {"'", '"'}:
        if clean[-1] != clean[0]:
            raise ValueError(
                f".env.staging line {line_number} has an unterminated quote"
            )
        clean = clean[1:-1]
    if not clean:
        raise ValueError(f".env.staging line {line_number} has an empty value")
    return clean


def read_staging_env(path: Path = STAGING_ENV) -> dict[str, str]:
    """Read a deliberately tiny env contract without shell evaluation."""

    if not path.is_file():
        raise ValueError(
            f"staging env is missing: {path}; copy .env.staging.example first"
        )
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export ") or "=" not in line:
            raise ValueError(
                f".env.staging line {line_number} must be a plain KEY=value"
            )
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            upper_key = key.upper()
            if any(marker in upper_key for marker in FORBIDDEN_ENV_NAME_MARKERS):
                raise ValueError(
                    f"server credential field is forbidden in .env.staging: {key}"
                )
            raise ValueError(f"unsupported field in .env.staging: {key}")
        if key in values:
            raise ValueError(f"duplicate field in .env.staging: {key}")
        values[key] = _strip_env_value(raw_value, line_number=line_number)

    missing = sorted(ALLOWED_ENV_KEYS.difference(values))
    if missing:
        raise ValueError(
            ".env.staging is missing required fields: " + ", ".join(missing)
        )
    return values


def _reject_credential_shape(value: str) -> None:
    lower_value = value.lower()
    if any(pattern.search(value) for pattern in FORBIDDEN_VALUE_PATTERNS):
        raise ValueError("staging browser config contains a server credential shape")
    if JWT_PATTERN.fullmatch(value):
        raise ValueError("legacy JWT/anon keys are forbidden; use a publishable key")
    if any(marker in lower_value for marker in PLACEHOLDER_MARKERS):
        raise ValueError("staging coordinates still contain a placeholder")


def validate_staging_settings(values: dict[str, str]) -> StagingSettings:
    project_ref = values.get("STAGING_SUPABASE_PROJECT_REF", "").strip()
    supabase_url = values.get("STAGING_SUPABASE_URL", "").strip()
    publishable_key = values.get("STAGING_SUPABASE_PUBLISHABLE_KEY", "").strip()

    if PROJECT_REF_PATTERN.fullmatch(project_ref) is None:
        raise ValueError("staging Supabase project ref must be 20 lowercase characters")
    if project_ref == PRODUCTION_PROJECT_REF:
        raise ValueError("production Supabase project ref is forbidden in staging")

    _reject_credential_shape(supabase_url)
    _reject_credential_shape(publishable_key)
    try:
        parsed = urlsplit(supabase_url)
        parsed_port = parsed.port
    except ValueError as error:
        raise ValueError("staging Supabase URL is invalid") from error
    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "::1"} or hostname.endswith(".localhost"):
        raise ValueError("loopback Supabase URLs are forbidden in staging")
    try:
        is_loopback_address = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback_address = False
    if is_loopback_address:
        raise ValueError("loopback Supabase URLs are forbidden in staging")

    expected_hostname = f"{project_ref}.supabase.co"
    if (
        parsed.scheme != "https"
        or hostname != expected_hostname
        or parsed_port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "staging Supabase URL must be the matching HTTPS project origin"
        )
    if PUBLISHABLE_KEY_PATTERN.fullmatch(publishable_key) is None:
        raise ValueError(
            "only a browser-safe sb_publishable_* key is allowed in staging"
        )

    return StagingSettings(
        supabase_url=f"https://{expected_hostname}",
        project_ref=project_ref,
        publishable_key=publishable_key,
    )


def load_staging_settings(path: Path = STAGING_ENV) -> StagingSettings:
    return validate_staging_settings(read_staging_env(path))


def staging_config(settings: StagingSettings) -> dict[str, object]:
    return {
        "APP_NAME": "ContentEngine Staging",
        "STAGING_WORKBENCH": True,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_PUBLISHABLE_KEY": settings.publishable_key,
        "RPC_SCHEMA": "public",
        "STORAGE_BUCKET": "contentengine-private",
        "MOCK_ENABLED": True,
        "REAL_GENERATION_ENABLED": False,
        "ALLOW_REAL_SPEND": False,
        "CREATOR_GENERATE_MOCK_ONLY": True,
        "CHARACTER_PERFORMANCE_ENABLED": False,
        "MAX_BATCH_SIZE": 20,
        "MAX_MEDIA_BATCH_FILES": 20,
        "MAX_UPLOAD_BYTES": 52_428_800,
    }


def staging_config_text(settings: StagingSettings) -> str:
    return (
        CONFIG_PREFIX
        + json.dumps(
            staging_config(settings),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + ");\n"
    )


def _safe_output(source_dir: Path, output_dir: Path) -> None:
    source = source_dir.resolve()
    output = output_dir.resolve()
    if output == source or output in source.parents or source in output.parents:
        raise ValueError("staging output must be separate from browser source")
    if output.name in {"", ".", ".."}:
        raise ValueError("staging output path is too broad")


def build_staging_site(
    settings: StagingSettings,
    *,
    source_dir: Path = SOURCE_SITE,
    output_dir: Path = STAGING_SITE,
) -> Path:
    """Copy the static app and generate its only environment-specific file."""

    if not source_dir.is_dir() or not (source_dir / "index.html").is_file():
        raise ValueError("browser source directory is incomplete")
    _safe_output(source_dir, output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=".staging-build-", dir=output_dir.parent)
    )
    temporary_site = temporary_root / "site"
    source_root = source_dir.resolve()

    def ignore_source_config(directory: str, names: list[str]) -> set[str]:
        if Path(directory).resolve() == source_root and "config.js" in names:
            return {"config.js"}
        return set()

    try:
        shutil.copytree(source_dir, temporary_site, ignore=ignore_source_config)
        config_path = temporary_site / "config.js"
        config_path.write_text(staging_config_text(settings), encoding="utf-8")
        validate_generated_config(config_path)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temporary_site.replace(output_dir)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
    return output_dir / "config.js"


def _decode_generated_config(text: str) -> dict[str, object]:
    if not text.startswith(CONFIG_PREFIX) or not text.endswith(");\n"):
        raise ValueError("generated staging config.js has an invalid wrapper")
    payload = text[len(CONFIG_PREFIX) : -3]
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("generated staging config.js payload must be an object")
    return decoded


def validate_generated_config(path: Path = STAGING_CONFIG) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"generated staging config is missing: {path}")
    text = path.read_text(encoding="utf-8")
    config = _decode_generated_config(text)
    settings = validate_staging_settings(
        {
            "STAGING_SUPABASE_URL": str(config.get("SUPABASE_URL") or ""),
            "STAGING_SUPABASE_PROJECT_REF": (
                urlsplit(str(config.get("SUPABASE_URL") or "")).hostname or ""
            ).split(".", 1)[0],
            "STAGING_SUPABASE_PUBLISHABLE_KEY": str(
                config.get("SUPABASE_PUBLISHABLE_KEY") or ""
            ),
        }
    )
    expected = staging_config(settings)
    if config != expected:
        raise ValueError("generated staging config contains unsupported fields")
    return config


def _find_executable(name: str, windows_candidates: tuple[Path, ...] = ()) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    for candidate in windows_candidates:
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(f"{name} is required")


def docker_executable() -> str:
    return _find_executable(
        "docker",
        (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "DockerDesktop"
            / "resources"
            / "bin"
            / "docker.exe",
            Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        ),
    )


def staging_test_python_executable(
    *,
    root: Path | None = None,
    platform_name: str | None = None,
) -> str:
    """Select the repository-owned test interpreter, never a global Python."""

    project_root = ROOT if root is None else root
    platform = os.name if platform_name is None else platform_name
    windows_python = project_root / ".venv" / "Scripts" / "python.exe"
    posix_python = project_root / ".venv" / "bin" / "python"
    candidates = (
        (windows_python, posix_python)
        if platform == "nt"
        else (posix_python, windows_python)
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise SystemExit(
        "staging-test requires the repository .venv Python interpreter"
    )


def compose_args(*args: str) -> list[str]:
    return [
        docker_executable(),
        "compose",
        "--project-name",
        COMPOSE_PROJECT,
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def run(
    args: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("+", subprocess.list2cmdline(args), flush=True)
    completed = subprocess.run(args, cwd=ROOT, check=False, text=True)
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def staging_build() -> None:
    settings = load_staging_settings()
    config_path = build_staging_site(settings)
    print(
        json.dumps(
            {
                "ok": True,
                "site": str(STAGING_SITE),
                "config": str(config_path),
                "project_ref": settings.project_ref,
                "supabase_origin": settings.supabase_url,
                "real_generation_enabled": False,
                "allow_real_spend": False,
                "character_performance_enabled": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def staging_up() -> None:
    staging_build()
    run(compose_args("up", "-d", "staging-web"))


def staging_down() -> None:
    run(compose_args("down"))


def staging_status() -> None:
    built = STAGING_CONFIG.is_file()
    project_ref = None
    supabase_origin = None
    if built:
        config = validate_generated_config()
        supabase_origin = str(config["SUPABASE_URL"])
        project_ref = (urlsplit(supabase_origin).hostname or "").split(".", 1)[0]
    print(
        json.dumps(
            {
                "site_built": built,
                "site": str(STAGING_SITE),
                "url": "http://127.0.0.1:8768",
                "project_ref": project_ref,
                "supabase_origin": supabase_origin,
                "real_generation_enabled": False,
                "allow_real_spend": False,
                "character_performance_enabled": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    run(compose_args("ps"), check=False)


def staging_test() -> None:
    pytest_python = staging_test_python_executable()
    run(
        [
            pytest_python,
            "-m",
            "pytest",
            "-q",
            "tests/test_staging_workbench_v1.py",
        ]
    )
    run(compose_args("config", "--quiet"))
    node = _find_executable("node")
    if STAGING_CONFIG.is_file():
        validate_generated_config()
        run([node, "--check", str(STAGING_CONFIG)])
    else:
        run([node, "--check", str(SOURCE_SITE / "config.example.js")])


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(
        description="Build and serve the fail-closed ContentEngine staging preview"
    )
    command_parser.add_argument(
        "command",
        choices=(
            "staging-build",
            "staging-up",
            "staging-down",
            "staging-status",
            "staging-test",
        ),
    )
    return command_parser


def main() -> int:
    command = parser().parse_args().command
    actions = {
        "staging-build": staging_build,
        "staging-up": staging_up,
        "staging-down": staging_down,
        "staging-status": staging_status,
        "staging-test": staging_test,
    }
    try:
        actions[command]()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"staging workbench refused to continue: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
