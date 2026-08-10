from __future__ import annotations

import base64
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608100009_paid_research_youtube_source_guard.sql"
)
PROJECT_SCOPE_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040005_project_scoped_workflow.sql"
)
EDGE = ROOT / "supabase" / "functions" / "creator-product-research" / "index.ts"
INTAKE = ROOT / "web" / "app" / "workspace-research-video-intake.js"
APP = ROOT / "web" / "app" / "app.js"
API = ROOT / "web" / "app" / "supabase-api.js"
PRIVATE_ALIAS = "creator_start_project_research_pre_youtube_guard_v1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_youtube_paid_start_guard_migration_parses_and_preserves_one_alias() -> None:
    source = _read(MIGRATION)

    assert parse_sql(source)
    assert len(PRIVATE_ALIAS.encode("ascii")) <= 63
    assert source.count(f"rename to {PRIVATE_ALIAS}") == 1
    assert (
        "if to_regprocedure(\n"
        f"    'content_factory_private.{PRIVATE_ALIAS}(jsonb)'\n"
        "  ) is null then"
    ) in source
    assert "if to_regprocedure('public.creator_start_project_research(jsonb)') is null" in source

    wrapper = _between(
        source,
        "create or replace function public.creator_start_project_research(",
        "revoke all on function public.creator_start_project_research(jsonb)",
    )
    payload = wrapper.index("content_factory_private.require_payload(p_payload)")
    youtube_guard = wrapper.index("paid_research_has_unattached_youtube_url", payload)
    delegate = wrapper.index(PRIVATE_ALIAS, youtube_guard)
    assert payload < youtube_guard < delegate
    assert "research_youtube_source_requires_media" in wrapper[youtube_guard:delegate]


