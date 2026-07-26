from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_preflight_checks_runway_organization_without_creating_a_task() -> None:
    helper = _between(
        EDGE,
        "async function checkRunwayProviderReadiness",
        "async function fetchWithTimeout",
    )
    assert '`${RUNWAY_API_ORIGIN}/v1/organization`' in helper
    assert 'method: "GET"' in helper
    assert '"x-runway-version": RUNWAY_API_VERSION' in helper
    assert "/v1/image_to_video" not in helper
    assert "/v1/text_to_image" not in helper


def test_local_qa_origin_is_exactly_allowlisted_without_wildcard_cors() -> None:
    assert 'const LOCAL_QA_APP_ORIGIN = "http://127.0.0.1:8767"' in EDGE
    assert "USER_APP_ORIGINS.has(origin)" in EDGE
    assert '"access-control-allow-origin", origin' in EDGE
    assert '"access-control-allow-origin", "*"' not in EDGE
    assert "auth: \"user\"" in EDGE
    assert "cors: false" in EDGE


def test_preflight_is_membership_scoped_and_returns_only_safe_booleans() -> None:
    handler = _between(
        EDGE,
        "const handlePreflight = async",
        "const preflightPayload = readPreflightPayload",
    )
    assert '"creator_generation_spend_overview"' in handler
    assert "organization_id: payload.organization_id" in handler
    assert 'provider: "runway"' in handler
    assert "balance_sufficient: readiness.balanceSufficient" in handler
    assert "model_available: readiness.modelAvailable" in handler
    assert "daily_quota_available: readiness.dailyQuotaAvailable" in handler
    assert "learning_gate_version: GENERATION_LEARNING_GATE_VERSION" in handler
    assert "creditBalance" not in handler
    assert "maxDailyGenerations" not in handler


def test_server_rechecks_provider_immediately_before_paid_post() -> None:
    claim = EDGE.index("const claim = await claimSystemJob(current.id)")
    readiness = EDGE.index(
        "const providerReadiness = await checkRunwayProviderReadiness",
        claim,
    )
    provider_endpoint = EDGE.index("const providerEndpoint", readiness)
    provider_post = EDGE.index("createResponse = await fetchWithTimeout", provider_endpoint)
    assert claim < readiness < provider_endpoint < provider_post
    guard = EDGE[readiness:provider_endpoint]
    assert "if (!providerReadiness.ready)" in guard
    assert "await markFailed(startJob.id, providerReadiness.failureCode)" in guard


def test_client_performs_free_preflight_before_starting_paid_generation() -> None:
    submit = _between(
        APP,
        "async function submitRealGeneration(form, values, mode)",
        "async function submitMockBatch",
    )
    preflight = submit.index(
        "state.api.realGenerationPreflight(generationSku.model)"
    )
    paid_start = submit.index("state.api.startRealGeneration(payload)")
    assert preflight < paid_start
    assert 'setFormBusy(form, true, "Проверяем Runway без списания…")' in submit
    assert "providerStartAttempted = true" in submit
    assert (
        "preflightResult.preflight.learning_gate_version !=="
        in submit
    )
    assert "GENERATION_LEARNING_GATE_VERSION" in submit
    assert "Платный запуск не создан: бесплатная проверка Runway не пройдена" in submit

    assert "realGenerationPreflight(model)" in ADAPTER
    invoke = _between(
        ADAPTER,
        "async invokeRealGeneration(action, payload = {})",
        "recordMetric(snapshot)",
    )
    assert '"preflight"' in invoke
    assert 'new Set(["start", "reconcile"]).has(action)' in invoke
    assert 'if (action === "preflight")' in invoke


def test_user_can_run_preflight_without_confirming_a_paid_generation() -> None:
    assert 'data-action="check-runway-readiness"' in APP
    assert "Проверить Runway бесплатно" in APP
    runner = _between(
        APP,
        "async function runGenerationPreflight(form",
        "async function checkRunwayReadiness(control)",
    )
    assert "state.api.realGenerationPreflight(sku.model)" in runner
    assert "real_spend_confirmation" not in runner
    assert "startRealGeneration" not in runner
    assert "generationPreflightDecision(previous" in runner
    assert "return previous.promise" in runner
    validator = _between(
        APP,
        "function validateGenerationPreflight",
        "function syncGenerationPreflightUi",
    )
    assert "preflight.learning_gate_version !== GENERATION_LEARNING_GATE_VERSION" in validator
    assert "Проверка не создаёт задачу и ничего не списывает." in APP


def test_real_mode_automatically_runs_one_free_deduplicated_preflight() -> None:
    scheduler = _between(
        APP,
        "function scheduleAutomaticGenerationPreflight",
        "async function runGenerationPreflight",
    )
    assert "form.dataset.autoGenerationPreflightModel === sku.model" in scheduler
    assert "window.queueMicrotask" in scheduler
    assert "void runGenerationPreflight(form)" in scheduler
    assert "startRealGeneration" not in scheduler
    assert "real_spend_confirmation" not in scheduler
    assert "scheduleAutomaticGenerationPreflight(form)" in APP
    assert "if (real && spendAllowed)" in APP


def test_paid_client_requires_the_exact_deployed_learning_gate_version() -> None:
    assert (
        'const GENERATION_LEARNING_GATE_VERSION = "2026-07-26.v3"'
        in EDGE
    )
    assert (
        'const GENERATION_LEARNING_GATE_VERSION = "2026-07-26.v3"'
        in APP
    )
    assert (
        '"x-contentengine-learning-gate": GENERATION_LEARNING_GATE_VERSION'
        in EDGE
    )


def test_model_prompt_limits_match_the_provider_contract() -> None:
    assert "gen4_turbo: 1_000" in EDGE
    assert "seedance2_fast: 1_200" in EDGE
    assert "seedream5_lite: 1_200" in EDGE
    assert "!isBoundedText(value.brief, 1, promptLimit)" in EDGE

    for token in (
        "promptMaxLength: 1000",
        "promptMaxLength: 1200",
        "brief.maxLength = sku?.promptMaxLength || 1200",
        "brief.length > generationSku.promptMaxLength",
    ):
        assert token in APP
    assert "prompt_max_length: 1000" in ADAPTER
    assert "brief.length > sku.prompt_max_length" in ADAPTER
