"""Static contracts for complete project boundaries around generation specs."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040014_generation_spec_project_boundaries.sql"
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


def test_forward_migration_parses_and_is_ordered_after_rule_binding() -> None:
    assert MIGRATION.name > "202608040013_research_category_generation_rule_binding.sql"
    assert parse_sql(_read())


def test_v49_guard_extends_media_scope_with_all_immutable_provenance() -> None:
    sql = _read()
    guard = _function(
        sql, "content_factory_private.require_generation_spec_project_v49"
    ).casefold()
    provenance = _function(
        sql,
        "content_factory_private.require_generation_project_provenance_v49",
    ).casefold()

    assert "require_generation_spec_project_v48" in guard
    assert "spec_row.research_provenance" in guard
    assert "spec_row.repair_provenance" in guard
    assert "spec_row.performance_policy_provenance" in guard
    assert "spec_row.final_policy" in guard

    for project_anchor in (
        "run.project_id = p_project_id",
        "draft.project_id = p_project_id",
        "job.project_id = p_project_id",
        "review.project_id = p_project_id",
    ):
        assert project_anchor in provenance
    assert "run.product_id = p_product_id" in provenance
    assert "draft.product_id = run.product_id" in provenance
    assert "market-category identity is intentionally organization/product scoped" in provenance
    assert "category rule compiler and receipt" in provenance
    assert "source_run.project_id = p_project_id" not in provenance
    assert "source_draft.project_id = p_project_id" not in provenance
    assert "job.product_id = p_product_id" in provenance
    assert "review.media_object_id::text = job.output ->> 'output_media_id'" in provenance
    assert "{learning_policy,source_job_ids}" in provenance
    assert "{learning_policy,quality_guard_source_job_ids}" in provenance
    assert "{learning_policy,project_id}" in provenance
    assert "bounded_exploration_required" in provenance
    assert "product_platform_model" in provenance
    assert "exploration_angles_are_server_bounded" in provenance
    assert "'[\"first_person\"]'::jsonb" in provenance
    assert "'[\"before_buying\"]'::jsonb" in provenance
    assert "hard_rejected_structure_replaced" in provenance
    assert "safe_recovery_structures_are_server_bounded" in provenance
    assert "jsonb_array_length(source_job_ids_value) = 0" in provenance
    assert "and not bounded_exploration_value" in provenance
    assert "{learning_policy,project_id}' is not null" in provenance
    assert "generation_creative_signals" in provenance
    assert "job.project_id is distinct from p_project_id" in provenance
    assert provenance.count("generation_spec_project_scope_mismatch") >= 7


def test_prepare_requires_project_and_preflights_every_media_and_product() -> None:
    sql = _read()
    wrapper = _function(sql, "public.creator_prepare_generation_spec").casefold()
    request_guard = _function(
        sql,
        "content_factory_private.require_generation_request_project_v49",
    ).casefold()

    assert "not (p_payload ? 'project_id')" in wrapper
    assert "message = 'project_id_required'" in wrapper
    assert "'organization_id', 'project_id', 'idempotency_key'" in wrapper
    assert "membership_role" in wrapper
    assert "require_workspace_project" in wrapper
    assert "require_generation_request_project_v49" in wrapper
    assert "creator_prepare_generation_spec_pre_project_v49" in wrapper
    assert "p_payload - 'project_id'" in wrapper
    assert wrapper.count("require_generation_spec_project_v49") == 1
    assert "return result_value;" in wrapper
    assert "result_value ||" not in wrapper

    assert "from unnest(media_ids_value)" in request_guard
    assert "media.product_id = product_id_value" in request_guard
    assert "media.project_id = p_project_id" in request_guard
    assert "product.status = 'active'" in request_guard
    assert "scoped_media_count <> cardinality(media_ids_value)" in request_guard
    assert "require_generation_project_provenance_v49" in request_guard


def test_status_and_control_are_strict_project_first_rpc_boundaries() -> None:
    sql = _read()
    status = _function(sql, "public.creator_generation_spec_status").casefold()
    control = _function(sql, "public.creator_control_generation_spec").casefold()

    for wrapper, alias in (
        (status, "creator_generation_spec_status_pre_project_v49"),
        (control, "creator_control_generation_spec_pre_project_v49"),
    ):
        assert "not (p_payload ? 'project_id')" in wrapper
        assert "message = 'project_id_required'" in wrapper
        assert "membership_role" in wrapper
        assert "require_workspace_project" in wrapper
        assert "require_generation_spec_project_v49" in wrapper
        assert alias in wrapper
        assert "p_payload - 'project_id'" in wrapper
        assert "return result_value;" in wrapper
        assert "result_value ||" not in wrapper

    # Every patch/revert/recompute result is checked inside the same transaction;
    # raising here rolls the preserved mutation and idempotency receipt back.
    assert control.count("require_generation_spec_project_v49") == 2
    assert "result_value #>> '{generation_spec,spec_version}'" in control
    assert "result_value #>> '{generation_spec,spec_hash}'" in control


def test_every_public_wrapper_restores_exact_project_guc_on_both_paths() -> None:
    sql = _read()
    for name in (
        "public.creator_prepare_generation_spec",
        "public.creator_generation_spec_status",
        "public.creator_control_generation_spec",
        "public.creator_generation_spec_effective_policy",
    ):
        wrapper = _function(sql, name).casefold()
        assert "previous_project_setting := current_setting(" in wrapper
        assert "'contentengine.project_id'" in wrapper
        assert "previous_project_id <> project_id_value" in wrapper
        assert "exception when others then" in wrapper
        assert wrapper.count("coalesce(previous_project_setting, '')") == 2
        assert wrapper.index("require_generation_spec_project_v49") < wrapper.index(
            "project_id_value::text"
        ) or name == "public.creator_prepare_generation_spec"


def test_effective_policy_and_service_claim_use_complete_v49_guard() -> None:
    sql = _read()
    effective = _function(
        sql, "public.creator_generation_spec_effective_policy"
    ).casefold()
    claim = _function(
        sql,
        "content_factory_private.generation_spec_live_claim_snapshot",
    ).casefold()

    assert "require_generation_spec_project_v49" in effective
    assert "generation_spec_research_category_rule_current" in effective
    assert "generation_spec_research_category_rule_stale" in effective
    assert "creator_generation_spec_effective_policy_pre_project_v48" in effective
    assert "p_payload - 'project_id'" in effective
    assert "result_value || jsonb_build_object('project_id', project_id_value)" in effective

    prepare = _function(sql, "public.creator_prepare_generation_spec").casefold()
    control = _function(sql, "public.creator_control_generation_spec").casefold()
    assert "generation_spec_research_category_rule_current" in prepare
    assert "p_payload ->> 'action' = 'approve'" in control
    assert "p_payload ->> 'action' <> 'reject'" in control
    assert control.count("generation_spec_research_category_rule_current") == 2

    for exact_job_key in (
        "job.organization_id = organization_id_value",
        "job.id = generation_job_id_value",
        "job.generation_spec_id = spec_id_value",
        "job.generation_spec_version = spec_version_value",
        "job.generation_spec_hash = spec_hash_value",
    ):
        assert exact_job_key in claim
    assert "batch.project_id = project_id_value" in claim
    assert "batch.product_id = job_row.product_id" in claim
    assert "require_generation_spec_project_v49" in claim
    assert "job_row.product_id" in claim
    assert "message = 'generation_spec_provider_start_stale'" in claim
    assert "detail = 'generation_spec_project_scope_mismatch'" in claim
    assert "exception when sqlstate '42501'" in claim
    assert "when sqlstate 'p0002'" in claim
    assert "sqlerrm <> 'workspace_project_not_found'" in claim
    assert "detail = 'workspace_project_not_found'" in claim
    guc_at = claim.index("previous_project_setting := current_setting(")
    ambient_guard = claim[guc_at:claim.index("perform set_config(", guc_at)]
    assert "errcode = '42501'" in ambient_guard
    assert "message = 'generation_spec_project_scope_mismatch'" in ambient_guard
    assert "generation_spec_provider_start_stale" not in ambient_guard
    assert "generation_spec_live_claim_snapshot_pre_project_v48" in claim
    assert "return result_value;" in claim
    assert "result_value ||" not in claim


def test_private_aliases_and_guards_are_never_granted() -> None:
    sql = _read().casefold()
    for alias in (
        "creator_prepare_generation_spec_pre_project_v49",
        "creator_generation_spec_status_pre_project_v49",
        "creator_control_generation_spec_pre_project_v49",
    ):
        assert f"content_factory_private.{alias}" in sql
        assert re.search(
            rf"revoke all on function\s+content_factory_private\.{alias}\(\s*jsonb\s*\)\s+from public, anon, authenticated, service_role",
            sql,
        )
    for helper in (
        "require_generation_project_provenance_v49",
        "require_generation_request_project_v49",
        "require_generation_spec_project_v49",
        "generation_spec_live_claim_snapshot",
    ):
        assert f"revoke all on function\n  content_factory_private.{helper}" in sql
    assert "grant execute on function content_factory_private" not in sql
    for public_name in (
        "creator_prepare_generation_spec",
        "creator_generation_spec_status",
        "creator_control_generation_spec",
        "creator_generation_spec_effective_policy",
    ):
        assert (
            f"grant execute on function public.{public_name}(jsonb)\n"
            "  to authenticated"
        ) in sql


def test_required_deterministic_project_errors_are_installed() -> None:
    sql = _read().casefold()
    assert sql.count("message = 'project_id_required'") == 4
    assert sql.count("generation_spec_project_scope_mismatch") >= 16
    assert "require_workspace_project" in sql
    # require_workspace_project is the single canonical producer of this code.
    assert "message = 'workspace_project_not_found'" not in sql
    assert "sqlerrm <> 'workspace_project_not_found'" in sql
