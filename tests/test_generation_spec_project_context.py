"""Static contracts for project-scoped generation-spec consumption."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040008_generation_spec_project_context.sql"
)


def _read() -> str:
    assert MIGRATION.is_file(), f"Missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(qualified_name)}\s*\(",
        source,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"Missing SQL function {qualified_name}"
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    end = match.end() + terminator.end()
    return source[match.start() : end]


def test_forward_migration_parses() -> None:
    assert parse_sql(_read())


def test_effective_policy_contract_is_explicitly_project_first() -> None:
    sql = _read()
    wrapper = _function(sql, "public.creator_generation_spec_effective_policy")
    lowered = wrapper.casefold()

    assert "not (p_payload ? 'project_id')" in lowered
    assert "message = 'project_id_required'" in lowered
    assert "'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'" in lowered
    assert "p_payload - 'project_id'" in lowered
    assert "creator_generation_spec_effective_policy_pre_project_v48" in lowered
    assert "require_generation_spec_project_v48" in lowered
    assert "membership_role" in lowered
    assert "project_payload_from_context_v47" not in lowered
    assert "jsonb_build_object('project_id', project_id_value)" in lowered

    preserve = sql[sql.index("do $preserve_generation_spec_effective_policy_v48$") :]
    preserve = preserve[: preserve.index("$preserve_generation_spec_effective_policy_v48$;")]
    rename = "rename to creator_generation_spec_effective_policy_pre_project_v48"
    transfer = "set schema content_factory_private"
    assert rename in preserve
    assert transfer in preserve
    assert preserve.index(rename) < preserve.index(transfer)


def test_spec_scope_guard_binds_exact_product_and_every_media_to_project() -> None:
    guard = _function(
        _read(),
        "content_factory_private.require_generation_spec_project_v48",
    ).casefold()

    for exact_key in (
        "version.organization_id = p_organization_id",
        "version.spec_id = p_spec_id",
        "version.spec_version = p_spec_version",
        "version.spec_hash = p_spec_hash",
    ):
        assert exact_key in guard
    assert "spec_row.product_id <> p_expected_product_id" in guard
    assert "product.status = 'active'" in guard
    assert "from unnest(spec_row.media_ids)" in guard
    assert "media.product_id = spec_row.product_id" in guard
    assert "media.project_id = p_project_id" in guard
    assert "scoped_media_count <> cardinality(spec_row.media_ids)" in guard
    assert guard.count("generation_spec_project_scope_mismatch") == 3


def test_effective_policy_restores_exact_guc_on_success_and_failure() -> None:
    wrapper = _function(
        _read(),
        "public.creator_generation_spec_effective_policy",
    ).casefold()

    assert "previous_project_setting := current_setting(" in wrapper
    assert "'contentengine.project_id'" in wrapper
    assert "project_id_value::text" in wrapper
    assert "exception when others then" in wrapper
    assert wrapper.count("coalesce(previous_project_setting, '')") == 2
    assert wrapper.index("require_generation_spec_project_v48") < wrapper.index(
        "set_config("
    )


def test_live_claim_derives_context_only_from_exact_job_and_rejects_conflicts() -> None:
    claim = _function(
        _read(),
        "content_factory_private.generation_spec_live_claim_snapshot",
    ).casefold()

    for exact_key in (
        "job.organization_id = organization_id_value",
        "job.id = generation_job_id_value",
        "job.generation_spec_id = spec_id_value",
        "job.generation_spec_version = spec_version_value",
        "job.generation_spec_hash = spec_hash_value",
    ):
        assert exact_key in claim
    assert "project_id_value := job_row.project_id" in claim
    assert "batch.project_id = project_id_value" in claim
    assert "batch.product_id = job_row.product_id" in claim
    assert "require_generation_spec_project_v48" in claim
    assert "job_row.product_id" in claim
    assert "previous_project_id <> project_id_value" in claim
    assert "message = 'project_context_invalid'" in claim
    assert "generation_spec_live_claim_snapshot_pre_project_v48" in claim
    assert "project_payload_from_context_v47" not in claim
    assert claim.count("coalesce(previous_project_setting, '')") == 2
    assert "return result_value;" in claim
    assert "result_value || jsonb_build_object('project_id'" not in claim

    # The preserved engine already signs the complete snapshot.  The project
    # guard must not append an unsigned field after snapshot_hash is computed.
    alias_call = claim.index(
        "generation_spec_live_claim_snapshot_pre_project_v48"
    )
    first_context_set = claim.index("project_id_value::text")
    assert first_context_set < alias_call


def test_private_surfaces_remain_ungrantable() -> None:
    sql = _read().casefold()

    assert "revoke all on function\n  content_factory_private.require_generation_spec_project_v48" in sql
    assert "revoke all on function\n  content_factory_private.generation_spec_live_claim_snapshot(" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "grant execute on function public.creator_generation_spec_effective_policy(jsonb)\n  to authenticated" in sql
    assert "grant execute on function content_factory_private" not in sql
