from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202607190005_training_final_exam_rationale_v2.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")

REQUIRED_CODES = (
    "exam_sku_mismatch",
    "exam_qa_requirements",
    "exam_publication_evidence",
    "exam_payout_separation",
)


def _function_source(name: str, *, async_function: bool = False) -> str:
    prefix = "async function" if async_function else "function"
    start = APP.index(f"{prefix} {name}(")
    next_sync = APP.find("\nfunction ", start + 1)
    next_async = APP.find("\nasync function ", start + 1)
    endings = [value for value in (next_sync, next_async) if value >= 0]
    return APP[start : min(endings) if endings else len(APP)]


def test_migration_is_transactional_and_has_balanced_function_bodies() -> None:
    assert MIGRATION.lstrip().casefold().startswith("begin;")
    assert MIGRATION.rstrip().casefold().endswith("commit;")
    assert MIGRATION.count("$$") % 2 == 0
    assert "create or replace function public.creator_submit_exam(" in MIGRATION


def test_wrapper_requires_exactly_four_private_structured_rationales() -> None:
    assert "creator_submit_exam_pre_rationale_v2" in MIGRATION
    assert "content_factory_private.valid_training_rationale(" in MIGRATION
    assert "<> 4" in MIGRATION
    assert "jsonb_object_keys(submitted_rationales)" in MIGRATION
    assert "jsonb_typeof(submitted_rationales) <> 'object'" in MIGRATION
    for code in REQUIRED_CODES:
        assert f"'{code}'" in MIGRATION

    assert "final_exam_rationales_required" in MIGRATION
    assert "final_exam_rationale_invalid" in MIGRATION
    assert "count(distinct lower(regexp_replace(" in MIGRATION
    assert "final_exam_rationales_must_be_unique" in MIGRATION


def test_wrapper_does_not_change_or_disclose_exam_answer_keys() -> None:
    assert "training_answer_keys" not in MIGRATION
    assert "correct_answers" not in MIGRATION
    assert "critical_answers" not in MIGRATION
    assert "insert into content_factory.training_questions" not in MIGRATION.lower()
    assert "update content_factory.training_questions" not in MIGRATION.lower()
    assert "p_payload - 'rationales'" in MIGRATION
    assert "return result;" in MIGRATION


def test_rationales_are_saved_on_the_corresponding_attempt_and_immutable() -> None:
    assert "attempt.idempotency_key = left('exam:' || idempotency_key, 180)" in MIGRATION
    assert "attempt.id = attempt_id" in MIGRATION
    assert "attempt.organization_id = organization_id" in MIGRATION
    assert "attempt.profile_id = user_id" in MIGRATION
    assert "attempt.module_code = exam_code" in MIGRATION
    assert "for update" in MIGRATION.lower()
    assert "rationales = submitted_rationales" in MIGRATION
    assert "assessment_version = greatest(attempt.assessment_version, 2)" in MIGRATION
    assert "request_hash = content_factory_private.json_hash(jsonb_build_object(" in MIGRATION
    assert "'answers', attempt.answers" in MIGRATION
    assert "'rationales', submitted_rationales" in MIGRATION
    assert MIGRATION.count("final_exam_rationales_immutable") >= 3
    assert "existing_rationales <> submitted_rationales" in MIGRATION
    assert "existing_rationales <> '{}'::jsonb" in MIGRATION


def test_private_predecessor_is_not_browser_callable() -> None:
    assert "revoke all on function" in MIGRATION
    assert "from public, anon, authenticated" in MIGRATION
    assert "grant execute on function public.creator_submit_exam(jsonb)" in MIGRATION
    assert "to authenticated" in MIGRATION
    assert "has_function_privilege(" in MIGRATION
    assert "private_final_exam_rationale_implementation_is_browser_callable" in MIGRATION


def test_browser_renders_written_work_only_for_required_cases() -> None:
    prompts = APP[
        APP.index("const FINAL_EXAM_RATIONALE_PROMPTS") :
        APP.index("const REAL_GEN4_MODE")
    ]
    for code in REQUIRED_CODES:
        assert f"{code}:" in prompts
    assert prompts.count("exam_") == 4
    assert "Object.keys(FINAL_EXAM_RATIONALE_PROMPTS)" in prompts

    question_markup = _function_source("questionMarkup")
    assert "finalExamRequiresRationale(question.code)" in question_markup
    assert 'name="rationale_${escapeHtml(question.code)}"' in question_markup
    assert 'placeholder="Риск: … Проверка: … Действие: …"' in question_markup
    assert 'minlength="40"' in question_markup
    assert 'maxlength="900"' in question_markup


