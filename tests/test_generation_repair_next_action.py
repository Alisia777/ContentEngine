from __future__ import annotations

from pathlib import Path
import json
import subprocess

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270008_generation_repair_next_action.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_repair_next_action_test.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/content-review-view.js").read_text(encoding="utf-8")


def test_repair_next_action_sql_and_pgtap_parse() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


def test_server_reuses_authoritative_repair_policy() -> None:
    for token in (
        "public.creator_generation_repair_policy(",
        "policy_value -> 'applied'",
        "generation_repair_signals signal",
        "signal.source_review_id = p_review_id",
        "'in_progress'",
        "'succeeded'",
        "'failed'",
        "'available'",
        "'can_prepare'",
    ):
        assert token in MIGRATION


def test_catalog_exposes_no_repair_identity_prompt_or_job_identifier() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_content_review_catalog("
        ):
    ]
    assert "'repair_next_action'" in wrapper
    assert "'status'" not in wrapper
    assert "'can_prepare'" not in wrapper
    for forbidden in (
        "'generation_job_id'",
        "'assignee_id'",
        "'requested_by'",
        "'prompt'",
        "'brief'",
        "'guard_codes'",
        "'policy_hash'",
        "'score_snapshot'",
    ):
        assert forbidden not in wrapper


def test_browser_has_durable_repair_recovery_contract() -> None:
    for token in (
        "repairNextAction",
        "normalizeGenerationRepairNextAction",
        "prepare-generation-repair",
        "loadGenerationRepairForReview",
        "Доработка после QA готова",
        "Исправление уже запущено",
    ):
        assert token in APP or token in VIEW


def test_review_normalizer_accepts_only_bounded_repair_routing_state() -> None:
    module_url = (ROOT / "web/app/content-review-view.js").as_uri()
    script = f"""
import {{ normalizeContentReviewRun }} from {json.dumps(module_url)};
const valid = normalizeContentReviewRun({{
  id: "00000000-0000-4000-8000-000000000111",
  status: "completed",
  repair_next_action: {{
    status: "available",
    can_prepare: true,
    started_at: null,
    generation_job_id: "00000000-0000-4000-8000-000000000999",
    prompt: "must never survive normalization",
  }},
}});
const forged = normalizeContentReviewRun({{
  id: "00000000-0000-4000-8000-000000000112",
  status: "completed",
  repair_next_action: {{
    status: "retry_without_confirmation",
    can_prepare: true,
  }},
}});
process.stdout.write(JSON.stringify({{
  valid: valid.repairNextAction,
  forged: forged.repairNextAction,
}}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(result.stdout)
    assert payload["valid"] == {
        "status": "available",
        "canPrepare": True,
        "startedAt": None,
    }
    assert payload["forged"] is None
