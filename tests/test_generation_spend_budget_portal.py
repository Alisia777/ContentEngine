from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
VIEW = (APP_DIR / "generation-spend-view.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "manager-dashboard.css").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")


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


def test_spend_rpcs_are_scoped_and_policy_update_is_idempotent() -> None:
    assert 'generationSpendOverview: "creator_generation_spend_overview"' in API
    assert 'updateGenerationSpendPolicy: "creator_update_generation_spend_policy"' in API
    assert "generationSpendOverview()" in API
    assert "this.call(RPC.generationSpendOverview, this.withOrganization({}))" in API
    method = API[
        API.index("updateGenerationSpendPolicy(policy = {})") : API.index("inspectAccess(email)")
    ]
    assert "this.mutate(RPC.updateGenerationSpendPolicy" in method
    assert "expected_version: expectedVersion" in method
    assert "paid_generation_enabled: enabled" in method
    assert "daily_limit_minor: dailyLimitMinor" in method
    assert "perRequestLimitMinor > dailyLimitMinor" in method
    assert "idempotency_key" in API[API.index("async mutate(") : API.index("async uploadPrivateObject")]


def test_manager_budget_card_shows_reserved_committed_remaining_and_owner_controls() -> None:
    result = _run_view(
        """
        const data = {
          ok: true,
          organization_id: "private-org-id",
          currency: "USD",
          blocker_code: null,
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 2500,
            monthly_limit_minor: 10000,
            per_request_limit_minor: 232,
            timezone: "Europe/Moscow",
            version: 7,
            reason: "approved",
            updated_at: "2026-07-17T10:00:00Z",
          },
          usage: {
            day: { reserved_minor: 232, committed_minor: 464, remaining_minor: 1804 },
            month: { reserved_minor: 232, settled_minor: 2000, remaining_minor: 7768 },
          },
        };
        const normalized = subject.normalizeGenerationSpendOverview(data);
        const owner = subject.managerGenerationSpendMarkup({ status: "ready", data }, { canEdit: true });
        const viewer = subject.managerGenerationSpendMarkup({ status: "ready", data }, { canEdit: false });
        return { normalized, owner, viewer };
        """
    )
    assert result["normalized"]["day"]["reservedMinor"] == 232
    assert result["normalized"]["day"]["committedMinor"] == 464
    assert result["normalized"]["month"]["committedMinor"] == 2000
    owner = result["owner"]
    assert "Платные запуски разрешены" in owner
    assert "Предварительно учтено" in owner
    assert "Зарезервировано" in owner
    assert "generation-spend-policy-form" in owner
    assert 'name="expected_version" value="7"' in owner
    assert "Приостановить платные запуски" in owner
    assert "private-org-id" not in owner
    assert "generation-spend-policy-form" not in result["viewer"]


def test_spend_snapshot_fails_closed_for_policy_blocker_and_escapes_campaign_copy() -> None:
    result = _run_view(
        """
        const blocked = {
          ok: true,
          currency: "USD",
          blocker_code: "generation_spend_daily_limit_exceeded",
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 500,
            monthly_limit_minor: 2000,
            per_request_limit_minor: 232,
            version: 2,
          },
          usage: {
            day: { reserved_minor: 0, committed_minor: 500, remaining_minor: 0 },
            month: { reserved_minor: 0, committed_minor: 500, remaining_minor: 1500 },
          },
          campaigns: [{ name: "<img src=x onerror=alert(1)>", status: "active" }],
        };
        return {
          allowed: subject.generationSpendAllowsMinor(blocked, 25),
          snapshot: subject.generationSpendSnapshotMarkup({ status: "ready", data: blocked }, { requestMinor: 25 }),
          manager: subject.managerGenerationSpendMarkup({ status: "ready", data: blocked }, { canEdit: true }),
          loading: subject.generationSpendSnapshotMarkup({ status: "loading", data: null }, { requestMinor: 25 }),
          stale: subject.generationSpendSnapshotMarkup({ status: "error", data: { ...blocked, blocker_code: null, usage: { day: { remaining_minor: 500 }, month: { remaining_minor: 1500 } } } }, { requestMinor: 25 }),
          staleManager: subject.managerGenerationSpendMarkup({ status: "error", data: { ...blocked, blocker_code: null } }, { canEdit: true }),
          refreshingManager: subject.managerGenerationSpendMarkup({ status: "refreshing", data: { ...blocked, blocker_code: null } }, { canEdit: true }),
        };
        """
    )
    assert result["allowed"] is False
    assert "Платный запуск сейчас недоступен" in result["snapshot"]
    assert "Дневной бюджет платной генерации исчерпан" in result["snapshot"]
    assert "&lt;img" in result["manager"]
    assert "<img" not in result["manager"]
    assert "Проверяем денежный лимит" in result["loading"]
    assert "Тестовые варианты доступны" in result["loading"]
    assert "Не удалось подтвердить свежий остаток" in result["stale"]
    assert "Денежный лимит подтверждён" not in result["stale"]
    assert "Платные запуски разрешены" not in result["staleManager"]
    assert "Свежий остаток не подтверждён" in result["staleManager"]
    assert 'data-enabled="unknown"' in result["staleManager"]
    assert "<fieldset disabled>" in result["staleManager"]
    assert "Платные запуски разрешены" not in result["refreshingManager"]
    assert "Обновляем денежный контур" in result["refreshingManager"]
    assert "<fieldset disabled>" in result["refreshingManager"]


def test_live_generation_form_is_fail_closed_but_keeps_mock_available() -> None:
    assert 'from "./generation-spend-view.js?v=20260717.1"' in APP
    assert "generationSpend: {" in APP
    assert "async function loadGenerationSpendOverview" in APP
    assert "state.api.generationSpendOverview()" in APP
    assert "if (!state.generationSpend.data || state.generationSpend.status !== \"ready\") return false" in APP
    assert "seedanceSpendAllowed ? \"\" : \"disabled\"" in APP
    assert "gen4SpendAllowed ? \"\" : \"disabled\"" in APP
    assert "Тестовые варианты · без списаний" in APP
    assert "Платный запуск остановлен лимитом" in APP
    assert "async function submitGenerationSpendPolicy" in APP
    assert "canManageGenerationSpendPolicy()" in APP
    assert "generation_spend_policy_version_conflict" in APP
    assert "[error?.code, error?.serverCode].some" in APP
    assert "state.generationSpend.requestId += 1" in APP[
        APP.index("async function submitGenerationSpendPolicy") : APP.index(
            "function usdInputToMinor"
        )
    ]


def test_cost_copy_is_provisional_and_budget_ui_is_theme_responsive_and_cache_busted() -> None:
    cost = APP[APP.index("function generationCostMarkup") : APP.index("function realGenerationJobsFromBatches")]
    assert "Учтено предварительно" in cost
    assert "Зарезервировано" in cost
    assert "Резерв освобождён" in cost
    assert "Не является итоговым счётом провайдера" in cost
    assert "Фактически" not in cost
    for marker in (
        ".manager-spend",
        ".manager-spend-periods",
        ".manager-spend-form-grid",
        ".generation-spend-snapshot",
        "var(--surface",
        "var(--ink",
        "@media (max-width: 720px)",
    ):
        assert marker in CSS
    assert './manager-dashboard.css?v=20260717.3' in INDEX
    assert './app.js?v=20260717.3' in INDEX
    assert './supabase-api.js?v=20260717.3' in APP