def test_database_guard_is_private_fail_closed_and_provider_free() -> None:
    source = _read(MIGRATION)
    project_scope = _read(PROJECT_SCOPE_MIGRATION)
    folded = source.casefold()

    for field in ("objective", "marketplace_url"):
        assert f"p_payload ->> '{field}'" in source
    for host in ("youtube", "youtube(-nocookie)?", "youtu"):
        assert host in source
    assert source.count("'https?://") == 2
    assert "security definer" in folded
    assert "set search_path = ''" in folded
    assert (
        "revoke all on function\n"
        "  content_factory_private.paid_research_has_unattached_youtube_url(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in source
    assert (
        f"revoke all on function content_factory_private\n  .{PRIVATE_ALIAS}(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in source
    assert (
        "revoke all on function public.creator_start_project_research(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in source
    assert (
        "grant execute on function public.creator_start_project_research(jsonb)\n"
        "  to authenticated"
    ) in source
    assert (
        "revoke all on function public.creator_start_product_research(jsonb)\n"
        "  from public, anon, authenticated"
    ) in project_scope
    for forbidden in (
        "system_begin_research_provider_attempt",
        "net.http",
        "http_post(",
        "api.openai.com",
    ):
        assert forbidden not in folded


def test_edge_fallback_rejects_legacy_run_before_every_provider_boundary() -> None:
    source = _read(EDGE)
    handler = source[source.index("async function handleCreatorProductResearch(") :]

    claim = handler.index('"system_claim_product_research"')
    guard = handler.index("containsUnattachedYoutubeUrl(claim.run.brief)", claim)
    secret = handler.index("const apiKey = openAiSecret()", guard)
    continuation = handler.index("await readProviderResponse()", secret)
    attempt = handler.index("await beginProviderAttempt(", continuation)
    paid_post = handler.index('method: "POST"', attempt)

    assert claim < guard < secret < continuation < attempt < paid_post
    guarded_branch = handler[guard:secret]
    assert "containsUnattachedYoutubeUrl(claim.run.productUrl)" in guarded_branch
    assert '"input_validation_failed"' in guarded_branch
    assert "return await fail(" in guarded_branch
    assert "UNATTACHED_YOUTUBE_URL_PATTERN" in source
    pattern_line = next(
        line for line in source.splitlines() if "youtube(?:-nocookie)?" in line
    )
    assert pattern_line.strip().startswith("/https?:\\/\\/")
    assert not re.search(r"/[a-z]*g[a-z]*;?$", pattern_line.strip())


def test_market_only_submit_sanitizes_before_the_bubbling_paid_handler() -> None:
    intake = _read(INTAKE)
    app = _read(APP)
    submit = _between(
        intake,
        'form.addEventListener("submit", (event) => {',
        "}, { capture: true });",
    )
    bypass = _between(
        intake,
        'withoutVideo.addEventListener("click", () => {',
        "actions.append(upload, withoutVideo);",
    )

    assert submit.index("sanitizeMarketOnlyPaidResearch(form)") < submit.index(
        "validateInput(input, status)"
    )
    assert bypass.index("sanitizeMarketOnlyPaidResearch(form)") < bypass.index(
        "form.requestSubmit()"
    )
    assert "}, { capture: true });" in intake
    assert 'document.addEventListener("submit", handleSubmit);' in app
    assert "const values = new FormData(form);" in app
    for field in (
        "category_name",
        "research_focus",
        "competitor_references",
        "known_facts",
        "marketplace_url",
    ):
        assert field in intake

    intake_pattern = next(
        line.strip()
        for line in intake.splitlines()
        if "youtube(?:-nocookie)?" in line
    )
    edge_pattern = next(
        line.strip()
        for line in _read(EDGE).splitlines()
        if "youtube(?:-nocookie)?" in line
    )
    assert intake_pattern == edge_pattern
    assert "containsUnattachedYoutubeUrl(marketplace.value)" in intake


def test_database_guard_error_has_a_friendly_api_mapping() -> None:
    source = _read(API)
    mapping_line = next(
        line.strip()
        for line in source.splitlines()
        if line.lstrip().startswith("research_youtube_source_requires_media:")
    )

    assert "YouTube" in mapping_line
    assert "MP4" in mapping_line
    assert "исключите YouTube-ссылку" in mapping_line


def test_youtube_reference_sanitizer_is_idempotent_and_keeps_lookalikes() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")

    encoded = base64.b64encode(_read(INTAKE).encode("utf-8")).decode("ascii")
    script = f"""
      const mod = await import('data:text/javascript;base64,{encoded}');
      const inputs = [
        'Creator https://youtu.be/CXssfXBVInw, keep',
        'https://www.youtube.com/watch?v=CXssfXBVInw',
        'HTTP http://m.youtube.com/channel/UC1234567890',
        'Channel https://www.youtube.com/@creator/videos',
        'Studio https://studio.youtube.com/channel/UC1234567890',
        'Bare http://youtube.com',
        'Safe https://example.test/video',
        'Look https://youtube.com.evil.test/watch?v=CXssfXBVInw',
        'Look http://notyoutube.com/channel/UC1234567890',
        'Two https://youtu.be/CXssfXBVInw and https://www.youtube-nocookie.com/embed/CXssfXBVInw.'
      ];
      const once = inputs.map(mod.stripExactYoutubeReferences);
      const twice = once.map(mod.stripExactYoutubeReferences);
      const detected = [
        'http://youtu.be/CXssfXBVInw',
        'https://www.youtube.com/@creator/videos',
        'https://studio.youtube.com/channel/UC1234567890',
        'HTTP://WWW.YOUTUBE-NOCOOKIE.COM/embed/CXssfXBVInw',
        'https://youtube.com.evil.test/watch?v=CXssfXBVInw',
        'https://notyoutube.com/watch?v=CXssfXBVInw'
      ].map(mod.containsUnattachedYoutubeUrl);
      console.log(JSON.stringify({{ once, twice, detected }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(result.stdout)

    assert output["once"] == [
        "Creator keep",
        "",
        "HTTP",
        "Channel",
        "Studio",
        "Bare",
        "Safe https://example.test/video",
        "Look https://youtube.com.evil.test/watch?v=CXssfXBVInw",
        "Look http://notyoutube.com/channel/UC1234567890",
        "Two and",
    ]
    assert output["twice"] == output["once"]
    assert output["detected"] == [True, True, True, True, False, False]
