from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
EDGE = (ROOT / "supabase" / "functions" / "creator-reference-intelligence" / "index.ts").read_text(encoding="utf-8")
CLIENT = (APP / "workspace-reference-intelligence.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-reference-intelligence.css").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CONFIG = (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github" / "workflows" / "deploy-reference-intelligence.yml").read_text(encoding="utf-8")


def test_reference_intelligence_is_lazy_loaded_only_where_briefs_exist() -> None:
    for marker in (
        'route === "/workspace/research" || route === "/workspace/generation"',
        'workspace-reference-intelligence.css?v=20260731.5',
        'workspace-reference-intelligence.js?v=20260731.5',
    ):
        assert marker in LOADER


def test_reference_inbox_accepts_links_images_pdf_and_video_frames() -> None:
    for marker in (
        'Примеры для ТЗ',
        'Ссылки на примеры',
        'image/jpeg,image/png,image/webp,application/pdf,video/mp4',
        'VIDEO_FRAME_RATIOS',
        'canvas.toDataURL("image/jpeg"',
        'Разобрать примеры',
        'Вставить в вводные ТЗ',
        'Вставить в замысел',
        'РЕФЕРЕНСЫ — ТОЛЬКО СТИЛЬ, НЕ ФАКТЫ О ТОВАРЕ',
    ):
        assert marker in CLIENT


def test_reference_parser_keeps_examples_out_of_product_evidence() -> None:
    for marker in (
        'Референсы — НЕ источник фактов о товаре',
        'Не переносить из них характеристики, цену',
        'Не копировать чужой товар, бренд, логотип',
        'concise_instruction',
        'do_not_copy',
        'providerUrls',
        'idempotency-key',
        'store: false',
    ):
        assert marker in EDGE
    assert 'fine_tun' not in EDGE.lower()
    assert 'training_data' not in EDGE.lower()


def test_reference_parser_has_bounded_authenticated_inputs() -> None:
    for marker in (
        'auth: "user"',
        'MAX_BODY_BYTES',
        'MAX_URLS = 8',
        'MAX_ASSETS = 12',
        'MAX_TOTAL_ASSET_BYTES',
        'publicHttpsUrl',
        'request_too_large',
        'reference_payload_invalid',
        'OPENAI_API_KEY',
        'web_search',
        'input_file',
        'input_image',
    ):
        assert marker in EDGE
    assert 'service_role' not in EDGE
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in EDGE


def test_client_does_not_submit_or_mutate_existing_business_forms() -> None:
    for forbidden in (
        'requestSubmit',
        'form.submit(',
        'transitionTask',
        'decidePayout',
        'confirmPlacement',
        'innerHTML',
        'outerHTML',
        'insertAdjacentHTML',
        'cloneNode',
    ):
        assert forbidden not in CLIENT
    assert 'target.dispatchEvent(new Event("input"' in CLIENT
    assert 'target.dispatchEvent(new Event("change"' in CLIENT


def test_reference_function_is_configured_and_deployed_after_main_release() -> None:
    assert '[functions.creator-reference-intelligence]' in CONFIG
    assert '[functions.creator-reference-intelligence]\nverify_jwt = true' in CONFIG
    for marker in (
        'workflows:\n      - Deploy Supabase and GitHub Pages',
        'supabase functions deploy creator-reference-intelligence',
        'SUPABASE_ACCESS_TOKEN',
        'EXPECTED_SUPABASE_PROJECT_REF',
    ):
        assert marker in DEPLOY


def test_reference_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    subprocess.run([node, "--check", str(APP / "workspace-reference-intelligence.js")], check=True, capture_output=True, text=True)
    subprocess.run([node, "--check", str(APP / "workspace-os-v4-loader.js")], check=True, capture_output=True, text=True)


def test_reference_stylesheet_is_balanced_and_responsive() -> None:
    assert CSS.count("{") == CSS.count("}")
    assert '@media (max-width: 560px)' in CSS
    assert '@media (prefers-reduced-motion: reduce)' in CSS
