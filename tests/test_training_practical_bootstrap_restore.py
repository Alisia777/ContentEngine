from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608170001_restore_training_practical_bootstrap_chain.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
PGTAP_PATH = ROOT / "supabase/tests/training_practical_bootstrap_chain_test.sql"
PGTAP = PGTAP_PATH.read_text(encoding="utf-8").casefold()

CHAIN_FUNCTIONS = (
    "creator_bootstrap_pre_practical_gate",
    "creator_bootstrap_pre_assessment_v5_sanitize",
    "creator_bootstrap_pre_training_waiver",
)
CANONICAL_SOURCES = {
    "creator_bootstrap_pre_practical_gate": (
        "202607160007_auth_email_delivery.sql"
    ),
    "creator_bootstrap_pre_assessment_v5_sanitize": (
        "202607190001_training_practical_review.sql"
    ),
    "creator_bootstrap_pre_training_waiver": (
        "202607190002_training_assessment_v5.sql"
    ),
}


def _private_function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+"
        rf"content_factory_private\.{re.escape(name)}"
        rf"\s*\(\s*p_payload\s+jsonb\s+default\s+'\{{\}}'::jsonb\s*\)"
        rf"\s*returns\s+jsonb(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, name
    return match.group("header").casefold(), match.group("body").casefold()


def _pinned_body(name: str) -> str:
    start = SQL.index(
        f"create or replace function content_factory_private.{name}(\n"
    )
    begin = SQL.index("\nas $$\n", start) + len("\nas $$\n")
    end = SQL.index("\n$$;\n", begin)
    return SQL[begin:end]


def _canonical_body(source_name: str) -> str:
    text = (ROOT / "supabase/migrations" / source_name).read_text(
        encoding="utf-8"
    )
    marker = "create or replace function public.creator_bootstrap(\n"
    assert text.count(marker) == 1, source_name
    start = text.index(marker)
    begin = text.index("\nas $$\n", start) + len("\nas $$\n")
    end = text.index("\n$$;\n", begin)
    return text[begin:end]


def test_forward_migration_is_transactional_and_next_in_order() -> None:
    assert MIGRATION.exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")
    # CI and the deploy tracker hash migration bytes; keep the file LF-only.
    assert b"\r" not in MIGRATION.read_bytes()

    versions = sorted(
        path.name for path in (ROOT / "supabase/migrations").glob("*.sql")
    )
    previous = "202608160005_local_mock_product_photo_range_v1.sql"
    assert previous in versions
    assert versions.index(MIGRATION.name) == versions.index(previous) + 1


def test_repins_exactly_the_three_private_chain_functions() -> None:
    created = re.findall(
        r"create\s+or\s+replace\s+function\s+([a-z_]+\.[a-z0-9_]+)\s*\(",
        LOWER,
    )
    assert sorted(created) == sorted(
        f"content_factory_private.{name}" for name in CHAIN_FUNCTIONS
    )
    # The public wrapper (202608030005 waiver overlay) must stay untouched.
    assert "create or replace function public." not in LOWER
    assert "alter function" not in LOWER
    assert "drop function" not in LOWER


def test_password_gate_layer_wraps_the_auth_email_gate() -> None:
    header, body = _private_function("creator_bootstrap_pre_practical_gate")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "content_factory_private.creator_bootstrap_pre_auth_email_gate(" in body
    assert "content_factory_private.auth_password_change_required(auth.uid())" in body
    assert "'{state}', '\"password_change_required\"'::jsonb" in body
    assert "'{password_change_required}', 'true'::jsonb" in body


def test_practical_layer_projects_evidence_queue_and_exam_block() -> None:
    header, body = _private_function(
        "creator_bootstrap_pre_assessment_v5_sanitize"
    )
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "content_factory_private.creator_bootstrap_pre_practical_gate(" in body
    assert "content_factory_private.training_practical_gate_satisfied(" in body
    assert "'practical_project', practical_project" in body
    assert "'practical_reviews', practical_reviews" in body
    assert "'practical_upload'" in body
    assert "'bucket_id', 'contentengine-training'" in body
    assert "'max_upload_bytes', 52428800" in body
    assert "limit 50" in body
    assert "practical_project_approval_required" in body
    assert "'{learning,exam,available}', 'false'::jsonb" in body
    assert "'{workspace_open}', 'false'::jsonb" in body


