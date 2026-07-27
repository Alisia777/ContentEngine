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
    }


def test_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


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
    ):
        assert token in APP
    assert "./generation-model-acceptance-view.js?v=20260727.1" in APP
    assert ".generation-model-acceptance__grid" in STYLES
    assert "./styles.css?v=20260727.7" in INDEX
    assert "./app.js?v=20260727.19" in INDEX
    assert "./supabase-api.js?v=20260727.11" in APP
