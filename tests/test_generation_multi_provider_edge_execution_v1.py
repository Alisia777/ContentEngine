from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
SNAPSHOT = (
    ROOT / "supabase/functions/_shared/generation-selection-snapshot.js"
).read_text(encoding="utf-8")
PROMPT_COMPILER = (
    ROOT / "web/app/content-generation-handoff.js"
).read_text(encoding="utf-8")


def _between(start: str, end: str, *, source: str = EDGE) -> str:
    start_at = source.index(start)
    return source[start_at : source.index(end, start_at)]


def test_executable_shortlist_is_exact_and_premium_models_stay_blocked() -> None:
    execution = _between(
        "const LIVE_GENERATION_EXECUTION_KEYS",
        "const RUNWAY_PROVIDER_ENDPOINTS",
    )
    assert {
        "runway:gen4_turbo",
        "runway:seedance2_fast",
        "runway:seedream5_lite",
        "runway:gen4.5",
        "runway:seedance2_mini",
        "runway:veo3.1_fast",
        "runway:gemini_omni_flash",
        "google:veo-3.1-lite-generate-preview",
    } == {
        line.split('"')[1]
        for line in execution.splitlines()
        if line.strip().startswith('"')
    }


def test_every_new_launch_is_authorized_by_exact_server_policy() -> None:
    parser = _between(
        "function readGenerationProviderPolicy(",
        "type ExactGenerationSku",
    )
    for key in (
        '"ok"',
        '"provider"',
        '"model"',
        '"launch_enabled"',
        '"catalog_version"',
        '"automatic_generation"',
        '"automatic_spend"',
    ):
        assert key in parser
    assert '"creator_generation_provider_policy"' in EDGE
    assert '"creator_generation_model_feature_flags"' in EDGE
    assert "generationFeatureFlags" not in EDGE
    assert "modelFeatureFlags.googleVeoLite" in EDGE
    assert "modelFeatureFlags.runwayPremium" in EDGE
    assert "policy?.launchEnabled === true" in EDGE

    preflight = _between(
        "const handlePreflight = async",
        "const preflightPayload = readPreflightPayload",
    )
    assert preflight.index("await loadProviderPolicy(") < preflight.index(
        "const exact = exactGenerationSku("
    )
    start = _between(
        "const startPayload = readStartPayload(body)",
        "if (!generationModePromptIsBound(startPayload))",
    )
    assert start.index("await loadProviderPolicy(") < start.index(
        "const startSku = exactGenerationSku("
    )
    assert 'code: "generation_provider_launch_disabled"' in preflight
    assert 'code: "generation_provider_launch_disabled"' in start


def test_successful_preflight_emits_strict_v3_receipt_and_server_token() -> None:
    handler = _between(
        "const handlePreflight = async",
        "const preflightPayload = readPreflightPayload",
    )
    expected = {
        "version",
        "receipt_id",
        "receipt_hash",
        "organization_id",
        "checked_by",
        "provider",
        "model",
        "input_mode",
        "duration_seconds",
        "format",
        "resolution",
        "audio",
        "last_frame",
        "ready",
        "estimated_cost_minor",
        "estimated_credits",
        "credential_configured",
        "balance_sufficient",
        "model_available",
        "daily_quota_available",
        "failure_code",
        "catalog_version",
        "pricing_version",
        "learning_gate_version",
        "checked_at",
        "expires_at",
        "status",
        "fresh",
        "spend_confirmation",
        "automatic_generation",
        "automatic_spend",
    }
    block = _between("      preflight: {", "      },\n    });", source=handler)
    emitted = {
        line.strip().split(":", 1)[0]
        for line in block.splitlines()[1:]
        if line.startswith("        ")
        and not line.startswith("          ")
        and ":" in line
    }
    assert emitted == expected
    assert 'version: "generation-provider-readiness-receipt-v3"' in block
    assert "receipt_version" not in handler
    assert "spend_confirmation: readiness.spendConfirmation" in block
    assert "failure_code: null" in block


def test_start_uses_the_single_shared_section_12_snapshot_contract() -> None:
    assert "GENERATION_SELECTION_SNAPSHOT_FIELDS" in EDGE
    assert "readGenerationSelectionSnapshot(" in EDGE
    matcher = _between(
        "function startSelectionSnapshotMatches(",
        "function publicExecutionPolicy(",
    )
    for field in (
        "recommendation_catalog_version",
        "pricing_version",
        "estimated_cost_minor",
        "requested_duration_seconds",
        "requested_ratio",
        "requested_resolution",
        "requested_audio",
        "input_mode",
        "reference_count",
        "provider_readiness_receipt_id",
    ):
        assert f"snapshot.{field}" in matcher
    assert "provider_readiness_receipt_hash" not in matcher
    assert '"version"' not in matcher
    assert "provider_readiness_receipt_hash" in _between(
        "function readStartPayload(",
        "function readPreflightPayload(",
    )
    snapshot_fields = _between(
        "export const GENERATION_SELECTION_SNAPSHOT_FIELDS",
        "const EXACT_SELECTION_KEYS",
        source=SNAPSHOT,
    )
    assert snapshot_fields.count('  "') == 17


