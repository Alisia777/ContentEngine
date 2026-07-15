from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web" / "app" / "first-shift-full-scenario.js"
CSS_PATH = ROOT / "web" / "app" / "first-shift-full-scenario.css"
MODULE = MODULE_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")


def test_full_shift_is_an_independent_exported_data_and_view_module() -> None:
    for exported_name in (
        "FIRST_SHIFT_FULL_SCENARIO",
        "FIRST_SHIFT_FULL_PHASES",
        "FIRST_SHIFT_PLATFORM_GUIDES",
        "FIRST_SHIFT_FULL_POLICY_REFERENCES",
        "createFirstShiftFullState",
        "evaluateFirstShiftFullAnswer",
        "reduceFirstShiftFullState",
        "firstShiftFullProgress",
        "firstShiftFullScenarioMarkup",
    ):
        assert f"export const {exported_name}" in MODULE or f"export function {exported_name}" in MODULE
    assert "from \"./app.js\"" not in MODULE
    assert "window." not in MODULE
    assert "document." not in MODULE


def test_scenario_covers_the_complete_operational_shift() -> None:
    required_steps = (
        "receive_task",
        "verify_articles_reward",
        "select_sources",
        "build_shot_plan",
        "approve_8s_brief",
        "choose_production_path",
        "paid_preflight",
        "paid_status_without_restart",
        "quality_control",
        "choose_platform_disclosure",
        "return_post_url",
        "record_metrics",
        "understand_payout",
    )
    for step_id in required_steps:
        assert f'id: "{step_id}"' in MODULE
    assert MODULE.count('phase: "') >= len(required_steps)


def test_task_contract_teaches_main_substitute_article_and_fixed_reward() -> None:
    for phrase in (
        "основной артикул",
        "подменный",
        "Подменник — не другой товар",
        "800 ₽",
        "само не меняется от просмотров",
    ):
        assert phrase in MODULE


def test_production_contract_teaches_8_second_brief_and_safe_paid_control() -> None:
    for phrase in (
        "0–2",
        "2–5",
        "5–8",
        "9:16 · 8 сек",
        "Снять или сгенерировать",
        "Стоимость видна до запуска",
        "Подтверждение будет нажато один раз",
        "проверку статуса без нового запуска",
    ):
        assert phrase in MODULE
    assert 'correct: ["check_existing"]' in MODULE


def test_quality_control_and_result_evidence_are_reproducible() -> None:
    for phrase in (
        "Этикетка меняет буквы",
        "Реплика блогера обрывается",
        "флакон другого объёма",
        "URL конкретного опубликованного клипа",
        "Дата и время",
        "Источник и подтверждение",
    ):
        assert phrase in MODULE


def test_platform_guides_cover_instagram_youtube_vk_without_evasion_advice() -> None:
    for platform in ("instagram", "youtube", "vk"):
        assert f'{platform}: {{' in MODULE
    assert "https://www.facebook.com/help/instagram/1109894795810258/" in MODULE
    assert "https://support.google.com/youtube/answer/154235" in MODULE
    assert "Не убирайте бренд ради обхода метки" in MODULE
    assert "Если в задаче нет однозначного решения" in MODULE
    assert 'correct: ["assigned_vk"]' in MODULE


def test_payout_training_separates_accrued_approved_and_paid() -> None:
    for status in ("Начислено", "Одобрено", "Выплачено"):
        assert status in MODULE
    assert "деньги считаются переведёнными только после статуса «Выплачено»" in MODULE
    assert 'correct: ["approved_not_paid"]' in MODULE


def test_renderer_has_accessible_controls_and_integration_actions() -> None:
    for contract in (
        'role="progressbar"',
        "<fieldset>",
        "<legend",
        'role="status"',
        'data-action="${FIRST_SHIFT_FULL_ACTIONS.select}"',
        'data-action="${FIRST_SHIFT_FULL_ACTIONS.check}"',
        'data-action="${FIRST_SHIFT_FULL_ACTIONS.next}"',
        'data-action="${FIRST_SHIFT_FULL_ACTIONS.previous}"',
        'data-action="${FIRST_SHIFT_FULL_ACTIONS.restart}"',
    ):
        assert contract in MODULE
    assert ".replaceAll(\"&\", \"&amp;\")" in MODULE


def test_styles_are_scoped_responsive_and_keyboard_visible() -> None:
    assert CSS.count(".first-shift-full") > 40
    for contract in (
        "--shift-green:",
        "grid-template-columns",
        ":focus-visible",
        "@media (max-width: 1050px)",
        "@media (max-width: 760px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in CSS
    assert "body {" not in CSS
    assert ":root" not in CSS


def test_runtime_reducer_requires_correct_decisions_and_completes_all_steps() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available")
    script = r"""
import { readFile } from 'node:fs/promises';
const source = await readFile('web/app/first-shift-full-scenario.js', 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const m = await import(moduleUrl);
const scenario = m.FIRST_SHIFT_FULL_SCENARIO;
if (scenario.steps.length !== 13) throw new Error('unexpected step count');
if (!Object.isFrozen(scenario) || !Object.isFrozen(scenario.steps[0])) throw new Error('scenario must be immutable');
for (const step of scenario.steps) {
  const evaluation = m.evaluateFirstShiftFullAnswer(step.id, step.correct);
  if (!evaluation.correct) throw new Error(`correct answer rejected: ${step.id}`);
}

let state = m.createFirstShiftFullState();
state = m.reduceFirstShiftFullState(state, { type: 'select', stepId: 'receive_task', value: 'start_fast' });
state = m.reduceFirstShiftFullState(state, { type: 'check', stepId: 'receive_task' });
if (!state.attempted.includes('receive_task')) throw new Error('failed attempt was not retained');
if (state.checked.includes('receive_task')) throw new Error('wrong answer passed');
if (!m.firstShiftFullScenarioMarkup(state).includes('first-shift-full__feedback--error')) throw new Error('wrong feedback missing');
const blocked = m.reduceFirstShiftFullState(state, { type: 'next' });
if (blocked.stepIndex !== 0) throw new Error('wrong answer advanced');

state = m.reduceFirstShiftFullState(state, { type: 'restart' });
for (const step of scenario.steps) {
  for (const value of step.correct) {
    state = m.reduceFirstShiftFullState(state, { type: 'select', stepId: step.id, value, selected: true });
  }
  state = m.reduceFirstShiftFullState(state, { type: 'check', stepId: step.id });
  if (!state.checked.includes(step.id)) throw new Error(`step did not pass: ${step.id}`);
  state = m.reduceFirstShiftFullState(state, { type: 'next' });
}
if (!state.completed) throw new Error('full shift did not complete');
const progress = m.firstShiftFullProgress(state);
if (progress.percent !== 100 || progress.passed !== 13) throw new Error('progress mismatch');
const completion = m.firstShiftFullScenarioMarkup(state);
if (!completion.includes('first-shift-full-restart')) throw new Error('completion restart missing');

const platform = m.firstShiftFullScenarioMarkup({ stepIndex: 9 });
for (const token of ['first-shift-full__platform-grid', 'facebook.com/help/instagram', 'support.google.com/youtube']) {
  if (!platform.includes(token)) throw new Error(`platform guide missing: ${token}`);
}
console.log('first shift full runtime OK');
"""
    completed = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "first shift full runtime OK" in completed.stdout
