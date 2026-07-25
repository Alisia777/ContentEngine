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

-- The production platform simulator keys are secret-injected as well. Local
-- pgTAP needs a complete, deterministic six-step key for each platform so the
-- server-owned grading path can be exercised without copying production
-- answers into source control.
insert into content_factory_private.training_platform_answer_keys (
  assessment_version,
  platform_code,
  step_code,
  allowed_options,
  correct_option,
  critical_options,
  updated_at
)
select
  1,
  platform.platform_code,
  step.step_code,
  jsonb_build_array('test_correct', 'test_wrong'),
  'test_correct',
  '[]'::jsonb,
  now()
from (
  values ('instagram'), ('youtube'), ('vk')
) platform(platform_code)
cross join (
  values
    ('account'),
    ('warmup'),
    ('publication'),
    ('review'),
    ('link'),
    ('result')
) step(step_code)
on conflict (assessment_version, platform_code, step_code) do update set
  allowed_options = excluded.allowed_options,
  correct_option = excluded.correct_option,
  critical_options = excluded.critical_options,
  updated_at = excluded.updated_at;

do $training_assessment_v5_test_fixture$
declare
  course_question_count integer;
  valid_key_count integer;
  valid_platform_key_count integer;
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

  select count(*) into valid_platform_key_count
  from content_factory_private.training_platform_answer_keys answer_key
  where answer_key.assessment_version = 1
    and answer_key.platform_code in ('instagram', 'youtube', 'vk')
    and answer_key.step_code in (
      'account', 'warmup', 'publication', 'review', 'link', 'result'
    )
    and answer_key.allowed_options @>
      jsonb_build_array(answer_key.correct_option)
    and not (
      answer_key.critical_options @>
        jsonb_build_array(answer_key.correct_option)
    );

  if valid_platform_key_count <> 18 then
    raise exception using
      errcode = '55000',
      message = 'test_platform_gate_fixture_invalid';
  end if;
end;
$training_assessment_v5_test_fixture$;

commit;
