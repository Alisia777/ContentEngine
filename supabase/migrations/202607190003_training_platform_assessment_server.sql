begin;

-- The browser may render and collect a platform exercise, but it must never
-- decide whether the learner passed it.  The answer key and immutable attempt
-- receipts live behind RPC-only boundaries.

create table content_factory_private.training_platform_answer_keys (
    assessment_version integer not null
      check (assessment_version between 1 and 100),
    platform_code text not null
      check (platform_code in ('instagram', 'youtube', 'vk')),
    step_code text not null
      check (step_code in (
        'account', 'warmup', 'publication', 'review', 'link', 'result'
      )),
    allowed_options jsonb not null check (
      jsonb_typeof(allowed_options) = 'array'
      and jsonb_array_length(allowed_options) between 2 and 6
      and length(allowed_options::text) <= 1200
    ),
    correct_option text not null
      check (correct_option ~ '^[a-z0-9][a-z0-9_]{1,79}$'),
    critical_options jsonb not null default '[]'::jsonb check (
      jsonb_typeof(critical_options) = 'array'
      and jsonb_array_length(critical_options) <= 4
      and length(critical_options::text) <= 800
    ),
    updated_at timestamptz not null default now(),
    primary key (assessment_version, platform_code, step_code),
    check (allowed_options @> jsonb_build_array(correct_option)),
    check (not (critical_options @> jsonb_build_array(correct_option))),
    check (allowed_options @> critical_options)
);

alter table content_factory_private.training_platform_answer_keys
  enable row level security;
revoke all on content_factory_private.training_platform_answer_keys
  from public, anon, authenticated;
grant all on content_factory_private.training_platform_answer_keys
  to service_role;

-- Production answer rows are provisioned from the protected
-- SUPABASE_TRAINING_KEYS_B64 environment secret after all migrations finish.
-- Keeping this public migration data-free prevents the GitHub source from
-- becoming an answer key for the browser exercise.

create table content_factory.training_platform_assessment_attempts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    module_code text not null default 'publishing_funnel'
      references content_factory.training_modules(code),
    walkthrough_id text not null check (
      walkthrough_id in (
        'platform_publish_instagram',
        'platform_publish_youtube',
        'platform_publish_vk'
      )
    ),
    platform_code text not null
      check (platform_code in ('instagram', 'youtube', 'vk')),
    assessment_version integer not null
      check (assessment_version between 1 and 100),
    decisions jsonb not null check (
      jsonb_typeof(decisions) = 'object'
      and length(decisions::text) <= 4096
    ),
    rationales jsonb not null check (
      jsonb_typeof(rationales) = 'object'
      and length(rationales::text) <= 12000
    ),
    correct_count integer not null check (correct_count between 0 and 6),
    critical_error_count integer not null
      check (critical_error_count between 0 and 6),
    score_percent integer not null check (score_percent between 0 and 100),
    passed boolean not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    completed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, profile_id, idempotency_key),
    check (module_code = 'publishing_funnel'),
    check (walkthrough_id = 'platform_publish_' || platform_code),
    check (passed = (
      correct_count >= 5 and critical_error_count = 0
    ))
);

create index training_platform_attempts_rate_limit_idx
  on content_factory.training_platform_assessment_attempts
  (organization_id, profile_id, platform_code, completed_at desc, id desc);

alter table content_factory.training_platform_assessment_attempts
  enable row level security;
revoke all on content_factory.training_platform_assessment_attempts
  from public, anon, authenticated;
grant all on content_factory.training_platform_assessment_attempts
  to service_role;

create or replace function
  content_factory_private.guard_training_platform_assessment_attempt()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'training_platform_attempt_immutable';
end;
$$;

create trigger guard_training_platform_assessment_attempt
before update or delete
on content_factory.training_platform_assessment_attempts
for each row execute function
  content_factory_private.guard_training_platform_assessment_attempt();

