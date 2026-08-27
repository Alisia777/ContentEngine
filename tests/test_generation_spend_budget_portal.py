from pathlib import Path
import json
import re
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


def test_campaign_hydration_restores_exact_draft_and_requires_explicit_reselection() -> None:
    result = _run_view(
        """
        const first = "11111111-1111-4111-8111-111111111111";
        const second = "22222222-2222-4222-8222-222222222222";
        const campaign = (id) => ({
          id,
          name: `Campaign ${id.slice(0, 4)}`,
          status: "active",
          enabled: true,
          blocker_code: null,
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 1000,
            monthly_limit_minor: 5000,
            per_request_limit_minor: 200,
            version: 1,
          },
          usage: {
            day: { reserved_minor: 0, committed_minor: 0, remaining_minor: 400 },
            month: { reserved_minor: 0, committed_minor: 0, remaining_minor: 700 },
          },
        });
        const data = {
          ok: true,
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 1000,
            monthly_limit_minor: 5000,
            per_request_limit_minor: 200,
            version: 1,
          },
          usage: {
            day: { remaining_minor: 1000 },
            month: { remaining_minor: 5000 },
          },
          campaigns: [campaign(first), campaign(second)],
        };
        return {
          restored: subject.generationCampaignSelectionState(data, {
            status: "ready",
            currentCampaignId: first,
            preferredCampaignId: second,
          }),
          reselection: subject.generationCampaignSelectionState(data, {
            status: "ready",
            currentCampaignId: first,
            requiresExplicitSelection: true,
          }),
          untrusted: subject.generationSpendAllowsMinor({ ...data, ok: false }, 100, first),
          unknownCost: subject.generationSpendAllowsMinor(data, null, first),
        };
        """
    )
    assert result["restored"]["ready"] is True
    assert result["restored"]["selectedId"] == "22222222-2222-4222-8222-222222222222"
    assert result["restored"]["preferredSelectionResolved"] is True
    assert result["reselection"]["selectedId"] == ""
    assert result["reselection"]["explicitSelectionRejected"] is True
    assert result["untrusted"] is False
    assert result["unknownCost"] is False
    assert "syncGenerationCampaignSelectUi(form)" in APP
    assert "pendingGenerationCampaignId" in APP


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
          manager: subject.managerGenerationSpendMarkup(
            { status: "ready", data: blocked },
            { canEdit: true, view: "campaigns" },
          ),
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
    assert "Dry-run задач доступен" in result["loading"]
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
    assert 'from "./generation-spend-view.js?v=20260826.rebuild-clean.35"' in APP
    assert "generationSpend: {" in APP
    assert "async function loadGenerationSpendOverview" in APP
    assert "state.api.generationSpendOverview()" in APP
    assert "if (!state.generationSpend.data || state.generationSpend.status !== \"ready\") return false" in APP
    assert "seedanceSpendAllowed ? \"\" : \"disabled\"" not in APP
    assert "gen4SpendAllowed ? \"\" : \"disabled\"" not in APP
    assert "Выбор за вами. ИИ может подсказать вариант" in APP
    assert "Dry-run задач · без файлов и списаний" in APP
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


def test_spend_explanation_is_provider_neutral_for_multimodel_routes() -> None:
    assert "Перед каждым платным запросом к провайдеру" in VIEW
    assert "Перед каждым запросом к Runway" not in VIEW


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
    assert './manager-dashboard.css?v=20260826.rebuild-clean.35' in INDEX
    assert './app.js?v=20260826.rebuild-clean.35' in INDEX
    assert './supabase-api.js?v=20260826.rebuild-clean.35' in APP


def test_campaign_create_field_survives_desktop_sanitizer_dom_clobbering_pass() -> None:
    # DOMPurify SANITIZE_DOM strips name attributes whose values collide with
    # document/form properties (e.g. name="name" clobbers form.name), so the
    # campaign name must travel under a non-clobbering field name.
    result = _run_view(
        """
        const data = {
          ok: true,
          currency: "USD",
          blocker_code: null,
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 2500,
            monthly_limit_minor: 10000,
            per_request_limit_minor: 232,
            version: 1,
          },
          usage: {
            day: { reserved_minor: 0, committed_minor: 0, remaining_minor: 2500 },
            month: { reserved_minor: 0, committed_minor: 0, remaining_minor: 10000 },
          },
        };
        return subject.managerGenerationSpendMarkup(
          { status: "ready", data },
          { canEdit: true, view: "new-campaign" },
        );
        """
    )
    assert 'name="campaign_name"' in result
    assert 'name="name"' not in result
    create = APP[
        APP.index("async function submitGenerationCampaignCreate")
        : APP.index("async function submitGenerationCampaignPolicy")
    ]
    assert 'values.get("campaign_name")' in create
    assert 'values.get("name")' not in create


def test_form_field_names_avoid_dom_clobbering_across_web_app() -> None:
    # The desktop v4 window renderer sanitizes markup with a DOM-clobbering
    # guard (DOMPurify SANITIZE_DOM): any name="..." value that exists as a
    # property of document or of a form element is silently stripped, so the
    # field never reaches FormData. Keep every field name outside that set.
    clobbering = {
        "name", "id", "title", "action", "method", "target", "elements",
        "length", "submit", "reset", "style", "dir", "lang", "hidden",
        "children", "attributes", "body", "head", "forms", "location",
        "all", "cookie", "domain", "referrer", "dataset", "className",
        "innerHTML", "innerText", "prefix", "slot", "part", "nonce",
    }
    offenders = []
    for path in sorted(APP_DIR.glob("*.js")) + sorted(APP_DIR.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'name="([A-Za-z_][\w-]*)"', text):
            if match.group(1) in clobbering:
                offenders.append(f"{path.name}: name=\"{match.group(1)}\"")
    assert offenders == []


def test_budget_refusals_reach_operator_by_name() -> None:
    """Боевой отказ 25.08.2026: дневной бюджет кампании исчерпан ($24.62 из
    $25), а оператор увидел «Сервис платной генерации временно недоступен» и
    решил, что портал сломан. Денежные стражи обязаны называться по имени:
    edge пробрасывает точный код (409, а не смазанный 503), клиентский словарь
    стратегии объясняет, что деньги не списаны и какой лимит поднять."""
    edge = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
        encoding="utf-8"
    )
    budget_codes = (
        "generation_campaign_daily_budget_exceeded",
        "generation_campaign_monthly_budget_exceeded",
        "generation_campaign_per_request_budget_exceeded",
        "generation_daily_budget_exceeded",
        "generation_monthly_budget_exceeded",
        "generation_per_request_budget_exceeded",
    )
    edge_set = edge.split("GENERATION_BUDGET_CODES = new Set([", 1)[1]
    edge_set = edge_set.split("]);", 1)[0]
    for code in budget_codes:
        assert f'"{code}"' in edge_set
        assert f"{code}:" in API
    assert "GENERATION_BUDGET_CODES.has(code)) return { code, status: 409 }" in edge
    strategy_map = API.split("generation_unavailable:", 1)[1]
    for code in budget_codes:
        assert "Деньги не списаны" in strategy_map.split(f"{code}:", 1)[1].split('",', 1)[0]
