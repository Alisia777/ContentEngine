from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web/app/training-platform-simulators.js"
STYLES_PATH = ROOT / "web/app/training-platform-simulators.css"
MODULE = MODULE_PATH.read_text(encoding="utf-8")
STYLES = STYLES_PATH.read_text(encoding="utf-8")


def _run_javascript(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable simulator contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "training-platform-simulators.mjs").write_text(
            MODULE,
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as simulator from './training-platform-simulators.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
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

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_simulator_is_an_isolated_frontend_contract_without_external_actions() -> None:
    for export in (
        "normalizePlatformSimulatorCatalog",
        "createPlatformSimulatorState",
        "reducePlatformSimulatorState",
        "createPlatformSimulatorSession",
        "reducePlatformSimulatorSession",
        "platformSimulatorReasoningIsSubstantive",
        "platformSimulatorAttemptPayload",
        "platformSimulatorAttemptReceipt",
        "trainingPlatformSimulatorsMarkup",
        "syncPlatformSimulatorWalkthroughDOM",
        "platformSimulatorWalkthroughSnapshot",
        "renderPlatformSimulatorSession",
        "bindTrainingPlatformSimulators",
    ):
        assert f"export function {export}(" in MODULE

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "navigator.sendBeacon",
        "window.open",
        "document.",
        "innerHTML",
        "outerHTML",
        "<iframe",
        "<form",
        "href=",
    ):
        assert forbidden not in MODULE


def test_catalog_has_three_serious_six_decision_platform_routes_without_browser_answer_keys() -> None:
    payload = _run_javascript(
        r"""
        return {
          passPercent: simulator.PLATFORM_SIMULATOR_PASS_PERCENT,
          minReasoning: simulator.PLATFORM_SIMULATOR_MIN_REASONING_LENGTH,
          minWords: simulator.PLATFORM_SIMULATOR_MIN_REASONING_WORDS,
          platforms: simulator.PLATFORM_SIMULATOR_CATALOG.map((platform) => ({
            id: platform.id,
            stepIds: platform.steps.map((step) => step.id),
            optionCounts: platform.steps.map((step) => step.options.length),
            optionKeys: [...new Set(platform.steps.flatMap((step) => step.options).flatMap(Object.keys))].sort(),
          })),
        };
        """
    )

    assert payload["passPercent"] == 80
    assert payload["minReasoning"] == 50
    assert payload["minWords"] == 8
    assert [platform["id"] for platform in payload["platforms"]] == [
        "instagram",
        "youtube",
        "vk",
    ]
    for platform in payload["platforms"]:
        assert platform["stepIds"] == [
            "account",
            "warmup",
            "publication",
            "review",
            "link",
            "result",
        ]
        assert platform["optionKeys"] == ["id", "label"]
        assert all(3 <= count <= 4 for count in platform["optionCounts"])

    assert "correct: true" not in MODULE
    assert "critical: true" not in MODULE
    assert "option.correct" not in MODULE
    assert "option.critical" not in MODULE


def test_markup_is_accessible_explicitly_fake_and_server_progress_compatible() -> None:
    payload = _run_javascript(
        r"""
        return { markup: simulator.trainingPlatformSimulatorsMarkup() };
        """
    )
    markup = payload["markup"]

    assert "Учебная симуляция — ничего не публикуется" in markup
    assert "не входит в соцсети" in markup
    assert markup.count('role="tab"') == 3
    assert markup.count('role="tabpanel"') == 3
    assert markup.count("data-simulator-reasoning ") == 18
    assert markup.count('minlength="50"') == 18
    assert markup.count("data-training-walkthrough=") == 3
    assert markup.count('data-training-course="publishing_funnel"') == 3
    assert markup.count("data-training-frame ") == 18
    assert 'data-training-walkthrough="platform_publish_instagram"' in markup
    assert 'data-training-walkthrough="platform_publish_youtube"' in markup
    assert 'data-training-walkthrough="platform_publish_vk"' in markup
    assert 'data-training-step-count="6"' in markup
    assert 'data-training-practice-required="true"' in markup
    assert 'data-training-complete="false"' in markup
    assert markup.count('role="status"') >= 21
    assert 'aria-live="polite"' in markup
    assert 'data-simulator-action="finish-attempt"' in markup
    assert markup.count("data-simulator-reset-global") == 3
    assert markup.count('data-simulator-action="edit-step"') == 18
    assert markup.count('tabindex="-1"') >= 18
    assert "Правильный вариант не показывается" in markup
    assert "сервер оценивает весь маршрут" in markup
    assert "data-simulator-receipt-score" in markup
    assert "data-simulator-receipt-critical" in markup
    assert "<form" not in markup
    assert "href=" not in markup


