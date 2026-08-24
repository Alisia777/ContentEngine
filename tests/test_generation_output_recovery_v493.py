from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
WORKER_PATH = ROOT / "supabase/functions/creator-background-worker/index.ts"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _integer_constant(source: str, name: str) -> int:
    match = re.search(rf"const {re.escape(name)} = ([0-9_]+);", source)
    assert match is not None, f"missing integer constant {name}"
    return int(match.group(1).replace("_", ""))


def _balanced_block(source: str, marker: str) -> str:
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for cursor in range(brace, len(source)):
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
            if depth == 0:
                return source[start : cursor + 1]
    raise AssertionError(f"unterminated block after {marker!r}")


def _status_section(source: str) -> str:
    start = source.index("const handleStatus")
    end = source.index("const handleReconciliation", start)
    return source[start:end]


def _output_section(source: str) -> str:
    status = _status_section(source)
    start = status.index("const outputUrl")
    end = status.index("const successPayload", start)
    return status[start:end]


def test_output_body_deadline_stays_armed_until_the_bounded_body_is_read() -> None:
    source = _text(GENERATOR_PATH)
    deadline = _balanced_block(source, "async function withFetchDeadline")

    controller = deadline.index("new AbortController()")
    timer = deadline.index("setTimeout(", controller)
    fetch = deadline.index("await fetch(", timer)
    consume = deadline.index("await consume(", fetch)
    finally_block = deadline.index("finally", consume)
    clear = deadline.index("clearTimeout(", finally_block)

    assert controller < timer < fetch < consume < finally_block < clear
    assert "signal: controller.signal" in deadline

    # Ролик Runway принимается потоком (archiveProviderOutputStream): дедлайн
    # передаётся помощнику и держится у него на всём пути — от первого GET до
    # конца загрузки в Storage. Буферного чтения тела в этой секции больше
    # нет: именно оно валило изолят по памяти на больших роликах.
    output = _output_section(source)
    streamed = output.index("await archiveProviderOutputStream(")
    assert output.index("OUTPUT_TIMEOUT_MS", streamed) > streamed
    assert "await readBoundedBytes(" not in output.split("} else {", 1)[1]
    assert "fetchWithTimeout(" not in output

    archive = _text(ROOT / "supabase/functions/_shared/provider-output-archive.ts")
    helper = _balanced_block(archive, "export async function archiveProviderOutputStream")
    controller = helper.index("new AbortController()")
    timer = helper.index("setTimeout(", controller)
    first_pass = helper.index("pipeTo(", timer)
    upload = helper.index("method: \"POST\"", first_pass)
    finally_block = helper.index("finally", upload)
    clear = helper.index("clearTimeout(", finally_block)
    assert controller < timer < first_pass < upload < finally_block < clear
    assert helper.count("signal: controller.signal") >= 2


def test_output_finalization_has_budget_inside_the_worker_dispatch_deadline() -> None:
    generator = _text(GENERATOR_PATH)
    worker = _text(WORKER_PATH)

    provider_ms = _integer_constant(generator, "PROVIDER_TIMEOUT_MS")
    output_ms = _integer_constant(generator, "OUTPUT_TIMEOUT_MS")
    storage_ms = _integer_constant(generator, "OUTPUT_STORAGE_TIMEOUT_MS")
    database_ms = _integer_constant(generator, "OUTPUT_DATABASE_TIMEOUT_MS")
    dispatch_ms = _integer_constant(worker, "DISPATCH_TIMEOUT_MS")

    # Every remote finalization stage has its own bounded budget. Three DB
    # windows cover submitted->processing, the success RPC, and authoritative
    # readback; the remaining interval is for hashing and serialization.
    bounded_total = provider_ms + output_ms + storage_ms + (3 * database_ms)
    assert bounded_total < dispatch_ms
    assert dispatch_ms - bounded_total >= 10_000


def test_provider_json_and_storage_operations_are_body_and_io_bounded() -> None:
    source = _text(GENERATOR_PATH)
    provider = _balanced_block(source, "async function fetchProviderJsonWithDeadline")
    operation = _balanced_block(source, "async function withOperationDeadline")
    status = _status_section(source)

    assert "await withFetchDeadline(" in provider
    # Потоковая приёмка (23.08): чтение тела провайдера ограничено и по
    # времени, и по байтам — maxBytes передаётся внутрь читателя.
    assert "value: await readProviderJson(response, maxBytes)" in provider
    assert "Promise.race([" in operation
    assert "new OperationDeadlineError()" in operation
    assert "fetchWithTimeout(" not in source

    assert "await fetchProviderJsonWithDeadline(" in status
    assert "PROVIDER_TIMEOUT_MS" in status
    assert "await withOperationDeadline(" in status
    assert "OUTPUT_STORAGE_TIMEOUT_MS" in status
    assert status.count("OUTPUT_DATABASE_TIMEOUT_MS") >= 2
    assert "OUTPUT_ACCESS_TIMEOUT_MS" in source


