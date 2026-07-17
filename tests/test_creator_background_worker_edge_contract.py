from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"
WORKER_AUTH = ROOT / "supabase/functions/_shared/internal-worker-auth.ts"
GENERATE = ROOT / "supabase/functions/creator-generate/index.ts"
RESEARCH = ROOT / "supabase/functions/creator-product-research/index.ts"
REVIEW = ROOT / "supabase/functions/creator-content-review/index.ts"
DEPLOY = ROOT / ".github/workflows/supabase-pages.yml"
SCHEDULE = ROOT / ".github/workflows/background-worker.yml"
CI = ROOT / ".github/workflows/ci.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_background_worker_is_named_secret_authenticated_and_bounded() -> None:
    source = _text(WORKER)
    config = tomllib.loads(_text(ROOT / "supabase/config.toml"))

    assert WORKER.is_file()
    assert config["functions"]["creator-background-worker"]["verify_jwt"] is False
    for name in (
        "creator-generate",
        "creator-product-research",
        "creator-content-review",
    ):
        assert config["functions"][name]["verify_jwt"] is True
    auth_source = _text(WORKER_AUTH)
    assert 'auth: "none"' in source
    assert "cors: false" in source
    assert "context.authMode !== \"none\"" in source
    assert "isInternalWorkerAuthorized(request)" in source
    assert 'Deno.env.get("CONTENTENGINE_WORKER_SECRET")' in auth_source
    assert "crypto.subtle.sign" in auth_source
    assert "difference |= leftBytes[index] ^ rightBytes[index]" in auth_source
    assert 'request.headers.get("origin") !== null' in auth_source
    assert "MAX_LIMIT_PER_QUEUE = 6" in source
    assert "MAX_TOTAL_DISPATCHES = 8" in source
    assert "generation + research + review > MAX_TOTAL_DISPATCHES" in source
    assert "MAX_BODY_BYTES = 1_024" in source
    assert "readBoundedBody(request.body, MAX_BODY_BYTES)" in source
    assert "request.text()" not in source


def test_generation_worker_only_retrieves_existing_runway_tasks() -> None:
    source = _text(WORKER)

    assert '.in("status", ["submitted", "processing"])' in source
    assert 'body: {\n        action: "status",' in source
    assert "creator-generate" in source
    assert "image_to_video" not in source
    assert '"action": "start"' not in source
    assert '"action": "reconcile"' not in source
    assert '"queued", "starting"' not in source
    assert "SUPABASE_SERVICE_ROLE_KEY" in source
    assert 'authorization: `Bearer ${serviceKey}`' in source
    assert "apikey: serviceKey" in source
    assert "[INTERNAL_WORKER_HEADER]: \"1\"" in source
    assert "[INTERNAL_WORKER_SECRET_HEADER]: secret" in source


def test_worker_dispatches_durable_research_and_image_review_queues() -> None:
    source = _text(WORKER)

    assert '.from("product_research_runs")' in source
    assert '.from("content_review_runs")' in source
    assert '.eq("status", "queued")' in source
    assert "creator-product-research" in source
    assert "creator-content-review" in source
    assert 'body: { action: "analyze", research_id: row.id }' in source
    assert (
        'body: { action: "analyze", review_id: row.id, frames: [] }'
        in source
    )
    assert "IMAGE_MIME_TYPES.has(media.mime_type)" in source
    assert 'media.mime_type === "video/mp4"' in source
    assert "skipped_video_reviews" in source


def test_existing_edges_keep_user_auth_and_add_isolated_worker_auth() -> None:
    generate = _text(GENERATE)
    research = _text(RESEARCH)
    review = _text(REVIEW)

    for source in (generate, research, review):
        assert 'auth: "user"' in source
        assert 'auth: "none"' in source
        assert '../_shared/internal-worker-auth.ts' in source
        assert "isInternalWorkerAuthorized(request)" in source
        assert 'request.headers.get(INTERNAL_WORKER_HEADER) !== "1"' in source
        assert '.schema("content_factory")' in source
        assert "internalWorker && request.headers.get(\"origin\") !== null" in source

    status_gate = generate.index("if (internalWorker) {", generate.index("const statusPayload"))
    start_parser = generate.index("const startPayload", status_gate)
    provider_create = generate.index("`${RUNWAY_API_ORIGIN}/v1/image_to_video`")
    assert status_gate < start_parser < provider_create
    assert "const signedUrl = internalWorker ? null" in generate


def test_worker_reconciles_expired_leases_before_reading_any_queue() -> None:
    source = _text(WORKER)

    assert '"system_reconcile_background_leases"' in source
    assert "LEASE_RECONCILE_LIMIT = 50" in source
    reconcile = source.index(
        "const reconciliation = await reconcileExpiredLeases"
    )
    generation_read = source.index("const generationQuery")
    research_read = source.index("const researchQuery")
    review_read = source.index("const reviewQuery")
    assert reconcile < generation_read < research_read < review_read
    assert '"lease_reconciliation_failed"' in source