def test_new_session_opens_instagram_instead_of_hiding_every_panel() -> None:
    payload = _run_javascript(
        r"""
        const session = simulator.createPlatformSimulatorSession({});
        return {
          activePlatformId: session.activePlatformId,
          platformIds: Object.keys(session.states),
        };
        """
    )
    assert payload["activePlatformId"] == "instagram"
    assert payload["platformIds"] == ["instagram", "youtube", "vk"]


def test_reasoning_is_structured_and_a_checked_answer_can_be_reopened_before_submit() -> None:
    payload = _run_javascript(
        r"""
        const platform = simulator.PLATFORM_SIMULATOR_CATALOG[0];
        const step = platform.steps[0];
        const selected = step.options[0];
        const other = step.options[1];
        let state = simulator.createPlatformSimulatorState(platform.id);
        state = simulator.reducePlatformSimulatorState(state, {
          type: "select-answer", stepId: step.id, optionId: selected.id,
        });
        const withoutReasoning = simulator.reducePlatformSimulatorState(state, { type: "check" });
        state = simulator.reducePlatformSimulatorState(state, {
          type: "set-reasoning", stepId: step.id, reasoning: "Слишком коротко",
        });
        const shortReasoning = simulator.reducePlatformSimulatorState(state, { type: "check" });
        state = simulator.reducePlatformSimulatorState(state, {
          type: "set-reasoning", stepId: step.id,
          reasoning: "Риск: чужой доступ разрушит аудит. Проверка: сверяю владельца и назначение аккаунта. Действие: продолжаю только после подтверждения.",
        });
        const accepted = simulator.reducePlatformSimulatorState(state, { type: "check" });
        const locked = simulator.reducePlatformSimulatorState(accepted, {
          type: "select-answer", stepId: step.id, optionId: other.id,
        });
        const reopened = simulator.reducePlatformSimulatorState(accepted, {
          type: "edit-step", stepId: step.id,
        });
        let revised = simulator.reducePlatformSimulatorState(reopened, {
          type: "select-answer", stepId: step.id, optionId: other.id,
        });
        revised = simulator.reducePlatformSimulatorState(revised, { type: "check" });
        const restarted = simulator.reducePlatformSimulatorState(accepted, { type: "reset" });
        return {
          noReasoningCompleted: withoutReasoning.completedStepIds.length,
          noReasoningFeedback: withoutReasoning.feedbackByStep[step.id],
          shortCompleted: shortReasoning.completedStepIds.length,
          acceptedDecision: accepted.decisionsByStep[step.id],
          lockedSelection: locked.selectedByStep[step.id],
          lockedDecision: locked.decisionsByStep[step.id],
          reopenedDecision: reopened.decisionsByStep[step.id] || null,
          reopenedSelection: reopened.selectedByStep[step.id],
          revisedDecision: revised.decisionsByStep[step.id],
          restartedCompleted: restarted.completedStepIds.length,
        };
        """
    )

    assert payload["noReasoningCompleted"] == 0
    assert "минимум 50" in payload["noReasoningFeedback"]
    assert payload["shortCompleted"] == 0
    assert set(payload["acceptedDecision"]) == {"optionId", "reasoning"}
    assert len(payload["acceptedDecision"]["reasoning"]) >= 50
    assert payload["lockedSelection"] == payload["acceptedDecision"]["optionId"]
    assert payload["lockedDecision"] == payload["acceptedDecision"]
    assert payload["reopenedDecision"] is None
    assert payload["reopenedSelection"] == payload["acceptedDecision"]["optionId"]
    assert payload["revisedDecision"]["optionId"] != payload["acceptedDecision"]["optionId"]
    assert payload["restartedCompleted"] == 0


