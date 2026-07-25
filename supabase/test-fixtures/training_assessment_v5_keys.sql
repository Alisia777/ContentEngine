begin;

-- TEST-ONLY synthetic grading material for local pgTAP. Production answer
-- keys are injected from an encrypted deployment secret and never live in the
-- repository. Choosing the first visible option here only makes workflow tests
-- deterministic; it does not encode the production grading policy.
insert into content_factory_private.training_answer_keys (
  question_code,
  correct_answers,
  critical_answers,
  rubric,
  updated_at
)
select
  question.code,
  jsonb_build_array(question.options -> 0 ->> 'value'),
  '[]'::jsonb,
  'TEST-ONLY synthetic local pgTAP key',
  now()
from content_factory.training_questions question
join content_factory.training_modules module
  on module.code = question.module_code
where module.module_type = 'course'
  and module.is_active
  and question.order_index between 901 and 1000
  and strpos(
    question.code,
    'course_check_' || module.code || '_'
  ) = 1
on conflict (question_code) do update set
  correct_answers = excluded.correct_answers,
  critical_answers = excluded.critical_answers,
  rubric = excluded.rubric,
  updated_at = excluded.updated_at;

do $training_assessment_v5_test_fixture$
declare
  course_question_count integer;
  valid_key_count integer;
begin
  select count(*) into course_question_count
  from content_factory.training_questions question
  join content_factory.training_modules module
    on module.code = question.module_code
  where module.module_type = 'course'
    and module.is_active
    and question.order_index between 901 and 1000
    and strpos(
      question.code,
      'course_check_' || module.code || '_'
    ) = 1;

  select count(*) into valid_key_count
  from content_factory.training_questions question
  join content_factory.training_modules module
    on module.code = question.module_code
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where module.module_type = 'course'
    and module.is_active
    and question.order_index between 901 and 1000
    and strpos(
      question.code,
      'course_check_' || module.code || '_'
    ) = 1
    and jsonb_array_length(answer_key.correct_answers) = 1
    and exists (
      select 1
      from jsonb_array_elements(question.options) option_item
      where option_item ->> 'value'
        = answer_key.correct_answers ->> 0
    );

  if course_question_count = 0
     or valid_key_count <> course_question_count then
    raise exception using
      errcode = '55000',
      message = 'test_course_gate_fixture_invalid';
  end if;
end;
$training_assessment_v5_test_fixture$;

commit;
