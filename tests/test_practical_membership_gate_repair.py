from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240001_repair_practical_membership_gate.sql"
)
FIXTURE = ROOT / "supabase/test-fixtures/training_assessment_v5_keys.sql"
CI = ROOT / ".github/workflows/ci.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_membership_gate_repair_uses_rename_safe_positional_locals() -> None:
    sql = _text(MIGRATION).casefold()
    function_bodies = sql[
        sql.index("create or replace function") :
        sql.index("do $membership_gate_repair_contract$")
    ]

    assert function_bodies.count("target_organization_id uuid := $1") == 2
    assert function_bodies.count("certification_required boolean := $2") == 2
    assert function_bodies.count("role_allowlist text[] := $3") == 2
    assert "membership_role.organization_id" not in function_bodies
    assert "membership_role_pre_practical_gate(" in sql
    assert "training_practical_gate_satisfied(" in sql
    assert "pg_get_functiondef(" in sql
    assert "private_membership_gate_is_browser_callable" in sql


def test_course_grading_fixture_is_explicitly_test_only_and_not_a_migration() -> None:
    fixture = _text(FIXTURE)

    assert "TEST-ONLY synthetic" in fixture
    assert "training_answer_keys" in fixture
    assert "question.options -> 0 ->> 'value'" in fixture
    assert "on conflict (question_code) do update" in fixture.casefold()
    assert "test_course_gate_fixture_invalid" in fixture
    assert FIXTURE.parent.name == "test-fixtures"
    assert FIXTURE.parent != MIGRATION.parent


def test_ci_loads_synthetic_keys_only_after_migration_lint() -> None:
    source = _text(CI)
    workflow = yaml.safe_load(source)
    steps = workflow["jobs"]["supabase-migrations"]["steps"]
    names = [step["name"] for step in steps]

    lint_index = names.index("Lint migrated database")
    fixture_index = names.index("Install test-only training grading fixture")
    tests_index = names.index("Run database security and workflow contract tests")

    assert lint_index < fixture_index < tests_index
    assert "supabase/test-fixtures/training_assessment_v5_keys.sql" in source
    assert "sed -n 's/^DB_URL=\"\\(.*\\)\"$/\\1/p'" in source
    assert "psql \"$DB_URL\"" in source


def test_python_ci_enforces_the_minimal_runtime_lint_gate() -> None:
    source = _text(CI)
    requirements = _text(ROOT / "requirements-dev.txt")
    ruff_config = _text(ROOT / "pyproject.toml")

    assert "python -m pip install -r requirements-dev.txt" in source
    assert "python -m ruff check app scripts" in source
    assert "ruff==0.16.0" in requirements
    assert 'select = ["E9", "F"]' in ruff_config
