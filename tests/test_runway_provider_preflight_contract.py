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
        "async function withFetchDeadline",
    )
    assert '`${RUNWAY_API_ORIGIN}/v1/organization`' in helper
    assert 'method: "GET"' in helper
    assert '"x-runway-version": RUNWAY_API_VERSION' in helper
    assert "/v1/image_to_video" not in helper
    assert "/v1/text_to_image" not in helper


def test_local_qa_origin_is_exactly_allowlisted_without_wildcard_cors() -> None:
    assert 'const LOCAL_QA_APP_ORIGIN = "http://127.0.0.1:8767"' in EDGE
    assert (
        'const LOCAL_PRODUCTION_QA_APP_ORIGIN = "http://127.0.0.1:8769"'
        in EDGE
    )
    assert "LOCAL_PRODUCTION_QA_APP_ORIGIN," in EDGE
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
    assert '"creator_generation_provider_policy"' in EDGE
    assert "organization_id: payload.organization_id" in handler
    assert "provider: payload.provider" in handler
    assert "balance_sufficient: readiness.balanceSufficient" in handler
    assert "model_available: readiness.modelAvailable" in handler
    assert "daily_quota_available: readiness.dailyQuotaAvailable" in handler
    assert "learning_gate_version: GENERATION_LEARNING_GATE_VERSION" in handler
    assert "await recordProviderReadiness(" in handler
    assert "receipt_id: receipt.receiptId" in handler
    assert "receipt_hash: receipt.receiptHash" in handler
    assert 'version: "generation-provider-readiness-receipt-v3"' in handler
    assert "spend_confirmation: readiness.spendConfirmation" in handler
    assert "creditBalance" not in handler
    assert "maxDailyGenerations" not in handler


def test_server_rechecks_provider_immediately_before_paid_post() -> None:
    claim = EDGE.index("const claim = await claimSystemJob(current.id)")
    readiness = EDGE.index(
        "const providerReadiness = startJob.provider === \"google\"",
        claim,
    )
    provider_endpoint = EDGE.index("const providerEndpoint", readiness)
    provider_post = EDGE.index(
        "createResponse = await fetchProviderJsonWithDeadline",
        provider_endpoint,
    )
    assert claim < readiness < provider_endpoint < provider_post
    guard = EDGE[readiness:provider_endpoint]
    assert "if (!providerReadiness.ready)" in guard
    assert "providerReadiness.failureCode || \"provider_request_failed\"" in guard


def test_client_performs_free_preflight_before_starting_paid_generation() -> None:
    submit = _between(
        APP,
        "async function submitRealGeneration(form, values, mode)",
        "async function submitMockBatch",
    )
    preflight = submit.index(
        "await runGenerationPreflightForPaidStart("
    )
    paid_start = submit.index("state.api.startRealGeneration(payload)")
    assert preflight < paid_start
    paid_preflight = _between(
        APP,
        "async function runGenerationPreflightForPaidStart(",
        "async function submitRealGenerationReconciliation(",
    )
    assert 'existing?.status !== "ready"' in paid_preflight
    assert "runGenerationPreflight(form" not in paid_preflight
    assert 'setFormBusy(form, true, "Проверяем точный выбор и квитанцию…")' in submit
    assert "providerStartAttempted = true" in submit
    assert "const launchPreflight = validateGenerationPreflight(" in submit
    assert "state.api.bindRealGenerationClientContext(payload, {" in submit
    assert "expectedActorId: launchContext.userId" in submit
    assert "isContextCurrent: paidLaunchIsCurrent" in submit
    assert "свежая бесплатная проверка выбранной модели не пройдена" in submit

    assert "realGenerationPreflight(selection, legacyDurationSeconds = undefined)" in ADAPTER
    invoke = _between(
        ADAPTER,
        "async invokeRealGeneration(action, payload = {})",
        "recordMetric(snapshot)",
    )
    assert '"preflight"' in invoke
    assert '"start", "reconcile", "strategy_bind"' in invoke
    assert "generatedIdempotencyKey" in invoke
    assert 'if (action === "preflight")' in invoke
    assert "if (expectedActorId && actorId !== expectedActorId)" in invoke
    assert 'typeof isContextCurrent === "function"' in invoke
    assert "isContextCurrent() === true" in invoke
    assert invoke.index("actorId !== expectedActorId") < invoke.index(
        "this.supabase.functions.invoke"
    )
    assert invoke.index("actorId !== expectedActorId") < invoke.index(
        "writeMutationKeys(this.mutationKeys)"
    )


