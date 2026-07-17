from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "web" / "app" / "access-center-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "access-center.css").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "web" / "app" / "manager-dashboard-view.js").read_text(encoding="utf-8")


def _run_module(module_source: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(module_source, encoding="utf-8")
        (workdir / "contract.mjs").write_text(
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


def test_access_center_normalizes_honest_delivery_states_and_blocks_terminal_email_failures() -> None:
    result = _run_module(
        VIEW,
        """
        const subject = await import("./subject.mjs");
        const statuses = ["delivered", "deferred", "bounced", "complained", "failed", "suppressed", "accepted_unconfirmed"];
        const records = Object.fromEntries(statuses.map((delivery_status) => {
          const raw = {
            ok: true,
            action: "inspect",
            email: "Creator.Test@Example.com",
            access: {
              account_state: "recovery_required",
              recommended_action: "recovery",
              membership: { exists: true, status: "active", role: "trainee" },
              identity: { exists: true, email_confirmed: true, disabled: false },
              delivery: { delivery_status },
            },
          };
          return [delivery_status, subject.normalizeAccessCenterResult(raw)];
        }));
        for (const dispatch_status of ["failed", "suppressed"]) {
          records[`dispatch_${dispatch_status}`] = subject.normalizeAccessCenterResult({
            access: {
              account_state: "recovery_required",
              recommended_action: "recovery",
              membership: { exists: true },
              identity: { exists: true },
              delivery: { status: dispatch_status, delivery_status: "unknown" },
            },
          });
        }
        return records;
        """,
    )

    assert result["delivered"]["delivery"]["status"] == "delivered"
    assert result["deferred"]["delivery"]["status"] == "deferred"
    assert result["accepted_unconfirmed"]["delivery"]["status"] == "accepted"
    assert result["bounced"]["repairBlocked"] is True
    assert result["complained"]["repairBlocked"] is True
    assert result["failed"]["repairBlocked"] is True
    assert result["suppressed"]["repairBlocked"] is True
    assert result["delivered"]["repairBlocked"] is False
    assert result["dispatch_failed"]["delivery"]["status"] == "unknown"
    assert result["dispatch_failed"]["repairBlocked"] is False
    assert result["dispatch_suppressed"]["delivery"]["status"] == "unknown"
    assert result["dispatch_suppressed"]["repairBlocked"] is False


def test_access_center_markup_is_accessible_exact_and_disables_repair_after_bounce() -> None:
    result = _run_module(
        VIEW,
        """
        const subject = await import("./subject.mjs");
        const raw = {
          ok: true,
          action: "repair",
          email: "second.creator@example.com",
          outcome: "manual_review",
          access: {
            account_state: "unknown",
            recommended_action: "manual_review",
            membership: { exists: false },
            identity: { exists: true, email_confirmed: false },
            delivery: { purpose: "invite", delivery_status: "bounced" },
          },
        };
        const html = subject.accessCenterMarkup({
          status: "ready",
          email: "second.creator@example.com",
          result: raw,
          notice: "Проверка завершена",
        });
        return {
          exactEmail: html.includes("second.creator@example.com"),
          exactAction: html.includes("Проверить и восстановить доступ"),
          form: html.includes('id="manager-access-form"'),
          labelled: html.includes('aria-labelledby="manager-access-title"'),
          live: html.includes('role="status"') && html.includes('aria-live="polite"'),
          alert: html.includes('role="alert"'),
          disabled: html.includes('disabled aria-disabled="true"'),
          identity: html.includes("Учётная запись"),
          membership: html.includes("Членство в команде"),
          delivery: html.includes("Последнее письмо") && html.includes("Письмо возвращено"),
        };
        """,
    )

    assert all(result.values())


def test_failed_and_suppressed_delivery_have_distinct_manual_review_copy() -> None:
    result = _run_module(
        VIEW,
        """
        const subject = await import("./subject.mjs");
        const markup = (delivery_status) => subject.accessCenterMarkup({
          status: "ready",
          email: "creator@example.com",
          result: {
            ok: true,
            action: "inspect",
            email: "creator@example.com",
            access: {
              account_state: "unknown",
              recommended_action: "manual_review",
              membership: {},
              identity: {},
              delivery: { delivery_status },
            },
          },
        });
        const failed = markup("failed");
        const suppressed = markup("suppressed");
        return {
          failedProvider: failed.includes("Ошибка почтового провайдера"),
          failedManual: failed.includes("ручной проверки причины"),
          suppressedDuplicate: suppressed.includes("Повтор подавлен"),
          suppressedNotSent: suppressed.includes("Новое письмо не отправлялось"),
          bothDisabled: [failed, suppressed].every((html) => html.includes('disabled aria-disabled="true"')),
        };
        """,
    )

    assert all(result.values())


def test_creator_api_calls_only_creator_access_with_exact_manager_target() -> None:
    result = _run_module(
        API,
        """
        globalThis.window = {
          sessionStorage: {
            getItem() { return null; },
            setItem() {},
          },
        };
        const calls = [];
        const responses = [
          {
            ok: true,
            action: "inspect",
            email: "creator.test@example.com",
            access: { account_state: "recovery_required", recommended_action: "recovery", membership: {}, identity: {}, delivery: {} },
          },
          {
            ok: true,
            action: "repair",
            email: "creator.test@example.com",
            outcome: "recovery_requested",
            access: { account_state: "pending_delivery", recommended_action: "wait", membership: {}, identity: {}, delivery: {} },
          },
        ];
        const supabase = {
          schema() { return { rpc: async () => ({ data: {}, error: null }) }; },
          auth: { getSession: async () => ({ data: { session: { access_token: "manager-token" } }, error: null }) },
          functions: {
            invoke: async (name, options) => {
              calls.push({ name, options });
              return { data: responses.shift(), error: null };
            },
          },
        };
        const { CreatorApi } = await import("./subject.mjs");
        const api = new CreatorApi(supabase, { RPC_SCHEMA: "public", STORAGE_BUCKET: "private" });
        await api.inspectAccess(" Creator.Test@Example.com ");
        await api.repairAccess("Creator.Test@Example.com", "3b216b9d-b7b5-4ed4-9d40-e041bf2af676");
        return calls;
        """,
    )

    assert [call["name"] for call in result] == ["creator-access", "creator-access"]
    assert result[0]["options"]["body"] == {
        "action": "inspect",
        "email": "creator.test@example.com",
    }
    assert result[1]["options"]["body"] == {
        "action": "repair",
        "email": "creator.test@example.com",
        "request_id": "3b216b9d-b7b5-4ed4-9d40-e041bf2af676",
    }
    assert result[0]["options"]["headers"]["Authorization"] == "Bearer manager-token"


def test_creator_api_sanitizes_edge_errors_and_never_echoes_provider_payloads() -> None:
    result = _run_module(
        API,
        """
        globalThis.window = {
          sessionStorage: {
            getItem() { return null; },
            setItem() {},
          },
        };
        const supabase = {
          schema() { return { rpc: async () => ({ data: {}, error: null }) }; },
          auth: { getSession: async () => ({ data: { session: { access_token: "manager-token" } }, error: null }) },
          functions: {
            invoke: async () => ({
              data: null,
              error: {
                code: "FunctionsHttpError",
                message: "provider-secret-body",
                context: {
                  clone() {
                    return {
                      json: async () => ({
                        code: "email_rate_limited",
                        retry_after_seconds: 60,
                        provider_debug: "must-never-surface",
                      }),
                    };
                  },
                },
              },
            }),
          },
        };
        const { CreatorApi } = await import("./subject.mjs");
        const api = new CreatorApi(supabase, { RPC_SCHEMA: "public", STORAGE_BUCKET: "private" });
        try {
          await api.inspectAccess("creator.test@example.com");
          return { failed: false };
        } catch (error) {
          return {
            failed: true,
            code: error.code,
            message: error.message,
            details: error.details,
          };
        }
        """,
    )

    assert result["failed"] is True
    assert result["code"] == "email_rate_limited"
    assert "60" in result["message"]
    assert "provider" not in result["message"].lower()
    assert result["details"] == {"retry_after_seconds": 60}


def test_manager_workspace_wires_server_inspection_repair_and_refresh() -> None:
    for marker in (
        'from "./access-center-view.js?v=20260717.1"',
        "ensureAccessCenterStyles();",
        "accessCenterMarkup(state.accessCenter)",
        'action === "open-manager-access"',
        'action === "reset-manager-access"',
        'form.id === "manager-access-form"',
        "state.api.inspectAccess(normalizedEmail)",
        "state.api.repairAccess(normalizedEmail)",
        "refreshManagerDataAfterAccessRepair()",
        'loadSection("team", { silent: true })',
        "loadManagerDashboard({ silent: true })",
    ):
        assert marker in APP

    recovery_handler = APP.split('if (action === "send-manager-recovery")', 1)[1].split(
        'if (action === "copy-manager-reminder")',
        1,
    )[0]
    assert "resetPasswordForEmail" not in recovery_handler
    assert "openManagerAccessCenter(email)" in recovery_handler

    retry_function = APP.split("async function retryManagerInvite", 1)[1].split(
        "async function normalizeInviteFunctionError",
        1,
    )[0]
    assert '"creator-invite"' not in retry_function
    assert "openManagerAccessCenter(normalizedEmail)" in retry_function

    public_reset = APP.split("async function submitReset", 1)[1].split(
        "async function submitPassword",
        1,
    )[0]
    assert "resetPasswordForEmail" in public_reset


def test_manager_dashboard_exposes_only_the_verified_access_center_action() -> None:
    assert 'data-action="open-manager-access"' in DASHBOARD
    assert "Проверить и восстановить доступ" in DASHBOARD
    assert '<button class="btn btn-secondary btn-small" type="button" data-action="retry-manager-invite"' not in DASHBOARD
    assert '<button class="btn btn-secondary btn-small" type="button" data-action="send-manager-recovery"' not in DASHBOARD


def test_access_center_styles_are_scoped_responsive_theme_aware_and_injected_once() -> None:
    assert "link[data-access-center-styles]" in VIEW
    assert 'link.href = "./access-center.css?v=20260717.1"' in VIEW
    assert './access-center.css?v=20260717.1' in (
        ROOT / "web" / "app" / "index.html"
    ).read_text(encoding="utf-8")
    assert ".access-center" in CSS
    assert "var(--portal-surface" in CSS
    assert "var(--portal-primary" in CSS
    assert "var(--portal-ink" in CSS
    assert "var(--portal-ink-soft" in CSS
    assert "--portal-heading" not in CSS
    assert "--portal-muted" not in CSS
    assert "@media (max-width: 680px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
