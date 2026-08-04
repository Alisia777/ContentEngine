from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    ROOT
    / "supabase"
    / "tests"
    / "research_youtube_automatic_integration_test.sql"
)


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def test_automatic_youtube_integration_canary_parses() -> None:
    pglast = pytest.importorskip("pglast")

    assert pglast.parse_sql(_sql())


def test_canary_covers_the_real_automatic_lifecycle_and_no_retry() -> None:
    sql = _sql()

    required_calls = (
        "public.system_decide_research_youtube_global_rollout",
        "public.creator_decide_research_youtube_rollout",
        "public.creator_configure_research_source_collection_policy",
        "public.system_read_automatic_research_youtube_ingestion",
        "public.system_begin_automatic_research_youtube_transport",
        "public.system_record_research_youtube_transport",
        "public.system_complete_research_youtube_ingestion",
        "content_factory_private.research_category_evidence_readiness",
        "public.creator_research_category_learning_status",
    )
    for call in required_calls:
        assert call in sql

    assert sql.count("public.system_claim_due_research_youtube_collection") == 2
    assert "research_instagram_provider_legal_choice_required" in sql
    assert "the second automatic scheduler tick starts no retry" in sql
    assert "description', 'captions', 'transcript', 'tags', 'raw_response'" in sql
    assert sql.lstrip().startswith("begin;")
    assert sql.rstrip().endswith("rollback;")
