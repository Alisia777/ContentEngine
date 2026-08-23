from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240008_generation_media_identity.sql"
).read_text(encoding="utf-8")
ADAPTER_PATH = ROOT / "web/app/supabase-api.js"
ADAPTER = ADAPTER_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _merge(response: dict, identities: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for media identity contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            ADAPTER_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import { mergeGenerationMediaIdentity } from './subject.mjs';\n"
            f"const response = {json.dumps(response)};\n"
            f"const identities = {json.dumps(identities)};\n"
            "process.stdout.write(JSON.stringify("
            "mergeGenerationMediaIdentity(response, identities)"
            "));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_generation_media_identity_rpc_is_tenant_scoped_and_fail_closed() -> None:
    for token in (
        "creator_generation_media_identity",
        "content_factory_private.current_profile_id()",
        "content_factory_private.resolve_organization(p_payload)",
        "content_factory_private.membership_role(",
        "media.organization_id = organization_id",
        "and (team_scope or media.owner_id = user_id)",
        "media.status = 'ready'",
        "media.metadata ->> 'kind' in ('product_photo', 'packshot')",
        "media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb",
        "product.status = 'active'",
        "revoke all on function public.creator_generation_media_identity(jsonb)",
        "grant execute on function public.creator_generation_media_identity(jsonb)",
    ):
        assert token in MIGRATION
    function_header = MIGRATION[
        MIGRATION.index("create or replace function public.creator_generation_media_identity"):
        MIGRATION.index("#variable_conflict use_variable")
    ]
    assert "\nstable\n" not in function_header


def test_generation_media_identity_rejects_bad_or_oversized_id_lists() -> None:
    for token in (
        "jsonb_array_length(p_payload -> 'media_ids') not between 1 and 100",
        "jsonb_typeof(element) <> 'string'",
        "entry.value::uuid",
        "count(distinct requested.media_id)",
        "'generation_media_identity_ids_invalid'",
        "'generation_media_identity_payload_invalid'",
    ):
        assert token in MIGRATION


def test_adapter_merges_only_server_verified_product_identity() -> None:
    first = "11111111-1111-4111-8111-111111111111"
    second = "22222222-2222-4222-8222-222222222222"
    merged = _merge(
        {
            "media": [
                {"id": first, "original_filename": "verified.png"},
                {"id": second, "original_filename": "unresolved.png"},
            ]
        },
        {
            "items": [
                {
                    "id": first,
                    "product_id": "33333333-3333-4333-8333-333333333333",
                    "sku": "SKU-1",
                    "product_name": "Exact product",
                    "rights_confirmed": True,
                    "identity_verified": True,
                },
                {
                    "id": second,
                    "sku": "UNTRUSTED",
                    "product_name": "Must not merge",
                    "rights_confirmed": True,
                    "identity_verified": False,
                },
            ]
        },
    )
    assert merged["media"][0]["sku"] == "SKU-1"
    assert merged["media"][0]["product_name"] == "Exact product"
    assert merged["media"][0]["identity_verified"] is True
    assert merged["media"][0]["rights_confirmed"] is True
    assert merged["media"][1]["identity_verified"] is False
    assert merged["media"][1]["rights_confirmed"] is False
    assert "sku" not in merged["media"][1]


def test_generation_form_autofills_and_locks_exact_product_for_paid_runs() -> None:
    for token in (
        'generationMediaIdentity: "creator_generation_media_identity"',
        "mergeGenerationMediaIdentity(response, identityResponse)",
        "generationMediaIdentity(mediaIds, {",
        "project_id: requiredProjectId(projectIdSnake || projectId)",
        'data-media-identity-verified="${identity.verified ? "true" : "false"}"',
        'data-media-rights-confirmed="${identity.rightsConfirmed ? "true" : "false"}"',
        "function syncGenerationProductIdentity(form)",
        "input.disabled = real && !paidReady",
        "input.readOnly = real && input.value === value",
        "Товар зафиксирован:",
        'input[name="media_id"]:checked:not(:disabled)',
    ):
        assert token in ADAPTER or token in APP
    assert ".generation-product-identity" in STYLES
    assert ".generation-media-option:has(input:disabled)" in STYLES
    assert './styles.css?v=20260730.4' in INDEX
    assert './app.js?v=20260823.copy-engines.45' in INDEX
    assert './supabase-api.js?v=20260823.copy-engines.45' in APP


def test_primary_generation_photo_is_first_in_paid_payload() -> None:
    identity = APP[
        APP.index("function selectedGenerationProductIdentity("):
        APP.index("function syncGenerationMediaSelection(")
    ]
    assert "selection.primaryMediaId" in identity
    assert "...selection.mediaIds.filter(" in identity
    assert "mediaIds," in identity
