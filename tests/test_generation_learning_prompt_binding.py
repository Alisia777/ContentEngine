from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260012_generation_learning_prompt_binding.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT
    / "supabase/tests/generation_learning_prompt_binding_test.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
HANDOFF = (
    ROOT / "web/app/content-generation-handoff.js"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def test_browser_normalizer_accepts_wire_and_idempotent_app_shapes() -> None:
    for token in (
        '"preferred_angle",\n    "preferredAngle"',
        '"preferred_hook_patterns",\n        "preferredHookPatterns"',
        '"quality_guard_codes",\n    "qualityGuardCodes"',
        '"quality_guard_variants",\n    "qualityGuardVariants"',
        '"policy_hash",\n    "policyHash"',
        "JSON.stringify(wireValue) !== JSON.stringify(normalizedValue)",
    ):
        assert token in HANDOFF


def test_edge_binds_current_server_policy_to_exact_provider_prompt() -> None:
    start = EDGE[
        EDGE.index("const startPayload = readStartPayload(body)") :
        EDGE.index("const { data: startData, error: startError }")
    ]
    for token in (
        "function generationLearningPromptRequirements(",
        "function generationLearningPromptIsBound(",
        "requirements.every((requirement) => payload.brief.includes(requirement))",
        '"generation_learning_prompt_binding_invalid"',
        "generationLearningPromptIsBound(learningPolicy, startPayload)",
        "QA: упаковка без морфинга",
        "Структурный hook: одно простое действие с товаром",
    ):
        assert token in EDGE
    start_offset = EDGE.index("const startPayload = readStartPayload(body)")
    prompt_gate = EDGE.index(
        "generationLearningPromptIsBound(learningPolicy, startPayload)",
        start_offset,
    )
    paid_rpc = EDGE.index(
        '"creator_start_real_generation"',
        prompt_gate,
    )
    assert prompt_gate < paid_rpc


def test_database_recomputes_policy_and_rejects_missing_learned_fragments() -> None:
    for token in (
        "generation_learning_prompt_requirements(",
        "creator_start_real_generation_pre_prompt_binding_v5",
        "public.creator_generation_learning_policy(",
        "server_policy ->> 'policy_hash'",
        "learning_context ->> 'applied_policy_hash'",
        "server_policy ->> 'preferred_angle'",
        "learning_context ->> 'creative_angle'",
        "server_policy -> 'preferred_hook_patterns'",
        "learning_context -> 'hook_patterns'",
        "foreach requirement_value in array requirements",
        "position(requirement_value in coalesce(p_payload ->> 'brief', '')) = 0",
        "generation_learning_prompt_binding_invalid",
        ".creator_start_real_generation_pre_prompt_binding_v5(p_payload)",
    ):
        assert token in MIGRATION
    assert MIGRATION.index(
        "foreach requirement_value in array requirements"
    ) < MIGRATION.index(
        ".creator_start_real_generation_pre_prompt_binding_v5(p_payload)"
    )


def test_prompt_binding_only_accepts_allowlisted_structural_instructions() -> None:
    helper = MIGRATION[
        MIGRATION.index(
            "generation_learning_prompt_requirements("
        ) :
        MIGRATION.index(
            "-- Preserve the complete claim-evidence"
        )
    ]
    for token in (
        "'product_focus'",
        "'trust_builder'",
        "'demonstration'",
        "'comparison'",
        "'objection_handling'",
        "'curiosity_gap'",
        "'product_fidelity'",
        "'technical_stability'",
        "'hook_clarity'",
        "'visual_quality'",
        "'trust'",
        "'platform_fit'",
        "jsonb_array_length(guard_codes) > 3",
        "count(distinct item.value)",
    ):
        assert token in helper
    for forbidden in (
        "review.result",
        "decision.comment",
        "findings",
        "recommendations",
        "caption_text",
        "script_text",
    ):
        assert forbidden not in helper


def test_browser_edge_and_database_share_every_canonical_prompt_fragment() -> None:
    fragments = (
        "Обученный ракурс: товар целиком, строгий фокус.",
        "Обученный ракурс: естественная предметная подача.",
        "Обученный ракурс: одна видимая деталь товара.",
        "Обученный ракурс: ясный масштаб без второго товара.",
        "Обученный ракурс: упаковка и проверяемые детали.",
        "Обученный ракурс: выразительная деталь при видимом целом товаре.",
        "Обученное направление: товар главный во всех кадрах.",
        "Обученное направление: естественная подача без преувеличений.",
        "Обученное направление: одно видимое действие с товаром.",
        "Обученное направление: сравнение без второго товара и обещаний.",
        "Обученное направление: одна проверяемая деталь товара.",
        "Обученное направление: заметная деталь, затем товар целиком.",
        "Структурный hook: визуальный вопрос сразу раскрывается точным товаром.",
        "Структурный hook: видимая причина рассмотреть товар, без утверждений.",
        "Структурный hook: спокойная проверка товара перед выбором.",
        "Структурный hook: сравнение без второго товара, цифр и обещаний.",
        "Структурный hook: одно простое действие с товаром.",
        "Структурный hook: от первого лица; товар целиком и в фокусе.",
        "Структурный hook: один понятный шаг без цифр и надписей.",
        "Структурный hook: простой первый кадр сразу показывает товар.",
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
        assert fragment in HANDOFF
        assert fragment in EDGE
        assert fragment in MIGRATION


def test_runtime_sql_contract_covers_video_photo_and_tampering() -> None:
    assert "select plan(8);" in PGTAP
    for token in (
        "video policy resolves to the exact angle, hook and QA prompt fragments",
        "photo policy excludes video hook copy and keeps exact photo QA guards",
        "an unallowlisted learned angle cannot produce prompt requirements",
        "raw or unknown review material cannot become a QA prompt guard",
        "duplicated guard codes are rejected instead of silently normalized",
        "the final prompt-binding wrapper remains SECURITY DEFINER",
    ):
        assert token in PGTAP
    assert PGTAP.rstrip().endswith("rollback;")


def test_release_versions_bind_the_fixed_client_edge_and_adapter() -> None:
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in EDGE
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in APP
    assert "./content-generation-handoff.js?v=20260730.1" in APP
    assert "./supabase-api.js?v=20260729.2" in APP
    assert "./app.js?v=20260803.1" in INDEX
    assert "generation_learning_prompt_binding_invalid" in ADAPTER
