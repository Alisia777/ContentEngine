from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608050002_generation_advisory_launch_and_archive.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_paid_generation_keeps_invariants_but_drops_separate_approval_gate() -> None:
    assert "assert_generation_spec_current_pre_advisory_v1" in LOWER
    assert ".assert_generation_spec_current_pre_advisory_v1(" in LOWER
    assert "false,\n      dynamic_revalidation" in LOWER
    assert "ensurePreparedGenerationSpecForPaidStart" in APP
    assert "ensureApprovedGenerationSpecForPaidStart" not in APP
    assert 'runGenerationSpecControl(form, "approve")' not in APP
    assert "refreshGenerationSpec(form, { force: true })" in APP
    assert "generationSpecScopesMatch" in APP
    assert "preparedSpec.compiled_prompt" in APP


def test_generation_learning_is_advice_not_a_launch_gate() -> None:
    prepare = APP[
        APP.index("function generationSpecPreparePayload(form)"):
        APP.index("function generationSpecPayloadKey(")
    ]
    submit = APP[
        APP.index("async function submitRealGeneration(form, values, mode)"):
        APP.index("async function submitMockBatch(")
    ]
    assert "state.generationLearning.status" not in prepare
    assert "checkedLearningPolicy" not in prepare
    assert "await ensureGenerationLearningPolicy(" not in submit
    assert "generationLearningContext(form)" in submit
    assert "generation_learning_opt_out" not in submit


def test_archive_repair_is_recoverable_project_scoped_and_visible_in_ui() -> None:
    for token in (
        "add column if not exists archived_at timestamptz",
        "add column if not exists archived_by uuid",
        "creator_archive_generation_batch",
        "batch.project_id = project_id_value",
        "batch.archived_at is null",
        "generation_batch_archive_active",
        "source_media_preserved",
        "output_media_preserved",
        "alter function public.creator_generation_archive(jsonb) volatile",
        "notify pgrst, 'reload schema'",
    ):
        assert token in LOWER
    assert 'archiveGenerationBatch: "creator_archive_generation_batch"' in API
    assert "archiveGenerationBatch(batchId, options = {})" in API
    assert 'data-action="archive-generation-batch"' in APP
    assert "Подтвердить удаление dry-run" in APP
    assert "Исходники и готовые файлы сохранены" in APP


def test_archive_migration_is_transactional() -> None:
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")