def test_sequence_is_gated_and_incomplete_attempt_cannot_finish() -> None:
    payload = _run_javascript(
        r"""
        const platform = simulator.PLATFORM_SIMULATOR_CATALOG[1];
        let state = simulator.createPlatformSimulatorState(platform.id);
        const locked = simulator.reducePlatformSimulatorState(state, {
          type: "go-to-step", stepId: "result",
        });
        const prematurelyFinished = simulator.reducePlatformSimulatorState(state, {
          type: "finish-attempt",
        });
        return {
          initial: state.activeStepId,
          afterLockedJump: locked.activeStepId,
          lockedFeedback: locked.feedbackByStep[state.activeStepId],
          finished: prematurelyFinished.finished,
          passed: prematurelyFinished.passed,
          receipt: simulator.platformSimulatorAttemptReceipt(prematurelyFinished),
        };
        """
    )

    assert payload == {
        "initial": "account",
        "afterLockedJump": "account",
        "lockedFeedback": "Этот этап пока закрыт. Завершите текущий шаг — следующий откроется автоматически.",
        "finished": False,
        "passed": False,
        "receipt": None,
    }


def test_editing_an_earlier_step_preserves_its_draft_and_reopens_later_steps() -> None:
    payload = _run_javascript(
        r"""
        const platform = simulator.PLATFORM_SIMULATOR_CATALOG[0];
        let state = simulator.createPlatformSimulatorState(platform.id);
        for (const [index, step] of platform.steps.slice(0, 2).entries()) {
          state = simulator.reducePlatformSimulatorState(state, {
            type: "select-answer", stepId: step.id, optionId: step.options[0].id,
          });
          state = simulator.reducePlatformSimulatorState(state, {
            type: "set-reasoning", stepId: step.id,
            reasoning: `Риск: этап ${step.id} может нарушить маршрут. Проверка: сверяю задачу и доказательство. Действие: продолжаю после подтверждения.`,
          });
          state = simulator.reducePlatformSimulatorState(state, { type: "check" });
          if (index === 0) state = simulator.reducePlatformSimulatorState(state, { type: "next" });
        }
        const before = state;
        state = simulator.reducePlatformSimulatorState(state, {
          type: "go-to-step", stepId: platform.steps[0].id,
        });
        const edited = simulator.reducePlatformSimulatorState(state, {
          type: "edit-step", stepId: platform.steps[0].id,
        });
        return {
          beforeCompleted: before.completedStepIds,
          editedCompleted: edited.completedStepIds,
          activeStepId: edited.activeStepId,
          firstSelection: edited.selectedByStep[platform.steps[0].id],
          firstReasoning: edited.reasoningByStep[platform.steps[0].id],
          firstDecision: edited.decisionsByStep[platform.steps[0].id] || null,
          secondSelection: edited.selectedByStep[platform.steps[1].id] || null,
          secondDecision: edited.decisionsByStep[platform.steps[1].id] || null,
        };
        """
    )

    assert payload["beforeCompleted"] == ["account", "warmup"]
    assert payload["editedCompleted"] == []
    assert payload["activeStepId"] == "account"
    assert payload["firstSelection"]
    assert "Риск:" in payload["firstReasoning"]
    assert payload["firstDecision"] is None
    assert payload["secondSelection"] is None
    assert payload["secondDecision"] is None


