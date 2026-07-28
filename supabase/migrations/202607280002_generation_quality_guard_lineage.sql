begin;

-- Keep the exact, bounded QA guards that reached a provider prompt attached
-- to the immutable generation job.  This closes the causal-learning gap
-- without retaining reviewer prose, transcripts, findings or prompt copy.
create or replace function
  content_factory_private.valid_generation_quality_guard_codes(
    p_guard_codes jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  guard_code text;
  seen_codes text[] := array[]::text[];
begin
  if jsonb_typeof(p_guard_codes) <> 'array'
     or jsonb_array_length(p_guard_codes) > 3 then
    return false;
  end if;
  for guard_code in
    select item.value
    from jsonb_array_elements_text(p_guard_codes) item(value)
  loop
    if guard_code not in (
         'product_fidelity',
         'technical_stability',
         'audio_quality',
         'speech_fidelity',
         'hook_clarity',
         'visual_quality',
         'trust',
         'platform_fit'
       )
       or guard_code = any(seen_codes) then
      return false;
    end if;
    seen_codes := array_append(seen_codes, guard_code);
  end loop;
  return true;
exception when others then
  return false;
end;
$$;

revoke all on function
  content_factory_private.valid_generation_quality_guard_codes(jsonb)
  from public, anon, authenticated, service_role;

create table if not exists
  content_factory.generation_quality_guard_lineage (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_job_id uuid not null,
    product_id uuid not null,
    platform text not null check (
      platform in (
        'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
      )
    ),
    model text not null check (
      model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')
    ),
    source text not null check (
      source in (
        'baseline', 'approved_research', 'performance_learning'
      )
    ),
    applied_policy_hash text check (
      applied_policy_hash is null
      or applied_policy_hash ~ '^[0-9a-f]{64}$'
    ),
    guard_codes jsonb not null default '[]'::jsonb check (
      content_factory_private
        .valid_generation_quality_guard_codes(guard_codes)
    ),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (
        source = 'performance_learning'
        and applied_policy_hash is not null
      )
      or (
        source in ('baseline', 'approved_research')
        and applied_policy_hash is null
        and guard_codes = '[]'::jsonb
      )
    ),
    unique (organization_id, generation_job_id)
);

create index if not exists generation_quality_guard_lineage_learning_idx
  on content_factory.generation_quality_guard_lineage
  (organization_id, product_id, platform, model, created_at desc);

create index if not exists generation_quality_guard_lineage_codes_idx
  on content_factory.generation_quality_guard_lineage
  using gin (guard_codes);

alter table content_factory.generation_quality_guard_lineage
  enable row level security;
revoke all on content_factory.generation_quality_guard_lineage
  from public, anon, authenticated;
grant all on content_factory.generation_quality_guard_lineage
  to service_role;

create or replace function
  content_factory_private.guard_generation_quality_guard_lineage_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_quality_guard_lineage_append_only';
end;
$$;

drop trigger if exists generation_quality_guard_lineage_append_only
  on content_factory.generation_quality_guard_lineage;
create trigger generation_quality_guard_lineage_append_only
before update or delete
  on content_factory.generation_quality_guard_lineage
for each row execute function
  content_factory_private
    .guard_generation_quality_guard_lineage_append_only();

revoke all on function
  content_factory_private
    .guard_generation_quality_guard_lineage_append_only()
  from public, anon, authenticated, service_role;

