from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase" / "migrations" / "202607170002_generation_spend_budgets.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
).read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "GENERATION_SPEND_CONTROLS.md").read_text(encoding="utf-8")


def test_spend_schema_is_private_append_only_and_rpc_scoped() -> None:
    for marker in (
        "content_factory_private.generation_spend_platform_control",
        "content_factory.generation_spend_policies",
        "content_factory.generation_spend_ledger",
        "guard_generation_spend_ledger_append_only",
        "alter table content_factory.generation_spend_policies enable row level security",
        "alter table content_factory.generation_spend_ledger enable row level security",
        "revoke all on content_factory.generation_spend_policies",
        "revoke all on content_factory.generation_spend_ledger",
        "creator_generation_spend_overview",
        "creator_update_generation_spend_policy",
        "system_update_generation_spend_control",
    ):
        assert marker in MIGRATION

    assert (
        "grant execute on function public.creator_generation_spend_overview(jsonb)\n"
        "  to authenticated"
    ) in MIGRATION
    assert (
        "grant execute on function public.creator_update_generation_spend_policy(jsonb)\n"
        "  to authenticated"
    ) in MIGRATION
    assert (
        "revoke all on function public.system_update_generation_spend_control(jsonb)\n"
        "  from public, anon, authenticated"
    ) in MIGRATION


def test_money_is_reserved_and_rechecked_before_the_runway_post() -> None:
    for marker in (
        "create trigger generation_spend_reservation",
        "after insert on content_factory.generation_jobs",
        "create trigger c_generation_spend_start_guard",
        "before update of",
        "old.status <> 'queued'",
        "new.status <> 'starting'",
        "pg_advisory_xact_lock",
        "daily_limit_minor",
        "monthly_limit_minor",
        "per_request_limit_minor",
    ):
        assert marker in MIGRATION

    claim = EDGE.index("const claim = await claimSystemJob(current.id)")
    post = EDGE.index('`${RUNWAY_API_ORIGIN}/v1/image_to_video`', claim)
    between = EDGE[claim:post]
    assert 'claim.outcome !== "claimed"' in between
    assert "if (!claim.claimed)" in between


def test_only_reviewed_budget_codes_cross_the_edge_boundary() -> None:
    codes = {
        "paid_generation_paused",
        "paid_generation_policy_missing",
        "generation_daily_budget_exceeded",
        "generation_monthly_budget_exceeded",
        "generation_per_request_budget_exceeded",
        "generation_budget_reservation_invalid",
        "generation_budget_policy_changed",
    }
    for code in codes:
        assert f'"{code}"' in EDGE
        assert f"'{code}'" in MIGRATION
    assert "BUDGET_ERROR_CODES.has(value.message)" in EDGE


def test_accounting_lifecycle_does_not_mislabel_estimate_as_invoice() -> None:
    for event in ("'reserved'", "'settled'", "'released'", "'frozen'"):
        assert event in MIGRATION
    assert "accounting_basis', 'provider_sku_estimate'" in MIGRATION
    assert "accounted provider SKU estimate" in DOC
    assert "described as a reconciled Runway invoice" in DOC
    assert "budgets and unified Runway/OpenAI invoice reconciliation" in DOC
