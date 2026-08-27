from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260010_generation_claim_evidence.sql"
).read_text(encoding="utf-8")
TRAINING = (
    ROOT
    / "supabase/migrations/202607260011_generation_claim_evidence_training.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_claim_evidence_test.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-content-review/index.ts"
).read_text(encoding="utf-8")
VIEW_PATH = ROOT / "web/app/content-review-view.js"
VIEW = VIEW_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _image_approval_ready(evidence_status: str) -> bool:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for claim evidence browser contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            VIEW_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            f"""
import {{ generatedImageApprovalContextReady }} from "./subject.mjs";
const run = {{
  media: {{ kind: "generated_image" }},
  input: {{
    generationJobId: "11111111-1111-4111-8111-111111111111",
    platform: "vk",
    contentKind: "advertising",
    aiGenerated: true,
    externalAiProcessingConfirmed: true,
    adLabelConfirmed: true,
    ordConfirmed: true,
    advertiserName: "ООО Тест",
    erid: "test-erid",
    rightsConfirmed: true,
    claimsVerified: false,
    generationClaimEvidence: {{ status: {json.dumps(evidence_status)} }},
    productCategoryVerified: true,
    productCategorySource: "product_metadata",
    aiDisclosureConfirmed: false,
    mandatoryWarningConfirmed: false,
    audienceOver10000: false,
    rknRegistered: false,
  }},
}};
process.stdout.write(JSON.stringify(generatedImageApprovalContextReady(run)));
""",
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


def test_database_contract_is_server_owned_hashed_and_fail_safe() -> None:
    for marker in (
        "valid_research_claim_rows",
        "valid_approved_research_claims",
        "valid_generation_claim_evidence_input",
        "content_review_generation_claim_evidence_check",
        "creator_start_real_generation_pre_claim_v4",
        "generation_research_claim_evidence_invalid",
        "and draft.origin = 'ai'",
        "draft.status = 'approved'",
        "content_factory_private.json_hash(evidence_without_hash)",
        "to_jsonb(job_row.input ->> 'prompt_text')",
        "'null'::jsonb",
        "zz_generated_claim_evidence_guard",
        "media_row.metadata ->> 'kind' not in (",
        "'generated_video', 'generated_image'",
        "new.request_hash := content_factory_private.json_hash(new.input)",
        "notify pgrst, 'reload schema';",
    ):
        assert marker in MIGRATION
    public_gate = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation"
        ):
        MIGRATION.index(
            "create or replace function\n"
            "  content_factory_private.bind_generated_claim_evidence"
        )
    ]
    assert public_gate.index("valid_approved_research_claims") < public_gate.index(
        "creator_start_real_generation_pre_claim_v4"
    )


def test_database_rejects_spoofing_and_browser_bypass() -> None:
    for marker in (
        "tampering with a hashed evidence snapshot is rejected",
        "research claims cannot cite an undeclared model source",
        "historical review input remains readable without claim evidence",
        "browser sessions cannot bypass the research claim gate",
        "validated content review claim evidence constraint is installed",
    ):
        assert marker in PGTAP
    assert (
        "revoke all on function\n"
        "  content_factory_private.bind_generated_claim_evidence()"
    ) in MIGRATION


def test_edge_uses_evidence_without_treating_prohibitions_as_content() -> None:
    for marker in (
        "generation_claim_evidence — серверный неизменяемый снимок",
        "evidence не является текстом публикации",
        "readGenerationClaimEvidence",
        "positiveClaimSurface",
        "CLAIM.RESEARCH_EVIDENCE_BOUND",
        "CLAIM.OUTPUT_NOT_CONFIRMED",
        "CLAIM.RESEARCH_FORBIDDEN_EXACT",
        "CLAIM.SOURCE_NOT_CONFIRMED",
        "forbiddenResearchClaim",
        "trustScoreCap",
        "claimOverallScoreCap",
    ):
        assert marker in EDGE
    positive_surface = EDGE[
        EDGE.index("function positiveClaimSurface"):
        EDGE.index("function numericMetric")
    ]
    for prohibition in (
        "не\\b",
        "нельзя\\b",
        "запрещен",
        "do\\s+not",
        "avoid",
        "forbidden",
    ):
        assert prohibition in positive_surface


def test_browser_accepts_bound_research_but_not_unavailable_evidence() -> None:
    assert _image_approval_ready("bound") is True
    assert _image_approval_ready("unavailable") is False
    assert '(input.claimsVerified || researchClaimsBound)' in VIEW
    assert "claimEvidenceMarkup(run.input.generationClaimEvidence)" in VIEW
    assert "immutable snapshot approved AI research" in VIEW


def test_generated_video_quality_scan_is_independent_from_release_confirmations() -> None:
    submit_start = APP.index("async function submitContentReview(form)")
    submit_end = APP.index("persistContentReviewDraft(form)", submit_start)
    submit = APP[submit_start:submit_end]
    generated_gate = submit[
        submit.index('if (media.kind === "generated_video")'):
        submit.index('if (input.people_present === "yes"')
    ]
    assert "!input.claims_verified" not in generated_gate
    assert "!input.rights_confirmed" not in generated_gate
    assert "!input.ad_label_confirmed" not in generated_gate
    assert "!input.ord_confirmed" not in generated_gate
    assert "resolveGeneratedVideoReviewMedia(media)" in generated_gate
    assert 'input.content_kind = "advertising"' in generated_gate


def test_training_explains_research_provenance_and_human_boundary() -> None:
    for marker in (
        "immutable snapshot",
        "Safe claim означает только наличие исследовательской базы",
        "Forbidden claim, заявленный в результате как факт, блокирует",
        "не заменяют полный просмотр",
        "Server-bound research фиксирует происхождение",
        "generation claim evidence training contract failed",
        "generation claim evidence assessment contract failed",
    ):
        assert marker in TRAINING


def test_claim_evidence_release_bumps_browser_modules_and_error_copy() -> None:
    assert "./content-review-view.js?v=20260826.rebuild-clean.30" in APP
    assert "./supabase-api.js?v=20260826.rebuild-clean.30" in APP
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 10" in APP
    assert "./app.js?v=20260826.rebuild-clean.30" in INDEX
    assert "generation_research_claim_evidence_invalid" in ADAPTER
    assert "Платный запуск не создан" in ADAPTER
