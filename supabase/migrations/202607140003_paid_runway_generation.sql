begin;

-- Paid generation is intentionally narrow: the existing zero-cost mock path is
-- preserved verbatim, while real rows are limited to one audited Runway SKU.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_mode_check,
  drop constraint if exists generation_batches_allow_real_spend_check,
  drop constraint if exists generation_batches_status_check;

alter table content_factory.generation_batches
  add constraint generation_batches_mode_check
    check (mode in ('mock', 'real')),
  add constraint generation_batches_status_check
    check (status in (
      'mock_ready', 'queued', 'starting', 'submitted', 'processing',
      'succeeded', 'failed', 'cancelled'
    )),
  add constraint generation_batches_spend_contract_check
    check (
      (
        mode = 'mock'
        and not allow_real_spend
        and status in ('mock_ready', 'cancelled')
      )
      or (
        mode = 'real'
        and allow_real_spend
        and status in (
          'queued', 'starting', 'submitted', 'processing',
          'succeeded', 'failed', 'cancelled'
        )
      )
    );

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_mode_check,
  drop constraint if exists generation_jobs_provider_check,
  drop constraint if exists generation_jobs_allow_real_spend_check,
  drop constraint if exists generation_jobs_estimated_cost_minor_check,
  drop constraint if exists generation_jobs_actual_cost_minor_check,
  drop constraint if exists generation_jobs_status_check;

alter table content_factory.generation_jobs
  add constraint generation_jobs_mode_check
    check (mode in ('mock', 'real')),
  add constraint generation_jobs_provider_check
    check (provider in ('mock', 'runway')),
  add constraint generation_jobs_estimated_cost_nonnegative_check
    check (estimated_cost_minor >= 0),
  add constraint generation_jobs_actual_cost_nonnegative_check
    check (actual_cost_minor >= 0),
  add constraint generation_jobs_status_check
    check (status in (
      'mock_ready', 'queued', 'starting', 'submitted', 'processing',
      'succeeded', 'failed', 'cancelled'
    )),
  add constraint generation_jobs_spend_contract_check
    check (
      (
        mode = 'mock'
        and provider = 'mock'
        and not allow_real_spend
        and estimated_cost_minor = 0
        and actual_cost_minor = 0
        and status in ('mock_ready', 'cancelled')
      )
      or (
        mode = 'real'
        and provider = 'runway'
        and allow_real_spend
        and estimated_cost_minor = 25
        and status in (
          'queued', 'starting', 'submitted', 'processing',
          'succeeded', 'failed', 'cancelled'
        )
      )
    );

create index if not exists generation_jobs_real_quota_idx
  on content_factory.generation_jobs
  (organization_id, requested_by, created_at desc)
  where mode = 'real' and provider = 'runway';

create unique index if not exists generation_jobs_runway_provider_task_uq
  on content_factory.generation_jobs
  (provider, (output ->> 'provider_task_id'))
  where mode = 'real'
    and provider = 'runway'
    and nullif(btrim(output ->> 'provider_task_id'), '') is not null;

create or replace function content_factory_private.guard_generation_batch_contract()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.mode = 'mock' then
    if new.allow_real_spend or new.status not in ('mock_ready', 'cancelled') then
      raise exception using
        errcode = '42501',
        message = 'mock_generation_contract_invalid';
    end if;
    return new;
  end if;

  if new.mode <> 'real'
     or not new.allow_real_spend
     or new.status not in (
       'queued', 'starting', 'submitted', 'processing',
       'succeeded', 'failed', 'cancelled'
     )
     or new.total_requested <> 1
     or new.total_created <> case when new.status = 'succeeded' then 1 else 0 end
     or new.input ->> 'provider' is distinct from 'runway'
     or new.input ->> 'model' is distinct from 'gen4_turbo'
     or new.input -> 'duration_seconds' is distinct from '5'::jsonb
     or new.input ->> 'spend_confirmation'
          is distinct from 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
     or new.input #>> '{billing,currency}' is distinct from 'USD'
     or new.input #> '{billing,estimated_cost_minor}' is distinct from '25'::jsonb
     or new.input #> '{billing,estimated_credits}' is distinct from '25'::jsonb
     or coalesce(new.input ->> 'job_id', '') !~
          '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
    raise exception using
      errcode = '42501',
      message = 'real_generation_batch_contract_invalid';
  end if;

  return new;
end;
$$;

