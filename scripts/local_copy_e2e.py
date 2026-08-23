#!/usr/bin/env python3
"""Deterministic, no-network Copy E2E for the local workbench."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any
from urllib import error, parse, request
from uuid import UUID, uuid4

try:
    from scripts import dev_workbench
except ImportError:  # pragma: no cover - direct script execution
    # ImportError, а не ModuleNotFoundError: посторонний namespace-пакет
    # `scripts` (например, site-packages/win32/scripts из pywin32) может
    # найтись раньше и не содержать dev_workbench.
    import dev_workbench  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / ".dev-artifacts" / "copy-e2e"
DEFAULT_SYSTEM_ROOT = ROOT / ".dev-artifacts" / "copy-system-e2e"
LOCAL_EDGE_ORIGIN = "http://127.0.0.1:8767"
STORAGE_BUCKET = "contentengine-private"
MAX_HTTP_RESPONSE_BYTES = 1_048_576


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_mock_only() -> None:
    spend = os.environ.get("QVF_ALLOW_REAL_SPEND", "false").strip().lower()
    mode = os.environ.get("QVF_GENERATION_MODE", "mock").strip().lower()
    if spend != "false" or mode != "mock":
        raise SystemExit("Copy E2E is fail-closed: mock mode and QVF_ALLOW_REAL_SPEND=false are required")


def _require_system_mock_only() -> None:
    _require_mock_only()
    if os.environ.get("QVF_CREATOR_GENERATE_MOCK_ONLY", "").strip().lower() != "true":
        raise SystemExit("Copy system E2E requires QVF_CREATOR_GENERATE_MOCK_ONLY=true")


def _loopback_origin(value: str) -> str:
    parsed = parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise SystemExit("Copy system E2E accepts only a loopback HTTP Supabase origin")
    return f"{parsed.scheme}://{parsed.netloc}"


def _bounded_json_response(response: Any, context: str) -> dict[str, Any]:
    body = response.read(MAX_HTTP_RESPONSE_BYTES + 1)
    if len(body) > MAX_HTTP_RESPONSE_BYTES:
        raise SystemExit(f"{context} returned an oversized response")
    try:
        decoded = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as response_error:
        raise SystemExit(f"{context} returned invalid JSON") from response_error
    if not isinstance(decoded, dict):
        raise SystemExit(f"{context} returned an invalid payload")
    return decoded


def _http_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    context: str,
    *,
    timeout: int = 60,
) -> tuple[int, dict[str, Any]]:
    outbound = request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            **headers,
        },
    )
    try:
        with request.urlopen(outbound, timeout=timeout) as response:
            return int(response.status), _bounded_json_response(response, context)
    except error.HTTPError as response_error:
        return int(response_error.code), _bounded_json_response(response_error, context)
    except (error.URLError, TimeoutError, OSError) as response_error:
        raise SystemExit(f"{context} is unavailable") from response_error


def _local_coordinates() -> tuple[str, str]:
    status = dev_workbench.run(
        dev_workbench.supabase_args("status", "-o", "env"),
        capture=True,
    )
    output = status.stdout or ""
    api_match = re.search(r'^API_URL="?([^"\r\n]+)', output, re.MULTILINE)
    key_match = re.search(r'^PUBLISHABLE_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    if key_match is None:
        key_match = re.search(r'^ANON_KEY="?([^"\r\n]+)', output, re.MULTILINE)
    if api_match is None or key_match is None:
        raise SystemExit("Local Supabase coordinates are unavailable")
    return _loopback_origin(api_match.group(1)), key_match.group(1)


def _owner_session(api_url: str, publishable_key: str) -> tuple[str, str, str, str]:
    credentials_path = dev_workbench.LOCAL_OWNER_CREDENTIALS
    project_path = dev_workbench.LOCAL_PROJECT
    if not credentials_path.is_file() or not project_path.is_file():
        raise SystemExit("Run dev-up or provision_local_owner before Copy system E2E")
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    project = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(credentials, dict) or not isinstance(project, dict):
        raise SystemExit("Local owner/project metadata is invalid")
    auth_status, auth_payload = dev_workbench.local_auth_request(
        api_url,
        publishable_key,
        "/auth/v1/token?grant_type=password",
        {
            "email": str(credentials.get("email") or ""),
            "password": str(credentials.get("password") or ""),
        },
    )
    if auth_status != 200:
        raise SystemExit(f"Local owner sign-in failed (HTTP {auth_status})")
    access_token = str(auth_payload.get("access_token") or "").strip()
    user = auth_payload.get("user")
    if not access_token or not isinstance(user, dict):
        raise SystemExit("Local owner session is incomplete")
    try:
        actor_id = str(UUID(str(user.get("id") or "")))
        project_id = str(UUID(str(project.get("project_id") or "")))
    except (ValueError, TypeError, AttributeError) as identity_error:
        raise SystemExit("Local owner/project identity is invalid") from identity_error
    bootstrap_status, bootstrap = dev_workbench.local_rpc_request(
        api_url,
        publishable_key,
        access_token,
        "creator_bootstrap",
        {
            "client_version": "local-copy-system-e2e-v1",
            "session_id": f"local-copy-system-e2e-{uuid4().hex}",
        },
    )
    if bootstrap_status != 200:
        raise SystemExit(f"Local bootstrap failed (HTTP {bootstrap_status})")
    organization_id = dev_workbench._payload_uuid(
        bootstrap,
        ("organization", "id"),
        ("membership", "organization_id"),
        ("organization_id",),
    )
    return access_token, actor_id, organization_id, project_id


def _storage_upload(
    api_url: str,
    publishable_key: str,
    access_token: str,
    object_name: str,
    path: Path,
    mime_type: str,
) -> None:
    if object_name.startswith("/") or ".." in object_name.split("/"):
        raise SystemExit("Refusing an unsafe local Storage object name")
    body = path.read_bytes()
    upload = request.Request(
        f"{api_url}/storage/v1/object/{STORAGE_BUCKET}/"
        f"{parse.quote(object_name, safe='/')}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": publishable_key,
            "Content-Type": mime_type,
            "Content-Length": str(len(body)),
            "x-upsert": "false",
        },
    )
    try:
        with request.urlopen(upload, timeout=60) as response:
            if int(response.status) not in (200, 201):
                raise SystemExit(f"Local Storage upload failed (HTTP {response.status})")
            response.read(MAX_HTTP_RESPONSE_BYTES + 1)
    except error.HTTPError as upload_error:
        details = _bounded_json_response(upload_error, "Local Storage")
        raise SystemExit(
            f"Local Storage upload failed (HTTP {upload_error.code}, "
            f"code={details.get('error') or details.get('code') or 'unknown'})"
        ) from upload_error
    except (error.URLError, TimeoutError, OSError) as upload_error:
        raise SystemExit("Local Storage is unavailable") from upload_error


def _storage_download(
    api_url: str,
    publishable_key: str,
    access_token: str,
    object_name: str,
) -> bytes:
    download = request.Request(
        f"{api_url}/storage/v1/object/authenticated/{STORAGE_BUCKET}/"
        f"{parse.quote(object_name, safe='/')}",
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": publishable_key,
        },
    )
    try:
        with request.urlopen(download, timeout=60) as response:
            body = response.read(52_428_801)
    except (error.HTTPError, error.URLError, TimeoutError, OSError) as download_error:
        raise SystemExit("Local Storage output download failed") from download_error
    if len(body) > 52_428_800:
        raise SystemExit("Local Storage output exceeded the local media limit")
    return body


def _edge_request(
    api_url: str,
    publishable_key: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    status, response = _http_json(
        f"{api_url}/functions/v1/creator-generate",
        payload,
        {
            "Authorization": f"Bearer {access_token}",
            "apikey": publishable_key,
            "Origin": LOCAL_EDGE_ORIGIN,
        },
        f"creator-generate {payload.get('action', 'unknown')}",
        timeout=90,
    )
    if status != 200 or response.get("ok") is not True:
        raise SystemExit(
            f"creator-generate {payload.get('action')} failed "
            f"(HTTP {status}, code={response.get('code') or 'unknown'})"
        )
    contract = response.get("contract")
    action = str(payload.get("action") or "")
    if action.startswith("strategy_mock_") and (
        not isinstance(contract, dict)
        or contract.get("provider_call_started") is not False
    ):
        raise SystemExit("creator-generate did not prove provider_call_started=false")
    if isinstance(contract, dict) and "provider_call_started" in contract:
        if contract.get("provider_call_started") is not False:
            raise SystemExit("creator-generate did not prove provider_call_started=false")
    return response


def _rpc(
    api_url: str,
    publishable_key: str,
    access_token: str,
    function_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    status, response = dev_workbench.local_rpc_request(
        api_url,
        publishable_key,
        access_token,
        function_name,
        payload,
    )
    if status != 200 or response.get("ok") is not True:
        raise SystemExit(
            f"Local RPC {function_name} failed "
            f"(HTTP {status}, code={response.get('code') or 'unknown'})"
        )
    return response


def _register_media(
    api_url: str,
    publishable_key: str,
    access_token: str,
    organization_id: str,
    project_id: str,
    object_name: str,
    path: Path,
    mime_type: str,
    kind: str,
    idempotency_key: str,
    *,
    product_id: str | None = None,
    sku: str | None = None,
    product_name: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "bucket": STORAGE_BUCKET,
        "object_key": object_name,
        "original_filename": path.name,
        "mime_type": mime_type,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "kind": kind,
        "rights_confirmed": True,
        "idempotency_key": idempotency_key,
    }
    if product_id:
        payload["product_id"] = product_id
    elif kind in {"product_photo", "packshot"}:
        payload["sku"] = sku
        payload["product_name"] = product_name
    response = _rpc(
        api_url,
        publishable_key,
        access_token,
        "creator_register_media",
        payload,
    )
    media = response.get("media")
    if not isinstance(media, dict):
        raise SystemExit("creator_register_media returned invalid media")
    try:
        UUID(str(media.get("id") or ""))
    except (ValueError, TypeError, AttributeError) as media_error:
        raise SystemExit("creator_register_media returned invalid media identity") from media_error
    return media


def run_copy_e2e(output_root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    _require_mock_only()
    ffmpeg = shutil.which(os.environ.get("QVF_FFMPEG_PATH", "ffmpeg"))
    ffprobe = shutil.which(os.environ.get("QVF_FFPROBE_PATH", "ffprobe"))
    if not ffmpeg or not ffprobe:
        raise SystemExit("FFmpeg and FFprobe are required")

    output_root.mkdir(parents=True, exist_ok=True)
    storyboard_dir = output_root / "storyboard"
    references_dir = output_root / "new-product-references"
    archive_dir = output_root / "archive"
    storyboard_dir.mkdir(exist_ok=True)
    references_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)

    source = output_root / "source.mp4"
    _run(
        ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source),
    )
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(source)],
        check=True, capture_output=True, text=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    if not 4.5 <= duration <= 5.5:
        raise SystemExit(f"unexpected source duration: {duration}")

    storyboard = storyboard_dir / "frame-%02d.jpg"
    _run(ffmpeg, "-y", "-i", str(source), "-vf", "fps=1,scale=180:-1", str(storyboard))
    storyboard_frames = sorted(storyboard_dir.glob("frame-*.jpg"))
    if len(storyboard_frames) < 3:
        raise SystemExit("storyboard extraction did not produce three frames")
    original_product_frame = output_root / "original-product-frame.jpg"
    shutil.copy2(storyboard_frames[1], original_product_frame)

    reference_colors = ("0xED6A5A", "0xF4BF4F", "0x67D5B5")
    references: list[Path] = []
    for index, color in enumerate(reference_colors, start=1):
        path = references_dir / f"new-product-{index}.png"
        _run(
            ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={color}:s=360x640:d=0.1",
            "-frames:v", "1", "-update", "1", str(path),
        )
        references.append(path)

    preflight = {
        "ok": True,
        "strategy_id": "viral_product_swap",
        "provider_mode": "mock",
        "real_spend_allowed": False,
        "source_mime": "video/mp4",
        "duration_seconds": duration,
        "storyboard_frame_count": len(storyboard_frames),
        "new_product_reference_count": len(references),
        "provider_post_started": False,
    }
    (output_root / "preflight.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    generated = output_root / "mock-generated.mp4"
    _run(
        ffmpeg, "-y", "-i", str(source),
        "-vf", "drawbox=x=20:y=20:w=320:h=92:color=0x67D5B5@0.72:t=fill",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(generated),
    )

    archived_media = archive_dir / "viral-product-swap-mock.mp4"
    shutil.copy2(generated, archived_media)
    manifest = {
        "schema_version": 1,
        "authority": "creator-generate",
        "execution": "local_mock_only",
        "strategy_id": "viral_product_swap",
        "source": {"path": source.relative_to(output_root).as_posix(), "sha256": _sha256(source)},
        "storyboard": [path.relative_to(output_root).as_posix() for path in storyboard_frames],
        "original_product_frame": original_product_frame.relative_to(output_root).as_posix(),
        "new_product_references": [path.relative_to(output_root).as_posix() for path in references],
        "preflight": preflight,
        "result": {"path": archived_media.relative_to(output_root).as_posix(), "sha256": _sha256(archived_media)},
    }
    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"manifest": str(manifest_path), "output": str(archived_media), "frames": len(storyboard_frames)}


def run_copy_system_e2e(output_root: Path = DEFAULT_SYSTEM_ROOT) -> dict[str, Any]:
    """Exercise local Storage, strict Edge actions, DB snapshots and archive."""

    _require_system_mock_only()
    run_token = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid4().hex[:12]}"
    run_root = output_root / run_token
    media_root = run_root / "media"
    offline = run_copy_e2e(media_root)
    offline_manifest = json.loads(
        Path(offline["manifest"]).read_text(encoding="utf-8")
    )

    api_url, publishable_key = _local_coordinates()
    access_token, actor_id, organization_id, project_id = _owner_session(
        api_url,
        publishable_key,
    )
    prefix = f"{organization_id}/{actor_id}/uploads/{run_token}"

    source_path = media_root / offline_manifest["source"]["path"]
    original_path = media_root / offline_manifest["original_product_frame"]
    reference_paths = [
        media_root / relative
        for relative in offline_manifest["new_product_references"]
    ]
    generated_path = Path(offline["output"])
    if len(reference_paths) != 3:
        raise SystemExit("Copy system E2E requires exactly three product references")

    def upload_input(
        path: Path,
        mime_type: str,
        kind: str,
        ordinal: int,
        **product: str,
    ) -> dict[str, Any]:
        object_name = f"{prefix}/{ordinal:02d}-{path.name}"
        _storage_upload(
            api_url,
            publishable_key,
            access_token,
            object_name,
            path,
            mime_type,
        )
        return _register_media(
            api_url,
            publishable_key,
            access_token,
            organization_id,
            project_id,
            object_name,
            path,
            mime_type,
            kind,
            f"copy-system-media-{run_token}-{ordinal:02d}",
            **product,
        )

    source_media = upload_input(source_path, "video/mp4", "source_video", 1)
    source_media_id = str(source_media["id"])
    attached = _rpc(
        api_url,
        publishable_key,
        access_token,
        "contentengine_attach_generation_direct_mp4",
        {
            "organization_id": organization_id,
            "project_id": project_id,
            "media_id": source_media_id,
            "idempotency_key": f"copy-system-attach-{run_token}",
        },
    )
    source_attachment = attached.get("attachment")
    attached_media = attached.get("media")
    if (
        not isinstance(source_attachment, dict)
        or not isinstance(attached_media, dict)
        or source_attachment.get("source_kind") != "direct_mp4"
        or str(source_attachment.get("media_id") or "") != source_media_id
        or str(attached_media.get("id") or "") != source_media_id
    ):
        raise SystemExit("Direct MP4 attachment returned an invalid exact-source identity")
    original_media = upload_input(
        original_path,
        "image/jpeg",
        "creator_reference",
        2,
    )
    reference_media: list[dict[str, Any]] = []
    product_id: str | None = None
    for index, path in enumerate(reference_paths, start=3):
        if product_id is None:
            media = upload_input(
                path,
                "image/png",
                "product_photo",
                index,
                sku=f"LOCAL-COPY-{run_token}",
                product_name="Локальный тестовый товар Copy",
            )
            product_id = str(media.get("product_id") or "")
            try:
                UUID(product_id)
            except (ValueError, TypeError, AttributeError) as product_error:
                raise SystemExit("Copy product identity is invalid") from product_error
        else:
            media = upload_input(
                path,
                "image/png",
                "product_photo",
                index,
                product_id=product_id,
            )
        reference_media.append(media)

    probe = _edge_request(
        api_url,
        publishable_key,
        access_token,
        {
            "action": "strategy_media_probe",
            "organization_id": organization_id,
            "project_id": project_id,
            "media_id": source_media_id,
            "confirmation": True,
            "idempotency_key": f"copy-system-probe-{run_token}",
        },
    )
    duration_seconds = float(offline_manifest["preflight"]["duration_seconds"])
    duration_integer = int(round(duration_seconds))
    if abs(duration_seconds - duration_integer) > 0.01 or not 4 <= duration_integer <= 15:
        raise SystemExit("Copy source duration is not an exact supported integer")
    probed_duration = probe.get("duration_seconds")
    if not isinstance(probed_duration, (int, float)) or float(probed_duration) != duration_integer:
        raise SystemExit("Server MP4 probe duration does not match the exact source")

    views = ("front", "side", "back")
    selection = {
        "version": "2026-08-14.v1",
        "strategy_id": "viral_product_swap",
        "recipe_version": "2026-06",
        "duration_seconds": duration_integer,
        "resolution": "720p",
        "audio": True,
        "assets": [
            {
                "role": "source_video",
                "media_id": source_media_id,
                "duration_seconds": duration_integer,
            },
            {
                "role": "original_product_image",
                "media_id": str(original_media["id"]),
            },
            *[
                {
                    "role": "new_product_image",
                    "media_id": str(media["id"]),
                    "view": views[index],
                }
                for index, media in enumerate(reference_media)
            ],
        ],
        "attestations": {
            "source_media_rights_confirmed": True,
            "transformative_use_confirmed": True,
            "product_assets_rights_confirmed": True,
            "depicted_people_consent_confirmed": True,
        },
    }
    source_attachment_id = str(source_attachment.get("id") or "")
    source_attachment_hash = str(source_attachment.get("attachment_hash") or "")
    source_hash_snapshot = str(source_attachment.get("source_hash_snapshot") or "")
    for value, label in (
        (source_attachment_id, "attachment id"),
        (str(source_attachment.get("attached_by") or ""), "attachment actor"),
    ):
        try:
            UUID(value)
        except (ValueError, TypeError, AttributeError) as identity_error:
            raise SystemExit(f"Direct MP4 {label} is invalid") from identity_error
    if (
        str(source_attachment.get("attached_by") or "") != actor_id
        or not re.fullmatch(r"[0-9a-f]{64}", source_attachment_hash)
        or not re.fullmatch(r"[0-9a-f]{64}", source_hash_snapshot)
    ):
        raise SystemExit("Direct MP4 attachment hashes are invalid")

    prepare_payload = {
        "version": "generation-strategy-spec-prepare-request-v1",
        "organization_id": organization_id,
        "project_id": project_id,
        "platform": "tiktok",
        "product_category": "other",
        "selection": selection,
        "editable_intent": "Заменить исходный товар на локальный тестовый товар, сохранив сцену.",
        "proposed_prompt": "Сохранить движение, композицию, свет и монтаж исходного MP4; заменить только товар по трём точным референсам.",
        "mechanics_summary": None,
        "confirmation": True,
        "reason": "Local mock Copy system E2E prepares an exact human-reviewable spec.",
        "idempotency_key": f"copy-system-spec-{run_token}",
    }
    prepared = _rpc(
        api_url,
        publishable_key,
        access_token,
        "creator_prepare_generation_strategy_spec",
        prepare_payload,
    )
    prepared_replay = _rpc(
        api_url,
        publishable_key,
        access_token,
        "creator_prepare_generation_strategy_spec",
        prepare_payload,
    )
    draft = prepared.get("generation_spec")
    replay_draft = prepared_replay.get("generation_spec")
    exact_scope = draft.get("exact_scope") if isinstance(draft, dict) else None
    source_scope = exact_scope.get("source") if isinstance(exact_scope, dict) else None
    if (
        prepared.get("version") != "generation-strategy-spec-prepare-response-v1"
        or not isinstance(draft, dict)
        or draft.get("status") != "draft"
        or not isinstance(exact_scope, dict)
        or exact_scope.get("selection") != selection
        or exact_scope.get("strategy_id") != "viral_product_swap"
        or not isinstance(source_scope, dict)
        or source_scope.get("media_object_id") != source_media_id
        or not isinstance(replay_draft, dict)
        or (
            replay_draft.get("spec_id"),
            replay_draft.get("spec_version"),
            replay_draft.get("spec_hash"),
        )
        != (
            draft.get("spec_id"),
            draft.get("spec_version"),
            draft.get("spec_hash"),
        )
    ):
        raise SystemExit("Browser strategy spec wrapper did not return an exact draft")
    approved = _rpc(
        api_url,
        publishable_key,
        access_token,
        "creator_control_generation_spec",
        {
            "organization_id": organization_id,
            "project_id": project_id,
            "spec_id": draft.get("spec_id"),
            "expected_spec_version": draft.get("spec_version"),
            "expected_spec_hash": draft.get("spec_hash"),
            "action": "approve",
            "confirmation": True,
            "reason": "Local operator explicitly reviewed and approved this exact mock Copy spec.",
            "idempotency_key": f"copy-system-approve-{run_token}",
        },
    )
    approved_spec = approved.get("generation_spec")
    if not isinstance(approved_spec, dict) or approved_spec.get("status") != "approved":
        raise SystemExit("Strategy spec approval did not return an approved version")

    bound = _edge_request(
        api_url,
        publishable_key,
        access_token,
        {
            "action": "strategy_bind",
            "organization_id": organization_id,
            "project_id": project_id,
            "spec_id": approved_spec.get("spec_id"),
            "spec_version": approved_spec.get("spec_version"),
            "spec_hash": approved_spec.get("spec_hash"),
            "generation_strategy": selection,
            "confirmation": True,
            "idempotency_key": f"copy-system-bind-{run_token}",
        },
    )
    binding = bound.get("binding")
    bound_selection = bound.get("selection")
    if not isinstance(binding, dict) or not isinstance(bound_selection, dict):
        raise SystemExit("Strategy bind returned an invalid identity")
    mock_idempotency = f"copy-system-mock-{run_token}"
    common_mock = {
        "organization_id": organization_id,
        "project_id": project_id,
        "spec_id": approved_spec.get("spec_id"),
        "spec_version": approved_spec.get("spec_version"),
        "spec_hash": approved_spec.get("spec_hash"),
        "binding_id": binding.get("id"),
        "binding_hash": binding.get("binding_hash"),
        "selection_hash": bound_selection.get("selection_hash"),
        "confirmation": True,
        "idempotency_key": mock_idempotency,
    }
    mock_preflight = _edge_request(
        api_url,
        publishable_key,
        access_token,
        {"action": "strategy_mock_preflight", **common_mock},
    )
    upload = mock_preflight.get("output")
    if not isinstance(upload, dict):
        raise SystemExit("Mock preflight did not return a local upload target")
    output_object_name = str(upload.get("object_name") or "")
    expected_output_prefix = (
        f"{organization_id}/{actor_id}/local-mock-output/"
    )
    if not output_object_name.startswith(expected_output_prefix):
        raise SystemExit("Mock preflight returned an out-of-scope Storage target")
    _storage_upload(
        api_url,
        publishable_key,
        access_token,
        output_object_name,
        generated_path,
        "video/mp4",
    )
    mock_started = _edge_request(
        api_url,
        publishable_key,
        access_token,
        {
            "action": "strategy_mock_start",
            **common_mock,
            "output_object_name": output_object_name,
            "output_mime_type": "video/mp4",
            "output_size_bytes": generated_path.stat().st_size,
            "output_sha256": _sha256(generated_path),
        },
    )
    generation = mock_started.get("generation")
    if not isinstance(generation, dict) or generation.get("status") != "mock_ready":
        raise SystemExit("Mock completion did not create a mock_ready generation")
    generation_job_id = str(generation.get("generation_job_id") or "")
    batch_id = str(generation.get("batch_id") or "")
    mock_status = _edge_request(
        api_url,
        publishable_key,
        access_token,
        {
            "action": "strategy_mock_status",
            "organization_id": organization_id,
            "project_id": project_id,
            "generation_job_id": generation_job_id,
        },
    )
    if mock_status.get("generation") != generation:
        raise SystemExit("Mock status does not match the completed generation")

    archive = _rpc(
        api_url,
        publishable_key,
        access_token,
        "creator_generation_archive",
        {
            "organization_id": organization_id,
            "project_id": project_id,
            "period": "all",
            "status": "ready",
            "provider": "all",
            "strategy_id": "viral_product_swap",
            "page_size": 50,
        },
    )
    batches = archive.get("batches")
    if not isinstance(batches, list) or not any(
        isinstance(batch, dict) and str(batch.get("id") or "") == batch_id
        for batch in batches
    ):
        raise SystemExit("Mock Copy batch is missing from creator_generation_archive")

    downloaded = _storage_download(
        api_url,
        publishable_key,
        access_token,
        output_object_name,
    )
    generated_sha256 = _sha256(generated_path)
    if hashlib.sha256(downloaded).hexdigest() != generated_sha256:
        raise SystemExit("Downloaded local Storage output hash does not match")
    system_archive = run_root / "system-archive"
    system_archive.mkdir(parents=True, exist_ok=True)
    downloaded_path = system_archive / "viral-product-swap-storage-output.mp4"
    downloaded_path.write_bytes(downloaded)
    manifest = {
        "schema_version": 1,
        "authority": "creator-generate",
        "execution": "local_mock_system_e2e",
        "organization_id": organization_id,
        "project_id": project_id,
        "strategy_id": "viral_product_swap",
        "spec_setup": "browser_strategy_wrapper_project_scoped",
        "spec_id": approved_spec.get("spec_id"),
        "binding_id": binding.get("id"),
        "generation_job_id": generation_job_id,
        "batch_id": batch_id,
        "output_media_id": mock_started.get("output", {}).get("media_id"),
        "provider_call_started": False,
        "allow_real_spend": False,
        "estimated_cost_minor": 0,
        "actual_cost_minor": 0,
        "storage": {
            "bucket": STORAGE_BUCKET,
            "object_name": output_object_name,
            "size_bytes": len(downloaded),
            "sha256": generated_sha256,
        },
        "gates": {
            "storage_upload_and_download": True,
            "source_probe": probe.get("ok") is True,
            "strategy_spec_idempotent_replay": True,
            "strict_mock_preflight": mock_preflight.get("ok") is True,
            "strict_mock_start": mock_started.get("ok") is True,
            "strict_mock_status": mock_status.get("ok") is True,
            "db_archive": True,
        },
        "artifact": downloaded_path.relative_to(run_root).as_posix(),
    }
    manifest_path = system_archive / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path),
        "output": str(downloaded_path),
        "generation_job_id": generation_job_id,
        "batch_id": batch_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--system",
        action="store_true",
        help="run the loopback Storage -> creator-generate -> DB/archive E2E",
    )
    args = parser.parse_args()
    output_root = args.output_root
    if args.system and output_root == DEFAULT_ROOT:
        output_root = DEFAULT_SYSTEM_ROOT
    result = run_copy_system_e2e(output_root) if args.system else run_copy_e2e(output_root)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
