from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "web/app/generation-video-reference.js"
HANDOFF = ROOT / "web/app/content-generation-handoff.js"
READINESS = ROOT / "web/app/generation-form-readiness.js"
REFERENCE_TEXT = REFERENCE.read_text(encoding="utf-8")
HANDOFF_TEXT = HANDOFF.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
PROVIDER_ADAPTER = (
    ROOT / "supabase/functions/_shared/generation-provider-adapters.js"
).read_text(encoding="utf-8")
MIGRATION = (
    ROOT
    / "supabase/migrations/202608100014_generation_video_reference_lineage.sql"
).read_text(encoding="utf-8")

# A common UTF-8-as-Windows-1251/Latin-1 corruption signature: the visible
# Cyrillic letters Р/С followed by a C1 control or a Cyrillic supplement code
# point. Correct Russian prose does not contain this sequence.
MOJIBAKE_RE = re.compile(r"[\u0420\u0421][\u0080-\u00ff\u0400-\u040f\u0450-\u045f]")
AI_DID_NOT_WATCH = "\u0418\u0418 \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0440\u043e\u043b\u0438\u043a \u043d\u0435 \u043f\u0440\u043e\u0441\u043c\u0430\u0442\u0440\u0438\u0432\u0430\u043b."
AI_DID_NOT_WATCH_UI = "\u0418\u0418 \u043d\u0435 \u043f\u0440\u043e\u0441\u043c\u0430\u0442\u0440\u0438\u0432\u0430\u043b \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0440\u043e\u043b\u0438\u043a"


