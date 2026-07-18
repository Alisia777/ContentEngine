from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170005_content_review_queue_health.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase" / "tests" / "native_worker_scheduler_watchdog_test.sql"
).read_text(encoding="utf-8")
VIEW = (ROOT / "web" / "app" / "manager-dashboard-view.js").read_text(
    encoding="utf-8"
)
CSS = (ROOT / "web" / "app" / "manager-dashboard.css").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")


def _run_view(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(VIEW, encoding="utf-8")
        (workdir / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_health_rpc_keeps_existing_contract_and_grants() -> None:
    assert "create or replace function public.creator_operational_health(" in MIGRATION
    assert "security definer" in MIGRATION
    assert "set search_path = ''" in MIGRATION
    for response_key in (
        "'ok', true",
        "'organization_id', organization_id_value",
        "'scheduler', jsonb_build_object(",
        "'worker', jsonb_build_object(",
        "'generation', jsonb_build_object(",
        "'content_review', jsonb_build_object(",
    ):
        assert response_key in MIGRATION
    assert "array['owner', 'admin']" in MIGRATION
    assert "revoke all on function public.creator_operational_health(jsonb)" in MIGRATION
    assert "from public, anon;" in MIGRATION
    assert "grant execute on function public.creator_operational_health(jsonb)" in MIGRATION
    assert "to authenticated;" in MIGRATION


def test_queue_counters_are_tenant_scoped_current_and_non_inflating() -> None:
    assert MIGRATION.count("organization_id = organization_id_value") >= 2
    assert "where review.organization_id = organization_id_value" in MIGRATION
    assert "review.status = 'queued'" in MIGRATION
    assert "review.status = 'processing'" in MIGRATION
    assert "review.next_attempt_at is not null" in MIGRATION
    assert "review.next_attempt_at <= now()" in MIGRATION
    assert "review.next_attempt_at > now()" in MIGRATION
    assert "latest_attempt.status = 'retry_wait'" in MIGRATION
    assert "latest_attempt.status = 'dead_letter'" in MIGRATION
    assert "latest_attempt.status = 'outcome_unknown'" in MIGRATION
    assert "'terminal_scope', 'all_time'" in MIGRATION
    assert "left join lateral" in MIGRATION
    assert "order by attempt.attempt_no desc, attempt.id desc" in MIGRATION
    assert "min(review.created_at) filter (" in MIGRATION
    assert "where review.status = 'queued'" in MIGRATION
    assert "'oldest_queued_age_seconds', review_oldest_queued_age_seconds" in MIGRATION


def test_pgtap_exercises_counts_age_and_cross_tenant_isolation() -> None:
    for marker in (
        "organization health reports only current queued content reviews",
        "only queued reviews whose next attempt is due are counted as due",
        "the latest retry-wait attempt is represented once per queued review",
        "dead-letter content reviews are visible to the organization manager",
        "oldest queue age uses the oldest currently queued review",
        "terminal reviews do not inflate the oldest queued age",
        "terminal content-review counters disclose their cumulative scope",
        "terminal review incidents never cross the organization boundary",
    ):
        assert marker in PGTAP


def test_manager_sees_critical_review_queue_without_raw_provider_details() -> None:
    result = _run_view(
        """
        const html = subject.managerOperationalHealthMarkup({
          status: "ready",
          data: {
            scheduler: { ready: true },
            worker: {
              ready: true,
              heartbeat_fresh: true,
              heartbeat_at: "2026-07-17T10:00:00Z",
              latest_error_code: "private-provider-detail",
            },
            generation: { active: 0, due: 0, stalled: 0 },
            content_review: {
              queued: 4,
              processing: 2,
              due: 3,
              retry_wait: 1,
              dead_letter: 2,
              outcome_unknown: 1,
              oldest_queued_age_seconds: 3670,
            },
          },
        });
        return { html };
        """
    )
    html = result["html"]
    assert "manager-operations-danger" in html
    assert "manager-review-queue-danger" in html
    assert "Очередь AI-аудита" in html
    for label in (
        "В очереди",
        "В обработке",
        "Готово сейчас",
        "Ожидает повтора",
        "Исчерпаны попытки",
        "Исход неизвестен",
        "Старейшая в очереди",
    ):
        assert label in html
    assert "1 ч 1 мин" in html
    assert "Не запускайте их повторно вслепую" in html
    assert "накопленные за всё время инциденты" in html
    assert "не исчезают сами" in html
    assert "private-provider-detail" not in html


def test_manager_handles_legacy_health_response_without_false_zeroes() -> None:
    result = _run_view(
        """
        const html = subject.managerOperationalHealthMarkup({
          status: "ready",
          data: {
            scheduler: { ready: true },
            worker: { ready: true, heartbeat_fresh: true },
            generation: { active: 0, due: 0, stalled: 0 },
          },
        });
        return { html };
        """
    )
    html = result["html"]
    assert "manager-review-queue-neutral" in html
    assert "Сводка появится после следующего ответа сервера." in html
    assert html.count("<strong>—</strong>") == 12


def test_manager_surfaces_pre_dispatch_delay_and_storage_capacity_without_retry() -> None:
    result = _run_view(
        """
        const html = subject.managerOperationalHealthMarkup({
          status: "ready",
          data: {
            scheduler: { ready: true },
            worker: { ready: true, heartbeat_fresh: true },
            generation: {
              active: 0,
              due: 0,
              stalled: 0,
              queued: 8,
              starting: 2,
              oldest_queued_age_seconds: 1800,
              oldest_starting_age_seconds: 700,
            },
            storage: {
              registered_count: 1250,
              registered_bytes: 96636764160,
              quota_bytes: 107374182400,
              remaining_bytes: 10737418240,
              utilization_percent: 90,
            },
          },
        });
        return { html };
        """
    )
    html = result["html"]
    assert "manager-operations-danger" in html
    assert "Ждёт запуска" in html
    assert "Сверка запуска" in html
    assert "Старейшая до отправки" in html
    assert "Хранилище видео" in html
    assert "Заполнено" in html
    assert "90%" in html
    assert "не удаляет файлы автоматически" in html
    assert "не повторяет платную генерацию" in html


def test_review_health_layout_is_responsive_theme_aware_and_cache_busted() -> None:
    for marker in (
        ".manager-review-queue",
        ".manager-review-queue-metrics",
        ".manager-review-queue-warning",
        ".manager-review-queue-danger",
        "var(--surface",
        "var(--ink",
        "@media (max-width: 720px)",
    ):
        assert marker in CSS
    assert './manager-dashboard.css?v=20260717.5' in INDEX
    assert './app.js?v=20260718.3' in INDEX
    assert 'from "./manager-dashboard-view.js?v=20260718.1"' in APP
