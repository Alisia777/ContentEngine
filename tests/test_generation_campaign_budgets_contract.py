from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170003_generation_campaign_budgets.sql"
).read_text(encoding="utf-8")
SPEND_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202607170002_generation_spend_budgets.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
).read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
SPEND_VIEW = (ROOT / "web" / "app" / "generation-spend-view.js").read_text(
    encoding="utf-8"
)


def _between(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    return text[start_index : text.index(end, start_index)]


def _public_rpc(name: str) -> str:
    start = f"create or replace function public.{name}("
    return _between(MIGRATION, start, "\n$$;")


def test_campaign_schema_is_private_rls_scoped_and_attribution_is_durable() -> None:
    for table in (
        "content_factory.generation_campaigns",
        "content_factory.generation_campaign_spend_policies",
    ):
        assert re.search(
            rf"alter\s+table\s+{re.escape(table)}\s+enable\s+row\s+level\s+security",
            MIGRATION,
            flags=re.IGNORECASE,
        )
        assert f"revoke all on {table}\n  from public, anon, authenticated" in MIGRATION
        assert f"grant all on {table} to service_role" in MIGRATION

    for relation in ("generation_batches", "generation_jobs"):
        assert (
            f"alter table content_factory.{relation}\n"
            "  add column if not exists campaign_id uuid"
        ) in MIGRATION
        assert f"{relation}_campaign_fk" in MIGRATION
        assert f"{relation}_paid_campaign_check" in MIGRATION
        assert (
            f"before update of campaign_id on content_factory.{relation}"
        ) in MIGRATION

    assert "references content_factory.generation_campaigns(organization_id, id)" in MIGRATION
    assert "mode <> 'real' or not allow_real_spend or campaign_id is not null" in MIGRATION
    assert "content_factory_private.bind_paid_generation_campaign()" in MIGRATION
    assert "content_factory_private.guard_paid_campaign_identity()" in MIGRATION
    assert "generation_spend_reservation_identity_immutable" in MIGRATION


def test_campaign_budget_reuses_the_single_append_only_spend_ledger() -> None:
    assert "guard_generation_spend_ledger_append_only" in SPEND_MIGRATION
    assert (
        "before update or delete on content_factory.generation_spend_ledger"
        in SPEND_MIGRATION
    )
    assert "create trigger generation_spend_reservation" in SPEND_MIGRATION
    assert "after insert on content_factory.generation_jobs" in SPEND_MIGRATION
    assert "insert into content_factory.generation_spend_ledger" in SPEND_MIGRATION

    # Campaign accounting is a dimension over the authoritative job ledger.  It
    # must not introduce a second mutable balance or append a duplicate reserve.
    assert "insert into content_factory.generation_spend_ledger" not in MIGRATION
    assert "update content_factory.generation_spend_ledger" not in MIGRATION
    assert "delete from content_factory.generation_spend_ledger" not in MIGRATION
    assert "appends the single authoritative reservation ledger event" in MIGRATION
    assert "join content_factory.generation_jobs job" in MIGRATION
    assert "and job.campaign_id = new.campaign_id" in MIGRATION

    for marker in (
        "content_factory_private.reserve_generation_campaign_spend()",
        "before insert on content_factory.generation_jobs",
        "content_factory_private.guard_generation_campaign_spend_start()",
        "old.status <> 'queued'",
        "new.status <> 'starting'",
        "pg_advisory_xact_lock",
        "generation_campaign_per_request_budget_exceeded",
        "generation_campaign_daily_budget_exceeded",
        "generation_campaign_monthly_budget_exceeded",
    ):
        assert marker in MIGRATION


def test_campaign_commands_are_role_gated_idempotent_and_narrowly_granted() -> None:
    for name in (
        "creator_create_generation_campaign",
        "creator_update_generation_campaign_spend_policy",
    ):
        body = _public_rpc(name)
        assert "security definer" in body
        assert "set search_path = ''" in body
        assert "content_factory_private.membership_role(" in body
        assert "array['owner', 'admin']" in body
        assert "content_factory_private.begin_command(" in body
        assert "content_factory_private.finish_command(" in body
        assert f"'{name}'" in body
        assert (
            f"revoke all on function public.{name}(jsonb)\n"
            "  from public, anon"
        ) in MIGRATION
        assert (
            f"grant execute on function public.{name}(jsonb)\n"
            "  to authenticated"
        ) in MIGRATION

    update = _public_rpc("creator_update_generation_campaign_spend_policy")
    assert "content_factory_private.require_uuid(" in update
    assert "expected_version" in update
    assert "generation_campaign_budget_policy_changed" in update
    assert "version = policy.version + 1" in update

    start = _public_rpc("creator_start_real_generation")
    assert "p_payload ? 'campaign_id'" in start
    assert "content_factory_private.require_uuid(" in start
    assert "content_factory.generation_campaign_id" in start
    assert "stored_campaign_id is distinct from campaign_id_value" in start
    assert "'{job,campaign_id}'" in start
    assert "'{batch,campaign_id}'" in start


def test_edge_whitelists_validates_and_forwards_campaign_identity() -> None:
    common_payload = _between(EDGE, "type CommonStartPayload", "type StartPayload")
    start_reader = _between(EDGE, "function readStartPayload", "function readStatusPayload")
    assert "campaign_id: string" in common_payload
    assert '"campaign_id"' in start_reader
    assert "value.campaign_id" in start_reader
    assert "isUuid(value.campaign_id)" in start_reader
    assert "{ p_payload: rpcPayload(startPayload) }" in EDGE

    for code in (
        "paid_generation_campaign_required",
        "paid_generation_campaign_not_active",
        "paid_generation_campaign_policy_missing",
        "paid_generation_campaign_paused",
        "generation_campaign_per_request_budget_exceeded",
        "generation_campaign_daily_budget_exceeded",
        "generation_campaign_monthly_budget_exceeded",
        "generation_campaign_budget_policy_changed",
    ):
        assert f'"{code}"' in EDGE
        assert f"'{code}'" in MIGRATION
    assert "BUDGET_ERROR_CODES.has(value.message)" in EDGE


def test_start_and_status_responses_keep_campaign_attribution() -> None:
    status = _public_rpc("creator_real_generation_status")
    assert "job_row.campaign_id is null" in status
    assert "generation_campaign_binding_invalid" in status
    assert "'campaign_id', job_row.campaign_id" in status
    assert "'campaign_name', campaign_name_value" in status

    for marker in (
        "campaignId: string",
        "campaignName: string",
        "campaign_id: string",
        "campaign_name: string",
        "!isUuid(job.campaign_id)",
        "job.campaign_id !== batch.campaign_id",
        "campaign_id: job.campaignId",
        "campaign_name: job.campaignName",
        'from("generation_campaigns")',
        "startJob.campaignId !== startPayload.campaign_id",
        "current.campaignId !== startJob.campaignId",
        "current.campaignName !== startJob.campaignName",
    ):
        assert marker in EDGE


def test_api_exposes_campaign_commands_and_requires_it_for_paid_start() -> None:
    assert (
        'createGenerationCampaign: "creator_create_generation_campaign"'
        in API
    )
    assert (
        'updateGenerationCampaignSpendPolicy: '
        '"creator_update_generation_campaign_spend_policy"'
        in API
    )
    assert "createGenerationCampaign(campaign = {})" in API
    assert "this.mutate(RPC.createGenerationCampaign" in API
    assert "updateGenerationCampaignSpendPolicy(campaignId, policy = {})" in API
    assert "this.mutate(RPC.updateGenerationCampaignSpendPolicy" in API

    paid_start = _between(API, "startRealGeneration(batch)", "realGenerationStatus(")
    assert 'String(batch?.campaign_id || "").trim()' in paid_start
    assert "if (!isUuid(campaignId))" in paid_start
    assert 'code: "paid_generation_campaign_required"' in paid_start
    assert "campaign_id: campaignId" in paid_start


def test_generator_selector_and_preflight_use_the_same_campaign_budget() -> None:
    for marker in (
        "function activeGenerationCampaigns()",
        ".filter((campaign) => campaign.id && campaign.enabled && !campaign.blockerCode)",
        "function realGenerationSpendAllowed(mode, campaignId",
        'select name="campaign_id"',
        'generationForm && ["generation_mode", "campaign_id"].includes(event.target.name)',
        "generationSpendSnapshotMarkup(state.generationSpend",
        'String(values.get("campaign_id") || "").trim()',
        "realGenerationSpendAllowed(mode, campaignId)",
        "campaign_id: campaignId",
    ):
        assert marker in APP

    assert "generationSpendAllowsMinor(value, requestMinor, campaignId" in SPEND_VIEW
    assert "overview.campaigns.find((item) => item.id === normalizedCampaignId)" in SPEND_VIEW
    assert "!campaign || !campaign.enabled || campaign.blockerCode" in SPEND_VIEW
    assert "campaign.policy.perRequestLimitMinor" in SPEND_VIEW
    assert "campaign.day.remainingMinor" in SPEND_VIEW
    assert "campaign.month.remainingMinor" in SPEND_VIEW
    assert "generationSpendSnapshotMarkup(state = {}, { requestMinor = null, campaignId" in SPEND_VIEW