def test_user_can_run_preflight_without_confirming_a_paid_generation() -> None:
    assert 'data-action="check-runway-readiness"' in APP
    assert "Проверить доступность и стоимость" in APP
    runner = _between(
        APP,
        "async function runGenerationPreflight(",
        "async function checkRunwayReadiness(control)",
    )
    assert "state.api.realGenerationPreflight(" in runner
    assert "sku.durationSeconds" in runner
    assert "real_spend_confirmation" not in runner
    assert "startRealGeneration" not in runner
    assert "generationPreflightDecision(previous" in runner
    assert "const joined = await previous.promise" in runner
    assert "generationPreflightContextIsCurrent(requestContext, key)" in runner
    assert "generationPreflightRetryDelay({" in runner
    validator = _between(
        APP,
        "function validateGenerationPreflight",
        "function syncGenerationPreflightUi",
    )
    assert "normalizeGenerationProviderPreflight(" in validator
    assert "gateVersion: GENERATION_LEARNING_GATE_VERSION" in validator
    assert "expectedSelection: sku" in validator
    assert "expectedSelection: sku" in validator
    assert "preflight === null" in validator
    assert "Проверка не создаёт задачу и ничего не списывает." in APP


def test_real_mode_automatically_runs_one_free_deduplicated_preflight() -> None:
    scheduler = _between(
        APP,
        "function scheduleAutomaticGenerationPreflight",
        "async function runGenerationPreflight",
    )
    assert "form.dataset.autoGenerationPreflightKey === key" in scheduler
    assert "window.queueMicrotask" in scheduler
    assert "void runGenerationPreflight(form)" in scheduler
    assert "startRealGeneration" not in scheduler
    assert "real_spend_confirmation" not in scheduler
    assert "scheduleAutomaticGenerationPreflight(form)" in APP
    assert "scheduleAutomaticGenerationPreflight(form)" in APP


def test_transient_preflight_retries_are_bounded_context_bound_and_read_only() -> None:
    recovery = _between(
        APP,
        "function generationPreflightErrorCode",
        "function syncGenerationPreflightUi",
    )
    runner = _between(
        APP,
        "async function runGenerationPreflight(",
        "async function checkRunwayReadiness(control)",
    )
    for token in (
        "generationPreflightRetryDelay({",
        "captureGenerationRequestContext(",
        "generationPreflightContextIsCurrent(retryContext",
        'document.querySelector("#mock-batch-form")',
        "generationPreflightKey(currentSku) === generationPreflightKey(sku)",
        "currentEntry === entry",
            "window.setTimeout(() =>",
        "clearGenerationPreflightRetry(entry)",
    ):
        assert token in recovery
    assert "generationPreflightContextIsCurrent(requestContext, key)" in runner
    identity_guard = _between(
        APP,
        "function generationRequestIdentityIsCurrent(context)",
        "function generationRequestContextIsCurrent(context)",
    )
    context_guard = _between(
        APP,
        "function generationRequestContextIsCurrent(context)",
        "function generationPreflightContextIsCurrent(context, key)",
    )
    assert 'state.route?.path === context.route' in identity_guard
    assert "currentWorkspaceProjectId() === context.projectId" in identity_guard
    assert "generationRequestIdentityIsCurrent(context)" in context_guard
    assert "form?.isConnected" in context_guard
    assert 'document.querySelector("#mock-batch-form") === form' in context_guard
    for token in (
        "automaticRetry = false",
        "awaitRetry = false",
        "continueRetrySeries",
        "previous.retryAttempt + 1",
        "queueGenerationPreflightRetry(sku, entry",
        "retryScheduled: true",
    ):
        assert token in runner
    assert "startRealGeneration" not in recovery
    assert "real_spend_confirmation" not in recovery
    assert "сам повторит бесплатную проверку" in APP
    assert "const retryScheduled = entry.retryAt > Date.now()" in APP
    assert "|| retryScheduled" in APP
    assert "Автоповтор ${entry.retryAttempt} из 2…" in APP
    submit = _between(
        APP,
        "async function submitRealGeneration(form, values, mode)",
        "async function submitMockBatch",
    )
    paid_preflight = _between(
        APP,
        "async function runGenerationPreflightForPaidStart(",
        "async function submitRealGenerationReconciliation(",
    )
    assert 'existing?.status !== "ready"' in paid_preflight
    assert "validateGenerationPreflight(" in paid_preflight
    assert "preflight.spend_confirmation" in paid_preflight
    assert "runGenerationPreflight(form" not in paid_preflight
    assert "await runGenerationPreflightForPaidStart(" in submit
    assert submit.index("await runGenerationPreflightForPaidStart(") < submit.index(
        "state.api.startRealGeneration(payload)"
    )


def test_paid_client_requires_the_exact_deployed_learning_gate_version() -> None:
    assert (
        'const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"'
        in EDGE
    )
    assert (
        'const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"'
        in APP
    )
    assert (
        '"x-contentengine-learning-gate": GENERATION_LEARNING_GATE_VERSION'
        in EDGE
    )


def test_model_prompt_limits_match_the_provider_contract() -> None:
    assert "generationModelCatalogEntry(provider, model)?.promptLimit" in EDGE
    assert "!isBoundedText(value.brief, 1, promptLimit)" in EDGE

    assert "promptMaxLength: Number(catalogModel.promptLimit || 0)" in APP
    assert "brief.maxLength = sku?.promptMaxLength" in APP
    assert "brief.length > generationSku.promptMaxLength" in APP
