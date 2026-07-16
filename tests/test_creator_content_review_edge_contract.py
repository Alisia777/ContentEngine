from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-content-review/index.ts"
CI = ROOT / ".github/workflows/ci.yml"
DEPLOY = ROOT / ".github/workflows/supabase-pages.yml"


def _source() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_content_review_edge_is_authenticated_origin_bound_and_durable() -> None:
    source = _source()
    config = tomllib.loads(
        (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    )

    assert EDGE.is_file()
    assert config["functions"]["creator-content-review"]["verify_jwt"] is True
    assert 'auth: "user"' in source
    assert 'const PUBLIC_APP_ORIGIN = "https://alisia777.github.io"' in source
    assert 'request.headers.get("origin") !== PUBLIC_APP_ORIGIN' in source
    assert 'request.method !== "POST"' in source
    assert "readBoundedStream(request.body, MAX_BODY_BYTES)" in source
    assert "request.text()" not in source
    assert '"creator_content_review_status"' in source
    assert '"system_claim_content_review"' in source
    assert '"system_complete_content_review"' in source
    claim = source.index(
        '"system_claim_content_review"', source.index("withSupabase")
    )
    provider = source.index("OPENAI_RESPONSES_URL", claim)
    assert claim < provider
    assert "if (!claim.claimed)" in source


def test_review_uses_server_only_multimodal_openai_and_moderation() -> None:
    source = _source()

    for marker in (
        'Deno.env.get("OPENAI_API_KEY")',
        'const OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"',
        'const OPENAI_MODERATIONS_URL = "https://api.openai.com/v1/moderations"',
        'model: "omni-moderation-latest"',
        'type: "input_image"',
        'type: "json_schema"',
        "strict: true",
        "store: false",
        '"idempotency-key": `content-review:${claim.run.id}`',
        '"X-Client-Request-Id": claim.run.id',
    ):
        assert marker in source
    assert "OPENAI_API_KEY:" not in source
    assert "console.log" not in source
    assert "console.error" not in source


def test_review_separates_quality_from_fail_closed_compliance() -> None:
    source = _source()

    assert 'const RULESET_VERSION = "ru-content-compliance-2026-07-16.1"' in source
    assert "Высокий quality score никогда не отменяет blocker" in source
    assert '"compliance_status": complianceStatus' not in source
    assert "compliance_status: complianceStatus" in source
    assert "blockers_count: blockers.length" in source
    assert "warnings_count: warnings.length" in source
    assert "overall_score: currentScore" in source
    for rule in (
        "PLATFORM.RESTRICTED_RESOURCE",
        "AD.MARKING.ERID",
        "AD.ORD_ACK",
        "PUBLISHER.RKN_10K",
        "RIGHTS.MEDIA",
        "PERSON.IMAGE_RELEASE",
        "YOUTUBE.AI_DISCLOSURE",
        "BAA.DISCLAIMER",
        "CLAIM.THERAPEUTIC_NONMEDICAL",
        "CLAIM.GUARANTEE",
        "TECH.BLACK_FRAMES",
        "SCOPE.AUDIO_MANUAL_REVIEW",
    ):
        assert rule in source
    assert "Не маскируйте рекламу под рекомендацию" in source
    assert "human_review_required" in source


def test_video_review_is_bounded_and_discloses_frame_audio_limitations() -> None:
    source = _source()

    assert "const MIN_VIDEO_FRAMES = 3" in source
    assert "const MAX_FRAMES = 6" in source
    assert "const MAX_FRAME_BYTES = 524_288" in source
    assert "const MAX_TOTAL_FRAME_BYTES = 2_359_296" in source
    assert "DATA_IMAGE_PATTERN" in source
    assert 'claim.run.media.mimeType === "video/mp4"' in source
    assert "payload.frames.length < MIN_VIDEO_FRAMES" in source
    assert "Аудио не распознано" in source
    assert "не расшифровывает весь звук MP4" in source
    assert "media.sha256" in source
    assert "SCOPE.BROWSER_FRAMES_ADVISORY" in source


def test_review_fails_closed_before_paid_provider_for_stale_or_private_people_media() -> None:
    source = _source()
    claim = source.index('"system_claim_content_review"', source.index("withSupabase"))
    provider = source.index("const apiKey = openAiSecret()", claim)

    assert 'value.status !== "ready"' in source[:provider]
    assert "value.snapshot_matches !== true" in source[:provider]
    assert '"external_ai_processing_basis_required"' in source[:provider]
    assert 'stringInput(claim.run.input, "people_present") === "yes"' in source[:provider]
    assert 'boolInput(claim.run.input, "external_ai_processing_confirmed")' in source[:provider]


def test_generated_provenance_and_ad_classification_are_not_discarded() -> None:
    source = _source()

    for marker in (
        "CONTEXT.GENERATED_PROVENANCE",
        "product_category_verified",
        "product_category_source",
        "generation_job_id",
        "AD.CLASSIFICATION_CONFLICT",
        "ad_probability: adProbability",
        "ad_classification_summary: String(modelResult.ad_classification_summary)",
    ):
        assert marker in source
    assert 'category === "baa"' in source
    assert 'category === "supplement"' not in source


def test_image_review_uses_the_protected_original_not_browser_supplied_frames() -> None:
    source = _source()
    evidence = source[
        source.index("const imageUrls: string[] = [];") :
        source.index("if (!imageUrls.length) {", source.index("const imageUrls: string[] = [];"))
    ]

    assert 'if (claim.run.media.mimeType.startsWith("image/"))' in evidence
    assert "createSignedUrl(" in evidence
    assert "validateSignedStorageUrl" in evidence
    assert "} else {\n    imageUrls.push(...payload.frames);" in evidence


def test_review_rules_are_versioned_and_source_linked() -> None:
    source = _source()

    for marker in (
        "https://government.ru/docs/all/98086/",
        "https://publication.pravo.gov.ru/document/0001202507250057",
        "https://publication.pravo.gov.ru/document/0001202504070018",
        "https://publication.pravo.gov.ru/document/0001202504140029",
        "https://government.ru/docs/all/98196/",
        "https://government.ru/docs/all/95825/?page=18",
        "https://eec.eaeunion.org/comission/department/deptexreg/tr/bezopParfum.php",
        "https://support.google.com/youtube/answer/14328491",
    ):
        assert marker in source
    assert "LEGAL_SOURCE_URLS[sourceKey]" in source
    assert "ruleset_version: RULESET_VERSION" in source


def test_ci_and_production_deploy_content_review_edge() -> None:
    ci = CI.read_text(encoding="utf-8")
    workflow = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    name = "creator-content-review"

    assert f"deno fmt --check supabase/functions/{name}" in ci
    assert f"deno lint supabase/functions/{name}/index.ts" in ci
    assert f"deno check supabase/functions/{name}/index.ts" in ci

    steps = workflow["jobs"]["migrate"]["steps"]
    deploy = next(
        step
        for step in steps
        if step.get("name") == "Deploy authenticated content review function"
    )
    assert deploy["run"] == (
        "supabase functions deploy creator-content-review "
        '--project-ref "$SUPABASE_PROJECT_REF"'
    )
    assert "OPENAI_API_KEY" not in workflow["jobs"]["build-pages"]["env"]
