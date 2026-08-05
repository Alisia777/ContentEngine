from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608050001_research_manual_training_example.sql"
).read_text(encoding="utf-8")
RUNTIME_FIX = (
    ROOT
    / "supabase/migrations/202608050002_research_manual_training_example_runtime_fix.sql"
).read_text(encoding="utf-8")
MODULE = (ROOT / "web/app/research-training-example.js").read_text(
    encoding="utf-8"
)
CSS = (ROOT / "web/app/research-training-example.css").read_text(
    encoding="utf-8"
)
LOADER = (ROOT / "web/app/workspace-os-v4-loader.js").read_text(
    encoding="utf-8"
)
EXACT_AIR_FRYER_SHORT = "https://www.youtube.com/shorts/GW-NfEVlPGc"


def test_exact_air_fryer_short_is_a_supported_youtube_identity() -> None:
    assert EXACT_AIR_FRYER_SHORT.endswith("/GW-NfEVlPGc")
    assert 'parts[0] === "shorts"' in MODULE
    assert 'parts[0] === "watch"' in MODULE
    assert 'host === "youtu.be"' in MODULE
    assert '["shorts", "embed", "live"]' in MODULE
    assert "research_youtube_video_id" in MIGRATION
    assert "youtube[.]com/(shorts|embed|live)" in MIGRATION
    assert "youtube[.]com/watch[?]" in MIGRATION


def test_manual_example_is_evidence_not_a_paid_provider_run() -> None:
    combined = MIGRATION + RUNTIME_FIX
    for marker in (
        "creator_register_research_training_example",
        "system_register_research_training_example",
        "research-training-example-v1",
        "social_video",
        "user_supplied_youtube",
        "channel.short_vertical_video",
        "linked_pending_human_review",
        "registered_pending_category_binding",
        "provider_call_performed', false",
        "paid_analysis_performed', false",
        "exact_copy_allowed', false",
    ):
        assert marker in combined
    assert "creator_start_project_research" not in MODULE
    assert "creator-product-research" not in MODULE
    assert "requestSubmit" not in MODULE
    assert "без provider call" in MODULE
    assert "Один пример остаётся кандидатом" in MODULE


def test_runtime_fix_reads_binding_fields_into_scalar_targets() -> None:
    assert "binding_id_value uuid;" in RUNTIME_FIX
    assert "binding_category_id_value uuid;" in RUNTIME_FIX
    assert "select binding.id," in RUNTIME_FIX
    assert "into binding_id_value," in RUNTIME_FIX
    assert "select binding.*" not in RUNTIME_FIX
    assert "category_binding_id', binding_id_value" in RUNTIME_FIX
    assert "category_binding_matches', binding_matches" in RUNTIME_FIX


def test_manual_example_requires_exact_scope_and_human_acknowledgements() -> None:
    combined = MIGRATION + RUNTIME_FIX
    for marker in (
        "project_id",
        "run_id",
        "compliance_category",
        "market_category_name",
        "training_role",
        "human_summary",
        "public_source_ack",
        "no_exact_copy_ack",
        "research_training_example_category_mismatch",
        "research_training_example_ack_required",
    ):
        assert marker in combined
        assert marker in MODULE
    assert "array['owner', 'admin', 'producer']" in MIGRATION
    assert "category_binding_matches" in combined
    assert "provider_citation_verified', false" in combined


def test_research_route_loads_one_compact_example_action() -> None:
    for marker in (
        "research-training-example.css?v=${BUILD}",
        "research-training-example.js?v=${BUILD}",
        'route === "/workspace/research"',
    ):
        assert marker in LOADER
    assert "data-ce-research-example-launch" in MODULE
    assert "Добавить видео без платного анализа" in MODULE
    assert "Добавить YouTube-пример в обучение" in MODULE
    assert "MutationObserver" not in MODULE
    assert "innerHTML" not in MODULE
    assert "insertAdjacentHTML" not in MODULE


def test_manual_example_module_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    subprocess.run(
        [node, "--check", str(ROOT / "web/app/research-training-example.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_manual_example_stylesheet_is_balanced_and_responsive() -> None:
    assert CSS.count("{") == CSS.count("}")
    assert "@media (max-width: 680px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "min-height: 44px" in CSS
