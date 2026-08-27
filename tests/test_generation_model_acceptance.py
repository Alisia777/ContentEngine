from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270005_generation_model_acceptance.sql"
).read_text(encoding="utf-8")
NEXT_ACTION_MIGRATION = (
    ROOT
    / "supabase/migrations/202607270006_generation_model_acceptance_next_action.sql"
).read_text(encoding="utf-8")
FRESHNESS_MIGRATION = (
    ROOT
    / "supabase/migrations/202607280001_generation_model_acceptance_freshness.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_model_acceptance_test.sql"
).read_text(encoding="utf-8")
VIEW_PATH = ROOT / "web/app/generation-model-acceptance-view.js"
VIEW = VIEW_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _run_view(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable acceptance contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(VIEW, encoding="utf-8")
        runtime_body = body.replace(
            "subject.normalizeGenerationModelAcceptance(",
            "normalizeAcceptance(",
        ).replace(
            "subject.generationModelAcceptanceMarkup(",
            "acceptanceMarkup(",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            "const catalog = { version: 'legacy-acceptance-test-v1', models: [\n"
            "  { provider: 'runway', model: 'seedream5_lite', publicLabel: 'Seedream 5 Lite', contentKind: 'photo' },\n"
            "  { provider: 'runway', model: 'gen4_turbo', publicLabel: 'Gen-4 Turbo', contentKind: 'video' },\n"
            "  { provider: 'runway', model: 'seedance2_fast', publicLabel: 'Seedance 2 Fast', contentKind: 'video' },\n"
            "] };\n"
            "const normalizeAcceptance = (raw) => subject.normalizeGenerationModelAcceptance(raw, catalog);\n"
            "const acceptanceMarkup = (state) => subject.generationModelAcceptanceMarkup(state, catalog);\n"
            f"const result = await (async () => {{\n{runtime_body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _accepted_evidence() -> dict:
    return {
        "generation_job_id": "00000000-0000-4000-8000-000000000001",
        "media_id": "00000000-0000-4000-8000-000000000002",
        "media_sha256": "a" * 64,
        "review_id": "00000000-0000-4000-8000-000000000003",
        "review_completion_hash": "b" * 64,
        "review_model_provider": "openai",
        "review_model_version": "gpt-test",
        "decision_id": "00000000-0000-4000-8000-000000000004",
        "decision": "approved",
        "decided_at": "2026-07-27T12:00:00Z",
        "overall_score": 91,
        "blockers_count": 0,
        "compliance_status": "pass",
        "media_watched_confirmed": True,
        "independent_reviewer": True,
        "context_bound": True,
        "fresh": True,
        "expires_at": "2026-10-25T12:00:00Z",
    }


def test_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(NEXT_ACTION_MIGRATION)
    assert parse_sql(FRESHNESS_MIGRATION)
    assert parse_sql(PGTAP)


def test_sql_acceptance_expires_provider_quality_evidence_after_90_days() -> None:
    for token in (
        "generation_model_acceptance_freshness",
        "evidence_max_age_days constant integer := 90",
        "expires_at_value > p_evaluated_at",
        "'fresh', evidence_fresh_value",
        "'expires_at', expires_at_value",
        "'acceptance_evidence_stale'",
        "'generate_replacement_and_approve'",
        "'generation-model-acceptance-v3'",
        "accepted_count_value = total_models_value",
        "content_factory_private.generation_model_acceptance(",
        "content_factory_private.generation_model_acceptance_pending(",
    ):
        assert token in FRESHNESS_MIGRATION
    private_grant = FRESHNESS_MIGRATION[
        FRESHNESS_MIGRATION.index(
            "revoke all on function\n"
            "  content_factory_private.generation_model_acceptance_freshness"
        ):
        FRESHNESS_MIGRATION.index(
            "create or replace function public.creator_generation_model_acceptance"
        )
    ]
    assert "authenticated, service_role" in private_grant
    assert "grant execute" not in private_grant


def test_sql_acceptance_is_derived_from_the_full_immutable_chain() -> None:
    for token in (
        "job.mode = 'real'",
        "job.provider = 'runway'",
        "job.allow_real_spend",
        "job.status = 'succeeded'",
        "job.actual_cost_minor > 0",
        "media.sha256 = job.output ->> 'sha256'",
        "media.metadata ->> 'generation_job_id' = job.id::text",
        "review.status = 'completed'",
        "review.media_sha256_snapshot = output.media_sha256",
        "decision.review_completion_hash = review.completion_hash",
        "decision.media_sha256_snapshot = output.media_sha256",
        "decision.media_watched_confirmed",
        "decision.decided_by <> output.requested_by",
        "decision.decided_by <> output.assigned_to",
        "content_review_context_amendments",
        "amendment.created_by = decision.decided_by",
        "evidence.overall_score >= 80",
        "evidence.blockers_count = 0",
        "evidence.compliance_status is not null",
        "'all_models_accepted', accepted_count_value = 3",
    ):
        assert token in MIGRATION


def test_sql_status_uses_latest_decision_and_fails_closed() -> None:
    latest = MIGRATION[
        MIGRATION.index("select\n      output.generation_job_id"):
        MIGRATION.index("if evidence_row.decision_id is null")
    ]
    assert "order by decision.created_at desc, decision.id desc" in latest
    for status in ("unproven", "needs_revalidation", "accepted"):
        assert f"status_value := '{status}'" in MIGRATION
    assert "elsif not evidence_row.context_bound" in MIGRATION
    assert "elsif evidence_row.overall_score < 80" in MIGRATION
    assert "latest_decision_not_approved" in MIGRATION


def test_pending_review_navigation_uses_only_exact_opaque_evidence() -> None:
    for token in (
        "generation_model_acceptance_pending",
        "media.id::text = job.output ->> 'output_media_id'",
        "media.sha256 = job.output ->> 'sha256'",
        "candidate.media_sha256_snapshot = output.media_sha256",
        "candidate.input ->> 'generation_job_id'",
        "decision.review_completion_hash",
        "decision.media_watched_confirmed",
        "decision.decided_by <> output.requested_by",
        "'pending_review'",
        "'generation-model-acceptance-v2'",
    ):
        assert token in NEXT_ACTION_MIGRATION
    for forbidden in (
        "'output_object_name'",
        "'signed_url'",
        "'requested_by'",
        "'assigned_to'",
        "'owner_id'",
        "'prompt'",
    ):
        assert forbidden not in NEXT_ACTION_MIGRATION[
            NEXT_ACTION_MIGRATION.index("else jsonb_build_object("):
            NEXT_ACTION_MIGRATION.index("end\n    );")
        ]


def test_browser_refuses_a_forged_accepted_status_without_evidence() -> None:
    result = _run_view(
        """
const normalized = subject.normalizeGenerationModelAcceptance({
  version: "generation-model-acceptance-v1",
  all_models_accepted: true,
  models: [
    { model: "seedream5_lite", status: "accepted" },
    { model: "gen4_turbo", status: "accepted" },
    { model: "seedance2_fast", status: "accepted" },
  ],
});
return {
  acceptedCount: normalized.acceptedCount,
  allAccepted: normalized.allModelsAccepted,
  statuses: normalized.models.map((item) => item.status),
};
"""
    )
    assert result == {
        "acceptedCount": 0,
        "allAccepted": False,
        "statuses": ["unproven", "unproven", "unproven"],
    }


def test_browser_accepts_only_complete_score_and_context_evidence() -> None:
    evidence = json.dumps(_accepted_evidence())
    result = _run_view(
        f"""
const evidence = {evidence};
const normalized = subject.normalizeGenerationModelAcceptance({{
  models: [{{
    model: "seedream5_lite",
    status: "accepted",
    quality_threshold: 80,
    evidence,
  }}],
}});
const downgraded = subject.normalizeGenerationModelAcceptance({{
  models: [{{
    model: "seedream5_lite",
    status: "accepted",
    quality_threshold: 95,
    evidence,
  }}],
}});
return {{
  accepted: normalized.models[0].status,
  acceptedCount: normalized.acceptedCount,
  downgraded: downgraded.models[0].status,
}};
"""
    )
    assert result == {
        "accepted": "accepted",
        "acceptedCount": 1,
        "downgraded": "needs_revalidation",
    }


def test_browser_requires_authoritative_freshness_and_explains_expiry() -> None:
    evidence = _accepted_evidence()
    stale_evidence = {
        **evidence,
        "fresh": False,
        "expires_at": "2026-04-01T12:00:00Z",
    }
    missing_freshness = dict(evidence)
    missing_freshness.pop("fresh")
    missing_freshness.pop("expires_at")
    result = _run_view(
        f"""
const staleEvidence = {json.dumps(stale_evidence)};
const missingFreshness = {json.dumps(missing_freshness)};
const stale = subject.normalizeGenerationModelAcceptance({{
  version: "generation-model-acceptance-v3",
  models: [{{
    model: "seedream5_lite",
    status: "needs_revalidation",
    reason_code: "acceptance_evidence_stale",
    next_action_code: "generate_replacement_and_approve",
    evidence_max_age_days: 90,
    evidence: staleEvidence,
  }}],
}});
const forged = subject.normalizeGenerationModelAcceptance({{
  version: "generation-model-acceptance-v3",
  models: [{{
    model: "seedream5_lite",
    status: "accepted",
    evidence: missingFreshness,
  }}],
}});
return {{
  staleStatus: stale.models[0].status,
  staleFresh: stale.models[0].evidence?.fresh,
  staleAction: subject.nextGenerationModelAcceptanceAction(stale),
  staleMarkup: subject.generationModelAcceptanceMarkup({{
    status: "ready",
    data: {{
      version: "generation-model-acceptance-v3",
      models: [{{
        model: "seedream5_lite",
        status: "needs_revalidation",
        reason_code: "acceptance_evidence_stale",
        next_action_code: "generate_replacement_and_approve",
        evidence_max_age_days: 90,
        evidence: staleEvidence,
      }}],
    }},
  }}),
  forgedStatus: forged.models[0].status,
  forgedAcceptedCount: forged.acceptedCount,
}};
"""
    )
    assert result["staleStatus"] == "needs_revalidation"
    assert result["staleFresh"] is False
    assert result["staleAction"]["kind"] == "prepare"
    assert result["staleAction"]["model"] == "seedream5_lite"
    assert "90 дней" in result["staleMarkup"]
    assert "Подготовить перепроверку" in result["staleMarkup"]
    assert result["forgedStatus"] == "needs_revalidation"
    assert result["forgedAcceptedCount"] == 0


def test_browser_accepts_only_exact_pending_review_navigation() -> None:
    result = _run_view(
        """
const valid = subject.normalizeGenerationModelAcceptance({
  models: [{
    model: "seedream5_lite",
    status: "unproven",
    successful_runs: 1,
    pending_review_runs: 1,
    pending_review: {
      generation_job_id: "00000000-0000-4000-8000-000000000011",
      media_id: "00000000-0000-4000-8000-000000000012",
      review_id: "00000000-0000-4000-8000-000000000013",
      review_status: "completed",
      created_at: "2026-07-27T13:00:00Z",
    },
  }],
});
const forged = subject.normalizeGenerationModelAcceptance({
  models: [{
    model: "gen4_turbo",
    status: "unproven",
    successful_runs: 1,
    pending_review: {
      generation_job_id: "00000000-0000-4000-8000-000000000021",
      media_id: "00000000-0000-4000-8000-000000000022",
      review_id: "../../login",
      review_status: "completed",
    },
  }],
});
return {
  reviewId: valid.models[0].pendingReview?.reviewId || "",
  forgedPending: forged.models[1].pendingReview,
  validMarkup: subject.generationModelAcceptanceMarkup({
    status: "ready",
    data: {
      models: [{
        model: "seedream5_lite",
        status: "unproven",
        successful_runs: 1,
        pending_review_runs: 1,
        pending_review: {
          generation_job_id: "00000000-0000-4000-8000-000000000011",
          media_id: "00000000-0000-4000-8000-000000000012",
          review_id: "00000000-0000-4000-8000-000000000013",
          review_status: "completed",
        },
      }],
    },
  }),
  forgedMarkup: subject.generationModelAcceptanceMarkup({
    status: "ready",
    data: {
      models: [{
        model: "gen4_turbo",
        status: "unproven",
        successful_runs: 1,
        pending_review: {
          generation_job_id: "00000000-0000-4000-8000-000000000021",
          media_id: "00000000-0000-4000-8000-000000000022",
          review_id: "../../login",
          review_status: "completed",
        },
      }],
    },
  }),
};
"""
    )
    assert result["reviewId"] == "00000000-0000-4000-8000-000000000013"
    assert result["forgedPending"] is None
    assert (
        "#/workspace/review?view=current&amp;review=00000000-0000-4000-8000-000000000013"
        in result["validMarkup"]
    )
    assert "../../login" not in result["forgedMarkup"]
    assert (
        'data-action="refresh-generation-model-acceptance"'
        in result["forgedMarkup"]
    )


def test_browser_prioritizes_existing_outputs_and_never_guesses_a_new_paid_run() -> None:
    result = _run_view(
        """
const stale = subject.normalizeGenerationModelAcceptance({
  models: [{
    model: "seedream5_lite",
    status: "unproven",
    successful_runs: 1,
    next_action_code: "run_paid_smoke_and_approve",
  }],
});
const pending = subject.normalizeGenerationModelAcceptance({
  models: [{
    model: "seedream5_lite",
    status: "unproven",
    successful_runs: 1,
    next_action_code: "unknown_external_action",
  }, {
    model: "gen4_turbo",
    status: "unproven",
    successful_runs: 1,
    next_action_code: "review_succeeded_output",
    pending_review: {
      generation_job_id: "00000000-0000-4000-8000-000000000021",
      media_id: "00000000-0000-4000-8000-000000000022",
      review_id: "00000000-0000-4000-8000-000000000023",
      review_status: "completed",
    },
  }],
});
const replacement = subject.normalizeGenerationModelAcceptance({
  models: [{
    model: "seedream5_lite",
    status: "needs_revalidation",
    successful_runs: 1,
    next_action_code: "generate_replacement_and_approve",
  }],
});
const fresh = subject.normalizeGenerationModelAcceptance({ models: [] });
return {
  staleCode: stale.models[0].nextActionCode,
  staleAction: subject.nextGenerationModelAcceptanceAction(stale),
  pendingAction: subject.nextGenerationModelAcceptanceAction(pending),
  replacementAction: subject.nextGenerationModelAcceptanceAction(replacement),
  freshAction: subject.nextGenerationModelAcceptanceAction(fresh),
  staleMarkup: subject.generationModelAcceptanceMarkup({
    status: "ready",
    data: {
      models: [{
        model: "seedream5_lite",
        status: "unproven",
        successful_runs: 1,
        next_action_code: "run_paid_smoke_and_approve",
      }],
    },
  }),
};
"""
    )
    assert result["staleCode"] == "status_refresh_required"
    assert result["staleAction"]["kind"] == "refresh"
    assert result["staleAction"]["model"] == "seedream5_lite"
    assert result["pendingAction"]["kind"] == "review"
    assert result["pendingAction"]["model"] == "gen4_turbo"
    assert (
        result["pendingAction"]["reviewId"]
        == "00000000-0000-4000-8000-000000000023"
    )
    assert result["replacementAction"]["kind"] == "prepare"
    assert result["replacementAction"]["model"] == "seedream5_lite"
    assert result["freshAction"]["kind"] == "prepare"
    assert result["freshAction"]["model"] == "seedream5_lite"
    assert "Следующий безопасный шаг: Seedream 5 Lite" in result["staleMarkup"]
    assert 'data-action="refresh-generation-model-acceptance"' in result[
        "staleMarkup"
    ]


def test_browser_copy_never_confuses_provider_readiness_with_quality() -> None:
    result = _run_view(
        """
return {
  loading: subject.generationModelAcceptanceMarkup({ status: "loading" }),
  error: subject.generationModelAcceptanceMarkup({ status: "error" }),
  ready: subject.generationModelAcceptanceMarkup({
    status: "ready",
    data: { models: [] },
  }),
};
"""
    )
    assert "Сверяем реальные результаты" in result["loading"]
    assert "успешный API-ответ" in result["error"]
    assert "реального платного файла" in result["ready"]
    assert "data-acceptance-status=\"unproven\"" in result["ready"]


def test_portal_loads_and_invalidates_server_acceptance_status() -> None:
    for token in (
        'generationModelAcceptance: "creator_generation_model_acceptance"',
        "generationModelAcceptance()",
        "RPC.generationModelAcceptance",
    ):
        assert token in ADAPTER
    for token in (
        "generationModelAcceptance: {",
        "async function loadGenerationModelAcceptance(",
        "state.api.generationModelAcceptance()",
        "generationModelAcceptanceMarkup(",
        "state.generationModelAcceptance.status = \"idle\"",
        "function prepareGenerationAcceptance(model)",
        'action === "prepare-generation-acceptance"',
        'action === "refresh-generation-model-acceptance"',
        "loadGenerationModelAcceptance({ force: true })",
        "form.elements.real_spend_confirmation.checked = false",
        "form.dataset.autoGenerationPreflightKey = generationPreflightKey(sku)",
        "Платный запуск не выполнен",
    ):
        assert token in APP
    prepare = APP[
        APP.index("function prepareGenerationAcceptance(model)"):
        APP.index("function activeGenerationRepairPolicy(")
    ]
    assert "runGenerationPreflight(" not in prepare
    assert "realGenerationPreflight(" not in prepare
    assert "submitRealGeneration(" not in prepare
    refresh = APP[
        APP.index('if (action === "refresh-generation-model-acceptance")'):
        APP.index('if (action === "check-runway-readiness")')
    ]
    assert "loadGenerationModelAcceptance({ force: true })" in refresh
    assert "startRealGeneration" not in refresh
    assert "realGenerationPreflight" not in refresh
    assert "./generation-model-acceptance-view.js?v=20260826.rebuild-clean.32" in APP
    assert ".generation-model-acceptance__grid" in STYLES
    assert "./styles.css?v=20260826.rebuild-clean.32" in INDEX
    assert "./app.js?v=20260826.rebuild-clean.32" in INDEX
    assert "./supabase-api.js?v=20260826.rebuild-clean.32" in APP


def test_visible_generation_acceptance_refreshes_without_rebuilding_the_form() -> None:
    refresher = APP[
        APP.index("function generationModelAcceptanceIsStale()"):
        APP.index("async function handleAuthStateChange(")
    ]
    targeted_ui = APP[
        APP.index("function syncGenerationModelAcceptanceUi()"):
        APP.index("async function loadGenerationModelAcceptance(")
    ]
    loader = APP[
        APP.index("async function loadGenerationModelAcceptance("):
        APP.index("async function hydratePrivateMedia(")
    ]
    for token in (
        'state.route.path !== "/workspace/generation"',
        'document.visibilityState !== "visible"',
        "state.realGenerationStartInFlight",
        "acceptance?.contains(document.activeElement)",
        "generationModelAcceptanceIsStale()",
        "MANAGER_DASHBOARD_MAX_AGE_MS",
        "silent: true",
        "force: true",
    ):
        assert token in refresher
    assert "refreshGenerationModelAcceptanceIfStale," in APP
    assert APP.count("refreshGenerationModelAcceptanceIfStale();") >= 1
    assert '".generation-model-acceptance"' in targeted_ui
    assert "generationModelAcceptanceMarkup(" in targeted_ui
    assert "current.replaceWith(next)" in targeted_ui
    assert "render(" not in targeted_ui
    assert loader.count("syncGenerationModelAcceptanceUi()") == 2
    assert "mock-batch-form" not in targeted_ui
    assert "startRealGeneration" not in refresher
    assert "realGenerationPreflight" not in refresher
