from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    return APP[APP.index(start) : APP.index(end, APP.index(start))]


def test_strategy_archive_renders_dedicated_manual_status_action() -> None:
    actions = _between(
        "function generationActionsMarkup(details)",
        "function generationCostMarkup(details)",
    )
    assert 'data-action="refresh-generation-strategy-status"' in actions
    assert "GENERATION_STRATEGY_MANUAL_STATUS_REFRESH_STATUSES.has(details.status)" in actions
    assert actions.index("GENERATION_STRATEGY_MANUAL_STATUS_REFRESH_STATUSES") < actions.index(
        'if (details.status === "failed" || details.status === "cancelled")'
    )
    handler = APP[
        APP.index('if (action === "refresh-generation-strategy-status")') :
        APP.index('if (action === "check-generation-strategy")')
    ]
    assert handler.count("refreshGenerationStrategyArchiveStatus(") == 1
    for forbidden in (
        "startGenerationStrategy",
        "startRealGeneration",
        "realGenerationStatus",
        "repeatGeneration",
    ):
        assert forbidden not in handler


def test_manual_strategy_status_click_calls_exact_status_once_and_applies_response() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable strategy status refresh")
    source = _between(
        "function generationStrategyArchiveStatusRequest(jobId, projectId)",
        "function applyGenerationStrategyArchiveStatus(jobId, raw, options = {})",
    )
    script = f"""
const exactJobId = "88504197-4f6a-4159-9797-6f89cba92db9";
const otherJobId = "11111111-1111-4111-8111-111111111111";
const projectId = "4f0fcfa2-7233-4c0c-9e16-2c20e0aae379";
const organizationId = "22222222-2222-4222-8222-222222222222";
let strategyStatusCalls = 0;
let legacyStatusCalls = 0;
let startCalls = 0;
let repeatCalls = 0;
let applyCalls = 0;
const state = {{
  api: {{
    organizationId,
    generationStrategyStatus: async (request) => {{
      strategyStatusCalls += 1;
      if (request.action !== "strategy_status" || request.generation_job_id !== exactJobId) {{
        throw new Error("wrong exact request");
      }}
      return {{ job: {{ id: exactJobId, status: "succeeded" }} }};
    }},
    realGenerationStatus: async () => {{ legacyStatusCalls += 1; }},
    startGenerationStrategy: async () => {{ startCalls += 1; }},
  }},
  bootstrap: {{ organization: {{ id: organizationId }} }},
  sections: {{ generation: {{ data: {{ batches: [{{
    details: {{
      real: true,
      strategy: {{ strategyId: "viral_product_swap" }},
      jobId: exactJobId,
      status: "failed",
    }},
  }}] }} }} }},
  generationArchive: {{ strategyStatusInFlight: new Set() }},
}};
const GENERATION_STRATEGY_MANUAL_STATUS_REFRESH_STATUSES = new Set([
  "submitted", "processing", "running", "failed",
]);
class CreatorApiError extends Error {{
  constructor(message, options = {{}}) {{ super(message); this.code = options.code || ""; }}
}}
const contentReviewUuid = (value) => /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/u.test(String(value || ""));
const currentWorkspaceProjectId = () => projectId;
const listFrom = (value, key) => Array.isArray(value?.[key]) ? value[key] : [];
const generationBatchDetails = (item) => item.details;
const toast = () => undefined;
const actionErrorMessage = (error) => error?.message || "error";
const humanGenerationStatus = (status) => status;
const applyGenerationStrategyArchiveStatus = (jobId, raw) => {{
  if (jobId !== exactJobId || raw?.job?.id !== exactJobId) throw new Error("wrong apply");
  applyCalls += 1;
}};
const repeatGenerationStrategyFromArchive = async () => {{ repeatCalls += 1; }};
{source}
const control = {{
  disabled: false,
  textContent: "Проверить сейчас",
  isConnected: true,
  setAttribute() {{}},
  removeAttribute() {{}},
}};
const result = await refreshGenerationStrategyArchiveStatus(exactJobId, control);
const wrong = await refreshGenerationStrategyArchiveStatus(otherJobId, control);
process.stdout.write(JSON.stringify({{
  resultJobId: result?.job?.id || "",
  wrong,
  strategyStatusCalls,
  legacyStatusCalls,
  startCalls,
  repeatCalls,
  applyCalls,
  busyCleared: state.generationArchive.strategyStatusInFlight.size === 0,
  controlRestored: control.disabled === false && control.textContent === "Проверить сейчас",
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == {
        "resultJobId": "88504197-4f6a-4159-9797-6f89cba92db9",
        "wrong": None,
        "strategyStatusCalls": 1,
        "legacyStatusCalls": 0,
        "startCalls": 0,
        "repeatCalls": 0,
        "applyCalls": 1,
        "busyCleared": True,
        "controlRestored": True,
    }
