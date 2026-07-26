begin;

-- A single independent "needs changes" decision may prepare one bounded
-- retry.  Only enumerated score dimensions cross the boundary: reviewer
-- comments, findings, recommendations, captions and transcripts are never
-- copied into a future provider prompt.
create table if not exists content_factory.generation_repair_signals (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_job_id uuid not null,
    source_review_id uuid not null,
    source_generation_job_id uuid not null,
    source_media_id uuid not null,
    input_media_id uuid not null,
    product_id uuid not null,
    guard_codes jsonb not null check (
      jsonb_typeof(guard_codes) = 'array'
      and jsonb_array_length(guard_codes) between 1 and 3
      and length(guard_codes::text) <= 256
    ),
    score_snapshot jsonb not null check (
      jsonb_typeof(score_snapshot) = 'object'
      and length(score_snapshot::text) <= 512
    ),
    source_review_completion_hash text not null
      check (source_review_completion_hash ~ '^[0-9a-f]{64}$'),
    source_media_sha256 text not null
      check (source_media_sha256 ~ '^[0-9a-f]{64}$'),
    policy_hash text not null check (policy_hash ~ '^[0-9a-f]{64}$'),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, source_generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, source_review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, source_media_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, input_media_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, generation_job_id),
    unique (organization_id, source_review_id)
);

create index if not exists generation_repair_signals_source_idx
  on content_factory.generation_repair_signals
  (organization_id, source_review_id, created_at desc);

alter table content_factory.generation_repair_signals enable row level security;
revoke all on content_factory.generation_repair_signals
  from public, anon, authenticated;
grant all on content_factory.generation_repair_signals to service_role;

create or replace function
  content_factory_private.guard_generation_repair_signal_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_repair_signal_append_only';
end;
$$;

drop trigger if exists generation_repair_signal_append_only
  on content_factory.generation_repair_signals;
create trigger generation_repair_signal_append_only
before update or delete on content_factory.generation_repair_signals
for each row execute function
  content_factory_private.guard_generation_repair_signal_append_only();

