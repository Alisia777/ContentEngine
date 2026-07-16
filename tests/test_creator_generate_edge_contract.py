from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
WORKFLOW_PATH = ROOT / ".github/workflows/supabase-pages.yml"


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def test_real_generation_edge_function_is_authenticated_and_origin_bound() -> None:
    source = _source()
    config = tomllib.loads(
        (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    )

    assert SOURCE_PATH.is_file()
    assert config["functions"]["creator-generate"]["verify_jwt"] is True
    assert 'auth: "user"' in source
    assert 'const PUBLIC_APP_ORIGIN = "https://alisia777.github.io"' in source
    assert 'request.headers.get("origin") !== PUBLIC_APP_ORIGIN' in source
    assert 'request.method !== "POST"' in source
    assert "MAX_BODY_BYTES" in source
    assert "readBoundedStream(request.body, MAX_BODY_BYTES)" in source
    assert "request.text()" not in source
    assert 'content_type_invalid' in source
    assert 'context.userClaims?.id' in source
    assert 'action: "start"' in source
    assert 'action: "status"' in source
    assert 'return creatorGenerate(request)' in source


def test_real_generation_requires_explicit_spend_confirmation_and_db_claim() -> None:
    source = _source()

    for marker in (
        'value.mode !== "real"',
        'value.provider !== "runway"',
        'value.model === "gen4_turbo"',
        'value.duration_seconds === 5',
        'value.model === "seedance2_fast"',
        'value.duration_seconds === 8',
        'value.audio === true',
        'value.allow_real_spend !== true',
        'RUNWAY_GEN4_TURBO_5S_USD_0.25',
        'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32',
        '"creator_start_real_generation"',
        '"creator_real_generation_status"',
        '"system_update_real_generation"',
        'status: "starting"',
        'claimValue.claimed',
        'current.status !== "queued"',
    ):
        assert marker in source

    claim = source.index('status: "starting"')
    provider_call = source.index('`${RUNWAY_API_ORIGIN}/v1/image_to_video`')
    submitted = source.index('status: "submitted"', provider_call)
    assert claim < provider_call < submitted
    assert "cron" not in source.casefold()
    assert "schedule" not in source.casefold()


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

    assert 'const RUNWAY_API_ORIGIN = "https://api.dev.runwayml.com"' in source
    assert 'const RUNWAY_API_VERSION = "2024-11-06"' in source
    assert 'Deno.env.get("RUNWAYML_API_SECRET")' in source
    assert 'authorization: `Bearer ${secret}`' in source
    assert 'model: startJob.model' in source
    assert 'duration: startJob.durationSeconds' in source
    assert 'ratio: startJob.ratio' in source
    assert 'promptText: startJob.promptText' in source
    assert 'promptImage: signedInputUrl' in source
    assert 'promptImage: [{ uri: signedInputUrl }]' in source
    assert 'audio: true' in source
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
    create_start = source.index('`${RUNWAY_API_ORIGIN}/v1/image_to_video`')
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

    assert status_section.count("markFailed(") == 1
    failure = status_section.index("markFailed(")
    failure_guard = status_section.rfind('providerTask.status === "FAILED"', 0, failure)
    cancelled_guard = status_section.rfind(
        'providerTask.status === "CANCELLED"', 0, failure
    )
    assert failure_guard >= 0
    assert cancelled_guard >= 0
    assert "respondProviderUnavailable" in status_section


def test_output_is_allowlisted_bounded_verified_and_privately_persisted() -> None:
    source = _source()

    assert (
        'const RUNWAY_OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net"' in source
    )
    assert 'url.hostname !== RUNWAY_OUTPUT_HOST' in source
    assert 'url.protocol !== "https:"' in source
    assert 'const MAX_OUTPUT_BYTES = 52_428_800' in source
    assert '["video/mp4", "application/mp4"]' in source
    assert 'bytes[4] === 0x66' in source
    assert 'crypto.subtle.digest("SHA-256", bytes)' in source
    assert 'const STORAGE_BUCKET = "contentengine-private"' in source
    assert 'contentType: "video/mp4"' in source
    assert 'upsert: true' in source
    assert 'metadata: { sha256: digest }' in source
    assert 'output_object_name: current.outputObjectName' in source
    assert 'sha256: digest' in source
    assert 'createSignedUrl(job.outputObjectName, OUTPUT_URL_TTL_SECONDS)' in source
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


def test_production_workflow_masks_sets_and_deploys_runway_secret() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
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
    assert '"MOCK_ONLY"' not in text
    assert '"MOCK_ENABLED": True' in text
    assert '"REAL_GENERATION_ENABLED": True' in text
    assert '"REAL_PROVIDER": "runway"' in text
    assert '"REAL_MODEL": "gen4_turbo"' in text
    assert '"REAL_ESTIMATED_COST_USD": 0.25' in text


def test_ci_formats_lints_and_checks_both_edge_functions() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for function_name in ("creator-invite", "creator-generate"):
        assert f"deno fmt --check supabase/functions/{function_name}" in text
        assert f"deno lint supabase/functions/{function_name}/index.ts" in text
        assert f"deno check supabase/functions/{function_name}/index.ts" in text
