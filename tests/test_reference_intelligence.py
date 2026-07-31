from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
EDGE = (
    ROOT
    / "supabase"
    / "functions"
    / "creator-reference-intelligence"
    / "index.ts"
).read_text(encoding="utf-8")
CLIENT = (APP / "workspace-reference-intelligence.js").read_text(
    encoding="utf-8"
)
CSS = (APP / "workspace-reference-intelligence.css").read_text(
    encoding="utf-8"
)
LOADER = (APP / "workspace-os-v4-loader.js").read_text(
    encoding="utf-8"
)
CONFIG = (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
    encoding="utf-8"
)
DEPLOY = (ROOT / ".github" / "workflows" / "supabase-pages.yml").read_text(
    encoding="utf-8"
)


def test_reference_intelligence_is_lazy_loaded_only_where_briefs_exist() -> None:
    for marker in (
        'route === "/workspace/research" || route === "/workspace/generation"',
        "workspace-reference-intelligence.css?v=20260731.5",
        "workspace-reference-intelligence.js?v=20260731.5",
    ):
        assert marker in LOADER


def test_reference_inbox_accepts_links_images_pdf_and_video_frames() -> None:
    for marker in (
        "Примеры для безопасного ТЗ",
        "Ссылки на примеры",
        "image/jpeg,image/png,image/webp,application/pdf,video/mp4",
        "VIDEO_FRAME_RATIOS",
        'canvas.toDataURL("image/jpeg"',
        "Разобрать примеры",
        "Добавить в визуальный стиль",
        "Подготовить безопасное ТЗ",
        "РЕФЕРЕНСЫ — ТОЛЬКО СТИЛЬ, НЕ ФАКТЫ О ТОВАРЕ",
        "Не обучает модель",
        "Запускаю отдельный платный ИИ-разбор примеров",
    ):
        assert marker in CLIENT


def test_reference_parser_keeps_examples_out_of_product_evidence() -> None:
    for marker in (
        "Референсы — НЕ источник фактов о товаре",
        "Не переносить из них характеристики, цену",
        "Не копировать чужой товар, бренд, логотип",
        "concise_instruction",
        "do_not_copy",
        "providerUrls",
        "idempotency-key",
        "store: false",
    ):
        assert marker in EDGE
    assert "fine_tun" not in EDGE.lower()
    assert "training_data" not in EDGE.lower()


def test_reference_parser_has_bounded_authenticated_inputs() -> None:
    for marker in (
        'auth: "user"',
        "MAX_BODY_BYTES",
        "MAX_URLS = 8",
        "MAX_ASSETS = 16",
        "MAX_TOTAL_ASSET_BYTES",
        "publicHttpsUrl",
        "request_too_large",
        "reference_payload_invalid",
        "OPENAI_API_KEY",
        "web_search",
        "input_file",
        "input_image",
    ):
        assert marker in EDGE
    assert "service_role" not in EDGE
    assert "SUPABASE_SERVICE_ROLE_KEY" not in EDGE


def test_sensitive_reference_urls_are_rejected_on_client_and_server() -> None:
    for marker in (
        "sensitiveParams",
        "x-amz-signature",
        "x-goog-signature",
    ):
        assert marker in CLIENT
    for marker in (
        "SENSITIVE_URL_PARAMS",
        "TRACKING_URL_PARAMS",
        "SENSITIVE_URL_PARAMS.has",
        "x-amz-signature",
        "x-goog-signature",
    ):
        assert marker in EDGE


def test_research_reference_enters_visual_direction_not_known_facts() -> None:
    for marker in (
        '#product-research-brief-form',
        "form.elements.visual_direction",
        "Добавлено только в «Визуальный стиль»",
    ):
        assert marker in CLIENT
    assert "form.elements.known_facts" not in CLIENT
    assert '#product-research-start-form' not in CLIENT


def test_generation_reference_returns_to_existing_safe_compiler() -> None:
    for marker in (
        "form.dataset.generationScenarioIntent",
        '[data-action="restore-auto-generation-brief"]',
        "looksCompiledPrompt",
        "form.dataset.autoGenerationBrief",
        "Runway и оплата не запускались",
    ):
        assert marker in CLIENT
    assert "compileSafeGenerationBrief" not in CLIENT
    assert "compileContentGenerationPrompt" not in CLIENT


def test_reference_drafts_are_product_scoped_and_session_only() -> None:
    for marker in (
        "contentengine.reference-intelligence.v2",
        "window.sessionStorage",
        "referenceScope",
        "form.dataset.identityMediaId",
        "generation:${sku}:${productName}",
        "form.dataset.researchId",
        '[data-action="logout"]',
    ):
        assert marker in CLIENT
    assert "window.localStorage" not in CLIENT


def test_unverified_urls_cannot_be_applied() -> None:
    for marker in (
        "resultHasUnverifiedUrls",
        "provider-citations",
        "Неподтверждённая ссылка не может попасть в ТЗ",
        "parsed.urls.length > state.verifiedUrls.length",
    ):
        assert marker in CLIENT


def test_paid_reference_analysis_is_explicit_and_retry_id_is_stable() -> None:
    for marker in (
        'PAID_ANALYSIS_ACK = "REFERENCE_ANALYSIS_PAID_V1"',
        "data-reference-paid-ack",
        "const sameRequest = state.signature === signature",
        "if (!sameRequest) state.requestId = crypto.randomUUID()",
        "без нового платного запроса",
    ):
        assert marker in CLIENT


def test_client_does_not_submit_business_forms_or_use_html_sinks() -> None:
    for forbidden in (
        "requestSubmit",
        "form.submit(",
        "transitionTask",
        "decidePayout",
        "confirmPlacement",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "cloneNode",
    ):
        assert forbidden not in CLIENT
    assert 'dispatchEvent(new Event("input"' in CLIENT
    assert 'dispatchEvent(new Event("change"' in CLIENT


def test_reference_function_is_in_main_ci_and_atomic_production_deploy() -> None:
    assert "[functions.creator-reference-intelligence]" in CONFIG
    assert (
        "[functions.creator-reference-intelligence]\nverify_jwt = true"
        in CONFIG
    )
    for marker in (
        '"creator-reference-intelligence",',
        "deno fmt --check --line-width 120 supabase/functions/creator-reference-intelligence",
        "deno lint supabase/functions/creator-reference-intelligence/index.ts",
        "deno check supabase/functions/creator-reference-intelligence/index.ts",
        "deno check web/app/workspace-reference-intelligence.js",
    ):
        assert marker in CI
    for marker in (
        '"creator-reference-intelligence",',
        "Deploy authenticated reference intelligence function",
        "supabase functions deploy creator-reference-intelligence",
        "SUPABASE_ACCESS_TOKEN",
        "EXPECTED_SUPABASE_PROJECT_REF",
        "needs:\n      - migrate\n      - build-pages",
    ):
        assert marker in DEPLOY


def test_no_temporary_or_duplicate_reference_workflows_remain() -> None:
    for name in (
        "_temporary-control-character-fix.yml",
        "reference-intelligence-ci.yml",
        "deploy-reference-intelligence.yml",
    ):
        assert not (ROOT / ".github" / "workflows" / name).exists()


def test_reference_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    subprocess.run(
        [node, "--check", str(APP / "workspace-reference-intelligence.js")],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-loader.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_reference_stylesheet_is_balanced_and_responsive() -> None:
    assert CSS.count("{") == CSS.count("}")
    assert ".ce-reference-intelligence__scope" in CSS
    assert ".ce-reference-intelligence__limitations" in CSS
    assert "@media (max-width: 560px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
