from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_edge_accepts_one_exact_seedance_paid_sku() -> None:
    for token in (
        'model: "seedance2_fast"',
        "duration_seconds: 8",
        "audio: true",
        'format: "9:16"',
        'spend_confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32"',
        'value.model === "seedance2_fast"',
        "value.duration_seconds === 8",
        "value.audio === true",
        'value.format === "9:16"',
        "job.estimated_cost_minor === 232",
        "job.estimated_credits === 232",
    ):
        assert token in EDGE


def test_edge_uses_seedance_reference_mode_with_audio() -> None:
    seedance_start = EDGE.index('startJob.model === "seedance2_fast"')
    provider_call = EDGE.index('`${RUNWAY_API_ORIGIN}/v1/image_to_video`')
    request_section = EDGE[seedance_start:provider_call]

    assert "promptImage: [{ uri: signedInputUrl }]" in request_section
    assert "audio: true" in request_section
    assert "position" not in request_section
    assert "promptText: startJob.promptText" in request_section
    assert "duration: startJob.durationSeconds" in request_section
    assert "ratio: startJob.ratio" in request_section


def test_edge_returns_audio_and_credit_facts_without_provider_secrets() -> None:
    for token in (
        "audio: job.audio",
        "estimated_credits: job.estimatedCredits",
        'Deno.env.get("RUNWAYML_API_SECRET")',
    ):
        assert token in EDGE
    assert "RUNWAYML_API_SECRET:" not in EDGE
    assert "signed_url: signedInputUrl" not in EDGE


def test_portal_requires_explicit_seedance_price_confirmation() -> None:
    for token in (
        'const REAL_SEEDANCE_MODE = "real_seedance"',
        'model: "seedance2_fast"',
        "durationSeconds: 8",
        "estimatedCredits: 232",
        'estimatedUsd: "2.32"',
        'confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32"',
        "values.get(\"real_spend_confirmation\") !== generationSku.confirmation",
        "Голос создаётся по сценарию, но реплика может отличаться",
        "state.api.startRealGeneration(payload)",
    ):
        assert token in APP


def test_portal_requires_a_product_specific_script_and_never_auto_submits() -> None:
    assert "Это кислотный пилинг AHA тридцать и BHA два процента" not in APP
    assert "сценарий именно выбранного товара" in APP
    assert "SEEDANCE_BLOGGER_BRIEF" not in APP
    assert "requestSubmit()" not in APP


def test_adapter_revalidates_sku_before_invoking_edge() -> None:
    for token in (
        "const REAL_GENERATION_SKUS",
        "Number(batch?.duration_seconds) !== sku.duration_seconds",
        "Boolean(batch?.audio) !== sku.audio",
        "batch?.spend_confirmation !== sku.confirmation",
        "duration_seconds: sku.duration_seconds",
        "audio: sku.audio",
        "spend_confirmation: sku.confirmation",
    ):
        assert token in ADAPTER