def test_only_server_result_can_score_and_complete_a_six_step_attempt() -> None:
    payload = _run_javascript(
        r"""
        function run(platform) {
          let state = simulator.createPlatformSimulatorState(platform.id);
          platform.steps.forEach((step, index) => {
            const option = step.options[0];
            state = simulator.reducePlatformSimulatorState(state, {
              type: "select-answer", stepId: step.id, optionId: option.id,
            });
            state = simulator.reducePlatformSimulatorState(state, {
              type: "set-reasoning", stepId: step.id,
              reasoning: `Риск: на этапе ${step.id} можно потерять допуск. Проверка: сверяю доказательство и условия задачи. Действие: продолжаю только после подтверждения.`,
            });
            state = simulator.reducePlatformSimulatorState(state, { type: "check" });
            if (index < platform.steps.length - 1) {
              state = simulator.reducePlatformSimulatorState(state, { type: "next" });
            }
          });
          const before = state;
          const pending = simulator.reducePlatformSimulatorState(state, { type: "finish-attempt" });
          const payload = simulator.platformSimulatorAttemptPayload(pending);
          const passed = simulator.reducePlatformSimulatorState(pending, {
            type: "apply-server-result",
            result: { passed: true, score_percent: 83, critical_error_count: 0, receipt_id: "SIM-SERVER-001" },
          });
          return {
            before: { score: before.score, ready: before.readyToFinish, finished: before.finished, passed: before.passed },
            pending: { score: pending.score, status: pending.serverStatus, finished: pending.finished, passed: pending.passed, complete: pending.complete },
            passed: { score: passed.score, status: passed.serverStatus, finished: passed.finished, passed: passed.passed, complete: passed.complete },
            payload,
            receipt: simulator.platformSimulatorAttemptReceipt(passed),
          };
        }
        const platform = simulator.PLATFORM_SIMULATOR_CATALOG[0];
        return run(platform);
        """
    )

    assert payload["before"] == {
        "score": 0,
        "ready": True,
        "finished": False,
        "passed": False,
    }
    assert payload["pending"] == {
        "score": 0,
        "status": "pending",
        "finished": True,
        "passed": False,
        "complete": False,
    }
    assert payload["passed"] == {
        "score": 83,
        "status": "passed",
        "finished": True,
        "passed": True,
        "complete": True,
    }
    assert payload["payload"]["decisionCount"] == 6
    assert len(payload["payload"]["decisions"]) == 6
    assert len(payload["payload"]["rationales"]) == 6
    assert payload["receipt"]["receiptId"] == "SIM-SERVER-001"
    assert payload["receipt"]["score"] == 83


def test_failed_server_result_is_authoritative_and_does_not_reveal_the_answer_key() -> None:
    payload = _run_javascript(
        r"""
        return simulator.PLATFORM_SIMULATOR_CATALOG.map((platform) => {
          let state = simulator.createPlatformSimulatorState(platform.id);
          platform.steps.forEach((step, index) => {
            state = simulator.reducePlatformSimulatorState(state, {
              type: "select-answer", stepId: step.id, optionId: step.options.at(-1).id,
            });
            state = simulator.reducePlatformSimulatorState(state, {
              type: "set-reasoning", stepId: step.id,
              reasoning: `Риск: на этапе ${step.id} возможна рабочая ошибка. Проверка: сверяю основание и доказательство. Действие: выбираю безопасный следующий шаг.`,
            });
            state = simulator.reducePlatformSimulatorState(state, { type: "check" });
            if (index < platform.steps.length - 1) state = simulator.reducePlatformSimulatorState(state, { type: "next" });
          });
          const pending = simulator.reducePlatformSimulatorState(state, { type: "finish-attempt" });
          const failed = simulator.reducePlatformSimulatorState(pending, {
            type: "apply-server-result",
            result: { passed: false, status: "failed", score: 67, critical_error_count: 1, receipt_id: `SERVER-${platform.id}` },
          });
          const receipt = simulator.platformSimulatorAttemptReceipt(failed);
          return {
            id: platform.id,
            pending: pending.serverStatus,
            finished: failed.finished,
            passed: failed.passed,
            complete: failed.complete,
            receipt,
          };
        });
        """
    )

    assert [item["id"] for item in payload] == ["instagram", "youtube", "vk"]
    for item in payload:
        assert item["finished"] is True
        assert item["passed"] is False
        assert item["complete"] is False
        assert item["pending"] == "pending"
        assert item["receipt"]["passed"] is False
        assert item["receipt"]["criticalErrorCount"] == 1
        assert item["receipt"]["receiptId"].startswith("SERVER-")


def test_styles_are_scoped_responsive_keyboard_visible_and_motion_safe() -> None:
    assert STYLES.count(".training-platform-simulators") >= 25
    assert ":focus-visible" in STYLES
    assert "@media (max-width: 720px)" in STYLES
    assert "@media (max-width: 480px)" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert "min-height: 46px" in STYLES
    assert "textarea" in STYLES
    assert "[hidden]" in STYLES
    assert "data-simulator-passed" in STYLES
    assert "grid-template-columns: repeat(6, minmax(0, 1fr))" in STYLES
    assert "focusActiveStep" in MODULE
    assert 'if (actionName === "next") apply({ type: "next", platformId }, "step")' in MODULE
    assert 'if (actionName === "reset") apply({ type: "reset", platformId }, "step")' in MODULE