def test_final_exam_presentation_uses_full_work_cases_without_easy_prompts() -> None:
    presentation = APP[
        APP.index("const FINAL_EXAM_PRESENTATION") :
        APP.index("const FINAL_EXAM_RATIONALE_PROMPTS")
    ]
    for old_prompt in (
        "Фото товара не совпадают с артикулом в задаче. Что делать?",
        "Что проверить перед одобрением ролика? Выберите все нужные действия.",
        "Что сохранить после публикации? Выберите нужные данные.",
        "Креатор добавил ссылку на публикацию. Когда выплата подтверждена?",
    ):
        assert old_prompt not in presentation
    for work_signal in ("дедлайн", "доказательство", "конфликт"):
        assert work_signal in presentation.lower()
    assert "частично" not in presentation.lower()
    assert "приложить таймкод" in presentation
    assert "периода перехода" in presentation


def test_course_role_hints_do_not_reveal_a_single_expected_action() -> None:
    hints = APP[
        APP.index("const COURSE_KNOWLEDGE_PRESENTATION") :
        APP.index("const FINAL_EXAM_PRESENTATION")
    ]
    assert "выбирайте остановку" not in hints.lower()
    assert "выберите один безопасный следующий шаг" not in hints.lower()
    assert "точный набор" in hints.lower()
    assert "компромисс" in hints.lower()


def test_browser_validates_structure_uniqueness_and_submits_rationales() -> None:
    validator = _function_source("finalExamRationaleIsValid")
    assert "rationale.length >= 40" in validator
    assert "rationale.length <= 900" in validator
    assert "words.length >= 7" in validator
    assert "meaningfulWords.size >= 5" in validator
    assert "/риск\\s*:.+(проверка|доказательство)\\s*:.+" in validator
    assert "(действие|следующий шаг)\\s*:/iu.test(rationale)" in validator

    submit_exam = _function_source("submitExam", async_function=True)
    assert "for (const questionCode of FINAL_EXAM_RATIONALE_CODES)" in submit_exam
    assert "finalExamRationaleIsValid(rationale)" in submit_exam
    assert "normalizedRationales.has(normalizedRationale)" in submit_exam
    assert "rationales[questionCode] = rationale" in submit_exam
    assert "state.api.submitExam(answers, rationales)" in submit_exam

    assert "submitExam(answers, rationales)" in API
    api_submit = API[
        API.index("  submitExam(answers, rationales)") :
        API.index("  workspaceSection(")
    ]
    assert "answers," in api_submit
    assert "rationales," in api_submit


def test_exam_draft_is_per_user_ttl_bound_and_cleared_only_after_pass() -> None:
    draft_helpers = APP[
        APP.index("function finalExamDraftKey(") :
        APP.index("function finalExamPassScore(")
    ]
    assert "userId = state.user?.id" in draft_helpers
    assert "contentengine.final-exam-draft.v${FINAL_EXAM_DRAFT_VERSION}:${safeUser}" in draft_helpers
    assert "window.localStorage.setItem" in draft_helpers
    assert "updatedAt: Date.now()" in draft_helpers
    assert "FINAL_EXAM_DRAFT_MAX_AGE_MS" in draft_helpers
    assert "window.localStorage.getItem" in draft_helpers
    assert "draft.answers?.[question.code]" in draft_helpers
    assert "draft.rationales?.[questionCode]" in draft_helpers

    render_exam = _function_source("renderExam")
    assert "restoreFinalExamDraft();" in render_exam
    assert "if (state.bootstrap.training.exam.passed)" in render_exam
    assert "clearFinalExamDraft();" in render_exam

    submit_exam = _function_source("submitExam", async_function=True)
    assert "persistFinalExamDraft(form);" in submit_exam
    assert "if (state.examResult.passed) clearFinalExamDraft();" in submit_exam
    assert "if (!state.examResult.passed)" in submit_exam
    assert submit_exam.count("clearFinalExamDraft()") == 1

    form_activity = _function_source("handleFormActivity")
    assert 'event.target.closest?.("#exam-form")' in form_activity
    assert "persistFinalExamDraft(finalExamForm)" in form_activity
