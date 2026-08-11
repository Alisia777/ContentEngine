from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "web/app/content-generation-handoff.js"
SPEC_VIEW = ROOT / "web/app/generation-spec.js"
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
RECOMMENDATIONS = (
    ROOT / "web/app/workspace-generation-research-recommendations.js"
).read_text(encoding="utf-8")
TRAINING = (ROOT / "web/app/workspace-ai-research-training.js").read_text(
    encoding="utf-8"
)
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)


def _run_module(module: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable browser contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            module.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_live_option_two_is_verbatim_required_in_every_provider_prompt() -> None:
    result = _run_module(
        HANDOFF,
        r'''
        const option2 = "AIResearchSelection/v1 C=аэрогриль для маленькой кухни|H=Поместится ли на столешнице?|CTA=Сравните размеры своей кухни и сохраните ролик перед покупкой.|P=4 л; 1500 Вт; 10 программ; окно; гарантия 3 года|A=не обещать 8 программ";
        const option1 = "AIResearchSelection/v1 C=быстрый ужин без духовки|H=Что приготовить после работы?|CTA=Сохраните идею и сравните характеристики перед покупкой.|P=4 л; 1500 Вт; 10 программ; окно|A=не обещать 8 программ";
        const option3 = "AIResearchSelection/v1 C=уход и очистка после готовки|H=Легко ли мыть после ужина?|CTA=Проверьте детали ухода и сохраните памятку перед покупкой.|P=съёмная чаша; окно; гарантия 3 года|A=не обещать самоочистку";
        const brief = [
          "ТОВАР: MILIO A425D-Black",
          "КОНЦЕПЦИЯ: Аэрогриль для маленькой кухни — честная проверка размеров",
          "ХУК: Поместится ли он на небольшой столешнице?",
          "CTA: Сравните размеры своей кухни и сохраните ролик перед покупкой.",
          "ДОКАЗАТЕЛЬСТВА: 4 л, 1500 Вт, 10 программ, окно, гарантия 3 года",
          "НЕ ОБЕЩАТЬ / УЧЕСТЬ: Не говорить про 8 программ и не заменять духовку",
        ].join("\n");
        const learningPolicy = subject.normalizeGenerationLearningPolicy({
          version: "generation-learning-v4",
          applied: true,
          confidence: "high",
          selection_mode: "quality",
          evidence_count: 12,
          preferred_angle: "demonstration",
          preferred_hook_patterns: ["demonstration"],
          quality_guard_codes: ["product_fidelity", "technical_stability"],
          quality_guard_evidence_count: 12,
          quality_guard_confidence: "high",
          reason_codes: ["recurring_independent_quality_weakness"],
          policy_hash: "f".repeat(64),
        });
        const selected = (fragment) => ({
          required: true,
          provider_prompt_fragment_version: subject.AI_RESEARCH_PROVIDER_FRAGMENT_VERSION,
          provider_prompt_fragment: fragment,
          provider_prompt_fragment_hash: "a".repeat(64),
          currentBrief: brief,
        });
        const modes = ["real_photo", "real_gen4", "real_seedance"];
        const compiled = Object.fromEntries(modes.map((mode) => {
          const value = subject.compileSafeGenerationBrief({
            mode,
            productName: "MILIO A425D-Black",
            sku: "518413561",
            durationSeconds: mode === "real_seedance" ? 8 : 5,
            productCategory: "household",
            learningPolicy,
            selectedRecommendation: selected(option2),
          });
          return [mode, {
            ready: value.ready,
            blockers: value.blockers.map((item) => item.code),
            length: value.prompt.length,
            limit: subject.contentGenerationPromptLimit(mode),
            exactCore: value.prompt.split(option2).length - 1,
            selectionMarkers: value.prompt.split(subject.AI_RESEARCH_PROVIDER_FRAGMENT_MARKER).length - 1,
            humanMarkers: value.prompt.split(subject.AI_RESEARCH_HUMAN_INTENT_MARKER).length - 1,
            allLiveTokens: [
              "маленькой кухни", "Поместится ли на столешнице?",
              "Сравните размеры своей кухни и сохраните ролик перед покупкой.",
              "4 л", "1500 Вт", "10 программ", "окно",
              "гарантия 3 года", "8 программ",
            ].every((token) => value.prompt.includes(token)),
            exactHash: value.selectedRecommendationFragmentHash === "a".repeat(64),
            human: value.selectedRecommendationHumanIntent,
          }];
        }));
        const first = subject.compileSafeGenerationBrief({
          mode: "real_seedance", productName: "MILIO A425D-Black",
          sku: "518413561", durationSeconds: 8, productCategory: "household",
          selectedRecommendation: selected(option1),
        });
        const second = subject.compileSafeGenerationBrief({
          mode: "real_seedance", productName: "MILIO A425D-Black",
          sku: "518413561", durationSeconds: 8, productCategory: "household",
          selectedRecommendation: selected(option2),
        });
        const third = subject.compileSafeGenerationBrief({
          mode: "real_seedance", productName: "MILIO A425D-Black",
          sku: "518413561", durationSeconds: 8, productCategory: "household",
          selectedRecommendation: selected(option3),
        });
        return {
          compiled,
          distinctPositions: first.ready && second.ready && third.ready
            && new Set([first.prompt, second.prompt, third.prompt]).size === 3,
          firstExact: first.prompt.includes(option1),
          secondExact: second.prompt.includes(option2),
          thirdExact: third.prompt.includes(option3),
        };
        ''',
    )
    assert result["distinctPositions"] is True
    assert result["firstExact"] is True
    assert result["secondExact"] is True
    assert result["thirdExact"] is True
    for compiled in result["compiled"].values():
        assert compiled["ready"] is True, compiled["blockers"]
        assert compiled["length"] <= compiled["limit"]
        assert compiled["exactCore"] == 1
        assert compiled["selectionMarkers"] == 1
        assert compiled["humanMarkers"] == 1
        assert compiled["allLiveTokens"] is True
        assert compiled["exactHash"] is True
        assert compiled["human"].startswith("AIResearchHumanIntent/v1 C=")
        assert len(compiled["human"]) <= 150


def test_fragment_and_human_caps_are_canonical_and_fail_closed() -> None:
    result = _run_module(
        HANDOFF,
        r'''
        const marker = subject.AI_RESEARCH_PROVIDER_FRAGMENT_MARKER;
        const validFragment = `${marker} C=маленькая кухня|H=честный тест|CTA=Сравните перед покупкой.|P=4/1500/окно|A=не 8 программ`;
        const valid = {
          provider_prompt_fragment_version: subject.AI_RESEARCH_PROVIDER_FRAGMENT_VERSION,
          provider_prompt_fragment: validFragment,
          provider_prompt_fragment_hash: "b".repeat(64),
        };
        const malformed = [
          { ...valid, provider_prompt_fragment_version: ` ${subject.AI_RESEARCH_PROVIDER_FRAGMENT_VERSION}` },
          { ...valid, provider_prompt_fragment_hash: "B".repeat(64) },
          { ...valid, provider_prompt_fragment_hash: ` ${"b".repeat(64)}` },
          { ...valid, provider_prompt_fragment: ` ${validFragment}` },
          { ...valid, provider_prompt_fragment: `${validFragment} ` },
          { ...valid, provider_prompt_fragment: `prefix ${validFragment}` },
          { ...valid, provider_prompt_fragment: validFragment.replace(marker, "missing") },
          { ...valid, provider_prompt_fragment: `${validFragment} ${marker} duplicate` },
          { ...valid, provider_prompt_fragment: `${validFragment} airesearchselection/v1 duplicate` },
          { ...valid, provider_prompt_fragment: `${validFragment} AIResearchHumanIntent/v1 injected` },
          { ...valid, provider_prompt_fragment: `${marker} ${"x".repeat(241)}` },
          { ...valid, provider_prompt_fragment: `${marker} C=x\nH=y` },
          { ...valid, provider_prompt_fragment: validFragment.replace(" C=", "  C=") },
        ];
        const brief = [
          "КОНЦЕПЦИЯ: 😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀",
          "ХУК: честный\u00a0тест|без подмены",
          "CTA: Сравните размеры перед покупкой и сохраните",
          "ДОКАЗАТЕЛЬСТВА: 4 л и 1500 Вт",
          "НЕ ОБЕЩАТЬ / УЧЕСТЬ: не обещать 8 программ",
        ].join("\n");
        const human = subject.compileAiResearchHumanIntent({ currentBrief: brief });
        const nbspFragment = validFragment.replace(
          "маленькая кухня",
          "маленькая\u00a0кухня",
        );
        const nbspProvider = {
          ...valid,
          provider_prompt_fragment: nbspFragment,
        };
        const nbspCompiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "MILIO",
          sku: "518413561",
          productCategory: "household",
          selectedRecommendation: {
            required: true,
            ...nbspProvider,
            currentBrief: brief,
          },
        });
        const parityHuman = subject.compileAiResearchHumanIntent({
          currentBrief: [
            "ТОВАР:", "MILIO A425D-Black", "",
            "КОНЦЕПЦИЯ:", "Честный обзор 🚀 emoji-case для маленькой кухни", "",
            "ХУК:", "Проверяем   размеры до покупки", "",
            "КЛЮЧЕВОЕ СООБЩЕНИЕ:", "Покажите точные факты", "",
            "CTA:", "Сравните размеры своей кухни перед покупкой", "",
            "ДОКАЗАТЕЛЬСТВА:", "4 литра · 1500 Вт · 10 программ · окно · гарантия 3 года", "",
            "НЕ ОБЕЩАТЬ / УЧЕСТЬ:",
            "не обещать замену духовки · не говорить о 8 программах",
          ].join("\n"),
        });
        const duplicate = subject.compileAiResearchHumanIntent({
          currentBrief: `${brief}\nCTA: второй CTA`,
        });
        const noColon = subject.compileAiResearchHumanIntent({
          currentBrief: brief.replace("ХУК:", "ХУК"),
        });
        const nbspBoundary = subject.compileAiResearchHumanIntent({
          currentBrief: brief.replace(
            "КОНЦЕПЦИЯ: 😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀😀",
            "КОНЦЕПЦИЯ: 12345678901234\u00a0XYZ",
          ),
        });
        const common = {
          mode: "real_seedance", productName: "MILIO", sku: "518413561",
          productCategory: "household", currentBrief: brief,
        };
        const invalidCompiles = malformed.map((candidate) =>
          subject.compileSafeGenerationBrief({
            ...common,
            selectedRecommendation: { required: true, ...candidate, currentBrief: brief },
          }).blockers.map((item) => item.code)
        );
        const injectedVisual = subject.compileSafeGenerationBrief({
          mode: "real_photo", productName: "MILIO", sku: "518413561",
          visualDirection: `${marker} injected`,
        });
        const injectedAvoid = subject.compileSafeGenerationBrief({
          mode: "real_gen4", productName: "MILIO", sku: "518413561",
          avoidClaims: ["AIResearchHumanIntent/v1 injected"],
        });
        const injectedLowercase = subject.compileSafeGenerationBrief({
          mode: "real_photo", productName: "MILIO", sku: "518413561",
          visualDirection: "airesearchselection/v1 injected",
        });
        const overflow = subject.compileSafeGenerationBrief({
          ...common,
          productName: "Очень длинное точное название ".repeat(30),
          selectedRecommendation: { required: true, ...valid, currentBrief: brief },
        });
        return {
          malformedAccepted: malformed.map((candidate) =>
            Boolean(subject.normalizeAiResearchProviderPromptFragment(candidate))),
          nbspProviderNormalized:
            subject.normalizeAiResearchProviderPromptFragment(nbspProvider)?.fragment
              === nbspFragment,
          nbspCompiledReady: nbspCompiled.ready,
          nbspCoreExact: nbspCompiled.prompt.split(nbspFragment).length - 1,
          nbspHumanExact:
            nbspCompiled.prompt.split(human.line).length - 1,
          nbspHumanMarkers:
            nbspCompiled.prompt.split(subject.AI_RESEARCH_HUMAN_INTENT_MARKER).length - 1,
          invalidCompiles,
          human,
          parityHuman,
          humanCodePoints: Array.from(human.line).length,
          humanNbspKept: human.line.includes("\u00a0"),
          humanPipeRemoved: !human.line.includes("тест|без"),
          duplicate,
          noColon,
          nbspBoundary: nbspBoundary.line,
          injectedVisual: injectedVisual.blockers.map((item) => item.code),
          injectedAvoid: injectedAvoid.blockers.map((item) => item.code),
          injectedLowercase: injectedLowercase.blockers.map((item) => item.code),
          overflow: overflow.blockers.map((item) => item.code),
        };
        ''',
    )
    assert result["malformedAccepted"] == [False] * 13
    assert result["nbspProviderNormalized"] is True
    assert result["nbspCompiledReady"] is True
    assert result["nbspCoreExact"] == 1
    assert result["nbspHumanExact"] == 1
    assert result["nbspHumanMarkers"] == 1
    assert all(
        "ai_research_prompt_binding_invalid" in blockers
        for blockers in result["invalidCompiles"]
    )
    assert result["human"]["ready"] is True
    assert result["parityHuman"] == {
        "ready": True,
        "line": (
            "AIResearchHumanIntent/v1 C=Честный обзор 🚀…|"
            "H=Проверяем разме…|CTA=Сравните размеры своей…|"
            "P=4 литра · 1500…|A=не обещать замену д…"
        ),
        "changedSections": [
            "КОНЦЕПЦИЯ",
            "ХУК",
            "CTA",
            "ДОКАЗАТЕЛЬСТВА",
            "НЕ ОБЕЩАТЬ / УЧЕСТЬ",
        ],
    }
    assert result["humanCodePoints"] <= 150
    assert result["humanNbspKept"] is True
    assert result["humanPipeRemoved"] is True
    assert result["duplicate"]["ready"] is False
    assert result["noColon"]["ready"] is False
    assert "C=12345678901234\u00a0…|" in result["nbspBoundary"]
    assert "ai_research_prompt_reserved_marker_invalid" in result["injectedVisual"]
    assert "ai_research_prompt_reserved_marker_invalid" in result["injectedAvoid"]
    assert "ai_research_prompt_reserved_marker_invalid" in result["injectedLowercase"]
    assert "ai_research_prompt_budget_exceeded" in result["overflow"]


def test_true_opt_out_is_marker_free_and_selected_flow_cannot_drop_markers() -> None:
    result = _run_module(
        HANDOFF,
        r'''
        const fragment = "AIResearchSelection/v1 C=маленькая кухня|H=честный тест|CTA=Сравните перед покупкой.|P=4/1500/окно|A=не 8 программ";
        const brief = [
          "КОНЦЕПЦИЯ: маленькая кухня", "ХУК: честный тест",
          "CTA: Сравните перед покупкой.", "ДОКАЗАТЕЛЬСТВА: 4/1500/окно",
          "НЕ ОБЕЩАТЬ / УЧЕСТЬ: не 8 программ",
        ].join("\n");
        const active = subject.compileSafeGenerationBrief({
          mode: "real_gen4", productName: "MILIO", sku: "518413561",
          visualDirection: "очень подробное направление ".repeat(30),
          selectedRecommendation: {
            required: true,
            provider_prompt_fragment_version: subject.AI_RESEARCH_PROVIDER_FRAGMENT_VERSION,
            provider_prompt_fragment: fragment,
            provider_prompt_fragment_hash: "c".repeat(64),
            currentBrief: brief,
          },
        });
        const manual = subject.compileSafeGenerationBrief({
          mode: "real_gen4", productName: "MILIO", sku: "518413561",
          scenarioIntent: brief,
          selectedRecommendation: null,
        });
        const counts = (prompt) => ({
          selection: prompt.split(subject.AI_RESEARCH_PROVIDER_FRAGMENT_MARKER).length - 1,
          human: prompt.split(subject.AI_RESEARCH_HUMAN_INTENT_MARKER).length - 1,
        });
        return {
          activeReady: active.ready,
          activeCounts: counts(active.prompt),
          activeExact: active.prompt.includes(fragment),
          manualReady: manual.ready,
          manualCounts: counts(manual.prompt),
        };
        ''',
    )
    assert result == {
        "activeReady": True,
        "activeCounts": {"selection": 1, "human": 1},
        "activeExact": True,
        "manualReady": True,
        "manualCounts": {"selection": 0, "human": 0},
    }


def test_maximum_active_context_fails_closed_instead_of_dropping_ai_binding() -> None:
    result = _run_module(
        HANDOFF,
        r'''
        const fragment = "AIResearchSelection/v1 C=аэрогриль для маленькой кухни|H=Поместится ли на столешнице?|CTA=Сравните размеры своей кухни и сохраните ролик перед покупкой.|P=4 л; 1500 Вт; 10 программ; окно; гарантия 3 года|A=не обещать 8 программ";
        const brief = [
          "КОНЦЕПЦИЯ: Аэрогриль для маленькой кухни — честная проверка размеров",
          "ХУК: Поместится ли он на небольшой столешнице?",
          "CTA: Сравните размеры своей кухни и сохраните ролик перед покупкой.",
          "ДОКАЗАТЕЛЬСТВА: 4 л, 1500 Вт, 10 программ, окно, гарантия 3 года",
          "НЕ ОБЕЩАТЬ / УЧЕСТЬ: Не говорить про 8 программ и не заменять духовку",
        ].join("\n");
        const mechanics = "плавный проход от общего плана к панели управления и окну ".repeat(8)
          .slice(0, 360).trimEnd();
        const videoReference = `${subject.GENERATION_VIDEO_REFERENCE_PROMPT_MARKER} ${mechanics}. ${subject.GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER}`;
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: `MILIO A425D-Black ${"точная модель ".repeat(16)}`,
          sku: "518413561",
          durationSeconds: 8,
          productCategory: "household",
          generationReferenceFragment: videoReference,
          researchCategoryRule: {
            creativeAngle: "demonstration",
            hookPatterns: ["question_led", "concise"],
            categoryMaturity: "established",
            competitorCoverage: "sufficient",
            primarySignal: "format.single_action_demo",
          },
          learningPolicy: {
            version: "generation-learning-v4",
            applied: true,
            confidence: "high",
            selection_mode: "quality",
            evidence_count: 12,
            preferred_angle: "demonstration",
            preferred_hook_patterns: ["demonstration"],
            quality_guard_codes: ["product_fidelity", "technical_stability"],
            quality_guard_evidence_count: 12,
            quality_guard_confidence: "high",
            reason_codes: ["recurring_independent_quality_weakness"],
            policy_hash: "f".repeat(64),
          },
          selectedRecommendation: {
            required: true,
            provider_prompt_fragment_version: subject.AI_RESEARCH_PROVIDER_FRAGMENT_VERSION,
            provider_prompt_fragment: fragment,
            provider_prompt_fragment_hash: "e".repeat(64),
            currentBrief: brief,
          },
        });
        return {
          ready: compiled.ready,
          prompt: compiled.prompt,
          blockers: compiled.blockers.map((item) => item.code),
          referenceReady: subject.inspectGenerationVideoReferencePromptFragment(
            videoReference,
          ).ready,
        };
        ''',
    )
    assert result["referenceReady"] is True
    assert result["ready"] is False
    assert result["prompt"] == ""
    assert "ai_research_prompt_budget_exceeded" in result["blockers"]


def test_free_spec_card_shows_exact_prompt_and_binding_proof() -> None:
    result = _run_module(
        SPEC_VIEW,
        r'''
        const specId = "11111111-1111-4111-8111-111111111111";
        const selectionId = "22222222-2222-4222-8222-222222222222";
        const specHash = "a".repeat(64);
        const promptHash = "b".repeat(64);
        const fragmentHash = "c".repeat(64);
        const humanHash = "d".repeat(64);
        const proofHash = "e".repeat(64);
        const spec = {
          spec_id: specId, spec_version: 2, spec_hash: specHash,
          status: "draft", exact_scope: null,
          editable_intent: "Замысел <редактор>",
          compiled_prompt: "AIResearchSelection/v1 exact <provider>\nAIResearchHumanIntent/v1 C=edit",
          prompt_hash: promptHash, research_provenance: null,
          performance_policy_provenance: null, repair_provenance: null,
          created_at: "2026-08-11T10:00:00Z", updated_at: "2026-08-11T10:00:00Z",
        };
        const html = subject.generationSpecCardMarkup({
          dirty: false,
          status: "ready",
          data: {
            generationSpec: spec, history: [],
            recommendedNextAction: null,
          },
          aiResearchBinding: {
            id: "33333333-3333-4333-8333-333333333333",
            spec_id: specId, spec_version: 2, spec_hash: specHash,
            selection_id: selectionId, recommendation_position: 2,
            provider_prompt_fragment_version: "ai-research-provider-fragment-v1",
            provider_prompt_fragment_hash: fragmentHash,
            human_intent_fragment_version: "ai-research-human-intent-v1",
            human_intent_fragment_hash: humanHash,
            compiled_prompt_hash: promptHash,
            prompt_binding_proof_hash: proofHash,
            legacy: false,
          },
        });
        return {
          hidden: /(?:^|\s)hidden(?:\s|>|=)/u.test(html),
          forcedVisible: html.includes("display:block !important"),
          freeCopy: html.includes("без Runway/списания"),
          exactPromptEscaped: html.includes("AIResearchSelection/v1 exact &lt;provider&gt;"),
          selectionFull: html.includes(selectionId),
          position: html.includes('data-recommendation-position="2"'),
          fragmentHashFull: html.includes(fragmentHash),
          proofHashFull: html.includes(proofHash),
          proofNode: html.includes("data-generation-spec-ai-research-binding"),
        };
        ''',
    )
    assert result == {
        "hidden": False,
        "forcedVisible": True,
        "freeCopy": True,
        "exactPromptEscaped": True,
        "selectionFull": True,
        "position": True,
        "fragmentHashFull": True,
        "proofHashFull": True,
        "proofNode": True,
    }


def test_app_preserves_server_authority_and_provider_prompt_exactness() -> None:
    for token in (
        "normalizeAiResearchProviderPromptFragment",
        "state.api.generationResearchRecommendation({",
        "matchingRecommendations.length !== 1",
        "provider_prompt_fragment_version:",
        "provider_prompt_fragment_hash:",
        "selectedRecommendation,",
        "generationSpecAiResearchSelection(preparedPayload)",
        "state.api.generationSpecAiResearchBinding({",
        'source?.version !== "generation-spec-ai-research-binding-v2"',
        "provider_prompt_fragment_hash",
        "human_intent_fragment_hash",
        "prompt_binding_proof_hash",
        "await readGenerationSpecAiResearchBinding(",
        "state.generationSpec.aiResearchBinding = null;",
    ):
        assert token in APP
    assert APP.count("selectedRecommendation,") >= 2
    assert "AIResearchSelection/v1 C=" not in APP
    assert "hidden: true" not in APP[
        APP.index("${generationSpecCardMarkup({") :
        APP.index("${generationSpecCardMarkup({") + 220
    ]

    # No variant is preselected. The exact target or restored server position
    # is authoritative, and the resolver retains the returned sibling list.
    assert "activeIndex: -1" in RECOMMENDATIONS
    assert "runtime.response = source;" in RECOMMENDATIONS
    assert "const recommendations = Array.isArray(source.recommendations)" in RECOMMENDATIONS
    assert "checkbox.checked = false" in TRAINING
    assert "checkbox.checked = position === 1" not in TRAINING

    # The provider still receives the immutable server compiled prompt, not
    # editable_intent or an independently rebuilt browser string.
    assert "effectiveGenerationPolicy.compiledPrompt !== startPayload.brief" in EDGE
    assert "promptText: startJob.promptText" in EDGE
    assert EDGE.count("promptText: startJob.promptText") >= 3
