from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240010_generation_creative_learning_loop.sql"
).read_text(encoding="utf-8")
SCHEMA_RELOAD_MIGRATION = (
    ROOT
    / "supabase/migrations/202607240011_reload_generation_learning_rpc_schema.sql"
).read_text(encoding="utf-8")
WRITABLE_TRANSACTION_MIGRATION = (
    ROOT
    / "supabase/migrations/202607240012_generation_learning_rpc_writable_transaction.sql"
).read_text(encoding="utf-8")
LIVE_SMOKE = (
    ROOT
    / "supabase/test-fixtures/generation_creative_learning_live_smoke.sql"
).read_text(encoding="utf-8")
STALE_POLICY_LIVE_SMOKE = (
    ROOT
    / "supabase/test-fixtures/generation_learning_stale_policy_live_smoke.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def test_learning_signals_are_append_only_tenant_bound_and_structural() -> None:
    for token in (
        "create table if not exists content_factory.generation_creative_signals",
        "foreign key (organization_id, generation_job_id)",
        "foreign key (organization_id, product_id)",
        "unique (organization_id, generation_job_id)",
        "generation_creative_signal_append_only",
        "before update or delete",
        "alter table content_factory.generation_creative_signals enable row level security",
        "revoke all on content_factory.generation_creative_signals",
        "'product_focus', 'trust_builder', 'demonstration', 'comparison'",
        "'question_led', 'why_explanation', 'before_buying'",
        "prompt_hash text not null",
        "creative_brief_draft_id uuid",
        "scenario_position smallint",
        "references content_factory.creative_brief_drafts(organization_id, id)",
    ):
        assert token in MIGRATION
    table = MIGRATION.split(
        "create table if not exists content_factory.generation_creative_signals",
        1,
    )[1].split(");", 1)[0]
    assert "hook_text" not in table
    assert "prompt_text" not in table
    assert "claim" not in table


def test_policy_uses_only_approved_published_mature_metrics() -> None:
    policy = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ):
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation"
        )
    ]
    for token in (
        "content_factory_private.current_profile_id()",
        "content_factory_private.resolve_organization(p_payload)",
        "content_factory_private.membership_role(",
        "and (team_scope or media.owner_id = user_id)",
        "media.metadata -> 'rights_confirmed'",
        "job.status = 'succeeded'",
        "placement.status = 'published'",
        "decision.decision = 'approved'",
        "decision.media_watched_confirmed",
        "metric.views >= 100",
        "metric.clicks <= metric.views",
        "metric.orders <= metric.views",
        "having count(*) >= 3",
        "evidence_count >= 6",
        "eligible_angle_count >= 2",
        "percent_rank() over",
        "preferred_angle_score - coalesce(second_angle_score, 1) >= 0.10",
        "'claims_are_never_learned', true",
        "'product_identity_is_immutable', true",
        "'format_and_spend_are_immutable', true",
        "content_factory_private.json_hash(policy_without_hash)",
    ):
        assert token in policy


def test_learning_rpc_refreshes_the_postgrest_schema_cache() -> None:
    assert "notify pgrst, 'reload schema';" in SCHEMA_RELOAD_MIGRATION


def test_learning_rpc_allows_the_shared_profile_guard_to_refresh() -> None:
    policy_header = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ):
        MIGRATION.index("as $$", MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ))
    ]
    assert "\nstable\n" not in policy_header
    assert (
        "alter function public.creator_generation_learning_policy(jsonb) volatile;"
        in WRITABLE_TRANSACTION_MIGRATION
    )
    assert "notify pgrst, 'reload schema';" in WRITABLE_TRANSACTION_MIGRATION


def test_live_learning_smoke_is_rollback_only_and_checks_a_stable_winner() -> None:
    for token in (
        "begin;",
        "set local session_replication_role = replica;",
        "for position in 1..6 loop",
        "'trust_builder'",
        "'comparison'",
        "public.creator_generation_learning_policy(",
        "policy ->> 'applied' <> 'true'",
        "policy ->> 'confidence' <> 'medium'",
        "policy ->> 'preferred_angle' <> 'trust_builder'",
        "policy ->> 'avoid_angle' <> 'comparison'",
        "jsonb_array_length(policy -> 'source_job_ids') <> 3",
        "rollback;",
    ):
        assert token in LIVE_SMOKE
    assert LIVE_SMOKE.rstrip().endswith("rollback;")


def test_stale_policy_live_smoke_rejects_before_any_paid_state() -> None:
    for token in (
        "public.creator_start_real_generation(",
        "'source', 'performance_learning'",
        "'applied_policy_hash', repeat('a', 64)",
        "when sqlstate '55000'",
        "sqlerrm <> 'generation_learning_policy_stale'",
        "generation_batches",
        "generation_jobs",
        "generation_spend_ledger",
        "'paid_state_created', false",
        "rollback;",
    ):
        assert token in STALE_POLICY_LIVE_SMOKE
    assert STALE_POLICY_LIVE_SMOKE.rstrip().endswith("rollback;")


