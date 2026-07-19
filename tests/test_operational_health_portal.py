from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "web" / "app" / "manager-dashboard-view.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "manager-dashboard.css").read_text(encoding="utf-8")
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


def test_operational_health_api_is_organization_scoped() -> None:
    assert 'operationalHealth: "creator_operational_health"' in API
    assert "operationalHealth()" in API
    method = API[API.index("operationalHealth()") : API.index("inspectAccess(email)")]
    assert "this.call(RPC.operationalHealth, this.withOrganization({}))" in method
    assert "worker_secret" not in method
    assert "lease" not in method


def test_operational_card_marks_stalled_generation_as_danger_without_echoing_server_codes() -> None:
    result = _run_view(
        """
        const html = subject.managerDashboardMarkup({}, {
          status: "ready",
          data: {
            organization_id: "private-org-id",
            scheduler: { ready: true },
            worker: {
              ready: true,
              heartbeat_fresh: true,
              heartbeat_at: "2026-07-17T10:00:00Z",
              latest_error_code: "secret-provider-detail",
            },
            generation: { active: 4, due: 2, stalled: 1 },
          },
        });
        return { html };
        """
    )
    html = result["html"]
    assert "manager-operations-danger" in html
    assert "Требуется внимание руководителя" in html
    assert "без нового платного запуска" in html
    assert "secret-provider-detail" not in html
    assert "private-org-id" not in html


def test_operational_card_is_green_only_for_server_confirmed_scheduler_and_worker() -> None:
    result = _run_view(
        """
        const html = subject.managerDashboardMarkup({}, {
          status: "ready",
          data: {
            scheduler: { ready: true },
            worker: { ready: true, heartbeat_fresh: true, heartbeat_at: "2026-07-17T10:00:00Z" },
            generation: { active: 0, due: 0, stalled: 0 },
          },
        });
        return { html };
        """
    )
    assert "manager-operations-success" in result["html"]
    assert "Фоновая работа в норме" in result["html"]


def test_refreshing_card_has_precise_copy_busy_state_and_disabled_retry() -> None:
    result = _run_view(
        """
        const html = subject.managerOperationalHealthMarkup({
          status: "refreshing",
          data: {
            scheduler: { ready: true },
            worker: { ready: true, heartbeat_fresh: true, heartbeat_at: "2026-07-17T10:00:00Z" },
            generation: { active: 0, due: 0, stalled: 0 },
          },
        });
        return { html };
        """
    )
    html = result["html"]
    assert "Обновляем подтверждение" in html
    assert 'aria-busy="true"' in html
    assert 'aria-live="polite"' in html
    assert "disabled" in html
    assert "часть задач ещё находится в очереди" not in html


def test_dashboard_and_health_fail_independently_and_refresh_together() -> None:
    loader = APP[APP.index("async function loadManagerDashboard") : APP.index("async function hydratePrivateMedia")]
    assert "Promise.allSettled" in loader
    assert "const dashboardRequest" in loader
    assert "const healthRequest" in loader
    assert "state.api.managerDashboard()" in loader
    assert "state.api.operationalHealth()" in loader
    assert loader.count("WORKSPACE_REQUEST_TIMEOUT_MS") == 3
    assert '"manager_dashboard_timeout"' in loader
    assert '"operational_health_timeout"' in loader
    assert 'health.status = "error"' in loader
    assert 'target.status = "error"' in loader
    assert "loadGenerationSpendOverview({ silent: true, force: true })" in loader
    assert "managerDashboardMarkup(dashboard.data || {}, state.operationalHealth)" in APP
    assert "managerOperationalHealthMarkup(state.operationalHealth)" in APP


def test_visible_team_dashboard_refreshes_stale_server_health() -> None:
    assert "function managerDashboardIsStale()" in APP
    assert "state.operationalHealth.updatedAt" in APP
    assert "function refreshManagerDashboardIfStale()" in APP
    assert "document.visibilityState !== \"visible\"" in APP
    assert "MANAGER_DASHBOARD_MAX_AGE_MS" in APP
    assert "refreshManagerDashboardIfStale();" in APP
    assert "void loadManagerDashboard({ silent: true })" in APP


def test_operational_card_is_responsive_theme_aware_and_cache_busted() -> None:
    for marker in (
        ".manager-operations",
        ".manager-operations-success",
        ".manager-operations-warning",
        ".manager-operations-danger",
        "var(--surface",
        "var(--ink",
        "@media (max-width: 720px)",
    ):
        assert marker in CSS
    assert './manager-dashboard.css?v=20260717.5' in INDEX
    assert './app.js?v=20260719.1' in INDEX
    assert './supabase-api.js?v=20260718.2' in APP
    assert 'from "./manager-dashboard-view.js?v=20260718.1"' in APP
