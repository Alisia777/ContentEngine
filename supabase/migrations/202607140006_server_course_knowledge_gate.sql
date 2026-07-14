begin;

-- Migration 005 seeds and sanitizes the catalog atomically on a fresh deploy.
-- Repeat the mapping here as a compatibility backfill for any environment that
-- received an earlier catalog shape, and defensively remove all answer material
-- before the public grading RPC is installed.
with source_questions as (
  select
    module.code as module_code,
    question.item as question,
    question.ordinality::integer as question_order,
    case
      when strpos(
        question.item ->> 'id',
        'course_check_' || module.code || '_'
      ) = 1 then question.item ->> 'id'
      else 'course_check_' || module.code || '_' || (question.item ->> 'id')
    end as question_code
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content #> '{knowledge_check,questions}'
  ) with ordinality as question(item, ordinality)
  where module.module_type = 'course'
    and module.is_active
)
insert into content_factory.training_questions (
  code,
  module_code,
  question_type,
  prompt,
  options,
  order_index,
  updated_at
)
select
  source.question_code,
  source.module_code,
  'single_choice',
  source.question ->> 'prompt',
  source.question -> 'options',
  900 + source.question_order,
  now()
from source_questions source
on conflict (code) do update set
  module_code = excluded.module_code,
  question_type = excluded.question_type,
  prompt = excluded.prompt,
  options = excluded.options,
  order_index = excluded.order_index,
  updated_at = now();

with source_answers as (
  select
    module.code as module_code,
    question.item as question,
    case
      when strpos(
        question.item ->> 'id',
        'course_check_' || module.code || '_'
      ) = 1 then question.item ->> 'id'
      else 'course_check_' || module.code || '_' || (question.item ->> 'id')
    end as question_code
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content #> '{knowledge_check,questions}'
  ) as question(item)
  where module.module_type = 'course'
    and module.is_active
)
insert into content_factory_private.training_answer_keys (
  question_code,
  correct_answers,
  rubric,
  updated_at
)
select
  source.question_code,
  jsonb_build_array(source.question ->> 'correct_value'),
  nullif(btrim(source.question ->> 'explanation'), ''),
  now()
from source_answers source
where nullif(btrim(source.question ->> 'correct_value'), '') is not null
on conflict (question_code) do update set
  correct_answers = excluded.correct_answers,
  rubric = excluded.rubric,
  updated_at = now();

with rewritten_questions as (
  select
    module.code as module_code,
    jsonb_agg(
      (question.item - 'correct_value' - 'explanation')
      || jsonb_build_object(
        'id',
        case
          when strpos(
            question.item ->> 'id',
            'course_check_' || module.code || '_'
          ) = 1 then question.item ->> 'id'
          else 'course_check_' || module.code || '_' || (question.item ->> 'id')
        end
      )
      order by question.ordinality
    ) as questions
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content #> '{knowledge_check,questions}'
  ) with ordinality as question(item, ordinality)
  where module.module_type = 'course'
    and module.is_active
  group by module.code
)
update content_factory.training_modules module
set
  content = jsonb_set(
    module.content,
    '{knowledge_check,questions}',
    rewritten.questions,
    false
  ),
  updated_at = now()
from rewritten_questions rewritten
where module.code = rewritten.module_code;

alter table content_factory.training_modules
  drop constraint if exists training_modules_no_public_course_answer_keys;

alter table content_factory.training_modules
  add constraint training_modules_no_public_course_answer_keys check (
    module_type <> 'course'
    or (
      not jsonb_path_exists(
        content,
        '$.knowledge_check.questions[*].correct_value'
      )
      and not jsonb_path_exists(
        content,
        '$.knowledge_check.questions[*].explanation'
      )
    )
  );

