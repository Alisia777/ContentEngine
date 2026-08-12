"""SQL contracts for exact AI-selected Seedance speech binding."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608120001_ai_research_seedance_speech_binding.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "ai_research_generation_prompt_binding_test.sql"
)


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing SQL contract file: {path}"
    return path.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    pattern = re.compile(
        rf"create\s+or\s+replace\s+function\s+"
        rf"{re.escape(qualified_name).replace(r'\.', r'\s*\.\s*')}\s*\(",
        flags=re.IGNORECASE,
    )
    match = pattern.search(source)
    assert match is not None, f"Missing SQL function {qualified_name}"
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    return source[match.start() : match.end() + terminator.end()]


def test_additive_migration_and_pgtap_are_parseable_and_transactional() -> None:
    sql = _read(MIGRATION)
    pgtap = _read(PGTAP)
    assert MIGRATION.name > "202608110008_ai_research_generation_prompt_binding.sql"
    assert sql.lstrip().casefold().startswith("begin;")
    assert sql.rstrip().casefold().endswith("commit;")
    assert pgtap.lstrip().casefold().startswith("begin;")
    assert pgtap.rstrip().casefold().endswith("rollback;")
    assert parse_sql(sql)
    assert parse_sql(pgtap)


def test_server_parser_is_raw_only_structured_and_duration_bounded() -> None:
    sql = _read(MIGRATION)
    parser = _function(
        sql, "content_factory_private.ai_research_seedance_spoken_line"
    ).casefold()
    limits = _function(
        sql, "content_factory_private.ai_research_seedance_spoken_word_limit"
    ).casefold()
    for duration in (4, 8, 12, 15):
        assert str(duration) in limits
    assert "floor(p_duration_seconds * 22.0 / 8.0)" in limits
    assert "greatest(" in limits and "least(42" in limits
    for marker in (
        "'реплика / сюжет'",
        "spoken_seen := spoken_seen + 1",
        "spoken_seen <> 1",
        "ai_research_seedance_speech_has_control",
        "ai_research_seedance_source_has_unsafe_control",
        "[\"''«»‘’‚‛“”„‟‹›⹂「」『』〝〞〟﹁﹂﹃﹄＂＇｢｣]",
        "реплика[[:space:]]+героя",
        "generation_spec_prompt_has_external_reference",
        "spoken_token_count <> 1",
        "airesearchselection/v1",
        "regexp_matches(",
        "[[:alnum:]]+([-’''][[:alnum:]]+)*",
        "word_count_value not between 1 and word_limit_value",
    ):
        assert marker in parser
    assert "return spoken_value" in parser
    assert "outer_ascii_line_value !~*\n             '^реплика / сюжет:'" in parser
    controls = _function(
        sql,
        "content_factory_private.ai_research_seedance_speech_has_control",
    ).casefold()
    assert "between 0 and 31" in controls
    assert "between 127 and 159" in controls
    assert "generate_series(1, char_length" in controls
    source_controls = _function(
        sql,
        "content_factory_private."
        "ai_research_seedance_source_has_unsafe_control",
    ).casefold()
    assert "between 0 and 9" in source_controls
    assert "in (11, 12)" in source_controls
    assert "between 14 and 31" in source_controls
    assert "between 127 and 159" in source_controls
    assert "between 10 and 13" not in source_controls
    default_ignorables = _function(
        sql,
        "content_factory_private."
        "ai_research_seedance_has_default_ignorable",
    ).casefold()
    for codepoint in (
        173,
        847,
        1564,
        8203,
        8207,
        8288,
        8303,
        65279,
        917504,
        921599,
    ):
        assert str(codepoint) in default_ignorables
    assert "generate_series(1, char_length" in default_ignorables
    assert parser.count("ai_research_seedance_has_default_ignorable") >= 2
    structured = _function(
        sql,
        "content_factory_private.ai_research_seedance_structured_speech_count",
    ).casefold()
    assert "реплика[[:space:]]*/[[:space:]]*сюжет[[:space:]]*:" in structured
    assert "translate(" in structured
    directives = _function(
        sql,
        "content_factory_private.ai_research_seedance_speech_directive_count",
    ).casefold()
    assert "(герой|блогер|ведущ(ий|ая)|человек)" in directives
    assert "(говорит|произносит|рассказывает)" in directives
    assert "реплика[[:space:]]+героя([[:space:]]+дословно)?" in directives
    assert "translate(" in directives


def test_speech_proof_is_private_append_only_versioned_and_hashed() -> None:
    sql = _read(MIGRATION).casefold()
    assert "create table if not exists\n  content_factory.generation_spec_ai_research_speech_bindings" in sql
    for column in (
        "spoken_line_version",
        "spoken_line_hash",
        "spoken_prompt_fragment",
        "spoken_prompt_fragment_hash",
        "compiled_prompt_hash",
        "speech_binding_proof_hash",
    ):
        assert column in sql
    assert "ai-research-seedance-speech-v1" in sql
    assert "enable row level security" in sql
    assert "generation_spec_ai_research_speech_binding_append_only" in sql
    assert "reject_research_ai_handoff_mutation" in sql
    assert (
        "revoke all on content_factory.generation_spec_ai_research_speech_bindings\n"
        "  from public, anon, authenticated"
    ) in sql


def test_bind_preserves_public_acl_and_requires_exact_prompt_sentence() -> None:
    sql = _read(MIGRATION)
    lowered = sql.casefold()
    bind = _function(
        sql,
        "content_factory_private."
        "contentengine_bind_generation_spec_ai_research_pre_project_acl",
    ).casefold()
    delegate = (
        ".contentengine_bind_generation_spec_ai_research_"
        "pre_seedance_speech_v56(\n      p_payload"
    )
    assert delegate in bind
    assert bind.index(delegate) < bind.index("spoken_line_value :=")
    assert "spec_row.model <> 'seedance2_fast'" in bind
    assert "'реплика героя дословно: «' || spoken_line_value || '»'" in bind
    assert "spoken_marker_count_value <> 1" in bind
    assert "structured_speech_count_value <> 0" in bind
    assert "spoken_fragment_count_value <> 1" in bind
    assert "ai_research_seedance_has_default_ignorable" in bind
    assert "generation_spec_ai_research_speech_prompt_mismatch" in bind
    assert "insert into content_factory.generation_spec_ai_research_speech_bindings" in bind
    assert "select binding, version into binding_row, spec_row" not in bind
    assert "select binding.* into binding_row" in bind
    assert "select version.* into spec_row" in bind
    assert bind.count("for share;") >= 2
    assert not re.search(
        r"create\s+or\s+replace\s+function\s+public\s*\.\s*"
        r"contentengine_bind_generation_spec_ai_research\s*\(",
        lowered,
    )


def test_paid_start_delegates_v55_then_revalidates_exact_speech() -> None:
    sql = _read(MIGRATION)
    start = _function(sql, "public.creator_start_real_generation").casefold()
    delegate = ".creator_start_real_generation_pre_ai_speech_v56(p_payload)"
    assert delegate in start
    assert start.index(delegate) < start.index("spoken_line_value :=")
    assert "generation_spec_rejected" not in start
    assert "generation_ai_research_seedance_speech_binding_required" in start
    assert "generation_ai_research_seedance_speech_binding_invalid" in start
    assert "spec_row.model <> 'seedance2_fast' or binding_row.id is null" in start
    assert "spoken_marker_count_value <> 1" in start
    assert "structured_speech_count_value <> 0" in start
    assert "spoken_fragment_count_value <> 1" in start
    assert start.count("ai_research_seedance_has_default_ignorable") >= 2
    assert "return result_value" in start
    assert "creator_start_real_generation_pre_ai_research_prompt_v55" in _read(
        ROOT
        / "supabase"
        / "migrations"
        / "202608110008_ai_research_generation_prompt_binding.sql"
    ).casefold()

    v15_sql = _read(
        ROOT
        / "supabase"
        / "migrations"
        / "202608030017_generation_spec_control.sql"
    )
    v15_start = _function(v15_sql, "public.creator_start_real_generation").casefold()
    v15_assert = _function(
        v15_sql,
        "content_factory_private.assert_generation_spec_current",
    ).casefold()
    assert "approval_required and head_row.state <> 'approved'" in v15_assert
    assert "message = 'generation_spec_approval_required'" in v15_assert
    assert v15_start.index("assert_generation_spec_current(") < v15_start.index(
        ".creator_start_real_generation_pre_generation_spec_v15("
    )


def test_pgtap_covers_semantic_mismatch_legacy_rejection_and_rollback() -> None:
    pgtap = _read(PGTAP).casefold()
    for marker in (
        "server derives the exact raw structured speech",
        "duplicate speech heading hidden behind unicode whitespace",
        "outer tab is rejected before normalization",
        "ascii-multispace speech heading",
        "u+0085-prefixed heading",
        "inline nested speech label",
        "quoted wrapper",
        "c1 controls",
        "external reference",
        "default_ignorable",
        "every seedance duration",
        "contradicts the structured selected line",
        "second unicode-spaced structured speech directive",
        "legacy ai seedance binding without speech v1",
        "delegated writes roll back",
    ):
        assert marker in pgtap


def test_no_external_provider_or_acl_bypass_is_added() -> None:
    sql = _read(MIGRATION).casefold()
    for forbidden in (
        "net.http_post",
        "extensions.http_post",
        "supabase_functions.http_request",
        "runway",
    ):
        assert forbidden not in sql
    assert "grant execute on function public.creator_start_real_generation(jsonb)" in sql
    assert "notify pgrst, 'reload schema'" in sql
