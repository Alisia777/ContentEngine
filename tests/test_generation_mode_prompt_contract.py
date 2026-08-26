from __future__ import annotations

import json
from pathlib import Path
import subprocess

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280005_generation_mode_prompt_contract.sql"
).read_text(encoding="utf-8")
FLEXIBLE_MIGRATION = (
    ROOT
    / "supabase/migrations/202607280008_flexible_video_generation_durations.sql"
).read_text(encoding="utf-8")
INTERACTION_MIGRATION = (
    ROOT
    / "supabase/migrations/202607290004_sync_generation_interaction_prompt_contract.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_mode_prompt_contract_test.sql"
).read_text(encoding="utf-8")
RESEARCH_EDGE = (
    ROOT / "supabase/functions/creator-product-research/index.ts"
).read_text(encoding="utf-8")
GENERATION_EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
HANDOFF = (
    ROOT / "web/app/content-generation-handoff.js"
).read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/product-research-view.js").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def test_mode_prompt_migration_and_pgtap_parse() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(FLEXIBLE_MIGRATION)
    assert parse_sql(INTERACTION_MIGRATION)
    assert parse_sql(PGTAP)


def test_product_interaction_contract_matches_browser_edge_and_database() -> None:
    requirements = (
        "Масштаб и действие: товар показан целиком в естественном размере на устойчивой столешнице; герой взаимодействует с крышкой, панелью управления и готовым результатом.",
        "Масштаб и действие: товар показан целиком в естественном размере на месте использования; герой взаимодействует с управлением или рабочей частью.",
        "Масштаб и действие: товар для дома показан целиком в естественном размере на устойчивой поверхности; герой демонстрирует одну видимую рабочую часть и понятное безопасное действие.",
    )
    for requirement in requirements:
        assert requirement.removeprefix("Масштаб и действие: ") in HANDOFF
        assert requirement in GENERATION_EDGE
        assert requirement in INTERACTION_MIGRATION


def test_research_scenarios_are_bounded_to_the_recommended_model() -> None:
    for token in (
        "minItems: 1",
        "maxItems: 3",
        'scenario.spoken_script !== "" || shots.length !== 3',
        'shot.seconds !== "один кадр"',
        'scenario.spoken_script !== "" || shots.length !== 1',
        'shot.seconds !== "0–5 секунд"',
        "shots.length < 2 || shots.length > 3",
        "hasSameWordSequence(",
        'shot.on_screen_text !== "без текста"',
        "ровно одной строкой shot_list",
        "вместе должен повторять spoken_script слово в слово",
        "Для всех трёх режимов on_screen_text должен",
    ):
        assert token in RESEARCH_EDGE


def test_browser_explains_and_blocks_scenarios_that_need_manual_rewriting() -> None:
    module_url = (ROOT / "web/app/product-research-view.js").as_uri()
    script = f"""
import {{ inspectResearchScenarioGenerationReadiness as inspect }}
  from {json.dumps(module_url)};
const results = {{
  photo: inspect({{
    generation_mode: "real_photo",
    script: "",
    shot_list: "Композиция\\nМягкий свет\\nНейтральный фон",
  }}),
  gen4: inspect({{
    generation_mode: "real_gen4",
    script: "",
    shot_list: "Один спокойный проход камеры",
  }}),
  seedance: inspect({{
    generation_mode: "real_seedance",
    script: "Показываю точный товар крупно и возвращаю упаковку в центр.",
    shot_list: "Товар у лица\\nУпаковка крупно\\nТовар в центре",
  }}),
  longSpeech: inspect({{
    generation_mode: "real_seedance",
    script: Array.from({{ length: 23 }}, (_, index) => `слово${{index}}`).join(" "),
    shot_list: "Кадр один\\nКадр два",
  }}),
  gen4Drift: inspect({{
    generation_mode: "real_gen4",
    script: "Лишняя реплика",
    shot_list: "Первое действие\\nВторое действие",
  }}),
  generatedText: inspect({{
    generation_mode: "real_photo",
    script: "",
    shot_list: "Композиция. Текст: скидка 50%.\\nСвет\\nФон",
  }}),
}};
process.stdout.write(JSON.stringify(results));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["photo"]["ready"] is True
    assert payload["gen4"]["ready"] is True
    assert payload["seedance"]["ready"] is True
    assert payload["longSpeech"]["code"] == "seedance_scenario_not_ready"
    assert payload["gen4Drift"]["code"] == "gen4_scenario_not_ready"
    assert payload["generatedText"]["code"] == "generated_text_not_supported"
    assert "product-research-generation-readiness" in VIEW
    submit = APP[
        APP.index("async function submitProductResearchBrief(") :
        APP.index("function mergeProductResearchBrief")
    ]
    assert "inspectResearchScenarioGenerationReadiness" in submit
    assert submit.index("inspectResearchScenarioGenerationReadiness") < submit.index(
        "saveCreativeBriefDraft"
    )


def test_seedance_prompt_prohibits_generated_text_in_every_client_path() -> None:
    fragment = (
        "Без сгенерированных надписей, субтитров и декоративного текста."
    )
    assert fragment in HANDOFF
    assert 'required(seedance ? GENERATED_TEXT_GUARD : "")' in HANDOFF
    assert "required(GENERATED_TEXT_GUARD)" in HANDOFF
    assert fragment in GENERATION_EDGE
    assert fragment in MIGRATION
    assert "generated_text_guard_missing" in HANDOFF


def test_browser_inspector_rejects_duration_or_text_guard_tampering() -> None:
    module_url = (ROOT / "web/app/content-generation-handoff.js").as_uri()
    script = f"""