create or replace function
  content_factory_private.valid_platform_assessment_rationale(
    submitted jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  with normalized as (
    select regexp_replace(
      lower(btrim(submitted #>> '{}')),
      '[[:space:]]+',
      ' ',
      'g'
    ) as body
    where jsonb_typeof(submitted) = 'string'
  ), token_counts as (
    select
      normalized.body,
      count(*) filter (where length(token.value) >= 2) as word_count,
      count(distinct token.value) filter (
        where length(token.value) >= 3
      ) as meaningful_distinct_word_count,
      max(length(token.value)) as longest_word_length
    from normalized
    cross join lateral regexp_split_to_table(
      lower(normalized.body), '[^0-9A-Za-zА-Яа-яЁё_]+'
    ) token(value)
    group by normalized.body
  )
  select coalesce(bool_and(
    char_length(token_counts.body) between 50 and 900
    and token_counts.body !~ '[[:cntrl:]]'
    and char_length(regexp_replace(
      token_counts.body, '[^A-Za-zА-Яа-яЁё]', '', 'g'
    )) >= 35
    and token_counts.word_count >= 8
    and token_counts.meaningful_distinct_word_count >= 6
    and token_counts.longest_word_length >= 5
    and token_counts.body ~
      'риск[[:space:]]*:.+(проверка|доказательство)[[:space:]]*:.+(действие|следующий шаг)[[:space:]]*:.'
  ), false)
  from token_counts;
$$;

-- Existing client-authored progress and the certification based on it are not
-- accepted as proof of this new server assessment.  Learners redo only this
-- publishing mastery gate; other course progress is preserved.
delete from content_factory.training_walkthrough_progress
where module_code = 'publishing_funnel'
  and walkthrough_id in (
    'platform_publish_instagram',
    'platform_publish_youtube',
    'platform_publish_vk'
  );

update content_factory.training_certifications
set status = 'revoked'
where module_code = 'publishing_funnel'
  and status = 'passed';

-- Preserve the original validated implementation for every ordinary training
-- walkthrough, then put a narrow server-assessment firewall at its public name.
alter function public.creator_save_training_progress(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_save_training_progress(jsonb)
  rename to creator_save_training_progress_before_platform_gate;

create or replace function public.creator_save_training_progress(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  walkthrough_id_value text;
begin
  if jsonb_typeof(p_payload) = 'object' then
    walkthrough_id_value := lower(btrim(coalesce(
      p_payload ->> 'walkthrough_id', ''
    )));
  end if;

  if walkthrough_id_value in (
    'platform_publish_instagram',
    'platform_publish_youtube',
    'platform_publish_vk'
  ) then
    raise exception using
      errcode = '42501',
      message = 'platform_simulator_server_grading_required';
  end if;

  return content_factory_private
    .creator_save_training_progress_before_platform_gate(p_payload);
end;
$$;

create or replace function public.creator_submit_platform_simulator(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  constant_assessment_version constant integer := 1;
  expected_steps constant text[] := array[
    'account', 'warmup', 'publication', 'review', 'link', 'result'
  ];
  user_id uuid;
  organization_id uuid;
  platform_code_value text;
  walkthrough_id_value text;
  assessment_version_value integer;
  decisions_value jsonb;
  rationales_value jsonb;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  key_count integer;
  decision_key_count integer;
  rationale_key_count integer;
  distinct_rationale_count integer;
  recent_attempt_count integer;
  last_attempt_at timestamptz;
  correct_count_value integer;
  critical_error_count_value integer;
  score_percent_value integer;
  passed_value boolean;
  attempt_id_value uuid;
  completed_at_value timestamptz;
  walkthrough_value jsonb;
  all_frame_ids jsonb;
  current_frame_id_value text;
  duration_seconds_value integer;
  progress_row content_factory.training_walkthrough_progress%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 24576
     or p_payload - array[
       'organization_id', 'platform', 'assessment_version',
       'decisions', 'rationales', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );

  platform_code_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 24
  ));
  if platform_code_value not in ('instagram', 'youtube', 'vk') then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_platform_invalid';
  end if;

  if jsonb_typeof(p_payload -> 'assessment_version') <> 'number'
     or coalesce(p_payload ->> 'assessment_version', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_version_invalid';
  end if;
  begin
    assessment_version_value :=
      (p_payload ->> 'assessment_version')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_version_invalid';
  end;
  if assessment_version_value <> constant_assessment_version then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_version_unsupported';
  end if;

  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  decisions_value := coalesce(p_payload -> 'decisions', 'null'::jsonb);
  rationales_value := coalesce(p_payload -> 'rationales', 'null'::jsonb);
  if jsonb_typeof(decisions_value) <> 'object'
     or jsonb_typeof(rationales_value) <> 'object'
     or length(decisions_value::text) > 4096
     or length(rationales_value::text) > 12000 then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_answers_invalid';
  end if;

  select count(*) into decision_key_count
  from jsonb_object_keys(decisions_value);
  select count(*) into rationale_key_count
  from jsonb_object_keys(rationales_value);
  if decision_key_count <> 6
     or rationale_key_count <> 6
     or exists (
       select 1 from jsonb_object_keys(decisions_value) submitted(step_code)
       where not (submitted.step_code = any(expected_steps))
     )
     or exists (
       select 1 from jsonb_object_keys(rationales_value) submitted(step_code)
       where not (submitted.step_code = any(expected_steps))
     )
     or exists (
       select 1 from unnest(expected_steps) expected(step_code)
       where not (decisions_value ? expected.step_code)
          or not (rationales_value ? expected.step_code)
     ) then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_exact_six_steps_required';
  end if;

  if exists (
    select 1
    from unnest(expected_steps) expected(step_code)
    where jsonb_typeof(decisions_value -> expected.step_code) <> 'string'
       or (decisions_value ->> expected.step_code)
            !~ '^[a-z0-9][a-z0-9_]{1,79}$'
       or not content_factory_private.valid_platform_assessment_rationale(
         rationales_value -> expected.step_code
       )
  ) then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_substantive_rationale_required';
  end if;

  select count(distinct lower(regexp_replace(
    btrim(rationale.value #>> '{}'),
    '[^0-9A-Za-zА-Яа-яЁё_]+', ' ', 'g'
  )))
  into distinct_rationale_count
  from jsonb_each(rationales_value) rationale(step_code, value);
  if distinct_rationale_count <> 6 then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_distinct_rationales_required';
  end if;

  select count(*) into key_count
  from content_factory_private.training_platform_answer_keys answer_key
  where answer_key.assessment_version = assessment_version_value
    and answer_key.platform_code = platform_code_value;
  if key_count <> 6 then
    raise exception using
      errcode = '55000',
      message = 'platform_simulator_answer_key_invalid';
  end if;

  if exists (
    select 1
    from content_factory_private.training_platform_answer_keys answer_key
    where answer_key.assessment_version = assessment_version_value
      and answer_key.platform_code = platform_code_value
      and not (
        answer_key.allowed_options @> jsonb_build_array(
          decisions_value ->> answer_key.step_code
        )
      )
  ) then
    raise exception using
      errcode = '22023',
      message = 'platform_simulator_option_invalid';
  end if;

  walkthrough_id_value := 'platform_publish_' || platform_code_value;
  request_payload := jsonb_build_object(
    'profile_id', user_id,
    'platform', platform_code_value,
    'assessment_version', assessment_version_value,
    'decisions', decisions_value,
    'rationales', rationales_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_submit_platform_simulator',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'platform-assessment:' || user_id::text || ':' || platform_code_value
    )
  );
  select count(*), max(attempt.completed_at)
    into recent_attempt_count, last_attempt_at
  from content_factory.training_platform_assessment_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.platform_code = platform_code_value
    and attempt.completed_at > now() - interval '24 hours';

  if last_attempt_at > now() - interval '60 seconds' then
    raise exception using
      errcode = '55000',
      message = 'platform_simulator_cooldown';
  end if;
  if recent_attempt_count >= 8 then
    raise exception using
      errcode = '55000',
      message = 'platform_simulator_daily_attempt_limit';
  end if;

  select
    count(*) filter (
      where decisions_value ->> answer_key.step_code =
        answer_key.correct_option
    ),
    count(*) filter (
      where answer_key.critical_options @> jsonb_build_array(
        decisions_value ->> answer_key.step_code
      )
    )
  into correct_count_value, critical_error_count_value
  from content_factory_private.training_platform_answer_keys answer_key
  where answer_key.assessment_version = assessment_version_value
    and answer_key.platform_code = platform_code_value;

  score_percent_value := round(correct_count_value * 100.0 / 6)::integer;
  passed_value := correct_count_value >= 5
    and critical_error_count_value = 0;
  completed_at_value := now();

  insert into content_factory.training_platform_assessment_attempts (
    organization_id, profile_id, module_code, walkthrough_id,
    platform_code, assessment_version, decisions, rationales,
    correct_count, critical_error_count, score_percent, passed,
    request_hash, idempotency_key, completed_at
  ) values (
    organization_id, user_id, 'publishing_funnel', walkthrough_id_value,
    platform_code_value, assessment_version_value, decisions_value,
    rationales_value, correct_count_value, critical_error_count_value,
    score_percent_value, passed_value,
    content_factory_private.json_hash(request_payload),
    idempotency_key_value, completed_at_value
  )
  returning id into attempt_id_value;

  if passed_value then
    select walkthrough.value
      into walkthrough_value
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements(
      module.content -> 'interactive_walkthroughs'
    ) walkthrough(value)
    where module.code = 'publishing_funnel'
      and module.module_type = 'course'
      and module.is_active
      and walkthrough.value ->> 'id' = walkthrough_id_value;

    if walkthrough_value is null
       or jsonb_typeof(walkthrough_value -> 'frames') <> 'array'
       or jsonb_array_length(walkthrough_value -> 'frames') <> 6
       or coalesce(walkthrough_value ->> 'duration_seconds', '')
            !~ '^[0-9]+$' then
      raise exception using
        errcode = '55000',
        message = 'platform_simulator_walkthrough_catalog_invalid';
    end if;

    duration_seconds_value :=
      (walkthrough_value ->> 'duration_seconds')::integer;
    select
      jsonb_agg(frame.value ->> 'id' order by frame.ordinality),
      (array_agg(frame.value ->> 'id' order by frame.ordinality desc))[1]
    into all_frame_ids, current_frame_id_value
    from jsonb_array_elements(walkthrough_value -> 'frames')
      with ordinality frame(value, ordinality);

    if jsonb_array_length(all_frame_ids) <> 6
       or current_frame_id_value is null then
      raise exception using
        errcode = '55000',
        message = 'platform_simulator_walkthrough_catalog_invalid';
    end if;

    insert into content_factory.training_walkthrough_progress (
      organization_id, profile_id, module_code, walkthrough_id,
      current_frame_id, position_seconds, completed_frame_ids,
      completed, completed_at
    ) values (
      organization_id, user_id, 'publishing_funnel', walkthrough_id_value,
      current_frame_id_value, duration_seconds_value, all_frame_ids,
      true, completed_at_value
    )
    on conflict (
      organization_id, profile_id, module_code, walkthrough_id
    ) do update set
      current_frame_id = excluded.current_frame_id,
      position_seconds = greatest(
        content_factory.training_walkthrough_progress.position_seconds,
        excluded.position_seconds
      ),
      completed_frame_ids = excluded.completed_frame_ids,
      completed = true,
      completed_at = coalesce(
        content_factory.training_walkthrough_progress.completed_at,
        excluded.completed_at
      )
    returning * into progress_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'attempt', jsonb_build_object(
      'attempt_id', attempt_id_value,
      'assessment_version', assessment_version_value,
      'module_code', 'publishing_funnel',
      'walkthrough_id', walkthrough_id_value,
      'platform', platform_code_value,
      'decision_count', 6,
      'rationale_count', 6,
      'pass_percent', 80,
      'passed', passed_value,
      'completed_at', completed_at_value
    ),
    'progress', case
      when passed_value then jsonb_build_object(
        'module_code', progress_row.module_code,
        'walkthrough_id', progress_row.walkthrough_id,
        'completed', progress_row.completed,
        'completed_at', progress_row.completed_at,
        'version', progress_row.version
      )
      else null
    end
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'training_platform_simulator_graded',
    'training_platform_attempt',
    attempt_id_value::text,
    jsonb_build_object(
      'assessment_version', assessment_version_value,
      'module_code', 'publishing_funnel',
      'walkthrough_id', walkthrough_id_value,
      'platform', platform_code_value,
      'score_percent', score_percent_value,
      'critical_error_count', critical_error_count_value,
      'passed', passed_value,
      'server_graded', true
    ),
    'platform-assessment:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_submit_platform_simulator',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function
  content_factory_private.creator_save_training_progress_before_platform_gate(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.creator_save_training_progress_before_platform_gate(jsonb)
  to service_role;

revoke all on function public.creator_save_training_progress(jsonb)
  from public, anon;
grant execute on function public.creator_save_training_progress(jsonb)
  to authenticated;

revoke all on function public.creator_submit_platform_simulator(jsonb)
  from public, anon;
grant execute on function public.creator_submit_platform_simulator(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.valid_platform_assessment_rationale(jsonb)
  from public, anon, authenticated;
grant execute on function
  content_factory_private.valid_platform_assessment_rationale(jsonb)
  to service_role;

revoke all on function
  content_factory_private.guard_training_platform_assessment_attempt()
  from public, anon, authenticated;
grant execute on function
  content_factory_private.guard_training_platform_assessment_attempt()
  to service_role;

do $platform_assessment_contract$
declare
  save_definition text;
  submit_definition text;
begin
  select pg_get_functiondef(
    'public.creator_save_training_progress(jsonb)'::regprocedure
  ) into save_definition;
  select pg_get_functiondef(
    'public.creator_submit_platform_simulator(jsonb)'::regprocedure
  ) into submit_definition;

  if save_definition is null
     or strpos(
       save_definition, 'platform_simulator_server_grading_required'
     ) = 0
     or submit_definition is null
     or strpos(submit_definition, 'training_platform_answer_keys') = 0
     or strpos(submit_definition, 'platform_simulator_exact_six_steps_required') = 0
     or strpos(submit_definition, 'training_walkthrough_progress') = 0 then
    raise exception
      'platform simulator server assessment contract is incomplete';
  end if;
end;
$platform_assessment_contract$;

commit;
