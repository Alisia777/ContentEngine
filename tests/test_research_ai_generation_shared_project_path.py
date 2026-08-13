from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "research_ai_generation_shared_project_path_test.sql"
)


def _source() -> str:
    return PGTAP.read_text(encoding="utf-8")


def test_shared_project_full_path_fixture_parses_as_postgresql() -> None:
    statements = parse_sql(_source())

    assert len(statements) >= 50


def test_fixture_connects_authoritative_research_ai_and_generation_seams() -> None:
    source = _source().casefold()

    ordered_seams = (
        "public.creator_start_project_research(",
        "public.system_claim_product_research(",
        "public.system_complete_product_research(",
        "public.contentengine_ai_research_training_queue(",
        "public.creator_save_project_creative_brief_draft(",
        "public.creator_approve_project_creative_brief(",
        "public.contentengine_decide_ai_research_training(",
        "public.contentengine_generation_research_recommendations(",
        "public.creator_prepare_generation_spec(",
        "public.contentengine_bind_generation_spec_ai_research(",
    )
    positions = [source.index(seam) for seam in ordered_seams]

    assert positions == sorted(positions)
    assert "research_summary,results,0" in source
    assert "research_summary,conclusions,0" in source
    assert "queue,0,sources" in source
    assert "queue,0,analysis,guidance,recommendation" in source
    assert "human_draft.origin = 'human'" in source
    assert "human_draft.previous_draft_id = context_row.draft_id" in source
    assert "contract,presets_are_advisory" in source
    assert "contract,recommendations_are_editable" in source
    assert "generation_spec_ai_research_bindings binding" in source
    assert "binding.selection_id = context_row.selection_id" in source
    assert "binding.recommendation_snapshot = selection.recommendations -> 0" in source


def test_fixture_covers_shared_acl_and_server_owned_media_lifecycle() -> None:
    source = _source().casefold()

    assert "public.creator_grant_project_member(" in source
    assert "public.creator_project_media(" in source
    assert "content_factory.storage_project_read_allowed(" in source
    assert source.count("workspace_project_access_required") >= 4
    assert "generated_output:drafts" in source
    assert "the deterministic generated fixture retains exact advice and spec lineage" in source
    assert "a completed server review routes generated material to review" in source
    assert "an immutable approval routes generated material to ready" in source
    for system_role in ("'sources'", "'drafts'", "'review'", "'ready'"):
        assert system_role in source


def test_fixture_is_transactional_and_network_free() -> None:
    source = _source().casefold().strip()

    assert source.startswith("begin;")
    assert source.endswith("rollback;")
    assert "system_begin_research_provider_attempt" not in source
    assert "system_bind_research_provider_response" not in source
    assert "creator_start_real_generation" not in source
    assert "creator_start_real_photo_generation" not in source
    assert "net.http_" not in source
    assert "http_post(" not in source
    assert "'provider_attempts', 0" in source
    assert "'generation_batches', 1" in source
    assert "'generation_jobs', 1" in source
    assert "'spend_entries', 2" in source
    assert "'generation_job_id', 'ca600000-0000-4000-8000-000000000002'" in source
    assert source.count("disable trigger a_generation_spec_binding_guard") == 1
    assert source.count("enable trigger a_generation_spec_binding_guard") == 1
    assert "disable trigger all" not in source


def test_second_operator_does_not_inherit_teammate_learned_queue() -> None:
    source = _source().casefold()

    assert "jsonb_array_length(queue_value -> 'learned') = 0" in source
    assert (
        "the second operator does not inherit teammate learned queue but retains "
        "project-shared approved advice and binding"
    ) in source
    assert "the second member sees learned conclusions" not in source
