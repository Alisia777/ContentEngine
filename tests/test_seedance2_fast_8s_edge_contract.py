from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
PROVIDER_ADAPTER = (
    ROOT / "supabase/functions/_shared/generation-provider-adapters.js"
).read_text(encoding="utf-8")


def test_edge_accepts_duration_bound_seedance_paid_skus() -> None:
    for token in (
        '"runway:seedance2_fast"',
        "minimumDuration: 4",
        "maximumDuration: 15",
        "creditsPerSecond: 29",
        "`RUNWAY_SEEDANCE2_FAST_${duration}S_AUDIO_USD_${estimatedUsd}`",
        'model === "seedance2_fast"',
        "startPayload.spend_confirmation !== startSku.confirmation",
        "job.estimated_cost_minor !== exact.estimatedCostMinor",
        "job.estimated_credits !== exact.estimatedCredits",
    ):
        assert token in EDGE


def test_edge_uses_seedance_reference_mode_with_audio() -> None:
    seedance_start = PROVIDER_ADAPTER.index("function buildSeedance(")
    provider_call = PROVIDER_ADAPTER.index("\nfunction buildRunwayVeo(")
    request_section = PROVIDER_ADAPTER[seedance_start:provider_call]

    assert "references.map((uri) => ({ uri }))" in request_section
    assert "audio: selection.audio" in request_section
    reference_branch = request_section[
        request_section.index("body.promptImage = references.length") :
        request_section.index("} else {", request_section.index("body.promptImage = references.length"))
    ]
    assert 'position: "first"' in reference_branch
    assert "body.references" not in reference_branch
    assert "promptText: exactPrompt(input, entry)" in request_section
    assert "duration: selection.durationSeconds" in request_section
    assert "ratio: providerRatio" in request_section


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
        "Встроенный голос — черновик",
        "state.api.startRealGeneration(payload)",
    ):
        assert token in APP


def test_portal_requires_a_product_specific_script_and_never_auto_submits() -> None:
    assert "Это кислотный пилинг AHA тридцать и BHA два процента" not in APP
    assert "compileSafeGenerationBrief" in APP
    assert "productName: identity.productName" in APP
    assert "Портал сохранит ваш замысел" in APP
    assert "короткая дословная реплика" in APP
    assert "SEEDANCE_BLOGGER_BRIEF" not in APP
    assert "requestSubmit()" not in APP


def test_adapter_revalidates_sku_before_invoking_edge() -> None:
    for token in (
        "const REAL_GENERATION_SKUS",
        '!/^[A-Z0-9][A-Z0-9_.:-]{2,255}$/u.test',
        "provider_readiness_receipt_id",
        "provider_readiness_receipt_hash",
        "generation_selection_snapshot",
        "spend_confirmation",
    ):
        assert token in ADAPTER