def test_paid_boundary_dispatches_one_provider_post_and_never_blind_retries() -> None:
    paid = _between(
        "const claim = await claimSystemJob(current.id)",
        "const submittedPayload",
    )
    assert paid.count("createResponse = await fetchProviderJsonWithDeadline(") == 1
    assert paid.count("serializedProviderRequest = JSON.stringify(providerRequest.body)") == 1
    assert paid.count("body: serializedProviderRequest") == 1
    assert "MAX_GOOGLE_PROVIDER_REQUEST_BYTES" in paid
    assert "serializedRequestBytes > providerRequestLimit" in paid
    assert "provider_create_timeout" in paid
    assert "provider_create_http_unknown" in paid
    assert "provider_create_response_unknown" in paid
    assert paid.count("markReconciliationRequired(") == 3
    assert "createResponse = await fetchProviderJsonWithDeadline(" not in EDGE[
        EDGE.index("const submittedPayload") :
    ]


def test_google_chain_has_direct_auth_lro_output_storage_and_safe_redirects() -> None:
    for token in (
        'Deno.env.get("GEMINI_API_KEY")',
        '"x-goog-api-key": secret',
        'pollKind: "runway_task" | "google_long_running_operation"',
        "/v1beta/models/${GOOGLE_VEO_LITE_MODEL}:predictLongRunning",
        "parseCreatedGoogleOperation(createdValue)",
        "parseGoogleOperation(providerValue)",
        "response.generateVideoResponse",
        "generated.generatedSamples",
        'url.hostname === "storage.googleapis.com"',
        'url.hostname.endsWith(".googleusercontent.com")',
        "await fetchGoogleOutput(outputUrl, secret)",
        "supabaseAdmin.storage.from(STORAGE_BUCKET)",
    ):
        assert token in EDGE
    redirects = _between(
        "async function fetchGoogleOutput(",
        "function validateSupabaseSignedUrl(",
    )
    assert 'currentUrl.hostname === "generativelanguage.googleapis.com"' in redirects
    assert '"x-goog-api-key": apiKey' in redirects
    assert "redirect: \"manual\"" in redirects


def test_polling_output_and_reconciliation_are_provider_aware() -> None:
    assert '.in("provider", ["runway", "google"])' in EDGE
    assert "isValidProviderTaskId(current.provider, current.providerTaskId)" in EDGE
    assert 'current.provider === "google"' in EDGE
    assert "validateGoogleOutputUrl(providerValue.output[0])" in EDGE
    for token in (
        "GOOGLE_OPERATION_ID_VERIFIED",
        "GOOGLE_NO_OPERATION_VERIFIED",
        "RUNWAY_TASK_ID_VERIFIED",
        "RUNWAY_NO_TASK_VERIFIED",
    ):
        assert token in EDGE
    parser = _between(
        "function readReconcilePayload(",
        "function rpcPayload(",
    )
    assert "isValidGoogleOperationName(value.provider_task_id)" in parser
    handler = _between(
        "const handleReconciliation = async",
        "const handlePreflight = async",
    )
    assert "authorization.provider === \"google\"" in handler
    assert "isValidProviderTaskId(" in handler
    assert "expectedConfirmation" in handler
    assert "GOOGLE_OPERATION_NAME_PATTERN" in EDGE
    assert "createdAt: null" in handler
    assert "providerTask?.createdAt === null" in handler
    assert 'if (authorization.provider === "runway") {' in handler
    assert "systemPayload.provider_task_created_at = providerTask.createdAt" in handler
    assert "createdAt: authorization.startingAt" not in handler
    assert '!googleOperation.done\n            ? "RUNNING"' in handler
    assert 'googleOperation.error !== null\n            ? "FAILED"' in handler


def test_executable_catalog_copy_describes_only_the_projected_image_route() -> None:
    omni_policy = _between(
        '"runway:gemini_omni_flash": {',
        '"google:veo-3.1-lite-generate-preview": {',
    )
    assert '"быстрый ролик со звуком из одного исходного кадра"' in omni_policy
    assert '"короткий UGC-черновик с речью"' in omni_policy
    assert '"вариация готового видео в текущем маршруте"' in omni_policy
    assert '"1080p, 4K или точный последний кадр"' in omni_policy
    catalog_response = _between(
        "const modelCatalogPayload = readModelCatalogPayload(body)",
        "const readCurrentStatus = async",
    )
    assert "...executionPolicy" in catalog_response


