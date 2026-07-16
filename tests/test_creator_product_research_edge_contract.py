from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-product-research/index.ts"
WORKFLOW = ROOT / ".github/workflows/supabase-pages.yml"


def _source() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_research_edge_is_authenticated_origin_bound_and_claims_before_openai() -> None:
    source = _source()
    config = tomllib.loads(
        (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    )

    assert config["functions"]["creator-product-research"]["verify_jwt"] is True
    assert 'auth: "user"' in source
    assert 'const PUBLIC_APP_ORIGIN = "https://alisia777.github.io"' in source
    assert 'const allowed = new Set(["action", "research_id"])' in source
    assert 'Object.keys(value).length !== 2' in source
    assert '"creator_product_research_status"' in source
    assert '"system_claim_product_research"' in source
    assert '"system_complete_product_research"' in source
    claim = source.index('"system_claim_product_research"', source.index("withSupabase"))
    provider = source.index("OPENAI_RESPONSES_URL", claim)
    assert claim < provider
    assert "if (!claim.claimed)" in source


def test_research_uses_server_only_openai_web_search_vision_and_strict_json() -> None:
    source = _source()

    for marker in (
        'Deno.env.get("OPENAI_API_KEY")',
        'const OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"',
        'type: "web_search"',
        'tool_choice: "required"',
        'type: "input_image"',
        'type: "json_schema"',
        "strict: true",
        "store: false",
        'enum: ["prepublication_heuristic_not_probability"]',
        'task_type: "general"',
    ):
        assert marker in source
    assert "OPENAI_API_KEY:" not in source
    assert "console.log" not in source
    assert "console.error" not in source
    assert "error.message" not in source


def test_research_persists_only_provider_citations_and_private_signed_images() -> None:
    source = _source()

    assert 'include: ["web_search_call.action.sources"]' in source
    assert 'annotation.type !== "url_citation"' in source
    assert "providerSources.get(key)" in source
    assert "provider_citation_verified: true" in source
    assert 'source.source_type === "input_photo"' in source
    assert 'source_type: "product_photo"' in source
    assert "media_object_id: photo.mediaId" in source
    assert "visual_analysis: true" in source
    assert 'normalized.startsWith("utm_")' in source
    assert "url.searchParams.sort()" in source
    assert 'url.search = ""' not in source
    assert 'const STORAGE_BUCKET = "contentengine-private"' in source
    assert ".createSignedUrl(photo.objectName, SIGNED_IMAGE_TTL_SECONDS)" in source
    assert "validateSignedStorageUrl" in source
    assert "MAX_PHOTOS = 5" in source
    assert "MAX_PHOTO_BYTES = 10_485_760" in source
    assert "MAX_TOTAL_PHOTO_BYTES = 26_214_400" in source


def test_ambiguous_openai_outcome_is_terminal_and_never_auto_replayed() -> None:
    source = _source()

    status_gate = source.index('if (authorized.status !== "queued")')
    claim = source.index('"system_claim_product_research"', status_gate)
    provider = source.index("providerResponse = await fetchWithTimeout", claim)
    assert status_gate < claim < provider
    assert 'if (!claim.claimed)' in source[claim:provider]
    assert '"idempotency-key": `product-research:${claim.run.id}`' in source
    assert '"X-Client-Request-Id": claim.run.id' in source
    assert '"provider_outcome_unknown"' in source
    assert "Автоматического повтора платного запроса нет" in source
    assert 'status === 408 || status >= 500' in source
    assert '"provider_timeout"' not in source


def test_production_masks_syncs_and_deploys_openai_research() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    migrate = workflow["jobs"]["migrate"]
    steps = migrate["steps"]
    secret = next(
        step
        for step in steps
        if step.get("name") == "Synchronize private OpenAI API secret"
    )
    assert secret["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "OPENAI_API_KEY": "${{ secrets.OPENAI_API_KEY }}",
    }
    assert 'echo "::add-mask::$OPENAI_API_KEY"' in secret["run"]
    assert 'OPENAI_API_KEY="$OPENAI_API_KEY"' in secret["run"]
    deploy = next(
        step
        for step in steps
        if step.get("name") == "Deploy authenticated product research function"
    )
    assert deploy["run"] == (
        'supabase functions deploy creator-product-research '
        '--project-ref "$SUPABASE_PROJECT_REF"'
    )
    assert "OPENAI_API_KEY" not in workflow["jobs"]["build-pages"]["env"]


def test_ci_formats_lints_and_checks_research_edge() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    name = "creator-product-research"
    assert f"deno fmt --check supabase/functions/{name}" in ci
    assert f"deno lint supabase/functions/{name}/index.ts" in ci
    assert f"deno check supabase/functions/{name}/index.ts" in ci