-- The previous completion RPC minted zero-question synthetic attempts.  Those
-- course certificates are explicitly revoked and audited.  Final-exam
-- certificates and any non-synthetic attempt are deliberately untouched.
with revoked_certifications as (
  update content_factory.training_certifications certification
  set status = 'revoked'
  from content_factory.training_attempts attempt
  join content_factory.training_modules module
    on module.code = attempt.module_code
   and module.module_type = 'course'
  where certification.attempt_id = attempt.id
    and certification.module_code = module.code
    and certification.status = 'passed'
    and attempt.question_count = 0
    and attempt.answered_count = 0
    and attempt.correct_count = 0
  returning
    certification.id,
    certification.organization_id,
    certification.profile_id,
    certification.module_code,
    certification.attempt_id
)
insert into content_factory.factory_events (
  organization_id,
  profile_id,
  event_name,
  source,
  entity_type,
  entity_id,
  properties,
  idempotency_key
)
select
  revoked.organization_id,
  revoked.profile_id,
  'training_course_certificate_revoked',
  'system',
  'training_certification',
  revoked.id::text,
  jsonb_build_object(
    'reason', 'synthetic_zero_question_attempt_replaced_by_server_gate',
    'module_code', revoked.module_code,
    'attempt_id', revoked.attempt_id,
    'migration', '202607140006_server_course_knowledge_gate'
  ),
  'course-gate-revoke:' || revoked.id::text
from revoked_certifications revoked
on conflict on constraint factory_events_org_key_uq do nothing;

-- Workspace RPCs already centralize their authorization through
-- membership_role(..., true, ...). Extend that shared gate so a retained final
-- exam certificate cannot bypass the four refreshed course checks. Calls used
-- to study, submit a check, complete a course, or sit the exam pass false and
-- therefore remain available while the workspace is locked.
create or replace function content_factory_private.membership_role(
  organization_id uuid,
  require_certification boolean default false,
  allowed_roles text[] default null
)
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  user_id uuid := auth.uid();
  actor_role text;
