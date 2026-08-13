from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
VIEW = (APP_DIR / "product-research-view.js").read_text(encoding="utf-8")
TRAINING = (APP_DIR / "workspace-ai-research-training.js").read_text(
    encoding="utf-8"
)
EXACT_YOUTUBE = (
    APP_DIR / "workspace-ai-exact-youtube-sources.js"
).read_text(encoding="utf-8")
BOOTSTRAP = (
    APP_DIR / "workspace-research-training-bootstrap.js"
).read_text(encoding="utf-8")

CONFIRMATION = (
    "OPENAI_GPT_5_5_WEB_RESEARCH_20260813_"
    "DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000"
)


def _node_module(source: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(source, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _tariff_js() -> str:
    return f"""
      version: 'openai-api-2026-08-13-gpt-5.5-standard-context-v3',
      provider: 'openai',
      provider_key: 'openai_web_search',
      adapter_version: 'openai-responses-web-search-v1',
      model: 'gpt-5.5',
      currency: 'USD',
      billing_mode: 'metered_actual_usage',
      service_tier: 'default',
      input_usd_per_million_tokens: '5.00',
      output_usd_per_million_tokens: '30.00',
      long_context_threshold_input_tokens: 272000,
      long_context_input_usd_per_million_tokens: '10.00',
      long_context_output_usd_per_million_tokens: '45.00',
      web_search_usd_per_call: '0.01',
      max_output_tokens: 18000,
      max_provider_attempts: 1,
      fixed_total: false,
      confirmation_value: '{CONFIRMATION}',
    """


def test_operator_tariff_markup_is_exact_metered_and_never_prechecked() -> None:
    result = _node_module(
        VIEW,
        f"""
        const tariff = {{ {_tariff_js()} }};
        const html = subject.productResearchInputMarkup({{
          exactPaidAuthorizationRequired: true,
          paidTariff: tariff,
          defaults: {{
            platforms: ['youtube'],
            paid_analysis_confirmation: tariff.confirmation_value,
          }},
        }});
        const invalidHtml = subject.productResearchInputMarkup({{
          exactPaidAuthorizationRequired: true,
          paidTariff: {{ ...tariff, unexpected: true }},
        }});
        const evidence = subject.productResearchEvidenceMarkup({{
          status: 'completed',
          score: 61,
          sources: [],
        }}, {{
          aiReceiptHref: '#/workspace/ai?project_id=11111111-1111-4111-8111-111111111111&category=food&receipt=22222222-2222-4222-8222-222222222222',
          canStartNew: true,
        }});
        const confirmation = {{ checked: true }};
        const form = {{ elements: {{ paid_analysis_confirmation: confirmation }} }};
        const ownClickKept = subject.invalidateProductResearchPaidConfirmation(
          form,
          'paid_analysis_confirmation',
        );
        const inputMutationCleared = subject.invalidateProductResearchPaidConfirmation(
          form,
          'product_name',
        );
        return {{
          html,
          invalidHtml,
          evidence,
          ownClickKept,
          inputMutationCleared,
          confirmationChecked: confirmation.checked,
        }};
        """,
    )
    html = result["html"]
    assert 'name="paid_analysis_confirmation"' in html
    confirmation_fragment = html[html.index('name="paid_analysis_confirmation"') :]
    assert "checked" not in confirmation_fragment.split("</label>", 1)[0]
    assert 'name="paid_analysis_ack"' not in html
    assert "вход $5.00" in html
    assert "выход $30.00" in html
    assert "272000" in html
    assert "вход $10.00" in html
    assert "выход $45.00" in html
    assert "стандартный режим default" in html
    assert "веб-поиск $0.01" in html
    assert "Итоговая сумма заранее не фиксирована" in html
    assert "Точный тариф сейчас недоступен" in result["invalidHtml"]
    assert 'aria-disabled="true"' in result["invalidHtml"]
    assert 'data-product-research-evidence-read-only="true"' in result["evidence"]
    assert "<form" not in result["evidence"]
    assert "<textarea" not in result["evidence"]
    assert "Открыть свой чек в ИИ-центре" in result["evidence"]
    assert "Подготовить новое исследование" in result["evidence"]
    assert result["ownClickKept"] is False
    assert result["inputMutationCleared"] is True
    assert result["confirmationChecked"] is False
    assert CONFIRMATION in APP
    assert CONFIRMATION in VIEW
    assert CONFIRMATION in API


def test_paid_authorization_is_whole_on_wire_but_absent_from_retry_storage() -> None:
    result = _node_module(
        API,
        f"""
        const tariff = {{ {_tariff_js()} }};
        const storage = new Map();
        globalThis.window = {{
          sessionStorage: {{
            getItem: (key) => storage.get(key) || null,
            setItem: (key, value) => storage.set(key, String(value)),
          }},
        }};
        const rpcCalls = [];
        const supabase = {{
          schema: () => ({{
            rpc: async (name, args) => {{
              rpcCalls.push({{ name, payload: structuredClone(args.p_payload) }});
              return {{ data: null, error: {{ message: 'offline' }} }};
            }},
          }}),
        }};
        const api = new subject.CreatorApi(supabase, {{
          RPC_SCHEMA: 'public',
          STORAGE_BUCKET: 'private',
        }});
        api.organizationId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
        const input = {{
          product_name: 'Точный товар',
          sku: 'SKU-1',
          product_category: 'food',
          platforms: ['youtube'],
          project_id: '11111111-1111-4111-8111-111111111111',
          paid_analysis_ack: true,
          paid_analysis_authorization: tariff,
        }};
        const errors = [];
        for (let attempt = 0; attempt < 2; attempt += 1) {{
          try {{ await api.startProductResearch(input); }}
          catch (error) {{ errors.push(error.code); }}
        }}
        let changedCode = '';
        try {{
          await api.startProductResearch({{
            ...input,
            paid_analysis_authorization: {{
              ...tariff,
              confirmation_value: 'CALLER_CHANGED_TOKEN',
            }},
          }});
        }} catch (error) {{ changedCode = error.code; }}
        let extraCode = '';
        try {{
          await api.startProductResearch({{
            ...input,
            paid_analysis_authorization: {{ ...tariff, extra: true }},
          }});
        }} catch (error) {{ extraCode = error.code; }}
        return {{
          errors,
          changedCode,
          extraCode,
          rpcCalls,
          stored: [...storage.values()].join('\\n'),
          inputUnchanged: JSON.stringify(input.paid_analysis_authorization)
            === JSON.stringify(tariff),
        }};
        """,
    )
    assert result["errors"] == ["creator_api_error", "creator_api_error"]
    assert result["changedCode"] == "product_research_paid_authorization_invalid"
    assert result["extraCode"] == "product_research_paid_authorization_invalid"
    assert len(result["rpcCalls"]) == 2
    assert result["rpcCalls"][0]["payload"]["paid_analysis_authorization"] == (
        result["rpcCalls"][1]["payload"]["paid_analysis_authorization"]
    )
    assert result["rpcCalls"][0]["payload"]["paid_analysis_authorization"][
        "confirmation_value"
    ] == CONFIRMATION
    assert (
        result["rpcCalls"][0]["payload"]["idempotency_key"]
        == result["rpcCalls"][1]["payload"]["idempotency_key"]
    )
    assert "confirmation_value" not in result["stored"]
    assert CONFIRMATION not in result["stored"]
    assert result["inputUnchanged"] is True


def test_operator_shell_is_server_capability_driven_and_pending_safe() -> None:
    assert "flow.capabilities" not in APP  # no permissive alias branch
    for canonical in (
        "source.capabilities",
        "source.research_context",
        "researchContext.latest_own_run",
        "researchContext.paid_tariff",
        "can_start_paid_own",
        "can_read_own",
        "can_read_receipt",
        "can_decide_own",
        "can_edit_own",
        "receipt_scope",
        "run_scope",
    ):
        assert canonical in APP
    assert 'new Set(["research", "ai"])' in APP
    assert "pendingProjectCapability" in APP
    assert 'data-ai-research-training-host' in APP
    assert "canOpenProjectAiResearch() && !canViewLegacyAiLearning()" in APP
    operator_shell = APP[
        APP.index("function renderAiLearningSection") :
        APP.index("function stopAiLearningPolling")
    ]
    assert "loadAiLearningControlRoom" not in operator_shell
    assert "latestOwnProjectResearchRun" in APP
    assert "projectResearchRunAllowedByServer" in APP
    assert "does not persist this checkbox" in APP
    assert 'if (field.name === "paid_analysis_confirmation") return []' in APP
    assert "item.elementIndex === fieldIndex" in APP
    assert 'field.name === "paid_analysis_confirmation"' in APP
    assert APP.count("paid_analysis_authorization: paidTariff") >= 2
    activate = APP[
        APP.index("function activateWorkspaceProject(") :
        APP.index("function clearWorkspaceProjectSelection(")
    ]
    clear = APP[
        APP.index("function clearWorkspaceProjectSelection(") :
        APP.index("function workspaceProjectHref(")
    ]
    for project_reset in (activate, clear):
        assert "state.productResearch.prefill = null" in project_reset
        assert "state.productResearch.preservedSnapshot = null" in project_reset
        assert "resetResearchStageControl()" in project_reset


def test_operator_ai_queue_and_exact_youtube_are_fail_closed() -> None:
    result = _node_module(
        TRAINING,
        """
        const project = '11111111-1111-4111-8111-111111111111';
        const own = modValue({ ownership: 'own' });
        function modValue(item) {
          return subject.projectScopedTrainingSnapshot({
            project_id: project,
            queue: [{ project_id: project, receipt_id: 'r', ...item }],
            learned: [{ project_id: project, selection_id: 's', ...item }],
          }, project, 'own');
        }
        const missingOwnership = modValue({});
        const sibling = modValue({ ownership: 'project' });
        const crossProject = subject.projectScopedTrainingSnapshot({
          project_id: project,
          queue: [{
            project_id: '22222222-2222-4222-8222-222222222222',
            ownership: 'own',
          }],
          learned: [],
        }, project, 'own');
        return {
          ownAccepted: Boolean(own),
          missingOwnership,
          sibling,
          crossProject,
        };
        """,
    )
    assert result == {
        "ownAccepted": True,
        "missingOwnership": None,
        "sibling": None,
        "crossProject": None,
    }
    for marker in (
        "data-ai-research-training-host",
        "aiResearchReceiptScope",
        'receiptScope === "own"',
        'item?.ownership !== "own"',
        'card.dataset.ownership !== "own"',
        'params.getAll("receipt")',
        'card.dataset.canDecide !== "true"',
        'card.dataset.canEdit !== "true"',
        "contentengine:workspace-capabilities-ready",
    ):
        assert marker in TRAINING
    assert 'aiExactYoutubeSourceScope === "project"' in EXACT_YOUTUBE
    assert "exactYoutubeProjectScopeAllowed()" in EXACT_YOUTUBE
    assert "contentengine:workspace-capabilities-ready" in EXACT_YOUTUBE
    assert "aiProjectAssetAllowed" in BOOTSTRAP
    assert 'return exactYoutubeScope === "project"' in BOOTSTRAP
    assert "contentengine:workspace-capabilities-ready" in BOOTSTRAP
    assert 'receipt: clean(latest?.receipt_id' in EXACT_YOUTUBE
    assert "research_receipt:" not in EXACT_YOUTUBE


def test_old_own_research_status_and_paid_start_race_are_authoritative() -> None:
    result = _node_module(
        VIEW,
        """
        const run = '11111111-1111-4111-8111-111111111111';
        const project = '22222222-2222-4222-8222-222222222222';
        const receipt = '33333333-3333-4333-8333-333333333333';
        const own = subject.normalizeProductResearch({
          project_id: project,
          run: { id: run, status: 'completed' },
          research_context: {
            run_id: run,
            project_id: project,
            ownership: 'own',
            product_category: 'food',
            ai_receipt: { receipt_id: receipt, status: 'awaiting_human_review' },
          },
        });
        const sibling = subject.normalizeProductResearch({
          project_id: project,
          run: { id: run, status: 'completed' },
          research_context: {
            run_id: run,
            project_id: project,
            ownership: 'project',
          },
        });
        return {
          own,
          ownAccepted: subject.productResearchStatusMatchesContext(own, {
            runId: run, projectId: project, runScope: 'own',
          }),
          siblingRejected: subject.productResearchStatusMatchesContext(sibling, {
            runId: run, projectId: project, runScope: 'own',
          }),
          crossProjectRejected: subject.productResearchStatusMatchesContext(own, {
            runId: run,
            projectId: '44444444-4444-4444-8444-444444444444',
            runScope: 'own',
          }),
          currentStart: subject.productResearchRequestContextMatches(
            { requestId: 7, projectId: project },
            { requestId: 7, projectId: project },
          ),
          switchedProject: subject.productResearchRequestContextMatches(
            { requestId: 7, projectId: project },
            { requestId: 7, projectId: '44444444-4444-4444-8444-444444444444' },
          ),
          supersededRequest: subject.productResearchRequestContextMatches(
            { requestId: 7, projectId: project },
            { requestId: 8, projectId: project },
          ),
        };
        """,
    )
    assert result["ownAccepted"] is True
    assert result["siblingRejected"] is False
    assert result["crossProjectRejected"] is False
    assert result["currentStart"] is True
    assert result["switchedProject"] is False
    assert result["supersededRequest"] is False
    assert result["own"]["projectId"] == "22222222-2222-4222-8222-222222222222"
    assert result["own"]["ownership"] == "own"
    assert result["own"]["statusAuthorityVerified"] is True
    assert result["own"]["statusProductCategory"] == "food"
    assert result["own"]["aiReceipt"]["receiptId"] == (
        "33333333-3333-4333-8333-333333333333"
    )
    assert "persistProductResearchRunId(run?.id, projectId)" in APP
    assert "if (!startRequestIsCurrent()) return" in APP
    assert "if (!exactStartRequestIsCurrent()) return" in APP
    exact_start = APP[
        APP.index("async function submitExactYoutubeResearchEvidence(") :
        APP.index("async function submitContentReview(")
    ]
    assert "const exactSubmissionIsCurrent = () =>" in exact_start
    assert exact_start.count("if (!exactSubmissionIsCurrent()) return;") >= 5
    before_dispatch = exact_start[:exact_start.index("paidDispatchStarted = true")]
    assert before_dispatch.rindex("if (!exactSubmissionIsCurrent()) return;") > before_dispatch.index(
        "await persistContentReviewVideoEvidence("
    )
    nonrecoverable_catch = exact_start[exact_start.index("    } else {", exact_start.index("  } catch (error)")):]
    assert "if (!exactSubmissionIsCurrent()) return;" in nonrecoverable_catch
    assert "product_research_status_scope_mismatch" in APP
    assert "if (!key || !isWorkspaceProjectId(normalizedRunId)) return" in APP
    exact_youtube_tariff = APP[
        APP.index("function exactYoutubePaidAuthorizationMarkup(") :
        APP.index("function exactYoutubeResearchEvidenceRouteContext(")
    ]
    for marker in (
        "tariff.long_context_threshold_input_tokens",
        "tariff.long_context_input_usd_per_million_tokens",
        "tariff.long_context_output_usd_per_million_tokens",
        "tariff.service_tier",
        "повышенный тариф применяется ко всему запросу",
        "Итоговая сумма заранее не фиксирована",
    ):
        assert marker in exact_youtube_tariff
    polling = APP[
        APP.index("function scheduleProductResearchPolling(") :
        APP.index("async function pollProductResearchStatus(")
    ]
    assert 'state.productResearch.phase === "error"' in polling
    assert "latestOwnProjectResearchRun()?.run_id === normalizedRunId" not in APP


def test_exact_receipt_route_is_server_selected_and_file_source_focuses_media() -> None:
    assert "...(selectedReceiptKey ? { receipt_id: selectedReceiptKey } : {})" in TRAINING
    assert "&media=${encodeURIComponent(mediaId)}" in TRAINING
