from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION_PATH = (
    MIGRATIONS / "202608100015_research_provider_terminal_diagnostics.sql"
)
EDGE_PATH = (
    ROOT / "supabase" / "functions" / "creator-product-research" / "index.ts"
)
EDGE_TEST_PATH = (
    ROOT
    / "supabase"
    / "functions"
    / "creator-product-research"
    / "index_test.ts"
)
VIEW_PATH = ROOT / "web" / "app" / "product-research-view.js"
INTAKE_PATH = ROOT / "web" / "app" / "workspace-research-video-intake.js"
PROJECT_ACCESS_PATH = (
    MIGRATIONS / "202608100003_project_team_shared_media_access.sql"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_terminal_diagnostic_migration_is_valid_bounded_and_append_only() -> None:
    migration = read(MIGRATION_PATH)
    assert MIGRATION_PATH.name.startswith("202608100015_")
    assert parse_sql(migration)
    for marker in (
        "provider_terminal_status",
        "provider_error_code",
        "provider_error_type",
        "provider_error_message",
        "provider_message_present",
        "research_provider_health_terminal_diagnostic_consistent",
        "research-provider-health-receipt-v2",
        "provider_diagnostic_code",
        "terminal_diagnostic",
        "server_exact_video_binding",
        "evidence_frame_count_snapshot",
    ):
        assert marker in migration
    for forbidden in (
        "provider_response_id",
        "request_payload",
        "object_name",
        "source_url",
        "media_sha256_snapshot",
    ):
        assert forbidden not in migration
    assert "char_length(provider_error_message) between 10 and 280" in migration
    assert "provider_error_code in (" in migration
    assert "provider_error_type in (" in migration
    assert "provider_error_code_value not in (" in migration
    assert "provider_error_type_value not in (" in migration
    assert "provider_error_code ~ '^[a-z0-9]" not in migration
    assert "provider_error_type ~ '^[a-z0-9]" not in migration
    assert "status <> 'ready'" in migration
    assert "grant execute on function public.system_record_research_provider_health" in migration
    assert "to service_role" in migration


def test_edge_classifies_terminal_status_and_never_persists_raw_provider_message() -> None:
    edge = read(EDGE_PATH)
    diagnostic = edge.split(
        "function readProviderTerminalDiagnostic", 1
    )[1].split("export function readProviderResponseIdentity", 1)[0]
    health = edge.split("const recordProviderHealth = async", 1)[1].split(
        "const pending = async", 1
    )[0]
    for marker in (
        "providerTerminalFailure",
        'failureCode = "provider_unavailable"',
        'failureCode = "provider_response_invalid"',
        'failureCode = "provider_request_rejected"',
        'failureCode = "provider_authentication_failed"',
        "provider_terminal_status",
        "provider_error_code",
        "provider_error_type",
        "provider_error_message",
        "provider_message_present",
        "Автоматического повтора не было",
    ):
        assert marker in edge
    assert 'error["message"]' in diagnostic
    assert "typeof providerMessage" in diagnostic
    assert "error.message" not in diagnostic
    assert "sanitizeProviderDiagnosticMessage(error.message" not in diagnostic
    assert "healthPayload.provider_error_message = providerDiagnostic.message" in health
    assert 'method: "POST"' in edge
    assert edge.count('method: "POST"') == 1
    assert 'idempotency-key": `product-research:${claim.run.id}`' in edge


def test_official_response_error_codes_have_edge_sql_allowlist_parity() -> None:
    edge = read(EDGE_PATH)
    migration = read(MIGRATION_PATH)
    safe = edge.split("const SAFE_PROVIDER_ERROR_CODES", 1)[1].split(
        "]);", 1
    )[0]
    rejected = edge.split(
        "const PROVIDER_REJECTED_DIAGNOSTIC_CODES", 1
    )[1].split("]);", 1)[0]
    image_codes = (
        "invalid_image",
        "invalid_image_format",
        "invalid_base64_image",
        "invalid_image_url",
        "image_too_large",
        "image_too_small",
        "image_parse_error",
        "image_content_policy_violation",
        "invalid_image_mode",
        "image_file_too_large",
        "unsupported_image_media_type",
        "empty_image_file",
        "failed_to_download_image",
        "image_file_not_found",
    )
    for code in image_codes:
        assert f'"{code}"' in safe
        assert f'"{code}"' in rejected
        assert migration.count(f"'{code}'") == 2
    assert '"vector_store_timeout"' in safe
    assert '"vector_store_timeout"' not in rejected
    assert migration.count("'vector_store_timeout'") == 2


def test_deno_contract_covers_five_frames_terminal_error_and_no_secret_echo() -> None:
    tests = read(EDGE_TEST_PATH)
    for marker in (
        "terminal provider failure keeps bounded diagnostics after five-frame lineage",
        "exactVideo?.frames.length === 5",
        'code: "server_error"',
        'type: "provider_internal_error"',
        "providerMessagePresent",
        "must never persist the provider's arbitrary raw message",
        "incomplete and cancelled Responses states never authorize a retry",
        "terminal diagnostics reject opaque ids, secrets and unbounded incomplete reasons",
        "terminal diagnostic classification uses exact allowlisted mappings",
        'code: "request_timeout"',
        'code: "context_length_exceeded"',
        '"responses_failed.unclassified"',
        '"responses_incomplete.unspecified"',
        '"z".repeat(80)',
        "Автоматического повтора не было",
    ):
        assert marker in tests


def test_project_status_wrapper_derives_org_from_authoritative_run_shape() -> None:
    migration = read(MIGRATION_PATH)
    wrapper = migration.rsplit(
        "create or replace function public.creator_project_research_status(", 1
    )[1]
    assert (
        "creator_project_research_status_pre_exact_failure_marker_v1(p_payload)"
        in wrapper
    )
    assert "resolve_organization(p_payload)" not in wrapper
    assert "select run.organization_id into organization_id_value" in wrapper
    assert "from content_factory.product_research_runs run" in wrapper
    assert "where run.id = run_id_value" in wrapper
    assert "and run.project_id = project_id_value" in wrapper
    assert "result_value ->> 'organization_id'" not in wrapper
    access = wrapper.index(
        "content_factory_private.require_workspace_project_access("
    )
    exact_select = wrapper.index(
        "from content_factory.research_exact_youtube_research_bindings binding"
    )
    assert "actor_id_value := content_factory_private.current_profile_id()" in wrapper
    assert access < exact_select


def test_same_org_nonmember_cannot_read_new_run_scoped_diagnostics_or_exact_ids() -> None:
    migration = read(MIGRATION_PATH)
    access_contract = read(PROJECT_ACCESS_PATH)
    provider_wrapper = migration.split(
        "create or replace function public.creator_research_provider_status(", 1
    )[1].split(
        "create or replace function public.creator_project_research_status(", 1
    )[0]
    project_wrapper = migration.rsplit(
        "create or replace function public.creator_project_research_status(", 1
    )[1]
    assert "actor_id_value := auth.uid()" in provider_wrapper
    assert "content_factory_private.current_profile_id()" not in provider_wrapper
    assert "message = 'authentication_required'" in provider_wrapper
    provider_guard = provider_wrapper.index(
        "content_factory_private.require_workspace_project_access("
    )
    assert provider_guard < provider_wrapper.index(
        "from content_factory.research_provider_health_receipts receipt"
    )
    assert (
        "actor_id_value := content_factory_private.current_profile_id()"
        in project_wrapper
    )
    project_guard = project_wrapper.index(
        "content_factory_private.require_workspace_project_access("
    )
    assert project_guard < project_wrapper.index(
        "from content_factory.research_exact_youtube_research_bindings binding"
    )
    helper = access_contract.split(
        "content_factory_private.require_workspace_project_access(", 1
    )[1].split("revoke all on function", 1)[0]
    assert "workspace_project_access_allowed(" in helper
    assert "workspace_project_access_required" in helper


def test_terminal_receipt_is_future_only_and_repeat_get_is_idempotent() -> None:
    migration = read(MIGRATION_PATH)
    edge = read(EDGE_PATH)
    assert "future-only: immutable v1 receipts stay generic" in migration
    existing = migration.split("if receipt_row.id is not null then", 1)[1].split(
        "insert into content_factory.research_provider_health_receipts", 1
    )[0]
    for semantic_field in (
        "provider_terminal_status",
        "provider_error_code",
        "provider_error_type",
        "provider_error_message",
        "provider_message_present",
        "failure_code",
        "citation_count",
    ):
        assert f"receipt_row.{semantic_field} is distinct from" in existing
    assert "Concurrent/repeated GET observers" in existing
    assert "update content_factory.research_provider_health_receipts" not in migration.lower()
    health = edge.split("const recordProviderHealth = async", 1)[1].split(
        "const pending = async", 1
    )[0]
    assert health.count('"system_record_research_provider_health"') == 1
    assert "Never repeat or reinterpret a paid request because telemetry failed" in health


def test_sql_terminal_message_is_bound_to_status_and_incomplete_code() -> None:
    migration = read(MIGRATION_PATH)
    assert "provider_terminal_status = 'failed'" in migration
    assert "provider_terminal_status = 'cancelled'" in migration
    assert "provider_terminal_status = 'incomplete'" in migration
    assert "terminal_status_value = 'failed'" in migration
    assert "terminal_status_value = 'cancelled'" in migration
    assert "terminal_status_value = 'incomplete'" in migration
    assert "split_part(provider_error_code, '.', 2)" in migration
    assert "split_part(provider_error_code_value, '.', 2)" in migration
    assert (
        "Provider accepted the response and ended processing with status failed."
        in migration
    )
    assert (
        "Provider accepted the response and ended processing with status cancelled."
        in migration
    )


def test_ui_uses_current_server_binding_and_routes_to_fresh_evidence() -> None:
    view = read(VIEW_PATH)
    intake = read(INTAKE_PATH)
    assert "previous?.exactVideo" not in view
    for marker in (
        "markerSource === \"server_exact_video_binding\"",
        "normalized.frameCount === 5",
        'data-research-exact-video-evidence="verified"',
        'data-exact-video-product-name=',
        'data-exact-video-product-sku=',
        "Отсутствие подтверждённых цитат не означает, что кадры не передавались",
        "одноразовый evidence-набор потреблён",
    ):
        assert marker in view
    for marker in (
        "exactVideoTerminalFailure",
        "exactYoutubeResearchEvidenceRoute",
        "Повторно загружать MP4 не нужно",
        "Создать новый набор из 5 кадров из сохранённого MP4",
        "отдельных подтверждений обработки ИИ и оплаты",
    ):
        assert marker in intake
    exact_branch = intake.split("if (exactTerminalFailure) {", 1)[1].split(
        'const guard = el("section", "research-youtube-failure-guard', 1
    )[0]
    assert "zeroCitationProviderFailure" not in exact_branch
    exact_copy = intake.split("if (exactTerminalFailure) {", 1)[1].split(
        "return;", 1
    )[0]
    assert "Ноль цитат" not in exact_copy
    assert 'text.includes("0 цитат")' in intake
