from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040010_research_ai_handoff.sql"
)
RESEARCH_VIEW_PATH = ROOT / "web" / "app" / "product-research-view.js"
AI_VIEW_PATH = ROOT / "web" / "app" / "ai-learning-control-room.js"
APP_PATH = ROOT / "web" / "app" / "app.js"
API_PATH = ROOT / "web" / "app" / "supabase-api.js"

PRODUCT_CATEGORIES = (
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing research AI handoff asset: {path}"
    return path.read_text(encoding="utf-8")


def _sql_function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(qualified_name)}\s*\(",
        source,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"Missing SQL function {qualified_name}"
    next_match = re.search(
        r"\ncreate\s+or\s+replace\s+function\s+",
        source[match.end() :],
        flags=re.IGNORECASE,
    )
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(_read(path), encoding="utf-8")
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


def test_migration_is_valid_append_only_and_cross_organization_scoped() -> None:
    migration = _read(MIGRATION_PATH)
    parse_sql(migration)

    assert "create table if not exists content_factory.research_ai_category_bindings" in migration
    assert "create table if not exists content_factory.ai_research_evidence_receipts" in migration
    for category in PRODUCT_CATEGORIES:
        assert f"'{category}'" in migration
    assert migration.count("enable row level security") >= 2
    assert "unique (organization_id, run_id)" in migration
    assert "research_ai_category_binding_immutable" in migration
    assert "ai_research_evidence_receipt_append_only" in migration
    assert "create table if not exists content_factory.ai_research_evidence_dispositions" in migration
    assert "ai_research_evidence_disposition_append_only" in migration
    assert "unique (organization_id, receipt_id)" in migration
    assert "decision in ('approve', 'reject')" in migration
    assert "before update or delete" in migration
    assert "from public, anon, authenticated, service_role" in migration


def test_paid_project_research_requires_an_exact_category_and_never_infers_it() -> None:
    migration = _read(MIGRATION_PATH)
    start = _sql_function(migration, "public.creator_start_project_research")

    assert "product_research_ai_category_required" in start
    assert "require_ai_product_category" in start
    assert "delegated_payload := p_payload - 'product_category'" in start
    assert "creator_start_project_research_pre_ai_handoff_v1" in start
    assert "insert into content_factory.research_ai_category_bindings" in start
    assert "on conflict (organization_id, run_id) do nothing" in start
    assert "research_ai_category_binding_conflict" in start
    assert "'binding_kind', 'explicit_paid_start'" in start
    assert "category_name" not in start
    assert "product.title" not in start
    assert "product.sku" not in start


def test_successful_completion_emits_only_a_human_review_inbox_receipt() -> None:
    migration = _read(MIGRATION_PATH)
    completion = _sql_function(
        migration, "public.system_complete_product_research"
    )

    delegate = completion.index("complete_product_research_pre_ai_handoff_v1")
    insert = completion.index(
        "insert into content_factory.ai_research_evidence_receipts"
    )
    assert delegate < insert
    assert "completion_value ->> 'status' <> 'completed'" in completion
    assert "binding.organization_id = run_row.organization_id" in completion
    assert "binding.run_id = run_row.id" in completion
    assert "unmapped_legacy_run" in completion
    assert "on conflict (organization_id, run_id) do nothing" in completion
    assert "ai_research_evidence_receipt_conflict" in completion
    assert "'status', 'awaiting_human_review'" in completion
    assert "'raw_research_enters_prompt_automatically', false" in completion
    assert "'affects_effective_policy', false" in completion
    assert "ai_effective_category_policies" not in completion
    assert "ai_teaching_card_decisions" not in completion


def test_ai_control_room_inbox_is_exactly_org_and_category_scoped() -> None:
    migration = _read(MIGRATION_PATH)
    control = _sql_function(
        migration, "public.creator_ai_learning_control_room"
    )

    assert "creator_ai_learning_control_room_pre_research_inbox_v1" in control
    assert "receipt.organization_id = organization_id_value" in control
    assert "receipt.product_category = category_value" in control
    assert "receipt.status = 'awaiting_human_review'" in control
    assert "ai_research_evidence_dispositions disposition" in control
    assert "not exists" in control
    assert "run.project_id = receipt.project_id" in control
    assert "limit 50" in control.lower()
    assert "'research_inbox', inbox_value" in control
    assert "'research_decisions', decision_history_value" in control
    assert "disposition.organization_id = organization_id_value" in control
    assert "disposition.product_category = category_value" in control
    assert "'can_decide_research_inbox', can_decide_research_value" in control
    assert "'pending_research_inbox_affects_generation', false" in control
    assert "'raw_research_enters_prompt_automatically', false" in control
    assert "#/workspace/research?project_id=" in control
    assert "&run=" in control


def test_research_receipt_decision_is_idempotent_role_scoped_and_never_changes_policy() -> None:
    migration = _read(MIGRATION_PATH)
    decision = _sql_function(
        migration, "public.creator_decide_ai_research_receipt"
    )

    assert "array['owner', 'admin', 'producer']" in decision
    assert "creator_decide_ai_research_receipt" in decision
    assert "begin_command" in decision
    assert "finish_command" in decision
    assert "pg_advisory_xact_lock" in decision
    assert "receipt.organization_id = organization_id_value" in decision
    assert "receipt.product_category = category_value" in decision
    assert "receipt.receipt_hash = receipt_hash_value" in decision
    assert "decision_value not in ('approve', 'reject')" in decision
    assert "ai_research_receipt_already_decided" in decision
    assert "insert into content_factory.ai_research_evidence_dispositions" in decision
    assert "'affects_effective_policy', false" in decision
    assert "'raw_research_enters_prompt_automatically', false" in decision
    assert "ai_effective_category_policies" not in decision
    assert "ai_teaching_card_decisions" not in decision


def test_ai_research_inbox_decision_is_wired_from_button_to_authoritative_snapshot() -> None:
    app = _read(APP_PATH)
    api = _read(API_PATH)

    assert 'decideAiResearchReceipt: "creator_decide_ai_research_receipt"' in api
    assert "decideAiResearchReceipt(input = {})" in api
    assert "RPC.decideAiResearchReceipt" in api
    assert "receipt_id: receiptId" in api
    assert "receipt_hash: receiptHash" in api
    assert "confirmation: true" in api

    assert "async function decideAiResearchReceipt(control)" in app
    assert 'action === "decide-ai-research-receipt"' in app
    assert "await state.api.decideAiResearchReceipt" in app
    assert "applyAuthoritativeAiLearningResponse(response, category)" in app
    assert "busyResearchReceiptId" in app
    assert "не меняет правила и промпты автоматически" in app


def test_provider_status_is_genuinely_read_only_despite_stable_volatility() -> None:
    migration = _read(MIGRATION_PATH)
    status = _sql_function(migration, "public.creator_research_provider_status")
    lowered = status.lower()

    assert re.search(r"\bstable\b", lowered)
    assert "user_id := auth.uid()" in lowered
    assert "authentication_required" in lowered
    assert "current_profile_id" not in lowered
    assert not re.search(r"\b(insert|update|delete)\s+", lowered)
    assert "external_call_performed', false" in status
    assert "to_regclass(" in status
    assert "research_provider_response_bindings" in status
    assert "research_provider_response_receipts" in status
    assert "'response_state', response_state_value" in status
    assert "'binding_state', 'bound'" in status
    assert "'binding_state', 'not_bound'" in status
    assert "'provider_response_suffix', right(" in status
    assert "least(8, length(response.provider_response_id))" in status
    assert "'provider_response_id', response.provider_response_id" not in status
    for forbidden in ("prompt", "response_body", "api_key", "bearer_token"):
        assert f"'{forbidden}'," not in lowered


def test_research_start_ui_requires_one_fixed_category_without_guessing() -> None:
    result = _run_module(
        RESEARCH_VIEW_PATH,
        """
        const html = subject.productResearchInputMarkup({
          defaults: { productCategory: " BAA ", categoryName: "Жевательные БАДы" },
        });
        return {
          normalized: subject.normalizeProductResearchAiCategory(" BAA "),
          rejectedFreeText: subject.normalizeProductResearchAiCategory("БАДы"),
          rejectedUnknown: subject.normalizeProductResearchAiCategory("unknown"),
          categoryCount: subject.PRODUCT_RESEARCH_AI_CATEGORIES.length,
          requiredSelect: html.includes('name="product_category" required'),
          selected: html.includes('value="baa" selected'),
          humanGateCopy: html.includes("ИИ не применит его без проверки человеком"),
          inboxCopy: html.includes("Входящие ИИ-центра"),
          noAutoPolicyCopy: html.includes("не меняет правила ИИ"),
        };
        """,
    )
    assert result == {
        "normalized": "baa",
        "rejectedFreeText": "",
        "rejectedUnknown": "",
        "categoryCount": 8,
        "requiredSelect": True,
        "selected": True,
        "humanGateCopy": True,
        "inboxCopy": True,
        "noAutoPolicyCopy": True,
    }


def test_unknown_paid_provider_outcome_has_one_safe_primary_and_an_explicit_new_charge() -> None:
    result = _run_module(
        RESEARCH_VIEW_PATH,
        """
        const unknown = subject.normalizeProductResearch({ run: {
          id: "40000000-0000-4000-8000-000000000001",
          status: "failed",
          error_code: "provider_outcome_unknown",
          error_message: "provider uncertain",
        }});
        const ordinary = subject.normalizeProductResearch({ run: {
          id: "40000000-0000-4000-8000-000000000002",
          status: "failed",
          error_code: "provider_response_invalid",
        }});
        const unknownHtml = subject.productResearchProgressMarkup(unknown);
        const ordinaryHtml = subject.productResearchProgressMarkup(ordinary);
        const expiredLeaseHtml = subject.productResearchProgressMarkup({
          status: "failed",
          failureCode: "processing_lease_expired",
          providerControl: { runControl: { attempt: { attemptId: "attempt-1" } } },
        });
        const paidFailedHtml = subject.productResearchProgressMarkup({
          status: "failed",
          failureCode: "provider_response_invalid",
          failureMessage: "Формат ответа повреждён.",
          providerControl: {
            runControl: { attempt: { attemptId: "attempt-2" } },
            responseState: {
              bindingState: "bound",
              providerStatus: "completed",
            },
          },
        });
        return {
          failureCode: unknown.failureCode,
          exactTitle: unknownHtml.includes("Ответ провайдера пока не подтверждён"),
          safeStep: unknownHtml.includes("Скопировать ID для поддержки")
            && unknownHtml.includes('data-action="copy-product-research-support-id"')
            && unknownHtml.includes("новый платный анализ запускайте только отдельным"),
          onePrimary: (unknownHtml.match(/data-primary-action="true"/g) || []).length === 1,
          separateNewAnalysis: unknownHtml.includes('class="btn btn-ghost"')
            && unknownHtml.includes('data-action="new-product-research"')
            && !unknownHtml.includes("Начать заново"),
          explicitNewCharge: unknownHtml.includes("Это будет новая подтверждаемая оплата")
            && unknownHtml.includes("старый запрос мог быть принят")
            && unknownHtml.includes("с обязательными подтверждениями"),
          noAutomaticRetry: unknownHtml.includes("не повторяет такой запрос автоматически"),
          ordinaryCanRestart: ordinaryHtml.includes('data-action="new-product-research"'),
          expiredLeaseUsesSafePath: expiredLeaseHtml.includes('data-action="copy-product-research-support-id"')
            && expiredLeaseHtml.includes('data-action="new-product-research"')
            && expiredLeaseHtml.includes('data-primary-action="true"')
            && !expiredLeaseHtml.includes('data-action="refresh-product-research"')
            && !expiredLeaseHtml.includes("Начать заново"),
          paidFailureIsExplicit: paidFailedHtml.includes("Ответ получен — нужна повторная проверка")
            && paidFailedHtml.includes('data-action="revalidate-product-research-response"')
            && paidFailedHtml.includes("без оплаты")
            && paidFailedHtml.includes("не отправляет новый POST")
            && (paidFailedHtml.match(/data-primary-action="true"/g) || []).length === 1
            && !paidFailedHtml.includes('data-action="refresh-product-research"')
            && !paidFailedHtml.includes("Результат нельзя использовать")
            && !paidFailedHtml.includes("Начать заново"),
        };
        """,
    )
    assert result == {
        "failureCode": "provider_outcome_unknown",
        "exactTitle": True,
        "safeStep": True,
        "onePrimary": True,
        "separateNewAnalysis": True,
        "explicitNewCharge": True,
        "noAutomaticRetry": True,
        "ordinaryCanRestart": True,
        "expiredLeaseUsesSafePath": True,
        "paidFailureIsExplicit": True,
    }


def test_provider_status_copy_explains_background_get_without_a_second_charge() -> None:
    result = _run_module(
        RESEARCH_VIEW_PATH,
        """
        const html = subject.researchProviderControlMarkup({
          available: true,
          controls: {
            explicit_paid_analysis_required: true,
            creates_research_runs: false,
            automatic_canary: false,
            automatic_fallback: false,
            external_call_performed: false,
          },
          providers: [],
          run_control: {},
          latest_health: {},
        });
        const normalized = subject.normalizeResearchProviderControl({ control: {
          ok: true,
          version: "research-provider-control-plane-v1",
          providers: [{
            provider_key: "openai_web_search",
            adapter_version: "openai-responses-web-search-v1",
            display_name: "OpenAI web search",
            health: { status: "unknown", fresh: false },
          }],
          run_control: {
            run_id: "40000000-0000-4000-8000-000000000001",
            run_status: "processing",
            attempt: {
              provider_key: "openai_web_search",
              adapter_version: "openai-responses-web-search-v1",
              attempt_number: 1,
            },
          },
          response_state: {
            binding_state: "bound",
            provider_status: "in_progress",
            provider_response_suffix: "A1b2_C3d",
            provider_response_id: "resp_private_full_identifier_must_not_render",
            accepted_at: "2026-08-04T18:00:00Z",
            last_checked_at: "2026-08-04T18:01:00Z",
          },
          controls: {
            explicit_paid_analysis_required: true,
            creates_research_runs: false,
            automatic_canary: false,
            automatic_fallback: false,
            external_call_performed: false,
          },
        }});
        const responseHtml = subject.researchProviderControlMarkup(normalized);
        const utf8 = (value) => Buffer.from(value, "base64").toString("utf8");
        return {
          readsSavedResponse: html.includes(utf8("0YfQuNGC0LDQtdGCINGC0L7Qu9GM0LrQviDRg9C20LUg0YHQvtGF0YDQsNC90ZHQvdC90YvQuSByZXNwb25zZV9pZA==")),
          getOnly: html.includes(utf8("0LLRi9C/0L7Qu9C90Y/QtdGCINGC0L7Qu9GM0LrQviBHRVQ=")),
          noSecondPost: html.includes(utf8("0J/QvtCy0YLQvtGA0L3QvtCz0L4gUE9TVCDQuCDQvdC+0LLQvtCz0L4g0YHQv9C40YHQsNC90LjRjyDQvdC10YI=")),
          paidPostExplicit: html.includes(utf8("0J3QvtCy0YvQuSDQv9C70LDRgtC90YvQuSBQT1NUINCy0L7Qt9C80L7QttC10L0g0YLQvtC70YzQutC+INC60LDQuiDQvtGC0LTQtdC70YzQvdC+0LUg0Y/QstC90L4g0L/QvtC00YLQstC10YDQttC00ZHQvdC90L7QtSDQtNC10LnRgdGC0LLQuNC1")),
          oldClaimAbsent: !html.includes(utf8("0J/RgNC+0LLQtdGA0LrQsCDRgdGC0LDRgtGD0YHQsCDRgdCw0LzQsCDQvdC1INC+0LHRgNCw0YnQsNC10YLRgdGPINCy0L4g0LLQvdC10YjQvdC40Lkg0YHQtdGA0LLQuNGB")),
          responseBound: normalized.responseState.bindingState === "bound"
            && normalized.responseState.providerStatus === "in_progress",
          safeSuffixVisible: responseHtml.includes("…A1b2_C3d")
            && responseHtml.includes("GET"),
          fullIdAbsent: !responseHtml.includes("resp_private_full_identifier_must_not_render"),
        };
        """,
    )
    assert result == {
        "readsSavedResponse": True,
        "getOnly": True,
        "noSecondPost": True,
        "paidPostExplicit": True,
        "oldClaimAbsent": True,
        "responseBound": True,
        "safeSuffixVisible": True,
        "fullIdAbsent": True,
    }


def test_ai_inbox_is_visible_but_fail_closed_and_uses_a_local_deep_link() -> None:
    result = _run_module(
        AI_VIEW_PATH,
        """
        const categories = subject.AI_PRODUCT_CATEGORIES.map(({ key }) => ({
          key,
          product_category: key,
          readiness: { score: 0, dimensions: [], evidence_hash: "a".repeat(64) },
          knowledge_sources: [],
          teaching_cards: [],
          historical_cases: [],
          effective_policy: { status: "none", rules: [] },
        }));
        const base = {
          ok: true,
          version: "ai-learning-control-room-v1",
          organization_id: "10000000-0000-4000-8000-000000000001",
          selected_category: "baa",
          actor: { id: "60000000-0000-4000-8000-000000000001", role: "producer" },
          capabilities: { can_decide_research_inbox: true },
          state_version: 14,
          event_cursor: 14,
          categories,
          category_detail: categories.find((item) => item.key === "baa"),
          research_inbox: [
            {
              receipt_id: "20000000-0000-4000-8000-000000000001",
              project_id: "30000000-0000-4000-8000-000000000001",
              run_id: "40000000-0000-4000-8000-000000000001",
              product_category: "baa",
              project_name: "БАДы",
              product_name: "Магний",
              research_title: "Разбор рынка магния",
              status: "awaiting_human_review",
              receipt_hash: "a".repeat(64),
              source_count: 7,
              event_cursor: 14,
              received_at: "2026-08-04T18:00:00Z",
              deep_link: "javascript:alert(1)",
              requires_human_review: true,
              raw_research_enters_prompt_automatically: false,
              affects_effective_policy: false,
            },
            {
              receipt_id: "20000000-0000-4000-8000-000000000002",
              project_id: "30000000-0000-4000-8000-000000000002",
              run_id: "40000000-0000-4000-8000-000000000002",
              product_category: "electronics",
              status: "awaiting_human_review",
              receipt_hash: "c".repeat(64),
              requires_human_review: true,
              raw_research_enters_prompt_automatically: false,
              affects_effective_policy: false,
            },
          ],
          research_decisions: [
            {
              disposition_id: "50000000-0000-4000-8000-000000000001",
              receipt_id: "20000000-0000-4000-8000-000000000003",
              receipt_hash: "b".repeat(64),
              project_id: "30000000-0000-4000-8000-000000000003",
              run_id: "40000000-0000-4000-8000-000000000003",
              product_category: "baa",
              project_name: "Архив БАД",
              product_name: "Омега 3",
              research_title: "Проверенный рынок Омега 3",
              decision: "approve",
              reason_code: "operator_verified_research",
              decided_by_name: "Анна",
              decided_at: "2026-08-04T19:00:00Z",
              event_cursor: 15,
              human_review_completed: true,
              raw_research_enters_prompt_automatically: false,
              affects_effective_policy: false,
            },
            {
              disposition_id: "50000000-0000-4000-8000-000000000002",
              receipt_id: "20000000-0000-4000-8000-000000000004",
              receipt_hash: "d".repeat(64),
              project_id: "30000000-0000-4000-8000-000000000004",
              run_id: "40000000-0000-4000-8000-000000000004",
              product_category: "electronics",
              decision: "reject",
              human_review_completed: true,
              raw_research_enters_prompt_automatically: false,
              affects_effective_policy: false,
            },
          ],
        };
        const normalized = subject.normalizeAiLearningControlRoom(base);
        const html = subject.aiLearningControlRoomMarkup(normalized);
        const invalid = subject.normalizeAiLearningControlRoom({
          ...base,
          version: "invalid-version",
        });
        return {
          available: normalized.available,
          inboxCount: normalized.researchInbox.length,
          decisionCount: normalized.researchDecisions.length,
          safeDeepLink: normalized.researchInbox[0]?.deepLink,
          visible: html.includes("Входящие из исследований")
            && html.includes("1 исследование ждёт вашей проверки")
            && html.includes("Разбор рынка магния"),
          humanGate: html.includes("не обучают ИИ")
            && html.includes("не меняют правила генерации"),
          localLink: html.includes(
            '#/workspace/research?project_id=30000000-0000-4000-8000-000000000001&amp;run=40000000-0000-4000-8000-000000000001'
          ),
          unsafeLinkAbsent: !html.includes("javascript:"),
          decisionActions: html.includes('data-action="decide-ai-research-receipt"')
            && html.includes('data-receipt-hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"')
            && html.includes('data-decision="approve"')
            && html.includes('data-decision="reject"')
            && !html.includes('data-decision="approve" disabled'),
          explicitConfirmation: html.includes("подтверждаете, что открыли результат")
            && html.includes('data-confirmation="true"'),
          decisionHistoryVisible: html.includes("Проверенный рынок Омега 3")
            && html.includes("Проверено и принято")
            && html.includes("Анна"),
          crossCategoryAbsent: !html.includes("50000000-0000-4000-8000-000000000002"),
          invalidSnapshotInboxEmpty: invalid.researchInbox.length === 0
            && invalid.researchDecisions.length === 0,
        };
        """,
    )
    assert result == {
        "available": True,
        "inboxCount": 1,
        "decisionCount": 1,
        "safeDeepLink": (
            "#/workspace/research?project_id="
            "30000000-0000-4000-8000-000000000001"
            "&run=40000000-0000-4000-8000-000000000001"
        ),
        "visible": True,
        "humanGate": True,
        "localLink": True,
        "unsafeLinkAbsent": True,
        "decisionActions": True,
        "explicitConfirmation": True,
        "decisionHistoryVisible": True,
        "crossCategoryAbsent": True,
        "invalidSnapshotInboxEmpty": True,
    }