create or replace function content_factory_private.guard_generation_job_contract()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  provider_task_id_value text := nullif(btrim(new.output ->> 'provider_task_id'), '');
begin
  if new.mode = 'mock' then
    if new.provider <> 'mock'
       or new.allow_real_spend
       or new.estimated_cost_minor <> 0
       or new.actual_cost_minor <> 0
       or new.status not in ('mock_ready', 'cancelled') then
      raise exception using
        errcode = '42501',
        message = 'mock_generation_contract_invalid';
    end if;
    return new;
  end if;

  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or new.estimated_cost_minor <> 25
     or new.actual_cost_minor < 0
     or new.status not in (
       'queued', 'starting', 'submitted', 'processing',
       'succeeded', 'failed', 'cancelled'
     )
     or new.input ->> 'provider' is distinct from 'runway'
     or new.input ->> 'model' is distinct from 'gen4_turbo'
     or new.input -> 'duration_seconds' is distinct from '5'::jsonb
     or new.input ->> 'spend_confirmation'
          is distinct from 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
     or new.input #>> '{billing,currency}' is distinct from 'USD'
     or new.input #> '{billing,estimated_cost_minor}' is distinct from '25'::jsonb
     or new.input #> '{billing,estimated_credits}' is distinct from '25'::jsonb
     or coalesce(new.input ->> 'ratio', '') not in (
       '720:1280', '1280:720', '960:960'
     )
     or length(coalesce(new.input ->> 'input_object_name', '')) < 10
     or length(coalesce(new.input ->> 'output_object_name', '')) < 10 then
    raise exception using
      errcode = '42501',
      message = 'real_generation_job_contract_invalid';
  end if;

  if new.status in ('queued', 'starting') and (
    provider_task_id_value is not null or new.actual_cost_minor <> 0
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_unsubmitted_contract_invalid';
  end if;

  if new.status in ('submitted', 'processing', 'succeeded') and (
    provider_task_id_value is null or new.actual_cost_minor <> 25
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_submitted_contract_invalid';
  end if;

  if new.status = 'succeeded' and (
    new.output ->> 'output_object_name'
      is distinct from new.input ->> 'output_object_name'
    or coalesce(new.output ->> 'output_media_id', '') !~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    or new.output ->> 'failure_code' is not null
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_success_contract_invalid';
  end if;

  if new.status = 'failed' and (
    nullif(btrim(new.output ->> 'failure_code'), '') is null
    or new.output ->> 'output_media_id' is not null
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_failure_contract_invalid';
  end if;

  return new;
end;
$$;

drop trigger if exists generation_batches_mock_only_guard
  on content_factory.generation_batches;
drop trigger if exists generation_batches_contract_guard
  on content_factory.generation_batches;
create trigger generation_batches_contract_guard
before insert or update on content_factory.generation_batches
for each row execute function content_factory_private.guard_generation_batch_contract();

drop trigger if exists generation_jobs_mock_only_guard
  on content_factory.generation_jobs;
drop trigger if exists generation_jobs_contract_guard
  on content_factory.generation_jobs;
create trigger generation_jobs_contract_guard
before insert or update on content_factory.generation_jobs
for each row execute function content_factory_private.guard_generation_job_contract();

-- Generic task actions must not detach the human-review workflow from a paid
-- provider job. The system updater changes the job state first in the same
-- transaction, so only its terminal task transition passes this invariant.
create or replace function content_factory_private.guard_real_generation_review_task()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  generation_mode text;
  generation_provider text;
  generation_status text;
begin
  if new.generation_job_id is null or new.task_type <> 'video_review' then
    return new;
  end if;

  select job.mode, job.provider, job.status
  into generation_mode, generation_provider, generation_status
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = new.generation_job_id;

  if generation_mode <> 'real' or generation_provider <> 'runway' then
    return new;
  end if;

  if generation_status in ('queued', 'starting', 'submitted', 'processing')
     and new.status <> 'blocked' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_locked';
  end if;

  if generation_status in ('failed', 'cancelled') and new.status <> 'cancelled' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_terminal_state_invalid';
  end if;

  return new;
end;
$$;

drop trigger if exists real_generation_review_task_guard
  on content_factory.creator_tasks;
create trigger real_generation_review_task_guard
before insert or update of status, generation_job_id, task_type
on content_factory.creator_tasks
for each row execute function content_factory_private.guard_real_generation_review_task();

revoke all on function content_factory_private.guard_generation_batch_contract()
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_generation_job_contract()
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_real_generation_review_task()
  from public, anon, authenticated;

-- Preserve the large bootstrap implementation as a private implementation and
-- expose a narrow wrapper that updates only the capability introduced here.
-- The capability means the authenticated member passes the database gates;
-- deployment configuration still controls whether the Edge provider is ready.
alter function public.creator_bootstrap(jsonb)
  set schema content_factory_private;
revoke all on function content_factory_private.creator_bootstrap(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
  real_generation_allowed boolean;
begin
  result := content_factory_private.creator_bootstrap(p_payload);
  real_generation_allowed :=
    coalesce((result ->> 'workspace_open')::boolean, false)
    and result #>> '{membership,role}' in ('owner', 'admin', 'producer', 'operator');

  return jsonb_set(
    result,
    '{capabilities,real_generation}',
    to_jsonb(real_generation_allowed),
    false
  );
end;
$$;

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
  actor_role text;
  assignee_id_value uuid;
  idempotency_key text;
  sku_value text;
  product_name_value text;
  brief_value text;
  prompt_value text;
  format_value text;
  ratio_value text;
  platform_value text;
  destination_value text;
  payout_value bigint := 0;
  media_ids jsonb;
  media_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  product_id_value uuid;
  batch_id_value uuid := extensions.gen_random_uuid();
  job_id_value uuid := extensions.gen_random_uuid();
  task_id_value uuid := extensions.gen_random_uuid();
  output_object_name_value text;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
  team_scope boolean;
  user_daily_jobs bigint;
  organization_daily_jobs bigint;
  assignee_open_jobs bigint;
  organization_open_jobs bigint;
begin
  p_payload := content_factory_private.require_payload(p_payload);

  if p_payload - array[
    'organization_id', 'idempotency_key', 'sku', 'product_name', 'count',
    'format', 'brief', 'media_ids', 'platform', 'destination_ref',
    'assignee_id', 'payout_minor', 'mode', 'provider', 'model',
    'duration_seconds', 'allow_real_spend', 'spend_confirmation'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'real_generation_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  team_scope := actor_role in ('owner', 'admin', 'producer');
  assignee_id_value := user_id;
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
  product_name_value := content_factory_private.require_text(
    p_payload,
    'product_name',
    2,
    180
  );
  brief_value := btrim(coalesce(p_payload ->> 'brief', ''));
  format_value := content_factory_private.require_text(p_payload, 'format', 3, 4);
  platform_value := content_factory_private.require_text(p_payload, 'platform', 2, 40);
  destination_value := content_factory_private.require_text(
    p_payload,
    'destination_ref',
    2,
    240
  );
  media_ids := coalesce(p_payload -> 'media_ids', '[]'::jsonb);

  if nullif(btrim(coalesce(p_payload ->> 'assignee_id', '')), '') is not null then
    assignee_id_value := content_factory_private.require_uuid(p_payload, 'assignee_id');
  end if;

  if length(brief_value) > 1200 then
    raise exception using errcode = '22023', message = 'brief_invalid';
  end if;
  prompt_value := coalesce(
    nullif(brief_value, ''),
    'Polished product video featuring ' || product_name_value
  );
  prompt_value := left(prompt_value, 1200);

  if format_value not in ('9:16', '16:9', '1:1') then
    raise exception using errcode = '22023', message = 'format_invalid';
  end if;
  ratio_value := case format_value
    when '9:16' then '720:1280'
    when '16:9' then '1280:720'
    else '960:960'
  end;

  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) then
    raise exception using errcode = '22023', message = 'platform_invalid';
  end if;

  if p_payload -> 'count' is distinct from '1'::jsonb then
    raise exception using errcode = '22023', message = 'real_generation_count_must_be_one';
  end if;
  if p_payload ->> 'mode' is distinct from 'real'
     or p_payload ->> 'provider' is distinct from 'runway'
     or p_payload ->> 'model' is distinct from 'gen4_turbo'
     or p_payload -> 'duration_seconds' is distinct from '5'::jsonb
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or p_payload ->> 'spend_confirmation'
          is distinct from 'RUNWAY_GEN4_TURBO_5S_USD_0.25' then
    raise exception using errcode = '42501', message = 'real_generation_spend_confirmation_required';
  end if;

  if jsonb_typeof(media_ids) <> 'array' or jsonb_array_length(media_ids) <> 1 then
    raise exception using errcode = '22023', message = 'exact_one_product_media_required';
  end if;
  begin
    media_id_value := (media_ids ->> 0)::uuid;
  exception when invalid_text_representation then
    raise exception using errcode = '22023', message = 'media_id_invalid';
  end;

  if coalesce(p_payload ->> 'payout_minor', '0') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end if;
  begin
    payout_value := coalesce(p_payload ->> 'payout_minor', '0')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end;
  if payout_value < 0 or payout_value > 1000000 then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end if;
  if actor_role not in ('owner', 'admin') and payout_value <> 0 then
    raise exception using errcode = '42501', message = 'payout_role_not_allowed';
  end if;
  if actor_role = 'operator' and assignee_id_value <> user_id then
    raise exception using errcode = '42501', message = 'assignee_role_not_allowed';
  end if;

  if not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id
      and membership.profile_id = assignee_id_value
      and membership.status = 'active'
      and membership.role in ('owner', 'admin', 'producer', 'reviewer', 'operator')
      and exists (
        select 1
        from content_factory.training_certifications certification
        where certification.organization_id = membership.organization_id
          and certification.profile_id = membership.profile_id
          and certification.module_code = 'operator_final_exam'
          and certification.status = 'passed'
          and (
            certification.expires_at is null
            or certification.expires_at > now()
          )
      )
  ) then
    raise exception using errcode = '42501', message = 'certified_assignee_required';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_start_real_generation',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('real_generation_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('real_generation_quota:user')
  );

  select
    count(*) filter (where job.requested_by = user_id),
    count(*)
  into user_daily_jobs, organization_daily_jobs
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.mode = 'real'
    and job.provider = 'runway'
    and job.created_at >= now() - interval '24 hours';

  select
    count(*) filter (where job.assigned_to = assignee_id_value),
    count(*)
  into assignee_open_jobs, organization_open_jobs
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.mode = 'real'
    and job.provider = 'runway'
    and job.status in ('queued', 'starting', 'submitted', 'processing');

  if user_daily_jobs >= 10 then
    raise exception using errcode = '54000', message = 'real_generation_user_daily_quota_exceeded';
  end if;
  if organization_daily_jobs >= 50 then
    raise exception using errcode = '54000', message = 'real_generation_organization_daily_quota_exceeded';
  end if;
  if assignee_open_jobs >= 1 then
    raise exception using errcode = '54000', message = 'real_generation_assignee_concurrency_exceeded';
  end if;
  if organization_open_jobs >= 3 then
    raise exception using errcode = '54000', message = 'real_generation_organization_concurrency_exceeded';
  end if;

  insert into content_factory.products (
    organization_id, sku, title, status, created_by
  ) values (
    organization_id, sku_value, product_name_value, 'active', user_id
  )
  on conflict on constraint products_org_sku_uq do update set
    title = excluded.title,
    status = 'active',
    updated_at = now()
  returning id into product_id_value;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value
  for share;

  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.product_id is distinct from product_id_value
     or coalesce(media_row.metadata ->> 'kind', '') not in (
       'product_photo', 'packshot'
     )
     or (not team_scope and media_row.owner_id <> user_id) then
    raise exception using errcode = '42501', message = 'exact_product_media_mismatch';
  end if;

  output_object_name_value := organization_id::text || '/' ||
    assignee_id_value::text || '/generated/' || job_id_value::text || '.mp4';

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key
  ) values (
    batch_id_value,
    organization_id,
    product_id_value,
    user_id,
    left('Runway ' || sku_value || ' - 1 video', 180),
    'real',
    true,
    'queued',
    1,
    0,
    jsonb_build_object(
      'job_id', job_id_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'format', format_value,
      'ratio', ratio_value,
      'media_id', media_id_value,
      'assigned_to', assignee_id_value,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25,
        'credit_unit_usd_minor', 1
      )
    ),
    content_factory_private.json_hash(request_payload),
    idempotency_key
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key
  ) values (
    job_id_value,
    organization_id,
    product_id_value,
    batch_id_value,
    1,
    user_id,
    assignee_id_value,
    'real',
    'runway',
    true,
    25,
    0,
    'queued',
    jsonb_build_object(
      'sku', sku_value,
      'product_name', product_name_value,
      'prompt_text', prompt_value,
      'format', format_value,
      'ratio', ratio_value,
      'input_media_id', media_id_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', platform_value,
      'destination_ref', destination_value,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25,
        'credit_unit_usd_minor', 1
      )
    ),
    '{}'::jsonb,
    content_factory_private.json_hash(request_payload),
    'real-job:' || content_factory_private.json_hash(jsonb_build_object(
      'organization_id', organization_id,
      'idempotency_key', idempotency_key
    ))
  );

  insert into content_factory.creator_tasks (
    id, organization_id, assignee_id, created_by, product_id,
    generation_job_id, task_type, title, instructions,
    status, priority, payout_minor, result, idempotency_key
  ) values (
    task_id_value,
    organization_id,
    assignee_id_value,
    user_id,
    product_id_value,
    job_id_value,
    'video_review',
    left('Review Runway video - ' || product_name_value, 240),
    'Generation is in progress. Review the exact MP4 only after this task moves to review.',
    'blocked',
    2,
    payout_value,
    jsonb_build_object(
      'generation_status', 'queued',
      'review_required', true,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'estimated_cost_minor', 25,
      'currency', 'USD'
    ),
    'real-review:' || content_factory_private.json_hash(jsonb_build_object(
      'organization_id', organization_id,
      'job_id', job_id_value
    ))
  );

  result := jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'id', batch_id_value,
      'status', 'queued'
    ),
    'job', jsonb_build_object(
      'id', job_id_value,
      'batch_id', batch_id_value,
      'status', 'queued',
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'ratio', ratio_value,
      'prompt_text', prompt_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', 25
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'real_generation_queued',
    'generation_job',
    job_id_value::text,
    jsonb_build_object(
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'estimated_cost_minor', 25,
      'currency', 'USD'
    ),
    'real-generation:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_start_real_generation',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_real_generation_status(
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
  actor_role text;
  job_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
  manager_scope boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'job_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'real_generation_status_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role in ('owner', 'admin', 'producer');
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
    and job.mode = 'real'
    and job.provider = 'runway'
    and (
      manager_scope
      or job.requested_by = user_id
      or job.assigned_to = user_id
    );

  if job_row.id is null then
    raise exception using errcode = 'P0002', message = 'real_generation_not_found';
  end if;

  return jsonb_build_object(
    'ok', true,
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider', job_row.provider,
      'provider_task_id', job_row.output ->> 'provider_task_id',
      'model', job_row.input ->> 'model',
      'duration_seconds', (job_row.input ->> 'duration_seconds')::integer,
      'ratio', job_row.input ->> 'ratio',
      'estimated_cost_minor', job_row.estimated_cost_minor,
      'actual_cost_minor', job_row.actual_cost_minor,
      'output_object_name', job_row.input ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'updated_at', job_row.updated_at
    )
  );
end;
$$;

create or replace function public.system_update_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  job_id_value uuid;
  status_value text;
  provider_task_id_value text;
  stored_provider_task_id text;
  failure_code_value text;
  output_object_name_value text;
  mime_type_value text;
  sha256_value text;
  size_bytes_value bigint;
  storage_metadata jsonb;
  storage_user_metadata jsonb;
  storage_size bigint;
  storage_mime_type text;
  storage_sha256 text;
  linked_task_count integer;
  linked_task_id uuid;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  media_row content_factory.media_objects%rowtype;
  claimed boolean := false;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'job_id', 'status', 'provider_task_id', 'failure_code',
    'output_object_name', 'mime_type', 'size_bytes', 'sha256'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'real_generation_update_payload_invalid';
  end if;

  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  status_value := content_factory_private.require_text(p_payload, 'status', 6, 20);
  if status_value not in ('starting', 'submitted', 'processing', 'succeeded', 'failed') then
    raise exception using errcode = '22023', message = 'real_generation_update_status_invalid';
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
  for update;

  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend then
    raise exception using errcode = 'P0002', message = 'real_generation_not_found';
  end if;

  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = job_row.organization_id
    and batch.id = job_row.batch_id
  for update;

  if batch_row.id is null
     or batch_row.mode <> 'real'
     or not batch_row.allow_real_spend
     or batch_row.input ->> 'job_id' is distinct from job_row.id::text
     or batch_row.status is distinct from job_row.status then
    raise exception using errcode = '55000', message = 'real_generation_batch_state_invalid';
  end if;

  select count(*)::integer, (array_agg(task.id order by task.id))[1]
  into linked_task_count, linked_task_id
  from content_factory.creator_tasks task
  where task.organization_id = job_row.organization_id
    and task.generation_job_id = job_row.id
    and task.task_type = 'video_review';

  if linked_task_count <> 1 or linked_task_id is null then
    raise exception using errcode = '55000', message = 'real_generation_review_task_invalid';
  end if;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = job_row.organization_id
    and task.id = linked_task_id
  for update;

  if task_row.product_id is distinct from job_row.product_id
     or task_row.assignee_id is distinct from job_row.assigned_to
     or task_row.created_by is distinct from job_row.requested_by
     or task_row.id::text is distinct from job_row.input ->> 'review_task_id' then
    raise exception using errcode = '55000', message = 'real_generation_review_task_invalid';
  end if;

  if status_value = 'starting' then
    if p_payload - array['job_id', 'status']::text[] <> '{}'::jsonb then
      raise exception using errcode = '22023', message = 'real_generation_starting_payload_invalid';
    end if;

    if job_row.status = 'queued' then
      if task_row.status <> 'blocked' then
        raise exception using errcode = '55000', message = 'real_generation_review_task_invalid';
      end if;
      update content_factory.generation_jobs job
      set status = 'starting',
          output = job.output || jsonb_build_object('starting_at', now())
      where job.id = job_row.id
      returning * into job_row;

      update content_factory.generation_batches batch
      set status = 'starting'
      where batch.id = batch_row.id;

      update content_factory.creator_tasks task
      set result = task.result || jsonb_build_object('generation_status', 'starting')
      where task.id = task_row.id;

      claimed := true;
      perform content_factory_private.emit_event(
        job_row.organization_id,
        job_row.requested_by,
        'real_generation_starting',
        'generation_job',
        job_row.id::text,
        jsonb_build_object('claimed', true),
        'real-generation:' || job_row.id::text || ':starting',
        'system'
      );
    elsif job_row.status in (
      'starting', 'submitted', 'processing', 'succeeded', 'failed', 'cancelled'
    ) then
      claimed := false;
    else
      raise exception using errcode = '55000', message = 'real_generation_state_transition_invalid';
    end if;

    return jsonb_build_object(
      'ok', true,
      'claimed', claimed,
      'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider', job_row.provider,
        'provider_task_id', job_row.output ->> 'provider_task_id',
        'output_object_name', job_row.input ->> 'output_object_name',
        'updated_at', job_row.updated_at
      )
    );
  end if;

  stored_provider_task_id := nullif(btrim(job_row.output ->> 'provider_task_id'), '');
  if nullif(btrim(coalesce(p_payload ->> 'provider_task_id', '')), '') is not null then
    provider_task_id_value := content_factory_private.require_text(
      p_payload,
      'provider_task_id',
      1,
      240
    );
    if provider_task_id_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$' then
      raise exception using errcode = '22023', message = 'provider_task_id_invalid';
    end if;
  end if;

  if status_value = 'submitted' then
    if p_payload - array['job_id', 'status', 'provider_task_id']::text[] <> '{}'::jsonb
       or provider_task_id_value is null then
      raise exception using errcode = '22023', message = 'real_generation_submitted_payload_invalid';
    end if;
    if job_row.status = 'submitted'
       and stored_provider_task_id = provider_task_id_value then
      return jsonb_build_object('ok', true, 'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider_task_id', stored_provider_task_id,
        'updated_at', job_row.updated_at
      ));
    end if;
    if job_row.status <> 'starting' or task_row.status <> 'blocked' then
      raise exception using errcode = '55000', message = 'real_generation_state_transition_invalid';
    end if;

    update content_factory.generation_jobs job
    set status = 'submitted',
        actual_cost_minor = 25,
        output = job.output || jsonb_build_object(
          'provider_task_id', provider_task_id_value,
          'submitted_at', now(),
          'actual_cost_minor', 25,
          'currency', 'USD'
        )
    where job.id = job_row.id
    returning * into job_row;

    update content_factory.generation_batches batch
    set status = 'submitted'
    where batch.id = batch_row.id;

    update content_factory.creator_tasks task
    set result = task.result || jsonb_build_object('generation_status', 'submitted')
    where task.id = task_row.id;

  elsif status_value = 'processing' then
    if p_payload - array['job_id', 'status', 'provider_task_id']::text[] <> '{}'::jsonb
       or provider_task_id_value is null then
      raise exception using errcode = '22023', message = 'real_generation_processing_payload_invalid';
    end if;
    if job_row.status = 'processing'
       and stored_provider_task_id = provider_task_id_value then
      return jsonb_build_object('ok', true, 'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider_task_id', stored_provider_task_id,
        'updated_at', job_row.updated_at
      ));
    end if;
    if job_row.status <> 'submitted'
       or stored_provider_task_id is distinct from provider_task_id_value
       or task_row.status <> 'blocked' then
      raise exception using errcode = '55000', message = 'real_generation_state_transition_invalid';
    end if;

    update content_factory.generation_jobs job
    set status = 'processing',
        output = job.output || jsonb_build_object('processing_at', now())
    where job.id = job_row.id
    returning * into job_row;

    update content_factory.generation_batches batch
    set status = 'processing'
    where batch.id = batch_row.id;

    update content_factory.creator_tasks task
    set result = task.result || jsonb_build_object('generation_status', 'processing')
    where task.id = task_row.id;

  elsif status_value = 'succeeded' then
    if p_payload - array[
      'job_id', 'status', 'provider_task_id', 'output_object_name',
      'mime_type', 'size_bytes', 'sha256'
    ]::text[] <> '{}'::jsonb or provider_task_id_value is null then
      raise exception using errcode = '22023', message = 'real_generation_success_payload_invalid';
    end if;

    output_object_name_value := content_factory_private.require_text(
      p_payload,
      'output_object_name',
      10,
      1000
    );
    mime_type_value := lower(content_factory_private.require_text(
      p_payload,
      'mime_type',
      3,
      160
    ));
    sha256_value := lower(content_factory_private.require_text(
      p_payload,
      'sha256',
      64,
      64
    ));
    if coalesce(p_payload ->> 'size_bytes', '') !~ '^[0-9]+$' then
      raise exception using errcode = '22023', message = 'real_generation_output_size_invalid';
    end if;
    begin
      size_bytes_value := (p_payload ->> 'size_bytes')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using errcode = '22023', message = 'real_generation_output_size_invalid';
    end;

    if job_row.status = 'succeeded' then
      if stored_provider_task_id is distinct from provider_task_id_value
         or job_row.output ->> 'output_object_name' is distinct from output_object_name_value
         or job_row.output ->> 'sha256' is distinct from sha256_value
         or job_row.output ->> 'mime_type' is distinct from mime_type_value
         or job_row.output ->> 'size_bytes' is distinct from size_bytes_value::text then
        raise exception using errcode = '23505', message = 'real_generation_success_replay_conflict';
      end if;
      return jsonb_build_object('ok', true, 'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider_task_id', stored_provider_task_id,
        'output_object_name', job_row.output ->> 'output_object_name',
        'output_media_id', job_row.output ->> 'output_media_id',
        'updated_at', job_row.updated_at
      ));
    end if;

    if job_row.status <> 'processing'
       or stored_provider_task_id is distinct from provider_task_id_value
       or task_row.status <> 'blocked' then
      raise exception using errcode = '55000', message = 'real_generation_state_transition_invalid';
    end if;
    if output_object_name_value is distinct from job_row.input ->> 'output_object_name'
       or split_part(output_object_name_value, '/', 1) <> job_row.organization_id::text
       or split_part(output_object_name_value, '/', 2) <> job_row.assigned_to::text
       or split_part(output_object_name_value, '/', 3) <> 'generated'
       or output_object_name_value !~ ('/' || job_row.id::text || '[.]mp4$')
       or output_object_name_value ~ '(^|/)\.\.(/|$)'
       or mime_type_value <> 'video/mp4'
       or size_bytes_value < 1
       or size_bytes_value > 52428800
       or sha256_value !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023', message = 'real_generation_output_metadata_invalid';
    end if;

    perform pg_advisory_xact_lock(
      hashtext('contentengine-private'),
      hashtext(output_object_name_value)
    );

    select storage_object.metadata, storage_object.user_metadata
    into storage_metadata, storage_user_metadata
    from storage.objects storage_object
    where storage_object.bucket_id = 'contentengine-private'
      and storage_object.name = output_object_name_value
    for update;

    if storage_metadata is null
       or jsonb_typeof(storage_metadata) <> 'object'
       or coalesce(storage_metadata ->> 'size', '') !~ '^[0-9]+$'
       or nullif(btrim(coalesce(storage_metadata ->> 'mimetype', '')), '') is null then
      raise exception using errcode = 'P0002', message = 'real_generation_storage_object_invalid';
    end if;

    begin
      storage_size := (storage_metadata ->> 'size')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using errcode = '22023', message = 'real_generation_storage_metadata_invalid';
    end;
    storage_mime_type := lower(btrim(storage_metadata ->> 'mimetype'));
    storage_sha256 := lower(btrim(coalesce(
      storage_user_metadata ->> 'sha256',
      storage_metadata ->> 'sha256',
      ''
    )));

    if storage_size <> size_bytes_value
       or storage_mime_type <> 'video/mp4'
       or storage_mime_type <> mime_type_value
       or storage_sha256 <> sha256_value
       or storage_sha256 !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023', message = 'real_generation_storage_metadata_mismatch';
    end if;

    select media.* into media_row
    from content_factory.media_objects media
    where media.bucket_id = 'contentengine-private'
      and media.object_name = output_object_name_value
    for update;

    if media_row.id is not null and (
      media_row.organization_id <> job_row.organization_id
      or media_row.owner_id <> job_row.assigned_to
      or media_row.task_id is distinct from task_row.id
      or media_row.product_id is distinct from job_row.product_id
      or media_row.mime_type <> 'video/mp4'
      or media_row.size_bytes <> size_bytes_value
      or media_row.sha256 <> sha256_value
      or media_row.status <> 'ready'
      or media_row.metadata ->> 'kind' is distinct from 'generated_video'
      or media_row.metadata ->> 'provider' is distinct from 'runway'
      or media_row.metadata ->> 'generation_job_id' is distinct from job_row.id::text
    ) then
      raise exception using errcode = '23505', message = 'real_generation_media_conflict';
    end if;

    if media_row.id is null then
      insert into content_factory.media_objects (
        organization_id, owner_id, task_id, product_id,
        bucket_id, object_name, mime_type, size_bytes, sha256,
        status, metadata, idempotency_key
      ) values (
        job_row.organization_id,
        job_row.assigned_to,
        task_row.id,
        job_row.product_id,
        'contentengine-private',
        output_object_name_value,
        'video/mp4',
        size_bytes_value,
        sha256_value,
        'ready',
        jsonb_build_object(
          'original_filename', job_row.id::text || '.mp4',
          'kind', 'generated_video',
          'provider', 'runway',
          'model', 'gen4_turbo',
          'duration_seconds', 5,
          'ratio', job_row.input ->> 'ratio',
          'generation_job_id', job_row.id,
          'review_required', true
        ),
        'runway-output:' || job_row.id::text
      )
      returning * into media_row;
    end if;

    update content_factory.generation_jobs job
    set status = 'succeeded',
        actual_cost_minor = 25,
        output = (job.output - 'failure_code') || jsonb_build_object(
          'output_object_name', output_object_name_value,
          'output_media_id', media_row.id,
          'mime_type', 'video/mp4',
          'size_bytes', size_bytes_value,
          'sha256', sha256_value,
          'succeeded_at', now(),
          'actual_cost_minor', 25,
          'currency', 'USD'
        )
    where job.id = job_row.id
    returning * into job_row;

    update content_factory.generation_batches batch
    set status = 'succeeded',
        total_created = 1
    where batch.id = batch_row.id;

    update content_factory.creator_tasks task
    set status = 'review',
        submitted_at = coalesce(task.submitted_at, now()),
        result = jsonb_build_object(
          'generation_status', 'succeeded',
          'review_required', true,
          'output_media_id', media_row.id,
          'output_object_name', output_object_name_value,
          'provider', 'runway',
          'model', 'gen4_turbo',
          'duration_seconds', 5,
          'actual_cost_minor', 25,
          'currency', 'USD'
        )
    where task.id = task_row.id;

  elsif status_value = 'failed' then
    if p_payload - array[
      'job_id', 'status', 'provider_task_id', 'failure_code'
    ]::text[] <> '{}'::jsonb then
      raise exception using errcode = '22023', message = 'real_generation_failure_payload_invalid';
    end if;
    failure_code_value := content_factory_private.require_text(
      p_payload,
      'failure_code',
      3,
      80
    );
    if failure_code_value not in (
      'provider_configuration_error',
      'provider_authentication_failed',
      'provider_credits_unavailable',
      'provider_rate_limited',
      'provider_request_rejected',
      'provider_request_failed',
      'provider_task_failed',
      'provider_timeout',
      'provider_response_invalid',
      'output_download_failed',
      'output_validation_failed',
      'output_upload_failed',
      'internal_error'
    ) then
      raise exception using errcode = '22023', message = 'real_generation_failure_code_invalid';
    end if;

    if job_row.status = 'failed' then
      if job_row.output ->> 'failure_code' is distinct from failure_code_value
         or stored_provider_task_id is distinct from provider_task_id_value then
        raise exception using errcode = '23505', message = 'real_generation_failure_replay_conflict';
      end if;
      return jsonb_build_object('ok', true, 'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider_task_id', stored_provider_task_id,
        'failure_code', job_row.output ->> 'failure_code',
        'updated_at', job_row.updated_at
      ));
    end if;

    -- A normal Edge timeout never calls this transition: an ambiguous Runway
    -- POST remains `starting`, which holds the concurrency gate. The
    -- starting->failed path exists only for service-role reconciliation after
    -- an operator has independently confirmed that no provider task exists.
    if job_row.status not in ('queued', 'starting', 'submitted', 'processing')
       or task_row.status <> 'blocked' then
      raise exception using errcode = '55000', message = 'real_generation_state_transition_invalid';
    end if;
    if job_row.status in ('submitted', 'processing') and (
      provider_task_id_value is null
      or stored_provider_task_id is distinct from provider_task_id_value
    ) then
      raise exception using errcode = '55000', message = 'real_generation_provider_task_mismatch';
    end if;
    if job_row.status in ('queued', 'starting') and provider_task_id_value is not null then
      raise exception using errcode = '55000', message = 'real_generation_provider_task_mismatch';
    end if;

    update content_factory.generation_jobs job
    set status = 'failed',
        actual_cost_minor = case
          when stored_provider_task_id is null then 0 else 25
        end,
        output = (job.output - 'output_media_id' - 'output_object_name') ||
          jsonb_build_object(
            'failure_code', failure_code_value,
            'failed_at', now(),
            'actual_cost_minor', case
              when stored_provider_task_id is null then 0 else 25
            end,
            'currency', 'USD'
          )
    where job.id = job_row.id
    returning * into job_row;

    update content_factory.generation_batches batch
    set status = 'failed',
        total_created = 0
    where batch.id = batch_row.id;

    update content_factory.creator_tasks task
    set status = 'cancelled',
        completed_at = coalesce(task.completed_at, now()),
        result = jsonb_build_object(
          'generation_status', 'failed',
          'failure_code', failure_code_value,
          'review_required', false,
          'provider', 'runway'
        )
    where task.id = task_row.id;
  end if;

  perform content_factory_private.emit_event(
    job_row.organization_id,
    job_row.requested_by,
    'real_generation_' || status_value,
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'status', job_row.status,
      'actual_cost_minor', job_row.actual_cost_minor,
      'failure_code', job_row.output ->> 'failure_code'
    ),
    'real-generation:' || job_row.id::text || ':' || status_value,
    'system'
  );

  result := jsonb_build_object(
    'ok', true,
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider', job_row.provider,
      'provider_task_id', job_row.output ->> 'provider_task_id',
      'output_object_name', job_row.output ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'updated_at', job_row.updated_at
    )
  );
  return result;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon;
revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;
revoke all on function public.system_update_real_generation(jsonb)
  from public, anon, authenticated;

grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;
grant execute on function public.system_update_real_generation(jsonb)
  to service_role;

commit;