def test_sanitizer_layer_calls_practical_and_strips_diagnostics() -> None:
    header, body = _private_function("creator_bootstrap_pre_training_waiver")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert (
        "content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize("
        in body
    )
    for diagnostic in (
        "- 'attempt_id'",
        "- 'correct_count'",
        "- 'critical_error_count'",
        "- 'score_percent'",
        "- 'review_topics'",
    ):
        assert body.count(diagnostic) == 2, diagnostic
    # The cloud regression body called the auth email gate directly and
    # severed the practical + sanitizer layers.  It must never come back.
    assert "creator_bootstrap_pre_auth_email_gate" not in body


def test_bodies_are_verbatim_copies_of_the_canonical_sources() -> None:
    for name, source_name in CANONICAL_SOURCES.items():
        assert _pinned_body(name) == _canonical_body(source_name), name


def test_every_replacement_is_followed_by_a_revoke() -> None:
    for name in CHAIN_FUNCTIONS:
        assert re.search(
            rf"revoke all on function\s+content_factory_private\.{name}\(jsonb\)"
            rf"\s+from public, anon, authenticated;",
            SQL,
        ), name


def test_verification_do_block_pins_the_chain_and_privileges() -> None:
    do_block = SQL.split("do $training_practical_bootstrap_chain$", 1)[1].split(
        "$training_practical_bootstrap_chain$;", 1
    )[0]
    assert LOWER.count("training_practical_bootstrap_chain_invalid") == 6

    for procedure in (
        "'public.creator_bootstrap(jsonb)'::regprocedure",
        "'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'\n"
        "      ::regprocedure",
        "'content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)'\n"
        "      ::regprocedure",
        "'content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)'\n"
        "      ::regprocedure",
        "'content_factory_private.creator_bootstrap_pre_auth_email_gate(jsonb)'\n"
        "      ::regprocedure",
    ):
        assert procedure in do_block, procedure

    assert "'creator_bootstrap_pre_training_waiver('" in do_block
    assert "'creator_bootstrap_pre_assessment_v5_sanitize('" in do_block
    assert "'creator_bootstrap_pre_practical_gate('" in do_block
    assert "'creator_bootstrap_pre_course_gate('" in do_block
    assert "'auth_password_change_required('" in do_block
    for diagnostic in (
        "'- ''attempt_id'''",
        "'- ''correct_count'''",
        "'- ''critical_error_count'''",
        "'- ''score_percent'''",
        "'- ''review_topics'''",
    ):
        assert diagnostic in do_block, diagnostic
    # The regression detector: the sanitizer slot must NOT call the auth
    # email gate directly.
    assert re.search(
        r"or strpos\(\s*waiver_definition,\s*"
        r"'creator_bootstrap_pre_auth_email_gate\('\s*\)\s*>\s*0",
        do_block,
    )
    assert do_block.count("has_function_privilege(") == 3
    assert do_block.count("'authenticated',") == 3


def test_pgtap_suite_covers_wiring_and_learner_flow() -> None:
    assert PGTAP_PATH.exists()
    for marker in (
        "creator_bootstrap_pre_training_waiver(",
        "creator_bootstrap_pre_assessment_v5_sanitize(",
        "creator_bootstrap_pre_practical_gate(",
        "creator_bootstrap_pre_auth_email_gate(",
        "creator_bootstrap_pre_course_gate(",
        "has_function_privilege",
        "- ''attempt_id''",
        "contentengine-training",
        "practical_project_required",
        "practical_project_approval_required",
        "course-check:",
        "creator_save_practical_project",
        "creator_decide_practical_project",
        "practical_reviews",
        "blocked_reason",
        "? 'attempt_id'",
        "? 'correct_count'",
    ):
        assert marker in PGTAP, marker
    assert PGTAP.rstrip().endswith("rollback;")