def test_worker_delivers_transactional_outbox_and_surfaces_backlog() -> None:
    source = _text(WORKER)

    assert '"system_claim_notification_outbox"' in source
    assert '"system_emit_notification"' in source
    assert '"system_complete_notification_outbox"' in source
    assert '"system_notification_outbox_health"' in source
    assert "NOTIFICATION_OUTBOX_LIMIT = 12" in source
    assert '"notification_emit_failed"' in source
    assert "health.unresolved === 0" in source
    dispatch = source.index("const outcomes = await Promise.all")
    notification = source.index(
        "const notification = await deliverNotificationOutbox"
    )
    assert dispatch < notification
    assert "!notification.ok" in source
    assert '"background_batch_incomplete"' in source
    assert "notifyBestEffort" not in source
    assert "console.log" not in source
    assert "console.error" not in source
    assert "error.message" not in source


def test_deployment_syncs_worker_secret_and_deploys_only_worker_without_jwt() -> None:
    workflow = yaml.safe_load(_text(DEPLOY))
    steps = workflow["jobs"]["migrate"]["steps"]

    secret = next(
        step
        for step in steps
        if step.get("name") == "Synchronize private background worker secret"
    )
    assert secret["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "CONTENTENGINE_WORKER_SECRET": (
            "${{ secrets.CONTENTENGINE_WORKER_SECRET }}"
        ),
    }
    assert 'echo "::add-mask::$CONTENTENGINE_WORKER_SECRET"' in secret["run"]
    assert "SUPABASE_SECRET_KEYS" not in secret["run"]
    assert 'CONTENTENGINE_WORKER_SECRET="$CONTENTENGINE_WORKER_SECRET"' in secret["run"]

    worker_deploy = next(
        step
        for step in steps
        if step.get("name")
        == "Deploy secret-authenticated background worker function"
    )
    assert "creator-background-worker" in worker_deploy["run"]
    assert "--no-verify-jwt" in worker_deploy["run"]
    for name in (
        "Deploy authenticated real generation function",
        "Deploy authenticated product research function",
        "Deploy authenticated content review function",
    ):
        step = next(item for item in steps if item.get("name") == name)
        assert "--no-verify-jwt" not in step["run"]


def test_scheduled_dispatch_is_non_overlapping_secret_scoped_and_safe() -> None:
    text = _text(SCHEDULE)
    workflow = yaml.safe_load(text)
    dispatch = workflow["jobs"]["dispatch"]
    triggers = workflow.get("on") or workflow.get(True)

    assert 'cron: "*/5 * * * *"' in text
    assert workflow["permissions"] == {}
    assert workflow["concurrency"] == {
        "group": "production-background-content-worker",
        "cancel-in-progress": False,
    }
    smoke_input = triggers["workflow_dispatch"]["inputs"]["smoke_only"]
    assert smoke_input["type"] == "boolean"
    assert smoke_input["default"] is True
    assert smoke_input["required"] is True
    assert dispatch["environment"] == "production"
    assert dispatch["timeout-minutes"] == 8
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "RUNWAYML_API_SECRET" not in text
    assert "OPENAI_API_KEY" not in text
    assert 'echo "::add-mask::$CONTENTENGINE_WORKER_SECRET"' in text
    assert '--header "x-contentengine-internal-worker: 1"' in text
    assert (
        '--header "x-contentengine-worker-secret: '
        '$CONTENTENGINE_WORKER_SECRET"'
    ) in text
    assert "creator-background-worker" in text
    assert '"generation_limit":4' in text
    assert '"research_limit":1' in text
    assert '"review_limit":1' in text
    assert '"generation_limit":0' in text
    assert '"research_limit":0' in text
    assert '"review_limit":0' in text
    assert '--data "$payload"' in text
    assert "payload.get(\"ok\") is not True" in text
    assert '"expired_leases": payload.get("expired_leases", {})' in text
    assert 'notification_unresolved={unresolved}' in text
    assert 'notification_failed={delivery_failed}' in text
    assert 'notification.get("unresolved", 0) != 0' in text


def test_ci_formats_lints_and_type_checks_background_worker() -> None:
    ci = _text(CI)
    name = "creator-background-worker"

    assert f"deno fmt --check supabase/functions/{name}" in ci
    assert f"deno lint supabase/functions/{name}/index.ts" in ci
    assert f"deno check supabase/functions/{name}/index.ts" in ci
    assert "deno fmt --check supabase/functions/_shared/internal-worker-auth.ts" in ci
    assert "deno lint supabase/functions/_shared/internal-worker-auth.ts" in ci
    assert "deno check supabase/functions/_shared/internal-worker-auth.ts" in ci
    assert '"creator-background-worker",' in ci
    assert '"auth-email-webhook",' in ci
    assert 'function_config.get("verify_jwt") is not False' in ci