-- Wrap the complete audited generation chain.  The current server learning
-- policy is recomputed before the paid database command.  Only after that
-- command has produced or recovered an exact idempotent job do we append the
-- server policy hash, enumerated guards and prompt hash.  Any mismatch aborts
-- the transaction before the Edge worker can contact the provider.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_guard_lineage_v8;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_guard_lineage_v8(jsonb)
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
  learning_context jsonb;
  learning_source_value text;
  server_policy jsonb;
  policy_hash_value text;
  guard_codes_value jsonb := '[]'::jsonb;
  result_value jsonb;
  job_id_value uuid;
  prompt_hash_value text;
  job_row content_factory.generation_jobs%rowtype;
  creative_signal content_factory.generation_creative_signals%rowtype;
  existing_lineage
    content_factory.generation_quality_guard_lineage%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  learning_context := p_payload -> 'learning_context';
  -- Keep backward-compatible database fixtures and old idempotent callers on
  -- the complete existing command.  The production Edge contract requires a
  -- learning context; malformed values are still rejected by that inner
  -- command with its original error ordering.
  if learning_context is null
     or jsonb_typeof(learning_context) <> 'object' then
    return content_factory_private
      .creator_start_real_generation_pre_guard_lineage_v8(p_payload);
  end if;
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  user_id := content_factory_private.current_profile_id();

  learning_source_value := learning_context ->> 'source';
  if learning_source_value = 'performance_learning' then
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'operator']
    );
    server_policy := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id,
        'media_id', p_payload #>> '{media_ids,0}',
        'platform', p_payload ->> 'platform',
        'model', p_payload ->> 'model'
      )
    );
    policy_hash_value := server_policy ->> 'policy_hash';
    guard_codes_value := coalesce(
      server_policy -> 'quality_guard_codes',
      '[]'::jsonb
    );
    if server_policy -> 'applied' is distinct from 'true'::jsonb
       or policy_hash_value
            is distinct from learning_context ->> 'applied_policy_hash'
       or policy_hash_value !~ '^[0-9a-f]{64}$'
       or not content_factory_private
         .valid_generation_quality_guard_codes(guard_codes_value) then
      raise exception using
        errcode = '55000',
        message = 'generation_quality_guard_policy_stale';
    end if;
  elsif learning_source_value in ('baseline', 'approved_research') then
    policy_hash_value := null;
    guard_codes_value := '[]'::jsonb;
  end if;

  result_value := content_factory_private
    .creator_start_real_generation_pre_guard_lineage_v8(p_payload);

  if coalesce(result_value #>> '{job,id}', '') !~
     '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    raise exception using
      errcode = '55000',
      message = 'generation_quality_guard_lineage_binding_invalid';
  end if;
  job_id_value := (result_value #>> '{job,id}')::uuid;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
  for share;
  prompt_hash_value := content_factory_private.json_hash(
    to_jsonb(job_row.input ->> 'prompt_text')
  );
  select signal.* into creative_signal
  from content_factory.generation_creative_signals signal
  where signal.organization_id = organization_id
    and signal.generation_job_id = job_id_value;

  if learning_source_value not in (
       'baseline', 'approved_research', 'performance_learning'
     )
     or job_row.id is null
     or job_row.requested_by is distinct from user_id
     or job_row.product_id is null
     or job_row.input ->> 'platform'
          is distinct from p_payload ->> 'platform'
     or job_row.input ->> 'model'
          is distinct from p_payload ->> 'model'
     or job_row.input ->> 'prompt_text'
          is distinct from p_payload ->> 'brief'
     or creative_signal.id is null
     or creative_signal.product_id is distinct from job_row.product_id
     or creative_signal.platform
          is distinct from job_row.input ->> 'platform'
     or creative_signal.model is distinct from job_row.input ->> 'model'
     or creative_signal.source is distinct from learning_source_value
     or creative_signal.applied_policy_hash
          is distinct from policy_hash_value
     or creative_signal.prompt_hash is distinct from prompt_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generation_quality_guard_lineage_binding_invalid';
  end if;

  insert into content_factory.generation_quality_guard_lineage (
    organization_id,
    generation_job_id,
    product_id,
    platform,
    model,
    source,
    applied_policy_hash,
    guard_codes,
    prompt_hash,
    created_by
  ) values (
    organization_id,
    job_row.id,
    job_row.product_id,
    job_row.input ->> 'platform',
    job_row.input ->> 'model',
    learning_source_value,
    policy_hash_value,
    guard_codes_value,
    prompt_hash_value,
    user_id
  )
  on conflict (organization_id, generation_job_id) do nothing;

  select lineage.* into existing_lineage
  from content_factory.generation_quality_guard_lineage lineage
  where lineage.organization_id = organization_id
    and lineage.generation_job_id = job_id_value;
  if existing_lineage.id is null
     or existing_lineage.product_id is distinct from job_row.product_id
     or existing_lineage.platform
          is distinct from job_row.input ->> 'platform'
     or existing_lineage.model
          is distinct from job_row.input ->> 'model'
     or existing_lineage.source is distinct from learning_source_value
     or existing_lineage.applied_policy_hash
          is distinct from policy_hash_value
     or existing_lineage.guard_codes is distinct from guard_codes_value
     or existing_lineage.prompt_hash is distinct from prompt_hash_value
     or existing_lineage.created_by is distinct from user_id then
    raise exception using
      errcode = '23505',
      message = 'generation_quality_guard_lineage_conflict';
  end if;

  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