def test_generation_spec_gate_accepts_only_catalog_valid_new_model_scope() -> None:
    scope = _between(
        "function readGenerationSpecScope(",
        "function readGenerationSpecEffectivePolicy(",
    )
    for key in (
        '"provider"',
        '"input_mode"',
        '"ratio"',
        '"resolution"',
        '"spoken_dialogue"',
        '"reference_count"',
        '"reference_video"',
        '"first_frame"',
        '"last_frame"',
    ):
        assert key in scope
    assert "const exact = exactGenerationSku(" in scope
    assert "generationExecutionSemantics(" in scope
    assert "value.ratio !== value.format" in scope
    assert "value.reference_count !== exact.referenceImageCount" in scope
    runway_reader = _between(
        "function readRunwayModel(",
        "function readGenerationProvider(",
    )
    for model in (
        '"gen4.5"',
        '"seedance2_mini"',
        '"gemini_omni_flash"',
    ):
        assert model in runway_reader
    assert "readGenerationModel(provider, value.model)" in scope


def test_exact_sku_uses_catalog_capabilities_not_legacy_ratio_allowlists() -> None:
    exact = _between(
        "function exactGenerationSku(",
        "function startSelectionSnapshotMatches(",
    )
    assert "validateGenerationModelSelection(entry, selection" in exact
    assert "estimateGenerationModelCostMinor(entry, validated" in exact
    assert 'new Set(["9:16", "1:1", "16:9"])' not in exact
    start_parser = _between(
        "function readStartPayload(",
        "function readPreflightPayload(",
    )
    preflight_parser = _between(
        "function readPreflightPayload(",
        "function readModelCatalogPayload(",
    )
    assert 'new Set(["9:16", "1:1", "16:9"])' not in start_parser
    assert 'new Set(["9:16", "1:1", "16:9"])' not in preflight_parser
    reverse = _between(
        "function publicRatioFromProvider(",
        "function readGenerationSku(",
    )
    assert ".server?.providerRatios?.[resolution]" in reverse
    assert "Object.entries(ratios)" in reverse
    catalog_response = _between(
        "const modelCatalogPayload = readModelCatalogPayload(body)",
        "const readCurrentStatus = async",
    )
    assert "const executionPolicy = publicExecutionPolicy(" in catalog_response
    assert 'inputModes: ["image"]' in catalog_response
    assert "inputCapabilities: {" in catalog_response
    assert "allowedRatios," in catalog_response
    assert "allowedResolutions," in catalog_response
    assert "maxReferenceImages," in catalog_response
    assert "supportsFirstFrame: firstFrameSupported" in catalog_response
    assert "supportsLastFrame: lastFrameSupported" in catalog_response
    seedream_policy = _between(
        '"runway:seedream5_lite": {',
        '"runway:gen4_turbo": {',
    )
    assert 'allowedRatios: ["1:1"]' in seedream_policy
    assert 'allowedResolutions: ["2K"]' in seedream_policy


def test_new_model_prompt_guards_match_the_existing_client_compiler_exactly() -> None:
    prompt_gate = _between(
        "function generationModePromptIsBound(",
        "function productInteractionRequirement(",
    )
    assert "РЎ" not in prompt_gate
    assert "Рµ" not in prompt_gate
    exact_literals = (
        "Без речи, дикторского текста и сгенерированных надписей.",
        "Без сгенерированных надписей, субтитров и декоративного текста.",
    )
    for literal in exact_literals:
        assert literal in prompt_gate or literal in EDGE[: EDGE.index("const RUNWAY_OUTPUT_HOST")]
        assert literal in PROMPT_COMPILER
    for literal in (
        "Создай один непрерывный ролик длительностью ${payload.duration_seconds} секунд с соотношением сторон ${payload.format}.",
        "Создай один непрерывный UGC-ролик длительностью ${payload.duration_seconds} секунд с соотношением сторон ${payload.format}.",
    ):
        assert literal in prompt_gate
    for model in (
        '"gen4.5": silentVideoRequirements',
        "seedance2_mini: audioVideoRequirements",
        '"veo3.1_fast": payload.audio',
        "gemini_omni_flash: audioVideoRequirements",
        '"veo-3.1-lite-generate-preview": audioVideoRequirements',
    ):
        assert model in prompt_gate