def test_paid_wrapper_records_only_context_bound_to_created_job() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation"
        ):
        MIGRATION.rindex("commit;")
    ]
    for token in (
        "learning_context := p_payload -> 'learning_context'",
        "command_payload := p_payload - 'learning_context'",
        "generation_learning_context_invalid",
        "creator_start_real_generation_campaign_v1(",
        "creator_start_seedream5_lite_photo(",
        "job_row.input ->> 'prompt_text'",
        "is distinct from command_payload ->> 'brief'",
        "insert into content_factory.generation_creative_signals",
        "generation_learning_signal_binding_invalid",
        "generation_learning_signal_conflict",
        "generation_learning_policy_stale",
        "generation_learning_research_provenance_invalid",
        "and draft.status = 'approved'",
        "and draft.product_id = job_row.product_id",
        "computed_angle_value := case",
        "computed_patterns_value",
        "'{job,learning_signal_recorded}'",
    ):
        assert token in wrapper


def test_edge_and_browser_validate_the_same_bounded_learning_contract() -> None:
    for token in (
        "type GenerationLearningContext",
        '"learning_context"',
        '"creative_brief_draft_id"',
        '"scenario_position"',
        "readGenerationLearningContext(",
        "value.learning_context",
        "hookPatterns.length > 8",
        "new Set(hookPatterns).size !== hookPatterns.length",
        r"/^[0-9a-f]{64}$/u.test(value.applied_policy_hash)",
    ):
        assert token in EDGE
    for token in (
        'generationLearningPolicy: "creator_generation_learning_policy"',
            "generationLearningPolicy({",
            "project_id: projectIdSnake",
            "project_id: requiredProjectId(projectIdSnake || projectId)",
        "RPC.generationLearningPolicy",
    ):
        assert token in ADAPTER
    for token in (
        "function loadGenerationLearningPolicy(",
        "normalizeGenerationLearningPolicy",
        "function generationLearningContext(form)",
        'source: "performance_learning"',
        'source: "approved_research"',
        'source: "baseline"',
        "compiled.prompt !== autoPrompt",
        'data-action="disable-generation-learning"',
        'data-action="enable-generation-learning"',
        "Тексты обещаний, права и параметры запуска не обучаются",
    ):
        assert token in APP
    assert ".generation-learning-status" in STYLES
    assert "./styles.css?v=20260730.4" in INDEX
    assert "./app.js?v=20260823.copy-engines.47" in INDEX
    assert "./supabase-api.js?v=20260823.copy-engines.47" in APP


def test_paid_start_uses_learning_only_when_the_user_explicitly_applies_advice() -> None:
    loader = APP[
        APP.index("async function loadGenerationLearningPolicy("):
        APP.index("function automaticGenerationBriefCandidate(")
    ]
    submit = APP[
        APP.index("async function submitRealGeneration("):
        APP.index("async function submitMockBatch(")
    ]
    assert "learning.promise = pending" in loader
    assert "return await learning.promise" in loader
    assert "async function ensureGenerationLearningPolicy(" in loader
    assert "await ensureGenerationLearningPolicy(form, identity)" not in submit
    refresh = submit.index("values = new FormData(form)")
    preflight = submit.index(
        "await runGenerationPreflightForPaidStart(",
        refresh,
    )
    paid_start = submit.index("state.api.startRealGeneration(payload)", preflight)
    assert refresh < preflight < paid_start
    assert "learning_context: learningContext" in submit
    assert "syncAutomaticGenerationBrief(form" in submit
    assert "await ensurePreparedGenerationSpecForPaidStart(form)" in submit
    assert "Learning is advisory" in submit


def test_edge_only_fetches_learning_for_explicit_performance_advice() -> None:
    start = EDGE[
        EDGE.index("const startPayload = readStartPayload(body)"):
        EDGE.index("const { data: startData, error: startError }")
    ]
    assert '"learning_context",' in EDGE[
        EDGE.index("function readStartPayload"):
        EDGE.index("function readPreflightPayload")
    ]
    opt_in = start.index('if (learningSource === "performance_learning")')
    policy_rpc = start.index('"creator_generation_learning_policy"', opt_in)
    paid_state_rpc = EDGE.index(
        '"creator_start_real_generation"',
        EDGE.index("const startPayload = readStartPayload(body)"),
    )
    policy_required = start.index('"generation_learning_policy_required"')
    unavailable = start.index('"generation_learning_unavailable"')
    assert opt_in < policy_rpc < unavailable < policy_required
    assert "Learning is advisory by default" in start
    assert EDGE.index('"creator_generation_learning_policy"') < paid_state_rpc
    assert "startPayload.learning_opt_out !== true" in start
    assert 'delete (rest as Partial<StartPayload>).learning_opt_out' in EDGE
