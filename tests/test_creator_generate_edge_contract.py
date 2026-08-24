from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
PROVIDER_ADAPTER_PATH = (
    ROOT / "supabase/functions/_shared/generation-provider-adapters.js"
)
WORKFLOW_PATH = ROOT / ".github/workflows/supabase-pages.yml"
PAGES_BUILDER_PATH = ROOT / "scripts/build_pages_release.py"


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _call_arguments(source: str, function_name: str) -> list[str]:
    marker = f"{function_name}("
    calls: list[str] = []
    cursor = 0
    while True:
        start = source.find(marker, cursor)
        if start < 0:
            return calls
        index = start + len(marker)
        depth = 1
        while index < len(source) and depth:
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
            index += 1
        assert depth == 0, f"unterminated {function_name} call"
        calls.append(source[start + len(marker) : index - 1])
        cursor = index


def test_real_generation_edge_function_is_authenticated_and_origin_bound() -> None:
    source = _source()
    config = tomllib.loads(
        (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    )

    assert SOURCE_PATH.is_file()
    assert config["functions"]["creator-generate"]["verify_jwt"] is True
    assert 'auth: "user"' in source
    assert 'const PUBLIC_APP_ORIGIN = "https://alisia777.github.io"' in source
    assert 'const LOCAL_QA_APP_ORIGIN = "http://127.0.0.1:8767"' in source
    assert (
        'const LOCAL_SANDBOX_APP_ORIGIN = "http://127.0.0.1:8768"'
        in source
    )
    assert "LOCAL_SANDBOX_APP_ORIGIN," in source
    assert 'USER_APP_ORIGINS.has(request.headers.get("origin") ?? "")' in source
    assert '"access-control-allow-origin", origin' in source
    assert '"access-control-allow-origin", "*"' not in source
    assert 'request.method !== "POST"' in source
    assert "MAX_BODY_BYTES" in source
    assert "readBoundedStream(request.body, MAX_BODY_BYTES)" in source
    assert "request.text()" not in source
    assert 'content_type_invalid' in source
    assert 'context.userClaims?.id' in source
    assert 'action: "start"' in source
    assert 'action: "status"' in source
    assert 'return creatorGenerate(request)' in source


def test_generation_status_and_readback_are_fail_closed_to_exact_project() -> None:
    source = _source()
    status_type = source[
        source.index("type StatusPayload") : source.index("type ReconcilePayload")
    ]
    status_parser = source[
        source.index("function readStatusPayload") : source.index(
            "function readReconcilePayload"
        )
    ]
    status_reader = source[
        source.index("const readCurrentStatus") : source.index(
            "const updateSystemJob"
        )
    ]

    assert "project_id: string;" in status_type
    assert "project_id?: string;" not in status_type
    assert '"project_id",' in status_parser
    assert "!isUuid(value.project_id)" in status_parser
    assert "projectId: string" in status_reader
    assert "projectId?: string" not in status_reader
    assert '.eq("project_id", projectId)' in status_reader
    assert "data.project_id !== projectId" in status_reader
    assert "project_id: projectId" in status_reader
    assert "...(projectId ?" not in status_reader

    for function_name in (
        "readCurrentStatus",
        "respondWithCurrent",
        "respondProviderUnavailable",
    ):
        calls = _call_arguments(source, function_name)
        assert calls, f"expected calls to {function_name}"
        assert all(
            "projectId" in arguments or "project_id" in arguments
            for arguments in calls
        ), f"{function_name} call dropped project_id"


def test_generation_reconciliation_requires_and_accepts_exact_project() -> None:
    source = _source()
    reconcile_type = source[
        source.index("type ReconcilePayload") : source.index(
            "type ReconciliationContext"
        )
    ]
    reconcile_parser = source[
        source.index("function readReconcilePayload") : source.index(
            "function rpcPayload"
        )
    ]

    assert "project_id: string;" in reconcile_type
    assert '"project_id",' in reconcile_parser
    assert "!isUuid(value.project_id)" in reconcile_parser
    assert (
        'const allowed = new Set([...required, "provider_task_id"]);'
        in reconcile_parser
    )


def test_real_generation_requires_explicit_spend_confirmation_and_db_claim() -> None:
    source = _source()

    for marker in (
        'value.mode !== "real"',
        "readGenerationProvider(value.provider)",
        "readGenerationModel(provider, value.model)",
        "LIVE_GENERATION_EXECUTION_KEYS",
        'value.allow_real_spend !== true',
        "minimumDuration: 2",
        "maximumDuration: 10",
        "creditsPerSecond: 5",
        "minimumDuration: 4",
        "maximumDuration: 15",
        "creditsPerSecond: 29",
        "readRunwayGenerationSku(",
        "startPayload.spend_confirmation !== startSku.confirmation",
        '"creator_start_real_generation"',
        '"creator_real_generation_status"',
        '"system_update_real_generation"',
        'status: "starting"',
        'claim.claimed',
        'current.status !== "queued"',
    ):
        assert marker in source

    claim = source.index('status: "starting"')
    provider_call = source.index("createResponse = await fetchProviderJsonWithDeadline(", claim)
    submitted = source.index('status: "submitted"', provider_call)
    assert claim < provider_call < submitted
    assert "cron" not in source.casefold()
    assert "schedule" not in source.casefold()


def test_paid_provider_post_is_guarded_by_sanitized_database_budget_claim() -> None:
    source = _source()

    for code in (
        "paid_generation_paused",
        "paid_generation_policy_missing",
        "generation_daily_budget_exceeded",
        "generation_monthly_budget_exceeded",
        "generation_per_request_budget_exceeded",
        "generation_budget_reservation_invalid",
        "generation_budget_policy_changed",
    ):
        assert f'"{code}"' in source

    sanitizer = source[source.index("function readBudgetErrorCode") : source.index(
        "function budgetErrorHttpStatus"
    )]
    assert "BUDGET_ERROR_CODES.has(value.message)" in sanitizer
    assert "includes(" not in sanitizer
    claim_sanitizer = source[
        source.index("function readClaimErrorCode") : source.index(
            "function budgetErrorHttpStatus"
        )
    ]
    assert 'code === "real_generation_reconciliation_required"' in claim_sanitizer
    assert 'code === "generation_spec_provider_start_stale"' in claim_sanitizer
    assert 'typeof value.message === "string"' in claim_sanitizer
    assert 'typeof value.code === "string"' in claim_sanitizer

    start = source.index("const claim = await claimSystemJob(current.id)")
    provider_post = source.index("createResponse = await fetchProviderJsonWithDeadline(", start)
    claim_guard = source[start:provider_post]
    assert 'claim.outcome === "budget_rejected"' in claim_guard
    assert 'claim.outcome !== "claimed"' in claim_guard
    assert "if (!claim.claimed)" in claim_guard
    assert "budgetErrorHttpStatus(claim.code)" in claim_guard
    assert 'claim.code === "real_generation_reconciliation_required"' in claim_guard
    assert "? 409" in claim_guard


def test_paid_start_preserves_safe_database_rejection_codes() -> None:
    source = _source()

    sanitizer = source[
        source.index("function readSafeStartRpcErrorCode") : source.index(
            "function readClaimErrorCode"
        )
    ]
    assert "value.message.trim()" in sanitizer
    assert "(?:real_|paid_)?generation" in sanitizer
    assert "[a-z0-9_]{2,95}" in sanitizer
    assert "safeStartRpcCode ??" in source
    assert '"generation_rejected"' in source


def test_provider_task_transitions_preserve_task_id_and_processing_order() -> None:
    source = _source()

    assert "providerTaskId?: string" in source
    assert "failurePayload.provider_task_id = providerTaskId" in source
    assert "provider_task_id: current.providerTaskId" in source
    succeeded_poll = source.index('providerTask.status !== "SUCCEEDED"')
    force_processing = source.index('current.status === "submitted"', succeeded_poll)
    output_download = source.index("const outputUrl", force_processing)
    mark_succeeded = source.index('status: "succeeded"', output_download)
    assert succeeded_poll < force_processing < output_download < mark_succeeded


def test_runway_request_and_polling_are_fixed_to_reviewed_contract() -> None:
    source = _source()
    adapter = PROVIDER_ADAPTER_PATH.read_text(encoding="utf-8")

    assert 'const RUNWAY_API_ORIGIN = "https://api.dev.runwayml.com"' in source
    assert 'const RUNWAY_API_VERSION = "2024-11-06"' in source
    assert 'Deno.env.get("RUNWAYML_API_SECRET")' in source
    assert 'authorization: `Bearer ${secret}`' in source
    assert "buildGenerationProviderRequest(entry, selected, input)" in source
    assert "serializedProviderRequest = JSON.stringify(providerRequest.body)" in source
    assert "body: serializedProviderRequest" in source
    assert "function buildGen4(" in adapter
    assert "function buildSeedance(" in adapter
    for marker in (
        "model: entry.model",
        "duration: selection.durationSeconds",
        "ratio: providerRatio",
        "promptText: exactPrompt(input, entry)",
        '"firstFrameUrl"',
        "references.map((uri)",
        "audio: selection.audio",
    ):
        assert marker in adapter
    seedance_request = adapter[
        adapter.index("function buildSeedance(") : adapter.index(
            "\nfunction buildRunwayVeo(", adapter.index("function buildSeedance(")
        )
    ]
    reference_mode = seedance_request[
        seedance_request.index("body.promptImage = references.length") :
        seedance_request.index("} else {", seedance_request.index("body.promptImage = references.length"))
    ]
    assert "references.map((uri) => ({ uri }))" in reference_mode
    assert "body.references" not in reference_mode
    assert '`${RUNWAY_API_ORIGIN}/v1/tasks/${current.providerTaskId}`' in source
    assert "const MIN_PROVIDER_POLL_INTERVAL_MS = 5_000;" in source
    compact = " ".join(source.split())
    assert (
        "Date.now() - Date.parse(current.updatedAt) < "
        "MIN_PROVIDER_POLL_INTERVAL_MS"
    ) in compact
    for status in (
        "PENDING",
        "THROTTLED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
        "CANCELLED",
    ):
        assert f'"{status}"' in source
    assert 'TASK_ID_PATTERN' in source
    assert 'redirect: "manual"' in source


def test_ambiguous_provider_start_never_releases_spend_lock() -> None:
    source = _source()
    create_start = source.index("const providerEndpoint =")
    submitted = source.index('status: "submitted"', create_start)
    create_section = source[create_start:submitted]

    assert "STARTING_TIMEOUT_MS" not in source
    assert 'current.status === "starting"' in source
    assert "respondProviderUnavailable" in create_section
    assert "DEFINITIVE_CREATE_HTTP_STATUSES.has(createResponse.status)" in (
        create_section
    )
    assert "408" not in source[source.index("DEFINITIVE_CREATE_HTTP_STATUSES") : source.index("JOB_STATUSES")]
    assert "provider_timeout" not in create_section
    assert "provider_response_invalid" not in create_section


def test_persisted_provider_task_only_terminal_fails_on_explicit_task_failure() -> None:
    source = _source()
    status_start = source.index("const handleStatus")
    status_end = source.index("const statusPayload", status_start)
    status_section = source[status_start:status_end]

    assert status_section.count("markFailed(") == 2
    google_failure = status_section.index("markFailed(")
    assert 'if (operation.error !== null)' in status_section[:google_failure]
    task_failure = status_section.index("markFailed(", google_failure + 1)
    failure_guard = status_section.rfind('providerTask.status === "FAILED"', 0, task_failure)
    cancelled_guard = status_section.rfind(
        'providerTask.status === "CANCELLED"', 0, task_failure
    )
    assert failure_guard >= 0
    assert cancelled_guard >= 0
    assert "respondProviderUnavailable" in status_section


def test_output_is_allowlisted_bounded_verified_and_privately_persisted() -> None:
    source = _source()

    assert (
        'const RUNWAY_OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net"' in source
    )
    # Хост результата проверяется по белому списку своего провайдера: у Runway
    # он один, у fal — известный набор. Разрешать «любой https» нельзя.
    assert 'url.hostname === RUNWAY_OUTPUT_HOST' in source
    # У fal готовые файлы раздаются с меняющихся узлов одного домена (v3, v3b
    # и далее), поэтому проверяется домен и его поддомены, а не перечень узлов:
    # жёсткий перечень однажды уже сделал оплаченный ролик недоступным. Чужой
    # хост так не пройдёт — сравнение либо точное, либо по суффиксу с точкой.
    assert "falOutputHostAllowed(url.hostname)" in source
    assert 'const FAL_OUTPUT_DOMAINS = Object.freeze(["fal.media"]);' in source
    assert "hostname === domain || hostname.endsWith(`.${domain}`)" in source
    assert ": false;" in source
    assert 'url.protocol !== "https:"' in source
    assert 'const MAX_OUTPUT_BYTES = 52_428_800' in source
    for output_mime in (
        '"video/mp4"',
        '"application/mp4"',
        '"application/octet-stream"',
    ):
        assert output_mime in source
    assert 'bytes[4] === 0x66' in source
    assert 'crypto.subtle.digest("SHA-256", bytes)' in source
    assert 'const STORAGE_BUCKET = "contentengine-private"' in source
    assert 'contentType: "video/mp4"' in source
    assert 'upsert: true' in source
    assert 'metadata: { sha256: digest }' in source
    assert 'output_object_name: current.outputObjectName' in source
    assert 'sha256: digest' in source
    assert ".createSignedUrl(" in source
    assert "job.outputObjectName" in source
    assert "OUTPUT_URL_TTL_SECONDS" in source
    assert "OUTPUT_ACCESS_TIMEOUT_MS" in source
    assert 'signed_url' in source


def test_provider_errors_and_ephemeral_urls_are_not_returned_raw() -> None:
    source = _source()

    assert "providerValue.error" not in source
    assert "providerValue.failure" not in source
    assert "signed_url: outputUrl" not in source
    assert "signed_url: signedInputUrl" not in source
    assert "provider_error:" not in source
    assert "console.log" not in source
    assert "console.error" not in source
    assert "error.message" not in source
    assert "RUNWAYML_API_SECRET:" not in source
    for safe_code in (
        "provider_authentication_failed",
        "provider_credits_unavailable",
        "provider_rate_limited",
        "provider_request_rejected",
        "provider_task_failed",
        "provider_timeout",
        "provider_response_invalid",
        "output_download_failed",
        "output_validation_failed",
        "output_upload_failed",
    ):
        assert safe_code in source


def test_refusals_leave_a_redacted_trace_in_the_function_log() -> None:
    # Отказы платного пути обязаны попадать в function_logs. Без этого пустой
    # лог заставлял разбирать поломку часами: наружу уходил только непрозрачный
    # generation_unavailable, а причина не сохранялась нигде.
    source = _source()

    # Единственный сток, который Edge-рантайм пересылает в function_logs.
    # console.log/console.error по-прежнему запрещены тестом выше.
    assert "console.warn" in source

    # Каждый ответ со статусом >= 400 обязан слить накопленный след.
    assert "if (status >= 400) flushGenerationRefusal(request, body, status);" \
        in source

    # След живёт в WeakMap по объекту Request: параллельные вызовы внутри
    # одного изолята не должны смешивать причины отказов между собой.
    assert "const refusalTrails = new WeakMap<Request, string[]>();" in source
    assert "refusalTrails.delete(request);" in source

    # Редакция — это белый список, а не чёрный. Любое значение вне точных
    # шаблонов схлопывается в "unclassified", поэтому в лог не могут попасть
    # секреты, промпты, подписанные ссылки, тела провайдера и текст ошибок БД.
    assert "const REFUSAL_CODE_PATTERN = /^[a-z0-9_]{3,110}$/u;" in source
    assert "const REFUSAL_STAGE_PATTERN = /^[a-z0-9_.]{3,60}$/u;" in source
    assert '"unclassified"' in source

    # Одного класса символов мало: ключ вида key_live_9f3ab77c... целиком
    # состоит из [a-z0-9_] и прошёл бы как «код». Поэтому каждый сегмент
    # обязан быть коротким словом — так энтропия отсекается по форме.
    assert "REFUSAL_CODE_SEGMENT_PATTERN" in source
    assert "/^(?:[a-z]{1,24}[0-9]{0,3}|[0-9]{1,4})$/u;" in source
    assert "code.split(\"_\").every((segment) =>" in source

    # Код провайдера логируется только из уже санированной таксономии,
    # и проверяется тем же правилом формы слова.
    assert (
        "const REFUSAL_PROVIDER_CODE_PATTERN = /^[A-Z0-9][A-Z0-9._-]{0,59}$/u;"
        in source
    )
    assert "REFUSAL_PROVIDER_SEGMENT_PATTERN" in source
    assert "/^(?:[A-Z]{1,24}[0-9]{0,3}|[0-9]{1,4})$/u;" in source
    assert "code.split(/[._-]/u).every((segment) =>" in source

    # Упавшая оплаченная задача отвечает HTTP 200 с failed-джобой в теле,
    # поэтому её причина пишется напрямую, а не через слив отказов.
    assert 'logGenerationJobFailure("job.marked_failed", safeCode, {' in source

    # Ключевые швы платного маршрута инструментированы поимённо.
    for stage in (
        '"start.claim_budget_rejected"',
        '"start.claim_terminal"',
        '"start.claim_unavailable"',
        '"start.reserved_job_mismatch"',
        '"strategy_start.claim_rpc_rejected"',
        '"strategy_start.continuation_refused"',
        '"strategy_status.projection_unavailable"',
    ):
        assert stage in source

    # Наружу контракт не меняется: пользователь по-прежнему видит только код.
    assert 'reason: trail.length > 0 ? trail : ["not_instrumented"]' in source


def test_production_workflow_masks_sets_and_deploys_video_provider_secrets() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    builder = PAGES_BUILDER_PATH.read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    migrate = workflow["jobs"]["migrate"]
    steps = migrate["steps"]

    secret_step = next(
        step
        for step in steps
        if step.get("name") == "Synchronize private Runway API secret"
    )
    assert secret_step["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "RUNWAYML_API_SECRET": "${{ secrets.RUNWAYML_API_SECRET }}",
    }
    assert 'echo "::add-mask::$RUNWAYML_API_SECRET"' in secret_step["run"]
    assert "supabase secrets set" in secret_step["run"]
    assert 'RUNWAYML_API_SECRET="$RUNWAYML_API_SECRET"' in secret_step["run"]
    fal_secret_step = next(
        step
        for step in steps
        if step.get("name") == "Synchronize private fal.ai API secret"
    )
    assert fal_secret_step["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "FAL_KEY": "${{ secrets.FAL_KEY }}",
    }
    assert 'echo "::add-mask::$FAL_KEY"' in fal_secret_step["run"]
    assert "supabase secrets set" in fal_secret_step["run"]
    assert 'FAL_KEY="$FAL_KEY"' in fal_secret_step["run"]
    require_step = next(
        step
        for step in steps
        if step.get("name") == "Require production Supabase coordinates"
    )
    assert require_step["env"]["FAL_KEY"] == "${{ secrets.FAL_KEY }}"
    assert "${FAL_KEY:?Configure FAL_KEY in the production environment}" in (
        require_step["run"]
    )
    deploy = next(
        step
        for step in steps
        if step.get("name") == "Deploy authenticated real generation function"
    )
    assert deploy["run"] == (
        'supabase functions deploy creator-generate '
        '--project-ref "$SUPABASE_PROJECT_REF"'
    )
    assert "--no-verify-jwt" not in deploy["run"]
    assert "RUNWAYML_API_SECRET" not in workflow["jobs"]["build-pages"]["env"]
    assert "FAL_KEY" not in workflow["jobs"]["build-pages"]["env"]
    reject_secrets_step = next(
        step
        for step in workflow["jobs"]["build-pages"]["steps"]
        if step.get("name") == "Reject server secrets and localhost from Pages artifact"
    )
    assert "FAL_KEY" in reject_secrets_step["run"]
    assert "\nFAL_KEY=\n" in env_example
    assert '"MOCK_ONLY"' not in builder
    assert '"MOCK_ENABLED": True' in builder
    assert '"REAL_GENERATION_ENABLED": True' in builder
    assert '"REAL_PROVIDER": "runway"' in builder
    assert '"REAL_MODEL": "gen4_turbo"' in builder
    assert '"REAL_ESTIMATED_COST_USD": 0.25' in builder


def test_ci_formats_lints_and_checks_both_edge_functions() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for function_name in ("creator-invite", "creator-generate"):
        assert f"deno fmt --check supabase/functions/{function_name}" in text
        assert f"deno lint supabase/functions/{function_name}/index.ts" in text
        assert f"deno check supabase/functions/{function_name}/index.ts" in text