begin
  if user_id is null then
    raise exception using
      errcode = '42501',
      message = 'authentication_required';
  end if;

  select membership.role into actor_role
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = membership_role.organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';

  if actor_role is null then
    raise exception using
      errcode = '42501',
      message = 'active_membership_required';
  end if;

  if allowed_roles is not null
     and not (actor_role = any(allowed_roles)) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;

  if require_certification and not exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = membership_role.organization_id
      and certification.profile_id = user_id
      and certification.module_code = 'operator_final_exam'
      and certification.status = 'passed'
      and (
        certification.expires_at is null
        or certification.expires_at > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'final_exam_required';
  end if;

  if require_certification and exists (
    select 1
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
      and not exists (
        select 1
        from content_factory.training_certifications certification
        join content_factory.training_attempts attempt
          on attempt.id = certification.attempt_id
         and attempt.organization_id = certification.organization_id
         and attempt.profile_id = certification.profile_id
         and attempt.module_code = certification.module_code
        where certification.organization_id = membership_role.organization_id
          and certification.profile_id = user_id
          and certification.module_code = module.code
          and certification.status = 'passed'
          and (
            certification.expires_at is null
            or certification.expires_at > now()
          )
          and attempt.status = 'completed'
          and attempt.passed
          and attempt.idempotency_key like 'course-check:%'
          and attempt.question_count = jsonb_array_length(
            module.content #> '{knowledge_check,questions}'
          )
          and attempt.answered_count = attempt.question_count
          and attempt.correct_count >= (
            module.content #>> '{knowledge_check,pass_score}'
          )::integer
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'refreshed_courses_required';
  end if;

  return actor_role;
end;
$$;

-- Storage RLS uses a separate predicate, so keep it aligned with the shared
-- workspace RPC gate.  Otherwise an old final-exam certificate could still
-- read or upload private media while the refreshed courses are incomplete.
create or replace function content_factory.storage_access_allowed(
  p_organization_id text,
  p_owner_id text,
  p_allow_team_read boolean default false
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.training_certifications final_certification
      on final_certification.organization_id = membership.organization_id
     and final_certification.profile_id = membership.profile_id
     and final_certification.module_code = 'operator_final_exam'
     and final_certification.status = 'passed'
     and (
       final_certification.expires_at is null
       or final_certification.expires_at > now()
     )
    where membership.profile_id = auth.uid()
      and membership.status = 'active'
      and membership.organization_id::text = p_organization_id
      and (
        (
          p_allow_team_read
          and (
            p_owner_id = auth.uid()::text
            or membership.role in ('owner', 'admin', 'producer', 'reviewer')
          )
        )
        or (
          not p_allow_team_read
          and p_owner_id = auth.uid()::text
          and membership.role in (
            'owner', 'admin', 'producer', 'reviewer', 'operator'
          )
        )
      )
      and not exists (
        select 1
        from content_factory.training_modules module
        where module.module_type = 'course'
          and module.is_active
          and not exists (
            select 1
            from content_factory.training_certifications course_certification
            join content_factory.training_attempts attempt
              on attempt.id = course_certification.attempt_id
             and attempt.organization_id = course_certification.organization_id
             and attempt.profile_id = course_certification.profile_id
             and attempt.module_code = course_certification.module_code
            where course_certification.organization_id = membership.organization_id
              and course_certification.profile_id = membership.profile_id
              and course_certification.module_code = module.code
              and course_certification.status = 'passed'
              and (
                course_certification.expires_at is null
                or course_certification.expires_at > now()
              )
              and attempt.status = 'completed'
              and attempt.passed
              and attempt.idempotency_key like 'course-check:%'
              and attempt.question_count = jsonb_array_length(
                module.content #> '{knowledge_check,questions}'
              )
              and attempt.answered_count = attempt.question_count
              and attempt.correct_count >= (
                module.content #>> '{knowledge_check,pass_score}'
              )::integer
          )
      )
  )
$$;

revoke all on function
  content_factory.storage_access_allowed(text, text, boolean)
  from public, anon;
grant execute on function
  content_factory.storage_access_allowed(text, text, boolean)
  to authenticated;

create or replace function public.creator_submit_course_check(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  course_code text;
  idempotency_key text;
  answers jsonb;
  request_payload jsonb;
  replay jsonb;
  required_correct integer;
  declared_question_count integer;
  total_count integer;
  answered_count integer;
  correct_count integer;
  passed boolean;
  score numeric(6,5);
  attempt_id uuid;
  review_topics jsonb := '[]'::jsonb;
  feedback text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  course_code := content_factory_private.require_text(
    p_payload,
    'module_code',
    3,
    80
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  answers := coalesce(p_payload -> 'answers', '{}'::jsonb);

  if jsonb_typeof(answers) <> 'object' then
    raise exception using
      errcode = '22023',
      message = 'answers_must_be_an_object';
  end if;
  if (select count(*) from jsonb_object_keys(answers)) > 20
     or length(answers::text) > 32000 then
    raise exception using
      errcode = '22023',
      message = 'course_check_answers_invalid';
  end if;

  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );

  select
    case
      when coalesce(module.content #>> '{knowledge_check,pass_score}', '')
        ~ '^[1-9][0-9]*$'
      then (module.content #>> '{knowledge_check,pass_score}')::integer
      else null
    end,
    case
      when jsonb_typeof(module.content #> '{knowledge_check,questions}') = 'array'
      then jsonb_array_length(module.content #> '{knowledge_check,questions}')
      else null
    end
  into required_correct, declared_question_count
  from content_factory.training_modules module
  where module.code = course_code
    and module.module_type = 'course'
    and module.is_active;

  if required_correct is null
     or declared_question_count is null
     or declared_question_count < 1
     or required_correct > declared_question_count then
    raise exception using
      errcode = '55000',
      message = 'course_check_catalog_unavailable';
  end if;

  request_payload := jsonb_build_object(
    'module_code', course_code,
    'answers', answers
  );

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_submit_course_check',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  -- Serialize attempts per learner/course even when two tabs use different
  -- idempotency keys.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('creator_course_check:' || course_code)
  );

  select
    count(*),
    count(*) filter (
      where jsonb_array_length(
        content_factory_private.normalize_answer(answers -> question.code)
      ) > 0
    ),
    count(*) filter (
      where content_factory_private.normalize_answer(answers -> question.code)
        = content_factory_private.normalize_answer(answer_key.correct_answers)
    )
  into total_count, answered_count, correct_count
  from content_factory.training_questions question
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where question.module_code = course_code
    and question.order_index between 901 and 1000
    and strpos(question.code, 'course_check_' || course_code || '_') = 1;

  if total_count = 0 or total_count <> declared_question_count then
    raise exception using
      errcode = '55000',
      message = 'course_check_catalog_unavailable';
  end if;

  if exists (
    select 1
    from jsonb_object_keys(answers) submitted(question_code)
    where not exists (
      select 1
      from content_factory.training_questions question
      where question.module_code = course_code
        and question.code = submitted.question_code
        and question.order_index between 901 and 1000
        and strpos(question.code, 'course_check_' || course_code || '_') = 1
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'unknown_course_check_question';
  end if;

  passed := answered_count = total_count
    and correct_count >= required_correct;
  score := correct_count::numeric / total_count::numeric;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'question_code', question.code,
        'prompt', question.prompt
      )
      order by question.order_index
    ),
    '[]'::jsonb
  )
  into review_topics
  from content_factory.training_questions question
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where question.module_code = course_code
    and question.order_index between 901 and 1000
    and strpos(question.code, 'course_check_' || course_code || '_') = 1
    and content_factory_private.normalize_answer(answers -> question.code)
      <> content_factory_private.normalize_answer(answer_key.correct_answers);

  feedback := case
    when passed then 'Проверка пройдена. Теперь можно завершить блок.'
    else 'Повторите отмеченные темы и пройдите проверку ещё раз.'
  end;

  insert into content_factory.training_attempts (
    organization_id,
    profile_id,
    module_code,
    score,
    correct_count,
    answered_count,
    question_count,
    passed,
    answers,
    request_hash,
    idempotency_key
  ) values (
    organization_id,
    user_id,
    course_code,
    score,
    correct_count,
    answered_count,
    total_count,
    passed,
    answers,
    content_factory_private.json_hash(request_payload),
    left('course-check:' || idempotency_key, 180)
  )
  returning id into attempt_id;

  result := jsonb_build_object(
    'ok', true,
    'attempt_id', attempt_id,
    'module_code', course_code,
    'answered_count', answered_count,
    'question_count', total_count,
    'correct_count', correct_count,
    'required_correct', required_correct,
    'score_percent', round(score * 100, 2),
    'passed', passed,
    'review_topics', review_topics,
    'feedback', feedback
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case
      when passed then 'training_course_check_passed'
      else 'training_course_check_failed'
    end,
    'training_attempt',
    attempt_id::text,
    jsonb_build_object(
      'module_code', course_code,
      'answered_count', answered_count,
      'correct_count', correct_count,
      'question_count', total_count,
      'passed', passed
    ),
    'course-check:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_submit_course_check',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

-- Keep the established bootstrap implementation as a private implementation
-- detail.  The public wrapper adds mini-check state and enforces the refreshed
-- course gate without duplicating the large, already-audited bootstrap body.
alter function public.creator_bootstrap(jsonb)
  rename to creator_bootstrap_pre_course_gate;

alter function public.creator_bootstrap_pre_course_gate(jsonb)
  set schema content_factory_private;

revoke all on function
  content_factory_private.creator_bootstrap_pre_course_gate(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  result jsonb;
  course_checks jsonb := '[]'::jsonb;
  courses_required integer := 0;
  passed_checks integer := 0;
  certified_courses integer := 0;
  refreshed_courses_ready boolean := false;
begin
  result := content_factory_private.creator_bootstrap_pre_course_gate(p_payload);

  if jsonb_typeof(result -> 'learning') <> 'object'
     or nullif(result #>> '{organization,id}', '') is null then
    return result;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := (result #>> '{organization,id}')::uuid;

  select
    count(*),
    count(*) filter (
      where selected_attempt.id is not null and selected_attempt.passed
    ),
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'module_code', module.code,
          'status', case
            when selected_attempt.id is null then 'not_started'
            when selected_attempt.passed then 'passed'
            else 'retry_required'
          end,
          'passed', coalesce(selected_attempt.passed, false),
          'attempt_id', selected_attempt.id,
          'correct_count', selected_attempt.correct_count,
          'question_count', jsonb_array_length(
            module.content #> '{knowledge_check,questions}'
          ),
          'completed_at', selected_attempt.completed_at
        )
        order by module.order_index
      ),
      '[]'::jsonb
    )
  into courses_required, passed_checks, course_checks
  from content_factory.training_modules module
  left join lateral (
    select
      attempt.id,
      attempt.correct_count,
      attempt.completed_at,
      (
        attempt.status = 'completed'
        and attempt.passed
        and attempt.answered_count = attempt.question_count
        and attempt.question_count = jsonb_array_length(
          module.content #> '{knowledge_check,questions}'
        )
        and attempt.correct_count >= (
          module.content #>> '{knowledge_check,pass_score}'
        )::integer
      ) as passed
    from content_factory.training_attempts attempt
    where attempt.organization_id = organization_id
      and attempt.profile_id = user_id
      and attempt.module_code = module.code
      and attempt.idempotency_key like 'course-check:%'
      and attempt.question_count = jsonb_array_length(
        module.content #> '{knowledge_check,questions}'
      )
      and attempt.answered_count <= attempt.question_count
    order by
      (
        attempt.status = 'completed'
        and attempt.passed
        and attempt.answered_count = attempt.question_count
        and attempt.correct_count >= (
          module.content #>> '{knowledge_check,pass_score}'
        )::integer
      ) desc,
      attempt.completed_at desc
    limit 1
  ) selected_attempt on true
  where module.module_type = 'course'
    and module.is_active;

  certified_courses := coalesce(
    nullif(result #>> '{learning,courses_completed}', '')::integer,
    0
  );
  refreshed_courses_ready := courses_required > 0
    and passed_checks = courses_required
    and certified_courses = courses_required;

  result := jsonb_set(
    result,
    '{learning,course_checks}',
    course_checks,
    true
  );

  -- A previously passed final exam remains valid, but an old synthetic course
  -- completion no longer opens the workspace.  Once the four refreshed course
  -- checks are passed and completed, the existing exam certificate works again.
  if not refreshed_courses_ready then
    result := jsonb_set(result, '{state}', '"learning"'::jsonb, true);
    result := jsonb_set(result, '{workspace_open}', 'false'::jsonb, true);
    result := jsonb_set(
      result,
      '{learning,exam,available}',
      'false'::jsonb,
      true
    );
    result := jsonb_set(
      result,
      '{learning,exam,questions}',
      '[]'::jsonb,
      true
    );
    result := jsonb_set(
      result,
      '{capabilities,mock_generation}',
      'false'::jsonb,
      true
    );
    result := jsonb_set(
      result,
      '{capabilities,real_generation}',
      'false'::jsonb,
      true
    );
  end if;

  return result;
end;
$$;

create or replace function public.creator_complete_module(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  course_code text;
  idempotency_key text;
  request_payload jsonb;
  replay jsonb;
  required_correct integer;
  declared_question_count integer;
  attempt_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  course_code := content_factory_private.require_text(
    p_payload,
    'module_code',
    3,
    80
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );

  select
    case
      when coalesce(module.content #>> '{knowledge_check,pass_score}', '')
        ~ '^[1-9][0-9]*$'
      then (module.content #>> '{knowledge_check,pass_score}')::integer
      else null
    end,
    case
      when jsonb_typeof(module.content #> '{knowledge_check,questions}') = 'array'
      then jsonb_array_length(module.content #> '{knowledge_check,questions}')
      else null
    end
  into required_correct, declared_question_count
  from content_factory.training_modules module
  where module.code = course_code
    and module.module_type = 'course'
    and module.is_active;

  if required_correct is null
     or declared_question_count is null
     or declared_question_count < 1
     or required_correct > declared_question_count then
    raise exception using
      errcode = '22023',
      message = 'course_not_found';
  end if;

  -- Preserve the pre-migration command hash shape so a retained network retry
  -- can be inspected and safely superseded instead of raising a hash conflict.
  request_payload := p_payload - 'idempotency_key';
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('creator_complete_course:' || course_code)
  );

  select attempt.id into attempt_id
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = course_code
    and attempt.status = 'completed'
    and attempt.passed
    and attempt.idempotency_key like 'course-check:%'
    and attempt.question_count = declared_question_count
    and attempt.answered_count = declared_question_count
    and attempt.correct_count >= required_correct
  order by attempt.completed_at desc
  limit 1;

  if attempt_id is null then
    raise exception using
      errcode = '42501',
      message = 'course_knowledge_check_required';
  end if;

  -- Validate the server attempt before consulting an old command receipt.
  -- This prevents a retained pre-migration completion key from replaying the
  -- former synthetic-success response after its certificate was revoked.
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_complete_module',
    idempotency_key,
    request_payload
  );
  if replay is not null
     and coalesce(
       replay ->> 'knowledge_attempt_id',
       replay ->> 'attempt_id'
     ) = attempt_id::text then
    return replay;
  end if;

  insert into content_factory.training_certifications (
    organization_id,
    profile_id,
    module_code,
    attempt_id,
    status
  ) values (
    organization_id,
    user_id,
    course_code,
    attempt_id,
    'passed'
  )
  on conflict on constraint training_certifications_org_profile_module_uq do update set
    attempt_id = excluded.attempt_id,
    status = 'passed',
    granted_at = now(),
    expires_at = null;

  result := jsonb_build_object(
    'ok', true,
    'module_code', course_code,
    'completed', true,
    'attempt_id', attempt_id,
    'knowledge_attempt_id', attempt_id
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'training_course_completed',
    'training_module',
    course_code,
    jsonb_build_object(
      'module_code', course_code,
      'knowledge_attempt_id', attempt_id,
      'server_gate', true
    ),
    'course:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_complete_module',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

do $server_course_gate_contract$
declare
  public_question_count integer;
  server_question_count integer;
  private_key_count integer;
  invalid_question_count integer;
  leaked_answer_count integer;
begin
  select coalesce(sum(jsonb_array_length(
    module.content #> '{knowledge_check,questions}'
  )), 0)
  into public_question_count
  from content_factory.training_modules module
  where module.module_type = 'course'
    and module.is_active;

  select count(*)
  into server_question_count
  from content_factory.training_questions question
  join content_factory.training_modules module
    on module.code = question.module_code
   and module.module_type = 'course'
   and module.is_active
  where question.order_index between 901 and 1000
    and strpos(question.code, 'course_check_' || module.code || '_') = 1;

  select count(*)
  into private_key_count
  from content_factory_private.training_answer_keys answer_key
  join content_factory.training_questions question
    on question.code = answer_key.question_code
  join content_factory.training_modules module
    on module.code = question.module_code
   and module.module_type = 'course'
   and module.is_active
  where question.order_index between 901 and 1000
    and strpos(question.code, 'course_check_' || module.code || '_') = 1;

  select count(*)
  into invalid_question_count
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content #> '{knowledge_check,questions}'
  ) as rendered(question)
  where module.module_type = 'course'
    and module.is_active
    and (
      strpos(rendered.question ->> 'id', 'course_check_' || module.code || '_') <> 1
      or not exists (
        select 1
        from content_factory.training_questions server_question
        join content_factory_private.training_answer_keys answer_key
          on answer_key.question_code = server_question.code
        where server_question.code = rendered.question ->> 'id'
          and server_question.module_code = module.code
          and exists (
            select 1
            from jsonb_array_elements(server_question.options) option(item)
            where option.item ->> 'value'
              = answer_key.correct_answers ->> 0
          )
      )
    );

  select count(*)
  into leaked_answer_count
  from content_factory.training_modules module
  where module.module_type = 'course'
    and (
      jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*].correct_value'
      )
      or jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*].explanation'
      )
    );

  if public_question_count < 1
     or server_question_count <> public_question_count
     or private_key_count <> public_question_count
     or invalid_question_count <> 0
     or leaked_answer_count <> 0 then
    raise exception using
      errcode = '23514',
      message = 'server_course_knowledge_gate_contract_failed',
      detail = format(
        'public_questions=%s server_questions=%s private_keys=%s invalid_questions=%s leaked_answers=%s',
        public_question_count,
        server_question_count,
        private_key_count,
        invalid_question_count,
        leaked_answer_count
      );
  end if;
end;
$server_course_gate_contract$;

revoke all on function public.creator_submit_course_check(jsonb)
  from public, anon;
revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;
revoke all on function public.creator_complete_module(jsonb)
  from public, anon;

grant execute on function public.creator_submit_course_check(jsonb)
  to authenticated;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;
grant execute on function public.creator_complete_module(jsonb)
  to authenticated;

comment on function public.creator_submit_course_check(jsonb) is
  'Grades one course mini-check against private answer keys; never returns correct answers.';
comment on function public.creator_bootstrap(jsonb) is
  'Creator bootstrap with sanitized course content and refresh-safe mini-check status.';
comment on function public.creator_complete_module(jsonb) is
  'Completes a course only after a valid server-graded mini-check attempt.';

commit;
