from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260013_generation_review_repair_loop.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
HANDOFF = (
    ROOT / "web/app/content-generation-handoff.js"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_database_derives_one_bounded_repair_from_structured_scores() -> None:
    for token in (
        "creator_generation_repair_policy(",
        "decision_row.decision <> 'needs_changes'",
        "decision_row.media_watched_confirmed",
        "decision_row.decided_by in (",
        "review_row.result #>> '{scores,technical}'",
        "review_row.result #>> '{scores,product_fidelity}'",
        "review_row.result #>> '{scores,hook_clarity}'",
        "review_row.result #>> '{scores,visual_quality}'",
        "review_row.result #>> '{scores,trust}'",
        "review_row.result #>> '{scores,platform_fit}'",
        "where weakness.score < 85",
        "limit 3",
        "unique (organization_id, source_review_id)",
        "'raw_review_copy_excluded', true",
        "'provider_spend_requires_separate_confirmation', true",
    ):
        assert token in MIGRATION


def test_policy_never_reuses_free_form_review_material() -> None:
    resolver = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_repair_policy"
        ) : MIGRATION.index(
            "-- Keep the complete paid command private"
        )
    ]
    for forbidden in (
        "decision_row.comment",
        "-> 'findings'",
        "-> 'recommendations'",
        "caption_text",
        "script_text",
        "transcript",
    ):
        assert forbidden not in resolver


def test_paid_database_boundary_recomputes_and_binds_repair_policy() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation"
        ) :
    ]
    for token in (
        "creator_start_real_generation_pre_repair_v6",
        "public.creator_generation_repair_policy(",
        "server_policy ->> 'policy_hash'",
        "repair_context ->> 'policy_hash'",
        "server_policy -> 'guard_codes'",
        "repair_context -> 'guard_codes'",
        "generation_repair_prompt_requirements(",
        "position(requirement_value in coalesce(p_payload ->> 'brief', '')) = 0",
        "p_payload - 'repair_context'",
        "generation_repair_signals",
        "'{job,repair_signal_recorded}'",
    ):
        assert token in wrapper
    prompt_gate = wrapper.index(
        "foreach requirement_value in array requirements"
    )
    paid_call = wrapper.index(
        ".creator_start_real_generation_pre_repair_v6(",
        prompt_gate,
    )
    assert prompt_gate < paid_call


def test_edge_rejects_stale_or_unbound_repair_before_provider_state() -> None:
    for token in (
        "type GenerationRepairContext = {",
        'value.compiler_version !== "review-repair-v1"',
        "function generationRepairPromptRequirements(",
        "function generationRepairPromptIsBound(",
        '"creator_generation_repair_policy"',
        '"generation_repair_policy_stale"',
        '"generation_repair_prompt_binding_invalid"',
    ):
        assert token in EDGE
    start = EDGE.index("const startPayload = readStartPayload(body)")
    repair_gate = EDGE.index(
        "generationRepairPromptIsBound(repairPolicy, startPayload)",
        start,
    )
    paid_rpc = EDGE.index('"creator_start_real_generation"', repair_gate)
    provider_claim = EDGE.index("const claim = await claimSystemJob", paid_rpc)
    assert repair_gate < paid_rpc < provider_claim


def test_browser_prefills_repair_but_keeps_price_confirmation_separate() -> None:
    for token in (
        'generationRepairPolicy: "creator_generation_repair_policy"',
        "generationRepairPolicy(reviewId)",
        "normalizeGenerationRepairPolicy",
        "GENERATION_REPAIR_COMPILER_VERSION",
        "activeGenerationRepairPolicy(",
        "generationRepairContext(form)",
        "repair_context: repairContext",
        "persistGenerationRepair(",
        'navigate("/workspace/generation")',
        "Исправление после QA применено",
        "комментарий проверяющего не копируется",
    ):
        assert token in ADAPTER or token in HANDOFF or token in APP
    repair_decision = APP.index(
        'if (!contextApproval && decision.decision === "needs_changes")'
    )
    policy_fetch = APP.index(
        "state.api.generationRepairPolicy(reviewId)",
        repair_decision,
    )
    navigate = APP.index(
        'navigate("/workspace/generation")',
        policy_fetch,
    )
    assert repair_decision < policy_fetch < navigate
    submit = APP[
        APP.index("async function submitRealGeneration(") :
        APP.index("async function submitMedia(", APP.index(
            "async function submitRealGeneration("
        ))
    ]
    assert "const repairContext = generationRepairContext(form);" in submit
    assert "{ repair_context: repairContext }" in submit
    assert submit.index("real_spend_confirmation") < submit.index(
        "state.api.startRealGeneration(payload)"
    )
    assert 'name="real_spend_confirmation"' in APP
    assert 'checked />' not in APP[
        APP.index('name="real_spend_confirmation"') - 200 :
        APP.index('name="real_spend_confirmation"') + 300
    ]


def test_all_layers_share_canonical_repair_fragments() -> None:
    fragments = (
        "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
        "QA: резкий товар, ровный свет, без пересвета и размытия.",
        "QA: товар считывается первым.",
        "QA: чистые края без дублей, деформаций и AI-артефактов.",
        "QA: естественные материалы, свет и масштаб.",
        "QA: мастер 1:1, безопасные поля.",
        "QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.",
        "QA: стабильный проход без чёрных кадров, скачков и мерцания.",
        "QA: точный товар и одно действие видны в первые 2 секунды.",
        "QA: руки, лицо и фактуры без деформаций, дублей и мерцания.",
        "QA: естественная подача без гиперболы и новых обещаний.",
        "QA: мастер 9:16; товар и лицо в безопасных полях.",
    )
    for fragment in fragments:
        assert fragment in MIGRATION
        assert fragment in EDGE
        assert fragment in HANDOFF