def test_succeeded_output_failures_return_exact_safe_retryable_codes() -> None:
    source = _text(GENERATOR_PATH)
    helper_start = source.index("const respondOutputRetryable")
    helper_end = source.index("const handleStatus", helper_start)
    helper = source[helper_start:helper_end]

    for token in (
        "organizationId",
        "jobId",
        "projectId",
        "readCurrentStatusWithinDeadline(",
        "ok: false",
        "code",
        "safeJob(current)",
        "503",
    ):
        assert token in helper
    assert "markFailed(" not in helper
    assert "updateSystemJob(" not in helper

    output = _output_section(source)
    for code in (
        "output_download_failed",
        "output_validation_failed",
        "output_upload_failed",
        "output_access_failed",
    ):
        assert f'"{code}"' in source
    assert output.count("respondOutputRetryable(") >= 4

    # URL, MIME/signature, and Storage failures must not collapse back to the
    # provider-unavailable bucket after Runway has already returned SUCCEEDED.
    assert "respondProviderUnavailable(" not in output


def test_saved_output_without_a_signed_url_is_retryable_without_provider_work() -> None:
    source = _text(GENERATOR_PATH)
    status = _status_section(source)
    respond_with_current = source[
        source.index("const respondWithCurrent") : source.index(
            "const respondProviderUnavailable"
        )
    ]
    succeeded = status.split('if (current.status === "succeeded")', 1)[1].split(
        'if (current.status === "failed"', 1
    )[0]
    completed = status.split("const signedUrl = internalWorker ? null", 2)[-1]

    for section in (succeeded, completed):
        assert '"output_access_failed"' in section
        assert "respondOutputRetryable(" in section
        assert "!internalWorker" in section
        assert 'method: "POST"' not in section

    assert 'current.status === "succeeded" && signedUrl === null' in (
        respond_with_current
    )
    assert 'code: "output_access_failed"' in respond_with_current
    assert "503" in respond_with_current
    assert 'method: "POST"' not in respond_with_current

    app = _text(ROOT / "web/app/app.js")
    assert "output_access_failed" in app
    assert "новый платный запуск не нужен" in app


def test_browser_explains_every_retryable_output_stage_without_new_spend() -> None:
    app = _text(ROOT / "web/app/app.js")
    status_error = _balanced_block(app, "function applyRealGenerationStatusError")
    action_error = _balanced_block(app, "function actionErrorMessage")
    failure_messages = _balanced_block(app, "function generationFailureMessage")

    for code in (
        "output_download_failed",
        "output_validation_failed",
        "output_upload_failed",
        "output_access_failed",
    ):
        assert f'"{code}"' in status_error
        assert f'"{code}"' in action_error
        assert f"{code}:" in failure_messages
    assert failure_messages.count("нового запуска") >= 2
    assert "новый платный запуск не нужен" in failure_messages


def test_output_validation_accepts_octet_stream_only_after_signature_check() -> None:
    source = _text(GENERATOR_PATH)
    output = _output_section(source)

    # `application/octet-stream` допускается только вместе с проверкой
    # сигнатуры файла. Буферная ветка (Google): байты → isMp4 → upload.
    # Потоковая ветка (Runway): сниффер передаётся помощнику, и тот сверяет
    # первые байты ДО того, как отдать их в Storage.
    mime = output.index("const allowedOutputMimeTypes")
    octet_stream = output.index('"application/octet-stream"', mime)
    google_signature = output.index("!isMp4(outputBytes)", octet_stream)
    google_upload = output.index("storage.upload(", google_signature)
    streamed = output.index("await archiveProviderOutputStream(", google_upload)
    sniff = output.index("sniff: photoOutput ? isPng : isMp4", streamed)
    assert mime < octet_stream < google_signature < google_upload < streamed < sniff
    assert "MAX_OUTPUT_BYTES" in output[streamed:]

    archive = _text(ROOT / "supabase/functions/_shared/provider-output-archive.ts")
    meter = archive[
        archive.index("export function providerOutputMeter") : archive.index(
            "export function providerOutputStorageUrl"
        )
    ]
    sniff_call = meter.index("!sniff(head)")
    enqueue = meter.index("controller.enqueue(chunk)")
    assert sniff_call < enqueue
    assert '"output_validation_failed"' in meter[sniff_call:enqueue]


def test_output_retry_never_creates_a_second_paid_provider_task() -> None:
    generator = _text(GENERATOR_PATH)
    worker = _text(WORKER_PATH)
    status = _status_section(generator)
    output = _output_section(generator)

    succeeded = status.index('providerTask.status !== "SUCCEEDED"')
    assert '`${RUNWAY_API_ORIGIN}/v1/image_to_video`' not in status[succeeded:]
    assert 'method: "POST"' not in output
    assert "markFailed(" not in output
    assert 'status: "failed"' not in output

    generation_query = worker.split("const generationQuery", 1)[1].split(
        "const researchQuery", 1
    )[0]
    strategy_target = worker.split(
        "...dispatchStrategyRows.map((row): DispatchTarget => ({", 1
    )[1].split(
        "...dispatchGenerationRows.map((row): DispatchTarget => ({", 1
    )[0]
    generation_target = worker.split(
        "...dispatchGenerationRows.map((row): DispatchTarget => ({", 1
    )[1].split(
        "...dispatchResearchRows.map((row): DispatchTarget => ({", 1
    )[0]
    assert '.in("status", ["starting", "submitted", "processing"])' in (
        generation_query
    )
    assert 'action: "strategy_status"' in strategy_target
    assert '"action": "start"' not in strategy_target
    assert 'action: "status"' in generation_target
    assert '"action": "start"' not in generation_target
