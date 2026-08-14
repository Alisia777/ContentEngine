from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130006_generation_strategy_authority_v1.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "generation_strategy_authority_v1_test.sql"
ARCHIVE_BASE = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130003_generation_multimodel_archive_v1.sql"
)
CATALOG = (
    ROOT
    / "supabase"
    / "functions"
    / "_shared"
    / "generation-strategy-catalog.js"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def test_generation_strategy_sql_and_pgtap_parse() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert len(parse_sql(migration)) >= 75
    assert len(parse_sql(pgtap)) >= 25
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")


def test_three_business_ids_have_one_exact_runway_recipe_each() -> None:
    sql = _read(MIGRATION)

    assert "when 'viral_avatar_ugc' then 'product_ugc'" in sql
    assert "when 'viral_product_swap' then 'product_swap'" in sql
    assert "when 'viral_rebuild' then 'product_ad'" in sql
    assert "provider_path', '/v1/recipes/' || recipe_value" in sql
    assert "provider', 'runway'" in sql


def test_sql_version_tuple_matches_the_frozen_shared_catalog() -> None:
    sql = _read(MIGRATION)
    catalog = _read(CATALOG)

    assert 'GENERATION_STRATEGY_CATALOG_VERSION = "2026-08-14.v1"' in catalog
    assert 'RUNWAY_RECIPE_VERSION = "2026-06"' in catalog
    assert (
        'RUNWAY_RECIPE_PRICING_VERSION =\n'
        '  "runway-recipe-credits-2026-08-14.v1"'
    ) in catalog
    assert "'catalog_version', '2026-08-14.v1'" in sql
    assert "'recipe_version', '2026-06'" in sql
    assert "'pricing_version', 'runway-recipe-credits-2026-08-14.v1'" in sql
    assert "runway-recipes-2026-08-14" not in sql
    assert "generation-strategy-catalog-2026-08-14" not in sql


def test_role_ledger_covers_official_caps_without_weakening_spec_identity() -> None:
    sql = _read(MIGRATION)
    validator = _section(
        sql,
        "generation_strategy_binding_current(",
        "content_factory_private.enforce_generation_strategy_binding_current()",
    )
    binder = _section(
        sql,
        "create or replace function public.system_bind_generation_spec_strategy(",
        "create or replace function\n  content_factory_private.snapshot_generation_job_strategy()",
    )

    for role in (
        "product_primary",
        "product_reference",
        "creator_avatar",
        "original_product",
        "source_video",
        "style_reference",
    ):
        assert role in sql
    assert "jsonb_array_length(p_value) between 1 and 16" in sql
    assert "product_reference' and ordinal between 1 and 9" in sql
    assert "style_reference' and ordinal between 1 and 4" in sql
    assert (
        "primary_count + product_reference_count not between\n"
        "          cardinality(spec_row.media_ids) and 10"
    ) in validator
    assert "style_reference_count not between 0 and 4" in validator
    assert "media_row.product_id is distinct from spec_row.product_id" in binder
    assert "media_row.id <> all(spec_row.media_ids)" not in binder
    assert "and asset.media_object_id = any(spec_row.media_ids)" in validator
    assert "spec_product_asset_count <> cardinality(spec_row.media_ids)" in validator
    assert "primary_asset.media_object_id = spec_row.primary_media_id" in validator


def test_all_shared_attestations_are_immutable_and_fail_closed() -> None:
    sql = _read(MIGRATION)
    binder = _section(
        sql,
        "create or replace function public.system_bind_generation_spec_strategy(",
        "create or replace function\n  content_factory_private.snapshot_generation_job_strategy()",
    )

    for attestation in (
        "source_media_rights_confirmed",
        "transformative_use_confirmed",
        "product_assets_rights_confirmed",
        "depicted_people_consent_confirmed",
        "avatar_likeness_consent_confirmed",
    ):
        assert attestation in binder
        assert attestation in sql
    assert "is distinct from 'true'::jsonb" in binder
    assert "((strategy_id_value = 'viral_avatar_ugc') <>" in binder
    assert "(strategy_id = 'viral_avatar_ugc') = likeness_consent_confirmed" in sql


def test_low_level_binder_is_service_only_and_never_starts_a_provider() -> None:
    sql = _read(MIGRATION)
    binder = _section(
        sql,
        "create or replace function public.system_bind_generation_spec_strategy(",
        "create or replace function\n  content_factory_private.snapshot_generation_job_strategy()",
    )

    assert "grant execute on function public.system_bind_generation_spec_strategy(jsonb)\n  to service_role" in sql
    assert "from public, anon, authenticated, service_role" in sql
    assert "'provider_call_started', false" in binder
    assert "'paid_start_integrated', false" in binder
    assert "'edge_must_call_binder', true" in binder
    assert "fetch(" not in binder.lower()
    assert "http" not in binder.lower()
    assert "signed_url" not in binder.lower()
    assert "object_name" not in binder.lower()


def test_browser_safe_wrapper_resolves_all_database_authority_server_side() -> None:
    sql = _read(MIGRATION)
    wrapper = _section(
        sql,
        "create or replace function public.system_resolve_and_bind_generation_strategy(",
        "create or replace function public.system_generation_strategy_provider_policy(",
    )

    assert "'generation-strategy-resolve-bind-request-v1'" in wrapper
    assert "'selection'" in wrapper
    assert "research_exact_youtube_media_attachments" in wrapper
    assert "attachment.media_object_id = source_media_id_value" in wrapper
    assert "media.sha256 = attachment.media_sha256_snapshot" in wrapper
    assert "spec_row.media_ids <@ target_media_ids" in wrapper
    assert "spec_row.primary_media_id = any(target_media_ids)" in wrapper
    assert "target_count not between 1 and 10" in wrapper
    assert "style_count not between 0 and 4" in wrapper
    assert "public.system_bind_generation_spec_strategy(" in wrapper
    assert "'source_binding_id', source_attachment_row.id" in wrapper
    assert "'source_binding_hash', source_attachment_row.attachment_hash" in wrapper
    assert "'media_object_id', media_row.id, 'sha256', media_row.sha256" in wrapper
    assert "'browser_hashes_accepted', false" in wrapper
    assert "'browser_source_binding_accepted', false" in wrapper
    assert "to service_role" in wrapper


def test_price_formulas_and_confirmation_are_server_owned() -> None:
    sql = _read(MIGRATION)
    price = _section(
        sql,
        "generation_strategy_recipe_price(",
        "create or replace function public.system_generation_strategy_provider_policy(",
    )

    for base in ("then 192 else 208", "then 212 else 228", "then 200 else 216"):
        assert base in price
    assert "when '720p' then 36 else 40" in price
    assert "p_duration_seconds not between 4 and 15" in price
    assert "'estimated_pre_tax_usd_minor', credits_value" in price
    assert "'estimated_cost_minor', credits_value" in price
    assert "'credit_unit_cost_minor', 1" in price
    assert "'spend_confirmation', concat(" in price
    assert "'server_authoritative', true" in price
    assert "to service_role" in price


def test_policy_returns_the_shared_exact_capability_shape_but_is_not_enabled() -> None:
    sql = _read(MIGRATION)
    policy = _section(
        sql,
        "create or replace function public.system_generation_strategy_provider_policy(",
        "create or replace function public.creator_generation_strategy_repeat_data(",
    )

    for key in (
        "enabled",
        "catalog_version",
        "strategy_id",
        "provider",
        "recipe",
        "recipe_version",
        "provider_path",
        "pricing_version",
    ):
        assert f"'{key}'" in policy
    assert "'execution_capabilities'" in policy
    assert "'enabled', false" in policy
    assert "'launch_enabled', false" in policy
    assert "generation_strategy_start_path_not_integrated" in policy
    assert "receipt.expires_at > statement_timestamp()" in policy
    assert "provider_call_started', false" in policy


def test_job_snapshot_and_status_projection_are_append_only() -> None:
    sql = _read(MIGRATION)

    for table in (
        "generation_spec_strategy_bindings",
        "generation_spec_strategy_assets",
        "generation_job_strategy_snapshots",
        "generation_strategy_status_events",
    ):
        assert f"create table content_factory.{table}" in sql
    assert "generation_strategy_ledger_append_only" in sql
    assert "generation_job_strategy_snapshot_capture" in sql
    assert "generation_job_strategy_status_capture" in sql
    assert "create view content_factory.generation_strategy_status_projection" in sql
    assert "order by\n  event.organization_id, event.generation_job_id,\n  event.transition_ordinal desc" in sql
    assert "new.requested_by is distinct from binding_row.confirmed_by" in sql
    assert "generation_strategy_binding_current(" in sql


def test_archive_override_preserves_existing_filters_acl_and_keyset() -> None:
    sql = _read(MIGRATION)
    base = _read(ARCHIVE_BASE)
    archive = _section(
        sql,
        "create or replace function public.creator_generation_archive(",
        "comment on table content_factory.generation_spec_strategy_bindings",
    )

    preserved_markers = (
        "array['owner', 'admin', 'producer', 'reviewer', 'operator']",
        "team_scope or batch.created_by = user_id",
        "batch.archived_at is null",
        "period_cutoff is null or batch.created_at >= period_cutoff",
        "provider_value = 'all' or launch.provider = provider_value",
        "model_value = 'all' or lower(launch.model) = model_value",
        "selection_source_value = 'all'",
        "quality_status_value = 'all'",
        "(batch.created_at, batch.id) < (cursor_at, cursor_id)",
        "order by batch.created_at desc, batch.id desc",
        "limit page_size + 1",
        "'cursor_mode', 'keyset_created_at_id'",
    )
    for marker in preserved_markers:
        assert marker in base
        assert marker in archive
    assert "strategy_id_value = 'all'" in archive
    assert "strategy_snapshot.strategy_id = strategy_id_value" in archive
    assert "left join content_factory.generation_job_strategy_snapshots" in archive
    assert "when page.strategy_id is null then null" in archive
    assert "'strategy_repeat_data'" in archive


def test_repeat_is_read_only_and_legacy_null_is_explicit() -> None:
    sql = _read(MIGRATION)
    repeat = _section(
        sql,
        "create or replace function public.creator_generation_strategy_repeat_data(",
        "create or replace function public.creator_generation_archive(",
    )

    assert "language plpgsql\nstable\nsecurity definer" in repeat
    assert "'legacy_strategy_absent', true" in repeat
    assert "'repeat_data', null" in repeat
    assert "'requires_fresh_binding', true" in repeat
    assert "'requires_fresh_human_confirmation', true" in repeat
    assert "'requires_fresh_provider_readiness_receipt', true" in repeat
    assert "'requires_fresh_price_confirmation', true" in repeat
    assert "'provider_call_started', false" in repeat
    assert "'mutation_started', false" in repeat
    assert "insert into" not in repeat.lower()
    assert "update content_factory" not in repeat.lower()
    assert "delete from" not in repeat.lower()


def test_strategy_ledgers_cannot_store_urls_or_object_paths() -> None:
    sql = _read(MIGRATION)
    snapshot_contracts = _section(
        sql,
        "generation_strategy_asset_snapshot_valid(",
        "create table content_factory.generation_spec_strategy_bindings",
    )
    binder = _section(
        sql,
        "create or replace function public.system_bind_generation_spec_strategy(",
        "create or replace function\n  content_factory_private.snapshot_generation_job_strategy()",
    )

    for forbidden_key in ("'signed_url'", "'url'", "'object_name'", "'path'"):
        assert forbidden_key not in snapshot_contracts
        assert forbidden_key not in binder
    assert "asset.value - array[" in snapshot_contracts
    assert "source_snapshot_valid" in snapshot_contracts


def test_existing_selection_snapshot_v1_is_not_rewritten() -> None:
    sql = _read(MIGRATION).lower()

    assert "alter table content_factory.generation_job_selection_snapshots" not in sql
    assert "drop table content_factory.generation_job_selection_snapshots" not in sql
    assert "update content_factory.generation_job_selection_snapshots" not in sql
    assert "delete from content_factory.generation_job_selection_snapshots" not in sql