import * as subject from {json.dumps(module_url)};
const seedance = subject.compileSafeGenerationBrief({{
  mode: "real_seedance",
  productName: "Точный товар",
  sku: "SKU-BASE",
}});
const gen4 = subject.compileSafeGenerationBrief({{
  mode: "real_gen4",
  productName: "Точный товар",
  sku: "SKU-BASE",
}});
const seedanceDuration = subject.inspectContentGenerationPrompt(
  seedance.prompt.replace("8 секунд", "7 секунд"),
  "real_seedance",
  {{ productName: "Точный товар" }},
);
const seedanceText = subject.inspectContentGenerationPrompt(
  seedance.prompt.replace(
    "Без сгенерированных надписей, субтитров и декоративного текста.",
    "",
  ),
  "real_seedance",
  {{ productName: "Точный товар" }},
);
const gen4Duration = subject.inspectContentGenerationPrompt(
  gen4.prompt.replace("5 секунд", "6 секунд"),
  "real_gen4",
  {{ productName: "Точный товар" }},
);
process.stdout.write(JSON.stringify({{
  seedanceReady: seedance.ready,
  gen4Ready: gen4.ready,
  seedanceDuration: seedanceDuration.blockers.map((item) => item.code),
  seedanceText: seedanceText.blockers.map((item) => item.code),
  gen4Duration: gen4Duration.blockers.map((item) => item.code),
}}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["seedanceReady"] is True
    assert payload["gen4Ready"] is True
    assert "seedance_output_guard_missing" in payload["seedanceDuration"]
    assert "generated_text_guard_missing" in payload["seedanceText"]
    assert "gen4_output_guard_missing" in payload["gen4Duration"]


def test_edge_rejects_unbound_base_prompt_before_learning_or_paid_state() -> None:
    start_offset = GENERATION_EDGE.index(
        "const startPayload = readStartPayload(body)"
    )
    for token in (
        "function generationModePromptIsBound(",
        "`Точный товар: ${payload.product_name}, артикул ${payload.sku}.`",
        "generation_mode_prompt_binding_invalid",
        "countPromptWords(spokenMatch[1])",
        "spokenWords <= seedanceSpokenWordLimit(payload.duration_seconds)",
    ):
        assert token in GENERATION_EDGE
    base_gate = GENERATION_EDGE.index(
        "generationModePromptIsBound(startPayload)",
        start_offset,
    )
    learning_lookup = GENERATION_EDGE.index(
        '"creator_generation_learning_policy"',
        base_gate,
    )
    paid_rpc = GENERATION_EDGE.index(
        '"creator_start_real_generation"',
        learning_lookup,
    )
    assert base_gate < learning_lookup < paid_rpc


def test_database_rechecks_identity_mode_and_spoken_word_limit() -> None:
    wrapper = FLEXIBLE_MIGRATION[
        FLEXIBLE_MIGRATION.index(
            ".creator_start_real_generation_pre_review_autostart_v11("
        ) :
        FLEXIBLE_MIGRATION.index(
            "-- The outer v12 layer",
        )
    ]
    for token in (
        "generation_mode_prompt_requirements(",
        "identity_requirement := format(",
        "position(identity_requirement in brief_value) = 0",
        "foreach requirement_value in array requirements",
        "generation_mode_prompt_binding_invalid",
        "spoken_word_count not between 1 and spoken_word_limit",
        ".creator_start_real_generation_pre_mode_prompt_v10(p_payload)",
    ):
        assert token in wrapper
    prompt_gate = wrapper.index(
        "foreach requirement_value in array requirements"
    )
    prior_call = wrapper.index(
        ".creator_start_real_generation_pre_mode_prompt_v10(p_payload)"
    )
    assert prompt_gate < prior_call
    assert "duration_requirement := format(" in wrapper


def test_release_versions_bind_the_mode_prompt_contract() -> None:
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in (
        GENERATION_EDGE
    )
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in APP
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in API
    assert "./product-research-view.js?v=20260826.rebuild-clean.27" in APP
    assert "./content-generation-handoff.js?v=20260826.rebuild-clean.27" in APP
    assert "./supabase-api.js?v=20260826.rebuild-clean.27" in APP
    assert "./app.js?v=20260826.rebuild-clean.27" in INDEX
    assert "generation_mode_prompt_binding_invalid" in API
