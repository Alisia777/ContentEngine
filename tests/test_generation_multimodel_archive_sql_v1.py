"""Static contracts for the one multi-model archive projection."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130003_generation_multimodel_archive_v1.sql"
)
AUTHORITY = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130002_generation_multimodel_authority.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "generation_multimodel_archive_v1_test.sql"


def _read(path: Path = MIGRATION) -> str:
    assert path.is_file(), f"Missing contract file: {path}"
    return path.read_text(encoding="utf-8")


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _function(source: str, qualified_name: str) -> str:
    pattern = re.compile(
        r"create\s+or\s+replace\s+function\s+"
        + re.escape(qualified_name).replace(r"\.", r"\s*\.\s*")
        + r"\s*\(",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(source))
    assert matches, f"Missing SQL function {qualified_name}"
    match = matches[-1]
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    end = match.end() + terminator.end()
    return source[match.start() : end]


def test_migration_and_pgtap_exist_and_parse_after_frozen_authority() -> None:
    sql = _read()
    assert MIGRATION.name == "202608130003_generation_multimodel_archive_v1.sql"
    assert AUTHORITY.is_file()
    assert parse_sql(sql)
    assert PGTAP.is_file()
    assert parse_sql(_read(PGTAP))


def test_archive_remains_one_authenticated_project_scoped_rpc() -> None:
    sql = _read()
    archive = _normalized(_function(sql, "public.creator_generation_archive"))
    assert "language plpgsql volatile security definer set search_path = ''" in archive
    assert "content_factory_private.current_profile_id()" in archive
    assert "content_factory_private.resolve_organization(p_payload)" in archive
    assert "content_factory_private.membership_role(" in archive
    assert "'owner', 'admin', 'producer', 'reviewer', 'operator'" in archive
    assert "content_factory_private.require_workspace_project(" in archive
    assert "batch.organization_id = organization_id" in archive
    assert "batch.project_id = project_id_value" in archive
    assert "(team_scope or batch.created_by = user_id)" in archive
    assert "batch.archived_at is null" in archive
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_generation_archive\s*\(\s*jsonb\s*\)\s+"
        r"from\s+public\s*,\s*anon",
        sql,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_generation_archive\s*\(\s*jsonb\s*\)\s+"
        r"to\s+authenticated",
        sql,
        flags=re.IGNORECASE,
    )


def test_archive_filters_only_the_exact_immutable_snapshot_before_paging() -> None:
    archive = _normalized(_function(_read(), "public.creator_generation_archive"))
    for key in (
        "provider",
        "model",
        "content_kind",
        "selection_source",
        "quality_status",
    ):
        assert f"'{key}'" in archive
        assert f"generation_archive_{key}_invalid" in archive
    assert (
        "left join content_factory.generation_job_selection_snapshots launch "
        "on launch.organization_id = batch.organization_id "
        "and launch.project_id = batch.project_id "
        "and launch.batch_id = batch.id"
    ) in archive
    assert "provider_value = 'all' or launch.provider = provider_value" in archive
    assert "model_value = 'all' or lower(launch.model) = model_value" in archive
    assert "content_kind_value = 'all' or launch.content_kind = content_kind_value" in archive
    assert (
        "selection_source_value = 'all' or launch.selection_source = selection_source_value"
        in archive
    )
    assert "quality_status_value = 'all' or launch.quality_status = quality_status_value" in archive
    assert archive.index("launch.quality_status = quality_status_value") < archive.index(
        "limit page_size + 1"
    )
    assert "generation_catalog_entry" not in archive
    assert "real_generation_sku" not in archive


def test_archive_preserves_period_status_query_keyset_and_searches_snapshot_identity() -> None:
    archive = _normalized(_function(_read(), "public.creator_generation_archive"))
    for token in (
        "period_value text := '4w'",
        "period_value not in ('week', '4w', '12w', 'all')",
        "status_value not in ('all', 'active', 'ready', 'issue')",
        "length(query_value) > 120",
        "query_value ~ '[[:cntrl:]]'",
        "page_size not between 1 and 100",
        "(batch.created_at, batch.id) < (cursor_at, cursor_id)",
        "order by batch.created_at desc, batch.id desc",
        "limit page_size + 1",
        "count(*) > page_size as has_more",
        "'cursor_mode', 'keyset_created_at_id'",
        "'provider', provider_value",
        "'model', model_value",
        "'content_kind', content_kind_value",
        "'selection_source', selection_source_value",
        "'quality_status', quality_status_value",
        "launch.model",
        "launch.selection_snapshot ->> 'model_public_label'",
    ):
        assert token in archive
    assert "batch.input ->> 'model'" not in archive
    assert "batch.provider" not in archive


def test_archive_projects_exact_snapshot_or_json_null_without_mutation() -> None:
    archive = _normalized(_function(_read(), "public.creator_generation_archive"))
    for token in (
        "'generation_selection_snapshot', page.generation_selection_snapshot",
        "'generation_selection_snapshot_version', page.generation_selection_snapshot_version",
        "'generation_selection_snapshot_hash', page.generation_selection_snapshot_hash",
        "'provider', page.provider",
        "'model', page.model",
        "'model_public_label', page.model_public_label",
        "'content_kind', page.content_kind",
        "'selection_source', page.selection_source",
        "'quality_status', page.quality_status",
        "'catalog_version', page.catalog_version",
        "'pricing_version', page.pricing_version",
        "'estimated_cost_minor', page.estimated_cost_minor",
    ):
        assert token in archive
    assert "coalesce(launch." not in archive
    assert "coalesce(page.provider" not in archive
    for command in (" insert ", " update ", " delete ", " merge ", " truncate "):
        assert command not in f" {archive} "


def test_archive_slice_does_not_compete_with_acceptance_or_paid_authority() -> None:
    sql = _normalized(_read())
    assert "creator_generation_model_acceptance" not in sql
    assert "creator_start_real_generation" not in sql
    assert "generation_provider_launch_enabled" not in sql
    assert "provider_readiness_receipt" not in sql