def _node(body: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation reference contracts")
    script = (
        f"const reference = await import({json.dumps(REFERENCE.as_uri())});\n"
        f"const handoff = await import({json.dumps(HANDOFF.as_uri())});\n"
        f"const readiness = await import({json.dumps(READINESS.as_uri())});\n"
        f"const result = await (async () => {{\n{body}\n}})();\n"
        "process.stdout.write(JSON.stringify(result));\n"
    )
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
    return json.loads(result.stdout)


def test_youtube_identity_is_canonical_and_operator_only() -> None:
    result = _node(
        """
        const input = {
          url: "https://www.youtube.com/shorts/RIJ_v--Yncw?feature=share",
          mechanics_summary: "Show the finished result, demonstrate one product action, then reveal the result again.",
          source_access_confirmed: true,
          transformative_use_confirmed: true,
        };
        const normalized = reference.normalizeGenerationVideoReference(input);
        const fragment = reference.generationVideoReferencePromptFragment(input);
        return {
          normalized,
          fragment,
          fragmentHasUrl: /https?:\\/\\/|youtube|RIJ_v--Yncw/i.test(fragment),
          invalidUrl: reference.canonicalGenerationVideoReferenceUrl("https://example.com/watch?v=RIJ_v--Yncw"),
          urlInMechanics: reference.normalizeGenerationVideoReference({
            ...input,
            mechanics_summary: "Copy the mechanics from https://youtube.com/watch?v=RIJ_v--Yncw exactly.",
          }).code,
        };
        """
    )
    assert result["normalized"] == {
        "present": True,
        "ready": True,
        "code": "",
        "video_id": "RIJ_v--Yncw",
        "canonical_url": "https://youtube.com/watch?v=RIJ_v--Yncw",
        "mechanics_summary": (
            "Show the finished result, demonstrate one product action, then "
            "reveal the result again."
        ),
        "source_access_confirmed": True,
        "transformative_use_confirmed": True,
        "analysis_basis": "operator_summary",
        "ai_watched": False,
        "evidence_verified": False,
        "attestation_version": "generation-video-reference-v1",
    }
    assert result["fragment"]
    assert result["fragment"].startswith(
        "GenerationVideoReference/operator-summary:"
    )
    assert result["fragmentHasUrl"] is False
    assert result["invalidUrl"] == ""
    assert result["urlInMechanics"] == "generation_video_reference_mechanics_invalid"


def test_reference_mechanics_enter_video_prompt_but_url_never_does() -> None:
    result = _node(
        """
        const mechanics = "Show the finished result, demonstrate one product action, then reveal the result again.";
        const fragment = reference.generationVideoReferencePromptFragment({
          url: "https://youtu.be/RIJ_v--Yncw",
          mechanics_summary: mechanics,
          source_access_confirmed: true,
          transformative_use_confirmed: true,
        });
        const common = {
          productName: "MILIO air fryer",
          sku: "518413561",
          productCategory: "household",
          scenarioIntent: "Show the product in a bright kitchen.",
          generationReferenceFragment: fragment,
        };
        const video = handoff.compileSafeGenerationBrief({
          ...common,
          mode: "real_seedance",
          durationSeconds: 8,
        });
        const photo = handoff.compileSafeGenerationBrief({
          ...common,
          mode: "real_photo",
        });
        const rawUrl = handoff.compileSafeGenerationBrief({
          ...common,
          mode: "real_seedance",
          generationReferenceFragment: "Use https://youtube.com/watch?v=RIJ_v--Yncw",
        });
        return {
          videoReady: video.ready,
          mechanicsBound: video.prompt.includes(mechanics),
          urlAbsent: !video.prompt.includes("youtube") && !video.prompt.includes("RIJ_v--Yncw"),
          correctRussianDisclaimer: video.prompt.includes("ИИ исходный ролик не просматривал."),
          mojibakeAbsent: !/[РС][\u0080-\u00ff\u0400-\u040f\u0450-\u045f]/u.test(video.prompt),
          photoCodes: photo.blockers.map((item) => item.code),
          rawUrlCodes: rawUrl.blockers.map((item) => item.code),
        };
        """
    )
    assert result["videoReady"] is True
    assert result["mechanicsBound"] is True
    assert result["urlAbsent"] is True
    assert result["correctRussianDisclaimer"] is True
    assert result["mojibakeAbsent"] is True
    assert "generation_video_reference_mode_invalid" in result["photoCodes"]
    assert "generation_reference_url_forbidden" in result["rawUrlCodes"]


def test_compiler_rejects_marker_injection_mismatch_and_duplicates() -> None:
    result = _node(
        """
        const marker = reference.GENERATION_VIDEO_REFERENCE_PROMPT_MARKER;
        const disclaimer = reference.GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER;
        const mechanicsA = "Reveal the cooked result, show one product action, then reveal the result again";
        const mechanicsB = "Start with the closed product, add food, and end on a different plated result";
        const fragmentA = reference.generationVideoReferencePromptFragment({
          url: "https://youtube.com/shorts/RIJ_v--Yncw",
          mechanics_summary: mechanicsA,
          source_access_confirmed: true,
          transformative_use_confirmed: true,
        });
        const common = {
          mode: "real_seedance",
          productName: "MILIO air fryer",
          sku: "518413561",
          productCategory: "household",
          durationSeconds: 8,
        };
        const codes = (compiled) => compiled.blockers.map((item) => item.code);
        const valid = handoff.compileSafeGenerationBrief({
          ...common,
          scenarioIntent: "Show the product in a bright kitchen.",
          generationReferenceFragment: fragmentA,
        });
        const noReferenceInjection = handoff.compileSafeGenerationBrief({
          ...common,
          scenarioIntent: `Show the product. ${marker} ${mechanicsB}. ${disclaimer}`,
        });
        const duplicateAB = handoff.compileSafeGenerationBrief({
          ...common,
          scenarioIntent: `Show the product. ${marker} ${mechanicsB}. ${disclaimer}`,
          generationReferenceFragment: fragmentA,
        });
        const mismatchedFragment = handoff.compileSafeGenerationBrief({
          ...common,
          scenarioIntent: mechanicsB,
          generationReferenceFragment: `${fragmentA} ${mechanicsB}`,
        });
        const wrongDisclaimer = handoff.compileSafeGenerationBrief({
          ...common,
          scenarioIntent: mechanicsB,
          generationReferenceFragment: fragmentA.replace(
            disclaimer,
            "ИИ уже просмотрел исходный ролик.",
          ),
        });
        const mechanicsMarker = reference.normalizeGenerationVideoReference({
          url: "https://youtu.be/RIJ_v--Yncw",
          mechanics_summary: `${mechanicsA} ${marker} ${mechanicsB}`,
          source_access_confirmed: true,
          transformative_use_confirmed: true,
        });
        return {
          contractsEqual:
            handoff.GENERATION_VIDEO_REFERENCE_PROMPT_MARKER === marker
            && handoff.GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER === disclaimer
            && handoff.GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE
              === reference.GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE,
          validReady: valid.ready,
          validMarkerCount: valid.prompt.split(marker).length - 1,
          noReferenceInjection: codes(noReferenceInjection),
          duplicateAB: codes(duplicateAB),
          mismatchedFragment: codes(mismatchedFragment),
          wrongDisclaimer: codes(wrongDisclaimer),
          mechanicsMarkerCode: mechanicsMarker.code,
        };
        """
    )
    stable_code = "generation_video_reference_marker_invalid"
    assert result["contractsEqual"] is True
    assert result["validReady"] is True
    assert result["validMarkerCount"] == 1
    assert stable_code in result["noReferenceInjection"]
    assert stable_code in result["duplicateAB"]
    assert stable_code in result["mismatchedFragment"]
    assert stable_code in result["wrongDisclaimer"]
    assert (
        result["mechanicsMarkerCode"]
        == "generation_video_reference_mechanics_invalid"
    )


def test_generation_reference_user_facing_russian_is_utf8_not_mojibake() -> None:
    assert AI_DID_NOT_WATCH in REFERENCE_TEXT
    assert AI_DID_NOT_WATCH_UI in APP
    for name, source in (
        ("generation-video-reference.js", REFERENCE_TEXT),
        ("content-generation-handoff.js", HANDOFF_TEXT),
        ("app.js", APP),
        ("supabase-api.js", API),
    ):
        match = MOJIBAKE_RE.search(source)
        assert match is None, f"mojibake signature in {name}: {match.group(0)!r}"


def test_optional_reference_becomes_a_readiness_step_only_when_started() -> None:
    result = _node(
        """
        const base = {
          mode: "real_seedance",
          sku: "518413561",
          productName: "MILIO air fryer",
          productCategory: "household",
          platform: "youtube",
          destinationRef: "@brand",
          mediaCount: 3,
          brief: "A safe complete video brief.",
          campaignId: "campaign-1",
          spendAllowed: true,
          confirmationMatches: true,
          count: 1,
        };
        return {
          absent: readiness.evaluateGenerationFormReadiness(base),
          incomplete: readiness.evaluateGenerationFormReadiness({
            ...base,
            generationReferencePresent: true,
            generationReferenceReady: false,
          }),
          complete: readiness.evaluateGenerationFormReadiness({
            ...base,
            generationReferencePresent: true,
            generationReferenceReady: true,
          }),
        };
        """
    )
    assert result["absent"]["ready"] is True
    assert result["absent"]["total"] == 8
    assert result["incomplete"]["ready"] is False
    assert result["incomplete"]["total"] == 9
    assert result["incomplete"]["next"]["key"] == "video_reference"
    assert result["complete"]["ready"] is True
    assert result["complete"]["total"] == 9


def test_append_only_lineage_and_paid_job_binding_are_server_enforced() -> None:
    assert parse_sql(MIGRATION)
    for token in (
        "generation_spec_video_reference_bindings",
        "generation_job_video_reference_bindings",
        "generation_spec_video_reference_append_only",
        "generation_job_video_reference_append_only",
        "contentengine_bind_generation_spec_video_reference",
        "contentengine_generation_video_reference_lineage",
        "generation_video_reference_scope_mismatch",
        "generation_video_reference_job_binding_invalid",
        "p_payload - 'generation_reference_context'",
        "prompt_has_reference_value <> (context_value is not null)",
        "GenerationVideoReference/operator-summary:",
        "unique (organization_id, generation_job_id)",
        "'raw_url_enters_provider_prompt', false",
        "'project_shared', true",
        "'ai_watched', false",
        "'evidence_verified', false",
        "expected_prompt_fragment_value := prompt_marker_value || ' '",
        "expected_prompt_fragment_count_value <> 1",
        "prompt_marker_count_value <> 1",
        "position(prompt_marker_value in mechanics_summary_value) > 0",
        "spec_binding_row.mechanics_summary || '. '",
        "add column generation_video_reference_decided boolean not null default true",
        "alter column generation_video_reference_decided set default false",
        "job_row.generation_video_reference_decided",
        "if not (job_row.input ? 'generation_video_reference_context') then",
        "set generation_video_reference_decided = true",
    ):
        assert token in MIGRATION
    assert (
        "position(mechanics_summary_value in spec_row.compiled_prompt)"
        not in MIGRATION
    )
    assert "research_source" not in MIGRATION
    assert "research_provenance =" not in MIGRATION
    assert "research_provenance_changed', false" in MIGRATION


def test_paid_job_reference_decision_is_replay_safe_across_the_upgrade() -> None:
    legacy_default = MIGRATION.index(
        "add column generation_video_reference_decided boolean not null default true"
    )
    new_job_default = MIGRATION.index(
        "alter column generation_video_reference_decided set default false"
    )
    delegated_start = MIGRATION.index(
        ".creator_start_real_generation_pre_video_reference_v54("
    )
    decision_read = MIGRATION.index("job_row.generation_video_reference_decided")
    no_reference_decision = MIGRATION.index(
        "'generation_video_reference_context', null"
    )

    assert legacy_default < new_job_default < delegated_start < decision_read
    assert decision_read < no_reference_decision
    assert "if binding_id_value is null and job_binding_row.id is null then" in MIGRATION
    assert "message = 'idempotency_key_conflict'" in MIGRATION
    assert MIGRATION.count("set generation_video_reference_decided = true") == 2


def test_sql_binding_contract_rejects_split_a_b_adversarial_spec() -> None:
    marker = "GenerationVideoReference/operator-summary:"
    disclaimer = AI_DID_NOT_WATCH
    mechanics_a = (
        "Reveal the cooked result, show one product action, then reveal it again"
    )
    mechanics_b = (
        "Start closed, add food, and finish with a different plated result"
    )
    fragment_a = f"{marker} {mechanics_a}. {disclaimer}"
    adversarial_prompt = f"{fragment_a}\nЗамысел пользователя: {mechanics_b}."

    # This is the exact split-field shape that the former loose checks accepted:
    # one marker for A, while mechanics B merely appeared elsewhere in the brief.
    assert marker in adversarial_prompt
    assert mechanics_b in adversarial_prompt
    expected_fragment_b = f"{marker} {mechanics_b}. {disclaimer}"
    assert adversarial_prompt.count(marker) == 1
    assert adversarial_prompt.count(expected_fragment_b) == 0

    # The migration must derive B's complete canonical fragment and require one
    # contiguous occurrence, in addition to exactly one reserved marker.
    assert "expected_prompt_fragment_count_value <> 1" in MIGRATION
    assert "prompt_marker_count_value <> 1" in MIGRATION


def test_client_edge_and_archive_use_exact_context_without_provider_url() -> None:
    for token in (
        "bindGenerationSpecVideoReference",
        "generationVideoReferenceLineage",
        "generation_reference_context",
        "loadGenerationVideoReferenceLineage",
        "load-generation-video-reference",
        "ИИ не просматривал исходный ролик",
        "URL не передавался провайдеру генерации",
    ):
        assert token in APP or token in API
    assert '"generation_reference_context"' in EDGE
    assert "readGenerationVideoReferenceContext" in EDGE
    provider_body = EDGE[
        EDGE.index("function buildProviderRequest(") : EDGE.index(
            "function readStatusJob("
        )
    ]
    assert "startPayload" not in provider_body
    assert "generation_reference" not in provider_body
    assert "canonical_url" not in provider_body
    assert "promptText: job.promptText" in provider_body
    assert "promptText: exactPrompt(input, entry)" in PROVIDER_ADAPTER
    assert (
        'from "./generation-video-reference.js?v=20260826.rebuild-clean.18"'
        in APP
    )


def test_migration_prefix_is_unique() -> None:
    matches = list(
        (ROOT / "supabase/migrations").glob(
            "202608100014*"
        )
    )
    assert matches == [
        ROOT
        / "supabase/migrations/202608100014_generation_video_reference_lineage.sql"
    ]
