#!/usr/bin/env python3
"""Permanent local/staging workbench command surface."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from urllib import error, request
from urllib.parse import urlsplit
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
LOCAL_SUPABASE = LOCAL / "supabase"
LOCAL_SITE = LOCAL / "site"
LOCAL_DOCKER = LOCAL / "docker"
LOCAL_DOCKER_MEDIA = LOCAL_DOCKER / "media"
LOCAL_DOCKER_DATA = LOCAL_DOCKER / "data"
LOCAL_OWNER_CREDENTIALS = LOCAL / "owner.local.json"
LOCAL_PROJECT = LOCAL / "project.local.json"
SUPABASE_CLI_VERSION = "2.109.1"
SUPABASE_CLI_CACHE_TIMEOUT_SECONDS = 20
SUPABASE_CLI_BOOTSTRAP_TIMEOUT_SECONDS = 120
LOCAL_EDGE_RUNTIME_CONTAINER = "supabase_edge_runtime_contentengine-local"
LOCAL_KONG_CONTAINER = "supabase_kong_contentengine-local"
LOCAL_EDGE_HEALTH_URL = (
    f"http://{LOCAL_EDGE_RUNTIME_CONTAINER}:8081/_internal/health"
)
LOCAL_ENV = {
    "QVF_RUNTIME_PROFILE": "development",
    "QVF_GENERATION_MODE": "mock",
    "QVF_LLM_PROVIDER": "mock",
    "QVF_VIDEO_PROVIDER": "mock",
    "QVF_MOCK_PROVIDER_ENABLED": "true",
    "QVF_ALLOW_REAL_SPEND": "false",
    "QVF_CREATOR_GENERATE_MOCK_ONLY": "true",
    "QVF_CHARACTER_PERFORMANCE_ENABLED": "false",
}
FALLBACK_LOCAL_PUBLISHABLE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicmVmIjoic3VwYWJhc2UtZGVtbyIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjQxNzY5MjAwLCJleHAiOjE3OTk1MzU2MDB9."
    "jU7nQ9pAKTIFcR0MOKwEhP6I9nYkO_5nR9EIk8D8T8s"
)
DEFAULT_PYTEST_SHARDS = 6
PYTEST_RUNS_RELATIVE = Path(".dev-artifacts") / "pytest-runs"


def env() -> dict[str, str]:
    values = os.environ.copy()
    values.update(LOCAL_ENV)
    values["SUPABASE_TELEMETRY_DISABLED"] = "1"
    # Docker Desktop can update its CLI outside the process PATH. Its credential
    # helper lives beside docker.exe and must be discoverable by Compose.
    docker_bin = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "resources" / "bin"
    if docker_bin.is_dir():
        values["PATH"] = str(docker_bin) + os.pathsep + values.get("PATH", "")
    ffmpeg = next((LOCAL / "tools").glob("ffmpeg-*/**/ffmpeg.exe"), None)
    ffprobe = next((LOCAL / "tools").glob("ffmpeg-*/**/ffprobe.exe"), None)
    if ffmpeg and ffprobe:
        values["QVF_FFMPEG_PATH"] = str(ffmpeg)
        values["QVF_FFPROBE_PATH"] = str(ffprobe)
    return values


def run(args: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", subprocess.list2cmdline(args), flush=True)
    return subprocess.run(args, cwd=ROOT, env=env(), check=check, text=True, capture_output=capture)


def ensure_local_docker_dirs() -> None:
    """Keep mutable Compose media and SQLite data inside this worktree."""

    for directory in (LOCAL_DOCKER_MEDIA, LOCAL_DOCKER_DATA):
        directory.mkdir(parents=True, exist_ok=True)


def require_tools(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise SystemExit("Missing required local tools: " + ", ".join(missing))


def docker_executable() -> str:
    candidates = [
        shutil.which("docker"),
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise SystemExit("Docker CLI is required; start or install Docker Desktop")


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Stop a timed-out tool and children created by its launcher."""

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/pid", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


