from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-product-research/index.ts"
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
VIEW = ROOT / "web/app/product-research-view.js"
BACKGROUND_SQL = (
    ROOT
    / "supabase/migrations/202608040011_research_provider_background_responses.sql"
)
REVALIDATION_SQL = (
    ROOT
    / "supabase/migrations/202608040017_product_research_response_revalidation.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_openai_responses_submit_is_background_non_stored_and_exactly_once() -> None:
    edge = _read(EDGE)
    request_body = _between(
        edge,
        "function openAiRequestBody(",
        "async function fetchWithTimeout(",
    )
    paid_branch = _between(
        edge,
        "} else {\n    const productImageUrls",
        "const outputText",
    )

    assert "background: true" in request_body
    assert "store: false" in request_body
    assert edge.count('method: "POST"') == 1
    assert paid_branch.count('method: "POST"') == 1
    assert "const providerLaunch = await beginBoundedProviderPost(" in paid_branch
    assert "fetchWithTimeout(\n          OPENAI_RESPONSES_URL," in paid_branch
    assert '"idempotency-key": `product-research:${claim.run.id}`' in paid_branch
    assert '"X-Client-Request-Id": claim.run.id' in paid_branch


def test_response_identity_is_bound_before_a_pending_result_is_returned() -> None:
    edge = _read(EDGE)
    paid_branch = _between(
        edge,
        "} else {\n    const productImageUrls",
        "const outputText",
    )

    identity = paid_branch.index("readProviderResponseIdentity(providerValue)")
    bind = paid_branch.index("await bindProviderResponse(", identity)
    receipt = paid_branch.index("await recordProviderResponseStatus(", bind)
    pending = paid_branch.index(
        "if (providerResponsePending(identity.status)) return await pending();",
        receipt,
    )

    assert identity < bind < receipt < pending
    assert '"system_bind_research_provider_response"' in edge
    assert "for (let attempt = 0; attempt < 2; attempt += 1)" in edge


def test_processing_observers_retrieve_by_saved_id_and_never_submit_again() -> None:
    edge = _read(EDGE)
    observer = _between(
        edge,
        "if (!claim.claimed) {",
        "} else {\n    const productImageUrls",
    )

    assert "await readProviderResponse()" in edge
    assert '"system_read_research_provider_response"' in edge
    assert "providerResponseRetrieveUrl(continuation.responseId)" in observer
    assert "export function providerResponseRetrieveUrl(responseId: string)" in edge
    assert "encodeURIComponent(responseId)" in edge
    assert '"include%5B%5D=web_search_call.action.sources"' in edge
    assert 'method: "GET"' in observer
    assert 'method: "POST"' not in observer
    assert "openAiRequestBody(" not in observer
    assert "it never issues another POST" in observer


def test_status_action_cannot_turn_an_unclaimed_queued_run_into_paid_post() -> None:
    edge = _read(EDGE)
    status_gate = edge.index(
        'if (authorized.status === "queued" && payload.action !== "analyze")'
    )
    claim = edge.index('"system_claim_product_research"', status_gate)

    assert 'type AnalyzePayload = {\n  action: "analyze" | "status" | "revalidate";' in edge
    assert "return json(request, authorized.data, 202);" in edge[status_gate:claim]
    assert "fetchWithTimeout(" not in edge[status_gate:claim]
    assert "revalidate" in edge[:status_gate]


def test_browser_status_expiry_is_reclassified_when_a_paid_attempt_exists() -> None:
    migration = _read(BACKGROUND_SQL)
    trigger = _between(
        migration,
        "content_factory_private.classify_attempted_research_expiry()",
        "-- The legacy watchdog labels every expired research lease",
    )

    assert "old.status = 'processing'" in trigger
    assert "new.error_code = 'processing_lease_expired'" in trigger
    assert "content_factory.research_run_provider_bindings" in trigger
    assert "new.error_code := 'provider_outcome_unknown'" in trigger
    assert "before update on content_factory.product_research_runs" in trigger.lower()


def test_saved_response_get_auth_failure_never_becomes_an_ordinary_paid_retry() -> None:
    edge = _read(EDGE)
    continuation = _between(
        edge,
        "if (!claim.claimed) {",
        "} else {\n    const productImageUrls",
    )
    failed_get = _between(
        continuation,
        "if (!providerResponse.ok) {",
        "try {\n      providerValue = await readProviderJson(providerResponse);",
    )

    assert 'failureCode === "provider_authentication_failed"' in failed_get
    assert '"blocked"' in failed_get
    assert 'return await fail(\n        "provider_outcome_unknown"' in failed_get
    assert 'return await fail(\n        failureCode === "provider_authentication_failed"' not in failed_get


def test_saved_response_identity_mismatch_waits_then_closes_as_unknown() -> None:
    edge = _read(EDGE)
    continuation = _between(
        edge,
        "if (!claim.claimed) {",
        "} else {\n    const productImageUrls",
    )
    identity = _between(
        continuation,
        "if (identity === null) {",
        "await recordProviderResponseStatus(\n      providerAttemptId,\n      identity.id",
    )

    assert "responseAge < MAX_BACKGROUND_RESPONSE_AGE_MS" in identity
    assert "return await pending()" in identity
    assert '"provider_outcome_unknown"' in identity
    assert '"provider_response_invalid"' not in identity


def test_worker_dispatches_processing_as_status_and_queued_as_analyze() -> None:
    worker = _read(WORKER)
    research_query = _between(worker, "const researchQuery", "const reviewCandidateLimit")
    research_target = _between(
        worker,
        "...dispatchResearchRows.map((row): DispatchTarget => ({",
        "...dispatchReviewRows.map",
    )

    assert '.eq("status", "queued")' in research_query
    assert "const researchProcessingQuery" in research_query
    assert '.eq("status", "processing")' in research_query
    assert '.order("updated_at", { ascending: true })' in research_query
    assert "MAX_RESEARCH_POLL_LIMIT = 4" in worker
    assert ".limit(payload.research_limit > 0 ? MAX_RESEARCH_POLL_LIMIT : 0)" in research_query
    assert ".update({ updated_at: pollDispatchedAt })" in worker
    assert "researchProcessingRows.length === 0" in worker
    assert "...researchProcessingRows" in worker
    assert "while (dispatchCount() > MAX_TOTAL_DISPATCHES)" in worker
    assert 'action: row.status === "processing" ? "status" : "analyze"' in research_target
    assert 'functionName: "creator-product-research"' in research_target
    assert "research_id: row.id" in research_target
    assert "project_id: row.project_id as string" in research_target


def test_processing_capacity_is_bounded_before_any_fifth_provider_post() -> None:
    sql = _read(BACKGROUND_SQL)
    edge = _read(EDGE)
    capacity = _between(
        sql,
        "content_factory_private.enforce_research_processing_capacity()",
        "-- The legacy watchdog labels every expired research lease",
    )

    assert "old.status = 'queued' and new.status = 'processing'" in capacity
    assert "pg_advisory_xact_lock" in capacity
    assert "contentengine_openai_research_pool" in capacity
    assert "active.status = 'processing'" in capacity
    assert "active.organization_id" not in capacity
    assert "active_count_value >= 4" in capacity
    assert "research_processing_capacity_full" in capacity
    assert "before update on content_factory.product_research_runs" in capacity.lower()
    assert '["queued", "processing"].includes(authorized.status)' in edge


def test_browser_advances_edge_status_before_reading_database_snapshot() -> None:
    api = _read(API)
    status_method = _between(
        api,
        "async productResearchStatus(runId, options = {})",
        "researchCategoryLearningStatus(runId)",
    )
    edge_refresh = status_method.index("await this.invokeProductResearch({")
    edge_action = status_method.index('action: "status"', edge_refresh)
    database_read = status_method.index("this.call(RPC.productResearchStatus")

    assert edge_refresh < edge_action < database_read
    assert "catch (error)" in status_method[edge_action:database_read]
    assert "Research background status refresh unavailable" in status_method


def test_failed_paid_response_can_be_revalidated_without_a_new_provider_post() -> None:
    edge = _read(EDGE)
    api = _read(API)
    app = _read(APP)
    view = _read(VIEW)
    sql = _read(REVALIDATION_SQL)

    revalidation_gate = _between(
        edge,
        'if (payload.action === "revalidate" && authorized.status === "failed")',
        'if (\n    authorized.status === "completed"',
    )
    assert '"system_revalidate_product_research_response"' in revalidation_gate
    assert 'method: "POST"' not in revalidation_gate
    assert "authorized = await readCurrentStatus()" in revalidation_gate

    api_method = _between(
        api,
        "async revalidateProductResearchResponse(runId, options = {})",
        "researchStageControlStatus(runId, options = {})",
    )
    assert 'action: "revalidate"' in api_method
    assert "return this.productResearchStatus" in api_method

    action_handler = _between(
        app,
        'if (action === "revalidate-product-research-response")',
        'if (action === "copy-product-research-support-id")',
    )
    assert "state.api.revalidateProductResearchResponse" in action_handler
    assert "Новый платный запрос не создавался" in action_handler
    assert "provider_response_expired" in action_handler

    assert 'data-action="revalidate-product-research-response"' in view
    assert "Повторно проверить ответ — без оплаты" in view
    assert "не отправляет новый POST" in view

    assert "old.error_code = 'provider_response_invalid'" in sql
    assert "and coalesce(\n      current_setting(" in sql
    assert "provider_attempt_created', false" in sql
    assert "clock_timestamp() - interval '8 minutes'" in sql
    assert "insert into content_factory.research_run_provider_bindings" not in sql
    assert "grant execute on function public.system_revalidate_product_research_response(jsonb)\n  to service_role" in sql
    assert "from public, anon, authenticated" in sql


def test_expired_exact_response_recovery_reserves_one_get_and_never_posts() -> None:
    edge = _read(EDGE)
    handler = edge[edge.index("async function handleCreatorProductResearch(") :]
    recovery = _between(
        handler,
        'if (revalidationCode !== "provider_response_expired")',
        "authorized = await readCurrentStatus()",
    )

    authorize = recovery.index(
        '"creator_authorize_product_research_response_recovery"'
    )
    reserve = recovery.index(
        '"system_claim_product_research_response_recovery"', authorize
    )
    strict_claim = recovery.index("readResponseRecoveryClaim(", reserve)
    assert authorize < reserve < strict_claim
    assert 'recovery_ack: true' in recovery
    assert 'provider_post_allowed !== false' in edge
    assert 'include_web_search_sources !== true' in edge
    assert 'method: "POST"' not in recovery

    claim = handler.index('"system_claim_product_research"', strict_claim)
    post_barrier = handler.index(
        "if (responseRecovery !== null && claim.claimed)", claim
    )
    assert '"system_read_product_research_response_recovery_reservation"' in handler
    reservation_read = handler.index(
        "await readResponseRecoveryReservation()", post_barrier
    )
    reservation_known = handler.index(
        "if (recoveryReservation.getReserved)", reservation_read
    )
    unknown_guard = handler[reservation_read:reservation_known]
    assert "if (recoveryReservation === null)" in unknown_guard
    assert "return await pending()" in unknown_guard
    assert "return await fail(" not in unknown_guard
    replay_barrier = handler.index(
        "if (responseRecovery === null) return await pending()",
        reservation_known,
    )
    continuation_read = handler.index(
        "continuation = await readProviderResponse()", replay_barrier
    )
    continuation_match = handler.index(
        "continuation.responseId !== responseRecovery.providerResponseId",
        continuation_read,
    )
    observer_get = handler.index('method: "GET"', continuation_match)
    paid_launch = handler.index(
        "const providerLaunch = await beginBoundedProviderPost(", observer_get
    )
    paid_post = handler.index('method: "POST"', paid_launch)
    assert (
        claim
        < post_barrier
        < reservation_read
        < replay_barrier
        < continuation_read
        < continuation_match
        < observer_get
        < paid_launch
        < paid_post
    )
    assert handler.count('method: "POST"') == 1
    assert "continuation.attemptId !== responseRecovery.attemptId" in handler
    assert "continuation.model !== responseRecovery.model" in handler
    assert "continuation.acceptedAt !== responseRecovery.acceptedAt" in handler
    assert 'continuation.providerStatus !== "completed"' in handler

    complete = handler.index("const completionStored = await complete(", observer_get)
    record_outcome = handler.index("await recordResponseRecoveryOutcome()", complete)
    assert observer_get < complete < record_outcome


def test_research_requires_fixed_ai_category_from_form_through_api_payload() -> None:
    view = _read(VIEW)
    app = _read(APP)
    api = _read(API)
    start_handler = _between(
        app,
        "async function submitProductResearchStart(form)",
        "async function refreshProductResearch",
    )
    start_api = _between(
        api,
        "async startProductResearch(input, {",
        "async productResearchStatus(runId, options = {})",
    )

    assert 'name="product_category" required' in view
    assert 'values.get("product_category")' in start_handler
    assert "AI_PRODUCT_CATEGORIES.some((category)" in start_handler
    assert "category.key === productCategory" in start_handler
    assert "product_category: productCategory" in start_handler
    assert "AI_PRODUCT_CATEGORY_SET.has(productCategory)" in start_api
    assert "product_category: productCategory" in start_api
    assert 'code: "product_research_ai_category_required"' in start_api


def test_terminal_unknown_outcome_exports_support_id_and_never_auto_retries() -> None:
    edge = _read(EDGE)
    view = _read(VIEW)
    app = _read(APP)
    progress = _between(
        view,
        "export function productResearchProgressMarkup(record, error = \"\")",
        "function researchStageLabel(stage)",
    )
    unknown_markup = _between(
        progress,
        "${providerOutcomeUnknown\n        ? `<div",
        ": responseValidationFailed",
    )

    assert '=== "provider_outcome_unknown"' in progress
    assert 'data-primary-action="true" data-action="copy-product-research-support-id"' in unknown_markup
    assert 'data-action="refresh-product-research"' not in unknown_markup
    assert 'class="btn btn-ghost" type="button" data-action="new-product-research"' in unknown_markup
    assert "Автоматического повтора нет" in unknown_markup
    support_copy = _between(
        app,
        'if (action === "copy-product-research-support-id")',
        'if (action === "generate-research-scenario")',
    )
    assert "navigator.clipboard.writeText" in support_copy
    assert "state.productResearch.record?.id" in support_copy
    new_research = _between(
        app,
        'if (action === "new-product-research")',
        'if (action === "reset-generation-filters")',
    )
    active_guard = new_research.index(
        'productResearchStatusKind(state.productResearch.record?.status) === "active"'
    )
    clear_saved_run = new_research.index("clearProductResearchRunId()")
    prepare_form = new_research.index("beginNewProductResearch({")
    assert active_guard < clear_saved_run < prepare_form
    assert "startProductResearch(" not in new_research
    assert "providerOutcomeUnknown" in progress
    assert edge.count('method: "POST"') == 1
    assert "it never issues another POST" in edge


def test_background_response_receipts_are_append_only_and_service_only() -> None:
    sql = _read(BACKGROUND_SQL).lower()

    assert "create table if not exists content_factory.research_provider_response_bindings" in sql
    assert "create table if not exists content_factory.research_provider_response_receipts" in sql
    assert "unique (organization_id, run_id)" in sql
    assert "unique (provider_key, provider_response_id)" in sql
    assert "reject_research_provider_mutation" in sql
    assert "research_provider_response_binding_immutable" in sql
    assert "research_provider_response_receipt_append_only" in sql
    assert "system_bind_research_provider_response" in sql
    assert "system_read_research_provider_response" in sql
    assert "system_record_research_provider_response_status" in sql
    assert "grant execute on function public.system_bind_research_provider_response(jsonb)\n  to service_role" in sql
    assert "grant execute on function public.system_read_research_provider_response(jsonb)\n  to service_role" in sql


def test_queued_research_explains_that_it_waits_without_a_second_charge() -> None:
    view = _read(VIEW)

    assert "waitingForProviderSlot" in view
    assert "Ожидает свободного места у провайдера" in view
    assert "нового запроса и списания портал не создаст" in view
