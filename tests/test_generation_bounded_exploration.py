from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607250003_bounded_generation_exploration.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
HANDOFF = (ROOT / "web/app/content-generation-handoff.js").read_text(
    encoding="utf-8"
)
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def test_exploration_wraps_the_mature_policy_without_weakening_it() -> None:
    for token in (
        "set schema content_factory_private",
        "rename to creator_generation_learning_performance_policy_v1",
        ".creator_generation_learning_performance_policy_v1(p_payload)",
        "performance_policy -> 'applied' is not distinct from 'true'::jsonb",
        "'selection_mode', 'performance'",
        "'version', 'generation-learning-v2'",
        "content_factory_private.json_hash(policy_without_hash)",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION


def test_exploration_is_server_bounded_balanced_and_cost_conscious() -> None:
    exploration = MIGRATION[
        MIGRATION.index("with candidates(angle, hook_patterns, priority)"):
        MIGRATION.index("policy_hash_value :=")
    ]
    for token in (
        "'product_focus'::text",
        "'demonstration'::text",
        "signal.product_id = product_id_value",
        "signal.platform = platform_value",
        "signal.model = model_value",
        "job.status not in ('failed', 'cancelled')",
        "order by usage.use_count, usage.priority",
        "'candidate_count', 2",
        "'balancing_scope', 'product_platform_model'",
        "'exploration_angles_are_server_bounded', true",
        "'provider_spend_requires_separate_confirmation', true",
    ):
        assert token in exploration
    assert "'comparison'::text" not in exploration
    assert "'curiosity_gap'::text" not in exploration


def test_existing_paid_start_rebinds_the_exploration_assignment_before_spend() -> None:
    # The exploration wrapper deliberately emits the existing, already-audited
    # performance_learning envelope.  Both the Edge function and the database
    # re-fetch the policy and bind its hash, angle and patterns before any job.
    for token in (
        'source: "performance_learning"',
        "applied_policy_hash: policy.policyHash",
    ):
        assert token in APP
    for token in (
        '"creator_generation_learning_policy"',
        '"generation_learning_policy_required"',
        '"generation_learning_policy_stale"',
    ):
        assert token in EDGE
    for token in (
        'selectionMode',
        '"bounded_exploration"',
    ):
        assert token in HANDOFF


def test_portal_explains_the_autonomous_experiment_and_busts_caches() -> None:
    for token in (
        "Автотест ракурса назначен",
        "система сама чередует два безопасных ракурса",
        "Товар, права, обещания и бюджет не меняются",
    ):
        assert token in APP
    assert "./content-generation-handoff.js?v=20260729.3" in APP
    assert "./app.js?v=20260729.6" in INDEX