def _run_bounded_npx_probe(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run one npx resolution probe without allowing an npm stall to persist."""

    print("+", subprocess.list2cmdline(args), flush=True)
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        env=env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=os.name != "nt",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        process.communicate()
        raise SystemExit(
            f"Timed out after {timeout}s while resolving pinned Supabase CLI "
            f"{SUPABASE_CLI_VERSION}; terminated the bootstrap process tree"
        ) from None
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


@functools.cache
def _resolved_supabase_executable() -> tuple[str, ...]:
    """Resolve exactly one pinned CLI, preferring npm cache without registry access."""

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise SystemExit("Node npx is required for the pinned local Supabase CLI")

    package = f"supabase@{SUPABASE_CLI_VERSION}"
    offline = [npx, "--yes", "--offline", package]
    cached_probe = _run_bounded_npx_probe(
        [*offline, "--version"], timeout=SUPABASE_CLI_CACHE_TIMEOUT_SECONDS
    )
    if cached_probe.returncode == 0:
        return tuple(offline)

    print(
        f"Pinned Supabase CLI {SUPABASE_CLI_VERSION} is absent from the npm cache; "
        "performing one bounded bootstrap",
        flush=True,
    )
    cold_probe = _run_bounded_npx_probe(
        [npx, "--yes", package, "--version"],
        timeout=SUPABASE_CLI_BOOTSTRAP_TIMEOUT_SECONDS,
    )
    if cold_probe.returncode != 0:
        detail = (cold_probe.stderr or cold_probe.stdout or "no npm diagnostic").strip()
        raise SystemExit(
            f"Pinned Supabase CLI {SUPABASE_CLI_VERSION} bootstrap failed; "
            f"retry when npm registry access is available. {detail[:500]}"
        )
    return tuple(offline)


def supabase_executable() -> list[str]:
    """Use npm's cached, pinned CLI on every local Supabase invocation."""

    return list(_resolved_supabase_executable())


def compose_args(*args: str) -> list[str]:
    return [
        docker_executable(), "compose", "-f", "docker-compose.yml", "-f",
        "docker-compose.local.yml", *args,
    ]


def ensure_local_edge_runtime() -> None:
    """Recover the enabled Edge Runtime after Docker Desktop restarts.

    Supabase CLI can report an already-created local project as started while
    one support container remains exited. The portal then fails closed and the
    server-owned generation strategy catalog disappears. Start only the known
    local Edge Runtime container and verify it through Kong's Docker DNS before
    exposing the portal.
    """
    docker = docker_executable()
    containers = run(
        [
            docker,
            "ps",
            "-a",
            "--filter",
            f"name=^/{LOCAL_EDGE_RUNTIME_CONTAINER}$",
            "--format",
            "{{.Names}}",
        ],
        capture=True,
    ).stdout.splitlines()
    if containers != [LOCAL_EDGE_RUNTIME_CONTAINER]:
        raise SystemExit("Expected one local Supabase Edge Runtime container")

    running = run(
        [
            docker,
            "inspect",
            "--format",
            "{{.State.Running}}",
            LOCAL_EDGE_RUNTIME_CONTAINER,
        ],
        capture=True,
    ).stdout.strip().lower()
    if running != "true":
        run([docker, "start", LOCAL_EDGE_RUNTIME_CONTAINER])

    for _ in range(60):
        probe = run(
            [
                docker,
                "exec",
                LOCAL_KONG_CONTAINER,
                "wget",
                "-qO-",
                LOCAL_EDGE_HEALTH_URL,
            ],
            check=False,
            capture=True,
        )
        if probe.returncode == 0:
            try:
                payload = json.loads(probe.stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("message") == "ok":
                print("Local Supabase Edge Runtime ready", flush=True)
                return
        time.sleep(0.5)
    raise SystemExit("Local Supabase Edge Runtime did not become ready")


def write_local_site() -> None:
    LOCAL.mkdir(exist_ok=True)
    if LOCAL_SITE.exists():
        shutil.rmtree(LOCAL_SITE)
    shutil.copytree(ROOT / "web" / "app", LOCAL_SITE)
    shutil.copytree(ROOT / "dev" / "browser", LOCAL_SITE / "workbench")
    status = run(supabase_args("status", "-o", "env"), check=False, capture=True)
    output = status.stdout or ""
    key_match = re.search(r'^PUBLISHABLE_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    if key_match is None:
        key_match = re.search(r'^ANON_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    url_match = re.search(r'^API_URL="?([^"\r\n]+)', output, re.MULTILINE)
    publishable = key_match.group(1) if key_match else FALLBACK_LOCAL_PUBLISHABLE_KEY
    api_url = url_match.group(1) if url_match else "http://127.0.0.1:54321"
    parsed_api_url = urlsplit(api_url)
    if (
        parsed_api_url.scheme != "http"
        or parsed_api_url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or not parsed_api_url.port
        or parsed_api_url.path not in ("", "/")
        or parsed_api_url.query
        or parsed_api_url.fragment
    ):
        raise SystemExit("Local Supabase API URL must be a loopback HTTP origin")
    local_api_origin = f"{parsed_api_url.scheme}://{parsed_api_url.netloc}"
    local_realtime_origin = f"ws://{parsed_api_url.netloc}"
    config = {
        "APP_NAME": "ContentEngine Local",
        "LOCAL_DEVELOPMENT": True,
        "LOCAL_SUPABASE_ORIGIN": local_api_origin,
        "SUPABASE_URL": api_url,
        "SUPABASE_PUBLISHABLE_KEY": publishable,
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
    config_text = (
        "window.CONTENTENGINE_CONFIG = Object.freeze("
        + json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        + ");\n"
    )
    (LOCAL_SITE / "config.js").write_text(config_text, encoding="utf-8")
    local_revision = hashlib.sha256(
        config_text.encode("utf-8") + (LOCAL_SITE / "app.js").read_bytes()
    ).hexdigest()[:16]
    index_path = LOCAL_SITE / "index.html"
    index_text = index_path.read_text(encoding="utf-8")
    index_text = re.sub(
        r'(\./(?:config|app)\.js)\?[^"\']+',
        rf'\1?local-workbench={local_revision}',
        index_text,
    )
    index_text = index_text.replace(
        "img-src 'self' data: blob: https://*.supabase.co;",
        f"img-src 'self' data: blob: https://*.supabase.co {local_api_origin};",
    ).replace(
        "media-src 'self' blob: https://*.supabase.co;",
        f"media-src 'self' blob: https://*.supabase.co {local_api_origin};",
    ).replace(
        "connect-src 'self' https://*.supabase.co wss://*.supabase.co;",
        (
            "connect-src 'self' https://*.supabase.co wss://*.supabase.co "
            f"{local_api_origin} {local_realtime_origin};"
        ),
    ).replace("; upgrade-insecure-requests", "")
    index_path.write_text(index_text, encoding="utf-8")


def local_owner_credentials() -> dict[str, str]:
    if LOCAL_OWNER_CREDENTIALS.is_file():
        payload = json.loads(LOCAL_OWNER_CREDENTIALS.read_text(encoding="utf-8"))
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("email"), str)
            and isinstance(payload.get("password"), str)
        ):
            return {"email": payload["email"], "password": payload["password"]}
        raise SystemExit(f"Invalid local credential file: {LOCAL_OWNER_CREDENTIALS}")
    credentials = {
        "email": "owner@contentengine.test",
        "password": f"Ce-{secrets.token_urlsafe(18)}-Aa1",
    }
    LOCAL.mkdir(exist_ok=True)
    LOCAL_OWNER_CREDENTIALS.write_text(
        json.dumps(credentials, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return credentials


def local_auth_request(
    api_url: str,
    publishable_key: str,
    path: str,
    payload: dict[str, object],
) -> tuple[int, dict[str, object]]:
    auth_request = request.Request(
        f"{api_url}{path}",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": publishable_key,
        },
    )
    try:
        with request.urlopen(auth_request, timeout=20) as response:
            status = int(response.status)
            body = response.read(1_048_577)
    except error.HTTPError as auth_error:
        status = int(auth_error.code)
        body = auth_error.read(1_048_577)
    except (error.URLError, TimeoutError, OSError) as auth_error:
        raise SystemExit("Local Supabase Auth is unavailable") from auth_error
    if len(body) > 1_048_576:
        raise SystemExit("Local Supabase Auth returned an oversized response")
    try:
        decoded = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as auth_error:
        raise SystemExit("Local Supabase Auth returned an invalid response") from auth_error
    if not isinstance(decoded, dict):
        raise SystemExit("Local Supabase Auth returned an invalid payload")
    return status, decoded


def local_rpc_request(
    api_url: str,
    publishable_key: str,
    access_token: str,
    function_name: str,
    payload: dict[str, object],
) -> tuple[int, dict[str, object]]:
    """Call one authenticated local SECURITY DEFINER authority.

    The bearer token is allowed to leave this process only for the exact
    loopback Supabase origin reported by the local CLI.  This helper is for
    provisioning control-plane objects; it is not a provider transport.
    """

    parsed = urlsplit(api_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or not parsed.port
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("Authenticated local RPC requires a loopback HTTP origin")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,95}", function_name):
        raise SystemExit("Invalid local RPC authority name")
    if not access_token:
        raise SystemExit("Local owner access token is missing")

    rpc_request = request.Request(
        f"{api_url}/rest/v1/rpc/{function_name}",
        data=json.dumps(
            {"p_payload": payload}, separators=(",", ":")
        ).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Accept-Profile": "public",
            "Authorization": f"Bearer {access_token}",
            "Content-Profile": "public",
            "Content-Type": "application/json",
            "apikey": publishable_key,
        },
    )
    try:
        with request.urlopen(rpc_request, timeout=30) as response:
            status = int(response.status)
            body = response.read(1_048_577)
    except error.HTTPError as rpc_error:
        status = int(rpc_error.code)
        body = rpc_error.read(1_048_577)
    except (error.URLError, TimeoutError, OSError) as rpc_error:
        raise SystemExit("Authenticated local Supabase RPC is unavailable") from rpc_error
    if len(body) > 1_048_576:
        raise SystemExit("Authenticated local Supabase RPC returned an oversized response")
    try:
        decoded = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as rpc_error:
        raise SystemExit("Authenticated local Supabase RPC returned invalid JSON") from rpc_error
    if not isinstance(decoded, dict):
        raise SystemExit("Authenticated local Supabase RPC returned an invalid payload")
    return status, decoded


def _payload_source(payload: dict[str, object]) -> dict[str, object]:
    nested = payload.get("data")
    return nested if isinstance(nested, dict) else payload


def _payload_uuid(payload: dict[str, object], *paths: tuple[str, ...]) -> str:
    source = _payload_source(payload)
    for path in paths:
        value: object = source
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        try:
            return str(UUID(str(value or "")))
        except (ValueError, TypeError, AttributeError):
            continue
    raise SystemExit("Local authority returned an invalid UUID")


def provision_local_owner() -> str:
    status = run(supabase_args("status", "-o", "env"), capture=True)
    output = status.stdout or ""
    api_match = re.search(r'^API_URL="?([^"\r\n]+)', output, re.MULTILINE)
    key_match = re.search(r'^PUBLISHABLE_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    if key_match is None:
        key_match = re.search(r'^ANON_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    if api_match is None or key_match is None:
        raise SystemExit("Local Supabase coordinates are unavailable")
    credentials = local_owner_credentials()
    sign_in_payload = {
        "email": credentials["email"],
        "password": credentials["password"],
    }
    auth_status, auth_payload = local_auth_request(
        api_match.group(1),
        key_match.group(1),
        "/auth/v1/token?grant_type=password",
        sign_in_payload,
    )
    if auth_status != 200:
        signup_status, _ = local_auth_request(
            api_match.group(1),
            key_match.group(1),
            "/auth/v1/signup",
            {**sign_in_payload, "data": {"display_name": "Local Owner"}},
        )
        if signup_status not in (200, 201):
            raise SystemExit(f"Local owner signup failed (HTTP {signup_status})")
        auth_status, auth_payload = local_auth_request(
            api_match.group(1),
            key_match.group(1),
            "/auth/v1/token?grant_type=password",
            sign_in_payload,
        )
    if auth_status != 200:
        raise SystemExit(f"Local owner sign-in failed (HTTP {auth_status})")
    access_token = str(auth_payload.get("access_token") or "").strip()
    if not access_token:
        raise SystemExit("Local owner access token is missing")
    user = auth_payload.get("user")
    if not isinstance(user, dict):
        raise SystemExit("Local owner identity is missing")
    try:
        user_id = str(UUID(str(user.get("id") or "")))
    except (ValueError, TypeError, AttributeError) as auth_error:
        raise SystemExit("Local owner identity is invalid") from auth_error

    docker = docker_executable()
    containers = run(
        [docker, "ps", "--filter", "name=supabase_db_contentengine-local", "--format", "{{.Names}}"],
        capture=True,
    ).stdout.splitlines()
    if len(containers) != 1:
        raise SystemExit("Expected one local Supabase database container")
    sql = (
        "select public.system_initialize_owner(jsonb_build_object("
        f"'user_id','{user_id}'::uuid,"
        "'idempotency_key','local-workbench-owner-v1',"
        "'organization_name','ContentEngine Local',"
        "'organization_slug','contentengine-local'));"
        "insert into content_factory.training_access_waivers ("
        "organization_id,profile_id,status,previous_role,granted_role,"
        "grant_reason,granted_by,granted_at,updated_at) "
        "select membership.organization_id,membership.profile_id,'active',"
        "'owner','owner',"
        "'Local workbench access; no training evidence is fabricated.',"
        "membership.profile_id,now(),now() "
        "from content_factory.memberships membership "
        f"where membership.profile_id='{user_id}'::uuid "
        "and membership.role='owner' and membership.status='active' "
        "on conflict (organization_id,profile_id) do update set "
        "status='active',previous_role='owner',granted_role='owner',"
        "grant_reason=excluded.grant_reason,granted_by=excluded.granted_by,"
        "granted_at=now(),revoked_by=null,revoked_at=null,"
        "revocation_reason=null,updated_at=now();"
    )
    run([
        docker, "exec", containers[0], "psql", "-U", "postgres", "-d", "postgres",
        "--set", "ON_ERROR_STOP=1", "-Atc", sql,
    ], capture=True)

    api_url = api_match.group(1)
    publishable_key = key_match.group(1)
    bootstrap_status, bootstrap_payload = local_rpc_request(
        api_url,
        publishable_key,
        access_token,
        "creator_bootstrap",
        {
            "client_version": "local-workbench-v1",
            "session_id": "local-workbench-provision-v1",
        },
    )
    if bootstrap_status != 200:
        raise SystemExit(f"Local owner bootstrap failed (HTTP {bootstrap_status})")
    organization_id = _payload_uuid(
        bootstrap_payload,
        ("organization", "id"),
        ("membership", "organization_id"),
        ("organization_id",),
    )

    project_status, project_payload = local_rpc_request(
        api_url,
        publishable_key,
        access_token,
        "creator_create_workspace_project",
        {
            "organization_id": organization_id,
            "idempotency_key": "local-workbench-project-v1",
            "name": "Контент Завод · Локальный проект",
            "color_token": "emerald",
        },
    )
    if project_status != 200:
        raise SystemExit(f"Local workspace project provisioning failed (HTTP {project_status})")
    project_id = _payload_uuid(
        project_payload,
        ("project_id",),
        ("project", "id"),
    )
    LOCAL_PROJECT.write_text(
        json.dumps({"project_id": project_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Local owner and workspace project ready: {credentials['email']} · {project_id}",
        flush=True,
    )
    return project_id


def prepare_overlay() -> None:
    LOCAL.mkdir(exist_ok=True)
    ensure_local_docker_dirs()
    if LOCAL_SUPABASE.exists():
        shutil.rmtree(LOCAL_SUPABASE)
    shutil.copytree(ROOT / "supabase", LOCAL_SUPABASE, ignore=shutil.ignore_patterns(".temp"))
    shutil.copy2(ROOT / "supabase" / "config.local.toml", LOCAL_SUPABASE / "config.toml")
    # Supabase CLI loads local Edge Function secrets from functions/.env.
    # Keeping the gates at the project root does not populate the worker and
    # would silently leave creator-generate outside its mock-only profile.
    (LOCAL_SUPABASE / "functions" / ".env").write_text(
        "QVF_CREATOR_GENERATE_MOCK_ONLY=true\nQVF_ALLOW_REAL_SPEND=false\nQVF_CHARACTER_PERFORMANCE_ENABLED=false\n",
        encoding="utf-8",
    )
    write_local_site()


def supabase_args(*args: str) -> list[str]:
    return [*supabase_executable(), "--workdir", str(LOCAL), *args]


def install_test_fixture() -> None:
    fixture = LOCAL_SUPABASE / "test-fixtures" / "training_assessment_v5_keys.sql"
    if not fixture.is_file():
        return
    docker = docker_executable()
    containers = run(
        [docker, "ps", "--filter", "name=supabase_db_contentengine-local", "--format", "{{.Names}}"],
        capture=True,
    ).stdout.splitlines()
    if len(containers) != 1:
        raise SystemExit("Expected one local Supabase database container")
    print("+ install local pgTAP fixture", flush=True)
    subprocess.run(
        [docker, "exec", "-i", containers[0], "psql", "-U", "postgres", "-d", "postgres", "--set", "ON_ERROR_STOP=1"],
        cwd=ROOT, env=env(), input=fixture.read_text(encoding="utf-8"), text=True, check=True,
    )


def dev_up() -> None:
    docker_executable()
    supabase_executable()
    prepare_overlay()
    run(supabase_args("start"))
    ensure_local_edge_runtime()
    provision_local_owner()
    write_local_site()  # regenerate config with the runtime publishable key
    run(compose_args("up", "-d", "--build"))
    dev_status()


def dev_down() -> None:
    docker_executable()
    supabase_executable()
    run(compose_args("down", "--remove-orphans"), check=False)
    run(supabase_args("stop"), check=False)


def dev_reset() -> None:
    docker_executable()
    supabase_executable()
    prepare_overlay()
    run(supabase_args("start"))
    ensure_local_edge_runtime()
    run(supabase_args("db", "reset"))
    install_test_fixture()
    provision_local_owner()
    run([pytest_python_executable(), "scripts/local_copy_e2e.py"])
    write_local_site()


def node_parse() -> None:
    require_tools("node")
    files = sorted((ROOT / "web" / "app").glob("*.js"))
    files += sorted((ROOT / "supabase" / "functions" / "_shared").glob("*.js"))
    files += sorted((ROOT / "dev" / "browser").glob("*.js"))
    for path in files:
        run(["node", "--check", str(path)])


def pytest_scratch_root() -> Path:
    """Return an ignored pytest artifact root, preferring the local E: workbench."""

    candidates: list[Path] = []
    if os.name == "nt":
        preferred_workbench = Path("E:/ContentEngine-local-workbench-v1")
        if preferred_workbench.is_dir():
            candidates.append(preferred_workbench / PYTEST_RUNS_RELATIVE)
    candidates.append(ROOT / PYTEST_RUNS_RELATIVE)

    attempted: set[str] = set()
    for candidate in candidates:
        marker = str(candidate.resolve(strict=False)).casefold()
        if marker in attempted:
            continue
        attempted.add(marker)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return candidate
    raise SystemExit("Cannot create an ignored scratch directory for parallel pytest")


def pytest_shard_count() -> int:
    raw = os.environ.get("QVF_DEV_TEST_SHARDS", str(DEFAULT_PYTEST_SHARDS))
    try:
        count = int(raw)
    except ValueError as exc:
        raise SystemExit("QVF_DEV_TEST_SHARDS must be an integer") from exc
    if count < 1 or count > 32:
        raise SystemExit("QVF_DEV_TEST_SHARDS must be between 1 and 32")
    return count


def pytest_python_executable(
    *,
    root: Path | None = None,
    platform_name: str | None = None,
    fallback: str | None = None,
) -> str:
    """Select the locked local test interpreter without depending on shell PATH."""

    project_root = ROOT if root is None else root
    platform = os.name if platform_name is None else platform_name
    fallback_executable = sys.executable if fallback is None else fallback
    override = os.environ.get("QVF_DEV_TEST_PYTHON", "").strip()
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            override_path = project_root / override_path
        if not override_path.is_file():
            raise SystemExit(
                "QVF_DEV_TEST_PYTHON must point to an existing Python executable"
            )
        return str(override_path.resolve())

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
    return fallback_executable


def _pytest_junit_counts(path: Path) -> dict[str, int | float]:
    root = ET.parse(path).getroot()
    if root.tag.rsplit("}", 1)[-1] == "testsuite":
        suites = [root]
    else:
        suites = [
            child
            for child in root
            if child.tag.rsplit("}", 1)[-1] == "testsuite"
        ]
    if not suites:
        raise ValueError("JUnit report contains no test suite")

    counts: dict[str, int | float] = {
        "tests": 0,
        "passed": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.0,
    }
    for suite in suites:
        tests = int(suite.attrib.get("tests", "0"))
        failures = int(suite.attrib.get("failures", "0"))
        errors = int(suite.attrib.get("errors", "0"))
        skipped = int(suite.attrib.get("skipped", "0"))
        counts["tests"] += tests
        counts["failures"] += failures
        counts["errors"] += errors
        counts["skipped"] += skipped
        counts["passed"] += max(0, tests - failures - errors - skipped)
        counts["duration_seconds"] += float(suite.attrib.get("time", "0"))
    counts["duration_seconds"] = round(float(counts["duration_seconds"]), 3)
    return counts


def _pytest_log_summary(path: Path) -> str:
    if not path.is_file():
        return "pytest summary unavailable"
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        clean = line.strip()
        if " in " in clean and re.search(
            r"\b(?:passed|failed|error|errors|skipped|deselected|xfailed|xpassed)\b",
            clean,
        ):
            return clean
    return "pytest summary unavailable"


def run_parallel_pytest() -> dict[str, object]:
    """Run the complete pytest collection in isolated deterministic shards."""

    shard_total = pytest_shard_count()
    pytest_python = pytest_python_executable()
    print(f"+ pytest interpreter {pytest_python}", flush=True)
    run_id = (
        f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        f"-{os.getpid()}-{secrets.token_hex(4)}"
    )
    run_dir = pytest_scratch_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    processes: list[tuple[int, subprocess.Popen[str], object, Path, Path]] = []
    try:
        for shard_index in range(shard_total):
            shard_dir = run_dir / f"shard-{shard_index + 1:02d}"
            temp_dir = shard_dir / "tmp"
            media_dir = shard_dir / "media"
            cache_dir = shard_dir / "pytest-cache"
            pycache_dir = shard_dir / "pycache"
            for directory in (temp_dir, media_dir, cache_dir, pycache_dir):
                directory.mkdir(parents=True, exist_ok=True)

            log_path = shard_dir / "pytest.log"
            junit_path = shard_dir / "junit.xml"
            database_path = shard_dir / "qvf-pytest.db"
            shard_env = env()
            shard_env.update({
                "TEMP": str(temp_dir),
                "TMP": str(temp_dir),
                "TMPDIR": str(temp_dir),
                "PYTHONPYCACHEPREFIX": str(pycache_dir),
                "QVF_DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
                "QVF_MEDIA_ROOT": str(media_dir),
                "QVF_ALLOW_REAL_SPEND": "false",
                "QVF_PYTEST_SHARD_INDEX": str(shard_index),
                "QVF_PYTEST_SHARD_TOTAL": str(shard_total),
            })
            args = [
                pytest_python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "scripts.pytest_shard_plugin",
                "--durations=25",
                "--durations-min=1.0",
                "-o",
                f"cache_dir={cache_dir}",
                f"--junitxml={junit_path}",
            ]
            print(
                f"+ pytest shard {shard_index + 1}/{shard_total} -> {log_path}",
                flush=True,
            )
            log_handle = log_path.open("w", encoding="utf-8", newline="")
            try:
                process = subprocess.Popen(
                    args,
                    cwd=ROOT,
                    env=shard_env,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    shell=False,
                )
            except BaseException:
                log_handle.close()
                raise
            processes.append(
                (shard_index, process, log_handle, log_path, junit_path)
            )

        returncodes: dict[int, int] = {}
        for shard_index, process, _handle, _log_path, _junit_path in processes:
            returncodes[shard_index] = process.wait()
    except BaseException:
        for _index, process, _handle, _log_path, _junit_path in processes:
            if process.poll() is None:
                process.terminate()
        for _index, process, _handle, _log_path, _junit_path in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        for _index, _process, handle, _log_path, _junit_path in processes:
            handle.close()

    aggregate: dict[str, int | float] = {
        "tests": 0,
        "passed": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 0.0,
    }
    shard_results: list[dict[str, object]] = []
    failed_shards: list[str] = []
    for shard_index, _process, _handle, log_path, junit_path in processes:
        returncode = returncodes[shard_index]
        result: dict[str, object] = {
            "shard": f"{shard_index + 1}/{shard_total}",
            "returncode": returncode,
            "log": str(log_path),
            "junit": str(junit_path),
            "pytest_summary": _pytest_log_summary(log_path),
        }
        try:
            counts = _pytest_junit_counts(junit_path)
        except (OSError, ET.ParseError, ValueError) as exc:
            result["report_error"] = str(exc)
            failed_shards.append(str(shard_index + 1))
        else:
            result.update(counts)
            for name in ("tests", "passed", "failures", "errors", "skipped"):
                aggregate[name] += int(counts[name])
            aggregate["duration_seconds"] += float(counts["duration_seconds"])
        if returncode != 0 and str(shard_index + 1) not in failed_shards:
            failed_shards.append(str(shard_index + 1))
        shard_results.append(result)

    aggregate["duration_seconds"] = round(float(aggregate["duration_seconds"]), 3)
    report: dict[str, object] = {
        "status": "failed" if failed_shards else "passed",
        "shards": shard_total,
        "run_dir": str(run_dir),
        "aggregate": aggregate,
        "shard_results": shard_results,
    }
    print(json.dumps({"parallel_pytest": report}, indent=2), flush=True)
    if failed_shards:
        raise SystemExit(
            "Parallel pytest failed in shard(s) "
            + ", ".join(failed_shards)
            + f"; retained logs: {run_dir}"
        )
    return report


def dev_test() -> None:
    require_tools("node")
    test_python = pytest_python_executable()
    run_parallel_pytest()
    node_parse()
    docker_executable()
    supabase_executable()
    prepare_overlay()
    run(supabase_args("start"))
    ensure_local_edge_runtime()
    run(supabase_args("db", "reset"))
    install_test_fixture()
    run(supabase_args("db", "lint", "--local", "--level", "error"))
    run(supabase_args("test", "db"))
    run([test_python, "scripts/local_copy_e2e.py"])
    provision_local_owner()
    write_local_site()
    run([test_python, "scripts/local_copy_e2e.py", "--system"])
    run([test_python, "scripts/browser_smoke.py"])
    run(["git", "diff", "--check"])


def dev_browser_smoke() -> None:
    if not LOCAL_SUPABASE.is_dir():
        prepare_overlay()
    else:
        write_local_site()
    provision_local_owner()
    run([pytest_python_executable(), "scripts/browser_smoke.py"])


def dev_status() -> None:
    print(json.dumps({
        "profile": "local",
        "real_spend_allowed": False,
        "provider_mode": "mock",
        "character_performance_enabled": False,
        "app": "http://127.0.0.1:8014",
        "desktop": "http://127.0.0.1:8767/",
        "desktop_generation": "http://127.0.0.1:8767/#/workspace/generation?project_id=<project_id>",
        "diagnostic_workbench": "http://127.0.0.1:8767/workbench/#/copy",
        "supabase_api": "http://127.0.0.1:54321",
        "supabase_studio": "http://127.0.0.1:54323",
        "mail": "http://127.0.0.1:54324",
        "creator_generate": "http://127.0.0.1:54321/functions/v1/creator-generate",
        "local_site_generated": LOCAL_SITE.is_dir(),
        "local_owner_email": "owner@contentengine.test",
        "local_owner_credentials_file": str(LOCAL_OWNER_CREDENTIALS),
        "local_project_file": str(LOCAL_PROJECT),
        "local_docker_media": str(LOCAL_DOCKER_MEDIA),
        "local_docker_data": str(LOCAL_DOCKER_DATA),
    }, ensure_ascii=False, indent=2))
    try:
        run(compose_args("ps"), check=False)
    except SystemExit:
        pass
    if LOCAL_SUPABASE.is_dir():
        try:
            run(supabase_args("status"), check=False)
        except SystemExit:
            pass


COMMANDS = {
    "dev-up": dev_up,
    "dev-down": dev_down,
    "dev-reset": dev_reset,
    "dev-test": dev_test,
    "dev-browser-smoke": dev_browser_smoke,
    "dev-status": dev_status,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    COMMANDS[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