revoke all on function
  content_factory_private.guard_generation_repair_signal_append_only()
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_repair_prompt_requirements(
    p_guard_codes jsonb,
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  requirements text[] := array[]::text[];
  guard_code text;
  requirement_value text;
  photo boolean;
begin
  if jsonb_typeof(p_guard_codes) <> 'array'
     or jsonb_array_length(p_guard_codes) not between 1 and 3
     or p_model not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or exists (
       select 1
       from jsonb_array_elements(p_guard_codes) item(value)
       where jsonb_typeof(item.value) <> 'string'
     )
     or (
       select count(*)
       from jsonb_array_elements_text(p_guard_codes)
     ) <> (
       select count(distinct item.value)
       from jsonb_array_elements_text(p_guard_codes) item(value)
     ) then
    return null;
  end if;
  photo := p_model = 'seedream5_lite';
  for guard_code in
    select item.value
    from jsonb_array_elements_text(p_guard_codes) item(value)
  loop
    requirement_value := case
      when photo and guard_code = 'product_fidelity'
        then 'QA: точная геометрия, этикетка, текст, цвет и пропорции.'
      when photo and guard_code = 'technical_stability'
        then 'QA: резкий товар, ровный свет, без пересвета и размытия.'
      when photo and guard_code = 'hook_clarity'
        then 'QA: товар считывается первым.'
      when photo and guard_code = 'visual_quality'
        then 'QA: чистые края без дублей, деформаций и AI-артефактов.'
      when photo and guard_code = 'trust'
        then 'QA: естественные материалы, свет и масштаб.'
      when photo and guard_code = 'platform_fit'
        then 'QA: мастер 1:1, безопасные поля.'
      when not photo and guard_code = 'product_fidelity'
        then 'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.'
      when not photo and guard_code = 'technical_stability'
        then 'QA: стабильный проход без чёрных кадров, скачков и мерцания.'
      when not photo and guard_code = 'hook_clarity'
        then 'QA: точный товар и одно действие видны в первые 2 секунды.'
      when not photo and guard_code = 'visual_quality'
        then 'QA: руки, лицо и фактуры без деформаций, дублей и мерцания.'
      when not photo and guard_code = 'trust'
        then 'QA: естественная подача без гиперболы и новых обещаний.'
      when not photo and guard_code = 'platform_fit'
        then 'QA: мастер 9:16; товар и лицо в безопасных полях.'
    end;
    if requirement_value is null then
      return null;
    end if;
    requirements := array_append(requirements, requirement_value);
  end loop;
  return requirements;
exception when others then
  return null;
end;
$$;

revoke all on function
  content_factory_private.generation_repair_prompt_requirements(jsonb, text)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_repair_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  team_scope boolean;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  decision_row content_factory.content_review_decisions%rowtype;
  media_row content_factory.media_objects%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  input_media_row content_factory.media_objects%rowtype;
  input_media_id_value uuid;
  model_value text;
  platform_value text;
  destination_value text;
  guard_codes_value jsonb := '[]'::jsonb;
  score_snapshot_value jsonb := '{}'::jsonb;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'review_id'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_repair_policy_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value;
  select decision.* into decision_row
  from content_factory.content_review_decisions decision
  where decision.organization_id = organization_id
    and decision.review_id = review_id_value;
  if review_row.id is null or decision_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'generation_repair_review_not_found';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id;
  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.id = media_row.task_id;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = task_row.generation_job_id;

  if not team_scope
     and user_id is distinct from media_row.owner_id
     and user_id is distinct from task_row.assignee_id
     and user_id is distinct from job_row.requested_by
     and user_id is distinct from job_row.assigned_to then
    raise exception using
      errcode = '42501',
      message = 'generation_repair_not_allowed';
  end if;

  if decision_row.decision <> 'needs_changes' then
    return jsonb_build_object(
      'version', 'review-repair-v1',
      'applied', false,
      'reason_codes', jsonb_build_array('needs_changes_decision_required')
    );
  end if;

  if review_row.status <> 'completed'
     or review_row.completion_hash is null
     or review_row.completion_hash is distinct from
          decision_row.review_completion_hash
     or review_row.media_sha256_snapshot is distinct from media_row.sha256
     or decision_row.media_sha256_snapshot is distinct from media_row.sha256
     or not decision_row.media_watched_confirmed
     or decision_row.decided_by in (
       job_row.requested_by,
       job_row.assigned_to
     )
     or media_row.status <> 'ready'
     or media_row.product_id is null
     or media_row.metadata ->> 'kind' not in (
       'generated_video', 'generated_image'
     )
     or media_row.metadata ->> 'generation_job_id'
          is distinct from job_row.id::text
     or task_row.id is null
     or task_row.task_type <> 'video_review'
     or task_row.generation_job_id is null
     or job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.status <> 'succeeded'
     or job_row.product_id is distinct from media_row.product_id
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or review_row.input ->> 'generation_job_id'
          is distinct from job_row.id::text then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_review_context_invalid';
  end if;

  model_value := lower(btrim(coalesce(job_row.input ->> 'model', '')));
  platform_value :=
    lower(btrim(coalesce(job_row.input ->> 'platform', '')));
  destination_value :=
    btrim(coalesce(job_row.input ->> 'destination_ref', ''));
  if model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or platform_value not in (
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or length(destination_value) not between 2 and 240
     or coalesce(job_row.input ->> 'input_media_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_generation_context_invalid';
  end if;
  input_media_id_value := (job_row.input ->> 'input_media_id')::uuid;

  select media.* into input_media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = input_media_id_value
    and media.product_id = job_row.product_id
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb;
  if input_media_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_input_media_invalid';
  end if;

  if jsonb_typeof(review_row.result -> 'scores') <> 'object'
     or coalesce(review_row.result #>> '{scores,technical}', '')
          !~ '^[0-9]{1,3}$'
     or coalesce(
          review_row.result #>> '{scores,product_fidelity}', ''
        ) !~ '^[0-9]{1,3}$'
     or coalesce(review_row.result #>> '{scores,hook_clarity}', '')
          !~ '^[0-9]{1,3}$'
     or coalesce(review_row.result #>> '{scores,visual_quality}', '')
          !~ '^[0-9]{1,3}$'
     or coalesce(review_row.result #>> '{scores,trust}', '')
          !~ '^[0-9]{1,3}$'
     or coalesce(review_row.result #>> '{scores,platform_fit}', '')
          !~ '^[0-9]{1,3}$'
     or (review_row.result #>> '{scores,technical}')::integer
          not between 0 and 100
     or (review_row.result #>> '{scores,product_fidelity}')::integer
          not between 0 and 100
     or (review_row.result #>> '{scores,hook_clarity}')::integer
          not between 0 and 100
     or (review_row.result #>> '{scores,visual_quality}')::integer
          not between 0 and 100
     or (review_row.result #>> '{scores,trust}')::integer
          not between 0 and 100
     or (review_row.result #>> '{scores,platform_fit}')::integer
          not between 0 and 100 then
    return jsonb_build_object(
      'version', 'review-repair-v1',
      'applied', false,
      'reason_codes', jsonb_build_array('structured_scores_unavailable')
    );
  end if;

  score_snapshot_value := jsonb_build_object(
    'technical',
      (review_row.result #>> '{scores,technical}')::integer,
    'product_fidelity',
      (review_row.result #>> '{scores,product_fidelity}')::integer,
    'hook_clarity',
      (review_row.result #>> '{scores,hook_clarity}')::integer,
    'visual_quality',
      (review_row.result #>> '{scores,visual_quality}')::integer,
    'trust',
      (review_row.result #>> '{scores,trust}')::integer,
    'platform_fit',
      (review_row.result #>> '{scores,platform_fit}')::integer
  );
  with weaknesses(code, score, priority) as (
    values
      (
        'product_fidelity'::text,
        (review_row.result #>> '{scores,product_fidelity}')::integer,
        1
      ),
      (
        'technical_stability',
        (review_row.result #>> '{scores,technical}')::integer,
        2
      ),
      (
        'hook_clarity',
        (review_row.result #>> '{scores,hook_clarity}')::integer,
        3
      ),
      (
        'visual_quality',
        (review_row.result #>> '{scores,visual_quality}')::integer,
        4
      ),
      (
        'trust',
        (review_row.result #>> '{scores,trust}')::integer,
        5
      ),
      (
        'platform_fit',
        (review_row.result #>> '{scores,platform_fit}')::integer,
        6
      )
  ),
  selected as (
    select weakness.*
    from weaknesses weakness
    where weakness.score < 85
    order by weakness.score, weakness.priority, weakness.code
    limit 3
  )
  select coalesce(
    jsonb_agg(code order by score, priority, code),
    '[]'::jsonb
  )
  into guard_codes_value
  from selected;

  if jsonb_array_length(guard_codes_value) = 0 then
    return jsonb_build_object(
      'version', 'review-repair-v1',
      'applied', false,
      'reason_codes', jsonb_build_array('no_structured_quality_weakness')
    );
  end if;

  policy_without_hash := jsonb_build_object(
    'version', 'review-repair-v1',
    'applied', true,
    'source_review_id', review_row.id,
    'source_generation_job_id', job_row.id,
    'source_media_id', media_row.id,
    'input_media_id', input_media_row.id,
    'product_id', job_row.product_id,
    'model', model_value,
    'platform', platform_value,
    'destination_ref', destination_value,
    'guard_codes', guard_codes_value,
    'score_snapshot', score_snapshot_value,
    'source_review_completion_hash', review_row.completion_hash,
    'source_media_sha256', media_row.sha256,
    'reason_codes', jsonb_build_array(
      'independent_review_structured_repair'
    ),
    'safety', jsonb_build_object(
      'raw_review_copy_excluded', true,
      'same_product_input_model_platform', true,
      'guard_count_bounded', true,
      'provider_spend_requires_separate_confirmation', true
    )
  );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);
  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value
  );
end;
$$;

revoke all on function public.creator_generation_repair_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_repair_policy(jsonb)
  to authenticated;

-- Keep the complete paid command private and add an immediate-repair binding
-- before it.  The old command never sees repair_context, so its request hash,
-- idempotency and provider spend semantics remain unchanged.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_repair_v6;

revoke all on function
  content_factory_private.creator_start_real_generation_pre_repair_v6(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
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
  repair_context jsonb;
  server_policy jsonb;
  requirements text[];
  requirement_value text;
  result jsonb;
  generation_job_id_value uuid;
  existing_signal content_factory.generation_repair_signals%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not p_payload ? 'repair_context' then
    return content_factory_private
      .creator_start_real_generation_pre_repair_v6(p_payload);
  end if;

  repair_context := p_payload -> 'repair_context';
  if jsonb_typeof(repair_context) <> 'object'
     or repair_context - array[
       'source_review_id',
       'source_generation_job_id',
       'guard_codes',
       'policy_hash',
       'compiler_version'
     ]::text[] <> '{}'::jsonb
     or (
       select count(*)
       from jsonb_object_keys(repair_context)
     ) <> 5
     or repair_context ->> 'compiler_version' <> 'review-repair-v1'
     or coalesce(repair_context ->> 'source_review_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     or coalesce(repair_context ->> 'source_generation_job_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     or coalesce(repair_context ->> 'policy_hash', '')
       !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_repair_context_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  server_policy := public.creator_generation_repair_policy(
    jsonb_build_object(
      'organization_id', organization_id,
      'review_id', repair_context ->> 'source_review_id'
    )
  );
  if server_policy -> 'applied' is distinct from 'true'::jsonb
     or server_policy ->> 'policy_hash'
          is distinct from repair_context ->> 'policy_hash'
     or server_policy ->> 'source_generation_job_id'
          is distinct from repair_context ->> 'source_generation_job_id'
     or server_policy -> 'guard_codes'
          is distinct from repair_context -> 'guard_codes'
     or server_policy ->> 'input_media_id'
          is distinct from p_payload #>> '{media_ids,0}'
     or server_policy ->> 'model'
          is distinct from p_payload ->> 'model'
     or server_policy ->> 'platform'
          is distinct from lower(btrim(coalesce(
            p_payload ->> 'platform',
            ''
          )))
     or server_policy ->> 'destination_ref'
          is distinct from btrim(coalesce(
            p_payload ->> 'destination_ref',
            ''
          )) then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_policy_stale';
  end if;

  requirements :=
    content_factory_private.generation_repair_prompt_requirements(
      server_policy -> 'guard_codes',
      p_payload ->> 'model'
    );
  if requirements is null or cardinality(requirements) = 0 then
    raise exception using
      errcode = '22023',
      message = 'generation_repair_prompt_binding_invalid';
  end if;
  foreach requirement_value in array requirements
  loop
    if position(requirement_value in coalesce(p_payload ->> 'brief', '')) = 0
    then
      raise exception using
        errcode = '22023',
        message = 'generation_repair_prompt_binding_invalid';
    end if;
  end loop;

  result := content_factory_private
    .creator_start_real_generation_pre_repair_v6(
      p_payload - 'repair_context'
    );
  if coalesce(result #>> '{job,id}', '') !~
     '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_job_binding_invalid';
  end if;
  generation_job_id_value := (result #>> '{job,id}')::uuid;

  insert into content_factory.generation_repair_signals (
    organization_id,
    generation_job_id,
    source_review_id,
    source_generation_job_id,
    source_media_id,
    input_media_id,
    product_id,
    guard_codes,
    score_snapshot,
    source_review_completion_hash,
    source_media_sha256,
    policy_hash,
    prompt_hash,
    created_by
  ) values (
    organization_id,
    generation_job_id_value,
    (server_policy ->> 'source_review_id')::uuid,
    (server_policy ->> 'source_generation_job_id')::uuid,
    (server_policy ->> 'source_media_id')::uuid,
    (server_policy ->> 'input_media_id')::uuid,
    (server_policy ->> 'product_id')::uuid,
    server_policy -> 'guard_codes',
    server_policy -> 'score_snapshot',
    server_policy ->> 'source_review_completion_hash',
    server_policy ->> 'source_media_sha256',
    server_policy ->> 'policy_hash',
    content_factory_private.json_hash(
      to_jsonb(coalesce(p_payload ->> 'brief', ''))
    ),
    user_id
  )
  on conflict do nothing;

  select signal.* into existing_signal
  from content_factory.generation_repair_signals signal
  where signal.organization_id = organization_id
    and signal.generation_job_id = generation_job_id_value;
  if existing_signal.id is null
     or existing_signal.source_review_id::text
          is distinct from server_policy ->> 'source_review_id'
     or existing_signal.source_generation_job_id::text
          is distinct from server_policy ->> 'source_generation_job_id'
     or existing_signal.guard_codes
          is distinct from server_policy -> 'guard_codes'
     or existing_signal.policy_hash
          is distinct from server_policy ->> 'policy_hash'
     or existing_signal.prompt_hash
          is distinct from content_factory_private.json_hash(
            to_jsonb(coalesce(p_payload ->> 'brief', ''))
          ) then
    raise exception using
      errcode = '55000',
      message = 'generation_repair_signal_conflict';
  end if;

  return jsonb_set(
    result,
    '{job,repair_signal_recorded}',
    'true'::jsonb,
    true
  );
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
