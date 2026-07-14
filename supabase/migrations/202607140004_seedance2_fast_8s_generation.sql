begin;

-- Generation batches now carry queryable billing/model facts in addition to
-- their immutable JSON request snapshot. Mock rows stay zero-cost. Existing
-- Gen-4 rows are backfilled from the contract introduced in 202607140003.
alter table content_factory.generation_batches
  add column provider text,
  add column model text,
  add column duration_seconds integer,
  add column audio boolean,
  add column estimated_cost_minor bigint,
  add column estimated_credits bigint,
  add column currency text;

update content_factory.generation_batches batch
set provider = case when batch.mode = 'real' then 'runway' else 'mock' end,
    model = case
      when batch.mode = 'real' then coalesce(
        nullif(batch.input ->> 'model', ''),
        'gen4_turbo'
      )
      else 'mock'
    end,
    duration_seconds = case
      when batch.mode = 'real'
        and coalesce(batch.input ->> 'duration_seconds', '') ~ '^[0-9]+$'
        then (batch.input ->> 'duration_seconds')::integer
      when batch.mode = 'real' then 5
      else 0
    end,
    audio = case
      when batch.mode = 'real'
        and batch.input ->> 'audio' in ('true', 'false')
        then (batch.input ->> 'audio')::boolean
      else false
    end,
    estimated_cost_minor = case
      when batch.mode = 'real'
        and coalesce(
          batch.input #>> '{billing,estimated_cost_minor}', ''
        ) ~ '^[0-9]+$'
        then (batch.input #>> '{billing,estimated_cost_minor}')::bigint
      when batch.mode = 'real' then 25
      else 0
    end,
    estimated_credits = case
      when batch.mode = 'real'
        and coalesce(
          batch.input #>> '{billing,estimated_credits}', ''
        ) ~ '^[0-9]+$'
        then (batch.input #>> '{billing,estimated_credits}')::bigint
      when batch.mode = 'real' then 25
      else 0
    end,
    currency = coalesce(
      nullif(batch.input #>> '{billing,currency}', ''),
      'USD'
    );

alter table content_factory.generation_batches
  alter column provider set not null,
  alter column model set not null,
  alter column duration_seconds set not null,
  alter column audio set not null,
  alter column estimated_cost_minor set not null,
  alter column estimated_credits set not null,
  alter column currency set not null,
  add constraint generation_batches_provider_check
    check (provider in ('mock', 'runway')),
  add constraint generation_batches_model_check
    check (model in ('mock', 'gen4_turbo', 'seedance2_fast')),
  add constraint generation_batches_duration_check
    check (duration_seconds >= 0),
  add constraint generation_batches_estimated_cost_nonnegative_check
    check (estimated_cost_minor >= 0),
  add constraint generation_batches_estimated_credits_nonnegative_check
    check (estimated_credits >= 0),
  add constraint generation_batches_currency_check
    check (currency = 'USD'),
  add constraint generation_batches_sku_contract_check
    check (
      (
        mode = 'mock'
        and provider = 'mock'
        and model = 'mock'
        and duration_seconds = 0
        and not audio
        and estimated_cost_minor = 0
        and estimated_credits = 0
      )
      or (
        mode = 'real'
        and provider = 'runway'
        and (
          (
            model = 'gen4_turbo'
            and duration_seconds = 5
            and not audio
            and estimated_cost_minor = 25
            and estimated_credits = 25
          )
          or (
            model = 'seedance2_fast'
            and duration_seconds = 8
            and audio
            and estimated_cost_minor = 232
            and estimated_credits = 232
          )
        )
      )
    );

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_spend_contract_check;

alter table content_factory.generation_jobs
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
        and status in (
          'queued', 'starting', 'submitted', 'processing',
          'succeeded', 'failed', 'cancelled'
        )
        and (
          (
            input ->> 'model' = 'gen4_turbo'
            and input -> 'duration_seconds' = '5'::jsonb
            and coalesce(input -> 'audio', 'false'::jsonb) = 'false'::jsonb
            and estimated_cost_minor = 25
          )
          or (
            input ->> 'model' = 'seedance2_fast'
            and input -> 'duration_seconds' = '8'::jsonb
            and input -> 'audio' = 'true'::jsonb
            and estimated_cost_minor = 232
          )
        )
      )
    );

create or replace function content_factory_private.real_generation_sku_config(
  p_model text,
  p_duration jsonb,
  p_audio jsonb,
  p_format text,
  p_confirmation text
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select case
    when p_model = 'gen4_turbo'
      and p_duration = '5'::jsonb
      and coalesce(p_audio, 'false'::jsonb) = 'false'::jsonb
      and p_format in ('9:16', '16:9', '1:1')
      and p_confirmation = 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    then jsonb_build_object(
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'audio', false,
      'ratio', case p_format
        when '9:16' then '720:1280'
        when '16:9' then '1280:720'
        else '960:960'
      end,
      'estimated_cost_minor', 25,
      'estimated_credits', 25,
      'currency', 'USD'
    )
    when p_model = 'seedance2_fast'
      and p_duration = '8'::jsonb
      and p_audio = 'true'::jsonb
      and p_format = '9:16'
      and p_confirmation = 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
    then jsonb_build_object(
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'audio', true,
      'ratio', '720:1280',
      'estimated_cost_minor', 232,
      'estimated_credits', 232,
      'currency', 'USD'
    )
    else null
  end
$$;

revoke all on function content_factory_private.real_generation_sku_config(
  text, jsonb, jsonb, text, text
) from public, anon, authenticated;

create or replace function content_factory_private.normalize_generation_batch_facts()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' and new.mode = 'mock' then
    new.provider := coalesce(new.provider, 'mock');
    new.model := coalesce(new.model, 'mock');
    new.duration_seconds := coalesce(new.duration_seconds, 0);
    new.audio := coalesce(new.audio, false);
    new.estimated_cost_minor := coalesce(new.estimated_cost_minor, 0);
    new.estimated_credits := coalesce(new.estimated_credits, 0);
    new.currency := coalesce(new.currency, 'USD');
  elsif tg_op = 'INSERT' and new.mode = 'real' then
    new.provider := coalesce(new.provider, 'runway');
    new.model := coalesce(new.model, new.input ->> 'model');
    new.duration_seconds := coalesce(
      new.duration_seconds,
      (new.input ->> 'duration_seconds')::integer
    );
    new.audio := coalesce(new.audio, (new.input ->> 'audio')::boolean, false);
    new.estimated_cost_minor := coalesce(
      new.estimated_cost_minor,
      (new.input #>> '{billing,estimated_cost_minor}')::bigint
    );
    new.estimated_credits := coalesce(
      new.estimated_credits,
      (new.input #>> '{billing,estimated_credits}')::bigint
    );
    new.currency := coalesce(new.currency, new.input #>> '{billing,currency}');
  end if;
  return new;
end;
$$;

drop trigger if exists a_generation_batch_facts_normalize
  on content_factory.generation_batches;
create trigger a_generation_batch_facts_normalize
before insert on content_factory.generation_batches
for each row execute function content_factory_private.normalize_generation_batch_facts();

revoke all on function content_factory_private.normalize_generation_batch_facts()
  from public, anon, authenticated;

create or replace function content_factory_private.guard_generation_batch_contract()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  sku_config jsonb;
begin
  if new.mode = 'mock' then
    if new.allow_real_spend
       or new.status not in ('mock_ready', 'cancelled')
       or new.provider <> 'mock'
       or new.model <> 'mock'
       or new.duration_seconds <> 0
       or new.audio
       or new.estimated_cost_minor <> 0
       or new.estimated_credits <> 0
       or new.currency <> 'USD' then
      raise exception using
        errcode = '42501',
        message = 'mock_generation_contract_invalid';
    end if;
    return new;
  end if;

  sku_config := content_factory_private.real_generation_sku_config(
    new.input ->> 'model',
    new.input -> 'duration_seconds',
    new.input -> 'audio',
    new.input ->> 'format',
    new.input ->> 'spend_confirmation'
  );

  if new.mode <> 'real'
     or not new.allow_real_spend
     or new.status not in (
       'queued', 'starting', 'submitted', 'processing',
       'succeeded', 'failed', 'cancelled'
     )
     or new.total_requested <> 1
     or new.total_created <> (
       case when new.status = 'succeeded' then 1 else 0 end
     )
     or sku_config is null
     or new.provider <> 'runway'
     or new.provider is distinct from new.input ->> 'provider'
     or new.model is distinct from sku_config ->> 'model'
     or new.duration_seconds::text is distinct from sku_config ->> 'duration_seconds'
     or new.audio is distinct from (sku_config ->> 'audio')::boolean
     or new.estimated_cost_minor::text
          is distinct from sku_config ->> 'estimated_cost_minor'
     or new.estimated_credits::text
          is distinct from sku_config ->> 'estimated_credits'
     or new.currency is distinct from sku_config ->> 'currency'
     or new.input ->> 'ratio' is distinct from sku_config ->> 'ratio'
     or new.input #>> '{billing,currency}' is distinct from new.currency
     or new.input #>> '{billing,estimated_cost_minor}'
          is distinct from new.estimated_cost_minor::text
     or new.input #>> '{billing,estimated_credits}'
          is distinct from new.estimated_credits::text
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
  sku_config jsonb;
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

  sku_config := content_factory_private.real_generation_sku_config(
    new.input ->> 'model',
    new.input -> 'duration_seconds',
    new.input -> 'audio',
    new.input ->> 'format',
    new.input ->> 'spend_confirmation'
  );

  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or sku_config is null
     or new.estimated_cost_minor::text
          is distinct from sku_config ->> 'estimated_cost_minor'
     or new.actual_cost_minor < 0
     or new.status not in (
       'queued', 'starting', 'submitted', 'processing',
       'succeeded', 'failed', 'cancelled'
     )
     or new.input ->> 'provider' is distinct from 'runway'
     or new.input ->> 'ratio' is distinct from sku_config ->> 'ratio'
     or new.input #>> '{billing,currency}' is distinct from 'USD'
     or new.input #>> '{billing,estimated_cost_minor}'
          is distinct from sku_config ->> 'estimated_cost_minor'
     or new.input #>> '{billing,estimated_credits}'
          is distinct from sku_config ->> 'estimated_credits'
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
    provider_task_id_value is null
    or new.actual_cost_minor <> new.estimated_cost_minor
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_submitted_contract_invalid';
  end if;

  if new.status = 'failed' and new.actual_cost_minor not in (
    0, new.estimated_cost_minor
  ) then
    raise exception using
      errcode = '42501',
      message = 'real_generation_failure_cost_invalid';
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

-- Keep the already-audited Gen-4 implementation byte-for-byte and route the
-- second paid SKU through a separate exact implementation. The public wrapper
-- retains the one-jsonb RPC signature and a shared idempotency namespace.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_gen4_turbo_5s;
revoke all on function content_factory_private.creator_start_gen4_turbo_5s(jsonb)
  from public, anon, authenticated;

create or replace function content_factory_private.creator_start_seedance2_fast_8s(
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
    'duration_seconds', 'audio', 'allow_real_spend', 'spend_confirmation'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_payload_invalid';
  end if;

  if p_payload -> 'count' is distinct from '1'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_count_must_be_one';
  end if;
  if p_payload ->> 'mode' is distinct from 'real'
     or p_payload ->> 'provider' is distinct from 'runway'
     or p_payload ->> 'model' is distinct from 'seedance2_fast'
     or p_payload -> 'duration_seconds' is distinct from '8'::jsonb
     or p_payload -> 'audio' is distinct from 'true'::jsonb
     or p_payload ->> 'format' is distinct from '9:16'
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or p_payload ->> 'spend_confirmation'
          is distinct from 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32' then
    raise exception using
      errcode = '42501',
      message = 'real_generation_spend_confirmation_required';
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

  if length(brief_value) < 1 or length(brief_value) > 1200 then
    raise exception using errcode = '22023', message = 'brief_invalid';
  end if;
  prompt_value := brief_value;

  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) then
    raise exception using errcode = '22023', message = 'platform_invalid';
  end if;

  if jsonb_typeof(media_ids) <> 'array' or jsonb_array_length(media_ids) <> 1 then
    raise exception using
      errcode = '22023',
      message = 'exact_one_product_media_required';
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
    raise exception using
      errcode = '54000',
      message = 'real_generation_user_daily_quota_exceeded';
  end if;
  if organization_daily_jobs >= 50 then
    raise exception using
      errcode = '54000',
      message = 'real_generation_organization_daily_quota_exceeded';
  end if;
  if assignee_open_jobs >= 1 then
    raise exception using
      errcode = '54000',
      message = 'real_generation_assignee_concurrency_exceeded';
  end if;
  if organization_open_jobs >= 3 then
    raise exception using
      errcode = '54000',
      message = 'real_generation_organization_concurrency_exceeded';
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

  -- For this higher-cost audio SKU, `ready` plus the immutable upload-time
  -- rights acknowledgement is the explicit approval gate.
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.product_id is distinct from product_id_value
     or coalesce(media_row.metadata ->> 'kind', '') not in (
       'product_photo', 'packshot'
     )
     or media_row.metadata -> 'rights_confirmed' is distinct from 'true'::jsonb
     or (not team_scope and media_row.owner_id <> user_id) then
    raise exception using
      errcode = '42501',
      message = 'seedance_approved_product_media_required';
  end if;

  output_object_name_value := organization_id::text || '/' ||
    assignee_id_value::text || '/generated/' || job_id_value::text || '.mp4';

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key,
    provider, model, duration_seconds, audio,
    estimated_cost_minor, estimated_credits, currency
  ) values (
    batch_id_value,
    organization_id,
    product_id_value,
    user_id,
    left('Runway Seedance 2 Fast ' || sku_value || ' - 1 video', 180),
    'real',
    true,
    'queued',
    1,
    0,
    jsonb_build_object(
      'job_id', job_id_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'audio', true,
      'format', '9:16',
      'ratio', '720:1280',
      'media_id', media_id_value,
      'assigned_to', assignee_id_value,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 232,
        'estimated_credits', 232,
        'credit_unit_usd_minor', 1
      )
    ),
    content_factory_private.json_hash(request_payload),
    idempotency_key,
    'runway',
    'seedance2_fast',
    8,
    true,
    232,
    232,
    'USD'
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
    232,
    0,
    'queued',
    jsonb_build_object(
      'sku', sku_value,
      'product_name', product_name_value,
      'prompt_text', prompt_value,
      'format', '9:16',
      'ratio', '720:1280',
      'audio', true,
      'input_media_id', media_id_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'platform', platform_value,
      'destination_ref', destination_value,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 232,
        'estimated_credits', 232,
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
    left('Review Runway Seedance audio video - ' || product_name_value, 240),
    'Generation is in progress. Review the exact MP4 and audio only after this task moves to review.',
    'blocked',
    2,
    payout_value,
    jsonb_build_object(
      'generation_status', 'queued',
      'review_required', true,
      'provider', 'runway',
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'audio', true,
      'estimated_cost_minor', 232,
      'estimated_credits', 232,
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
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'audio', true,
      'ratio', '720:1280',
      'prompt_text', prompt_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', 232,
      'estimated_credits', 232
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
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'audio', true,
      'estimated_cost_minor', 232,
      'estimated_credits', 232,
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

revoke all on function content_factory_private.creator_start_seedance2_fast_8s(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload ->> 'model' = 'seedance2_fast' then
    return content_factory_private.creator_start_seedance2_fast_8s(p_payload);
  end if;

  if p_payload ->> 'model' = 'gen4_turbo' then
    if p_payload ? 'audio'
       and p_payload -> 'audio' is distinct from 'false'::jsonb then
      raise exception using
        errcode = '42501',
        message = 'real_generation_spend_confirmation_required';
    end if;
    result := content_factory_private.creator_start_gen4_turbo_5s(
      p_payload - 'audio'
    );
    result := jsonb_set(result, '{job,audio}', 'false'::jsonb, true);
    result := jsonb_set(result, '{job,estimated_credits}', '25'::jsonb, true);
    return result;
  end if;

  raise exception using
    errcode = '42501',
    message = 'real_generation_spend_confirmation_required';
end;
$$;

-- Model-neutral provider state machine. Every mutable fact comes from the
-- locked job/batch SKU snapshot; callers cannot supply price/model overrides.
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
  sku_config jsonb;
  model_value text;
  duration_seconds_value integer;
  audio_value boolean;
  estimated_credits_value bigint;
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
    raise exception using
      errcode = '22023',
      message = 'real_generation_update_payload_invalid';
  end if;

  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  status_value := content_factory_private.require_text(p_payload, 'status', 6, 20);
  if status_value not in (
    'starting', 'submitted', 'processing', 'succeeded', 'failed'
  ) then
    raise exception using
      errcode = '22023',
      message = 'real_generation_update_status_invalid';
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

  sku_config := content_factory_private.real_generation_sku_config(
    job_row.input ->> 'model',
    job_row.input -> 'duration_seconds',
    job_row.input -> 'audio',
    job_row.input ->> 'format',
    job_row.input ->> 'spend_confirmation'
  );
  if sku_config is null
     or job_row.estimated_cost_minor::text
          is distinct from sku_config ->> 'estimated_cost_minor'
     or job_row.input #>> '{billing,estimated_credits}'
          is distinct from sku_config ->> 'estimated_credits' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_sku_state_invalid';
  end if;
  model_value := sku_config ->> 'model';
  duration_seconds_value := (sku_config ->> 'duration_seconds')::integer;
  audio_value := (sku_config ->> 'audio')::boolean;
  estimated_credits_value := (sku_config ->> 'estimated_credits')::bigint;

  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = job_row.organization_id
    and batch.id = job_row.batch_id
  for update;

  if batch_row.id is null
     or batch_row.mode <> 'real'
     or batch_row.provider <> 'runway'
     or not batch_row.allow_real_spend
     or batch_row.input ->> 'job_id' is distinct from job_row.id::text
     or batch_row.status is distinct from job_row.status
     or batch_row.model is distinct from model_value
     or batch_row.duration_seconds is distinct from duration_seconds_value
     or batch_row.audio is distinct from audio_value
     or batch_row.estimated_cost_minor is distinct from job_row.estimated_cost_minor
     or batch_row.estimated_credits is distinct from estimated_credits_value
     or batch_row.currency <> 'USD' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_batch_state_invalid';
  end if;

  select count(*)::integer, (array_agg(task.id order by task.id))[1]
  into linked_task_count, linked_task_id
  from content_factory.creator_tasks task
  where task.organization_id = job_row.organization_id
    and task.generation_job_id = job_row.id
    and task.task_type = 'video_review';

  if linked_task_count <> 1 or linked_task_id is null then
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_invalid';
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
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_invalid';
  end if;

  if status_value = 'starting' then
    if p_payload - array['job_id', 'status']::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'real_generation_starting_payload_invalid';
    end if;

    if job_row.status = 'queued' then
      if task_row.status <> 'blocked' then
        raise exception using
          errcode = '55000',
          message = 'real_generation_review_task_invalid';
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
        jsonb_build_object('claimed', true, 'model', model_value),
        'real-generation:' || job_row.id::text || ':starting',
        'system'
      );
    elsif job_row.status in (
      'starting', 'submitted', 'processing', 'succeeded', 'failed', 'cancelled'
    ) then
      claimed := false;
    else
      raise exception using
        errcode = '55000',
        message = 'real_generation_state_transition_invalid';
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
        'model', model_value,
        'duration_seconds', duration_seconds_value,
        'audio', audio_value,
        'output_object_name', job_row.input ->> 'output_object_name',
        'updated_at', job_row.updated_at
      )
    );
  end if;

  stored_provider_task_id := nullif(
    btrim(job_row.output ->> 'provider_task_id'),
    ''
  );
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
    if p_payload - array[
      'job_id', 'status', 'provider_task_id'
    ]::text[] <> '{}'::jsonb or provider_task_id_value is null then
      raise exception using
        errcode = '22023',
        message = 'real_generation_submitted_payload_invalid';
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
      raise exception using
        errcode = '55000',
        message = 'real_generation_state_transition_invalid';
    end if;

    update content_factory.generation_jobs job
    set status = 'submitted',
        actual_cost_minor = job.estimated_cost_minor,
        output = job.output || jsonb_build_object(
          'provider_task_id', provider_task_id_value,
          'submitted_at', now(),
          'actual_cost_minor', job.estimated_cost_minor,
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
    if p_payload - array[
      'job_id', 'status', 'provider_task_id'
    ]::text[] <> '{}'::jsonb or provider_task_id_value is null then
      raise exception using
        errcode = '22023',
        message = 'real_generation_processing_payload_invalid';
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
      raise exception using
        errcode = '55000',
        message = 'real_generation_state_transition_invalid';
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
      raise exception using
        errcode = '22023',
        message = 'real_generation_success_payload_invalid';
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
      raise exception using
        errcode = '22023',
        message = 'real_generation_output_size_invalid';
    end if;
    begin
      size_bytes_value := (p_payload ->> 'size_bytes')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'real_generation_output_size_invalid';
    end;

    if job_row.status = 'succeeded' then
      if stored_provider_task_id is distinct from provider_task_id_value
         or job_row.output ->> 'output_object_name'
              is distinct from output_object_name_value
         or job_row.output ->> 'sha256' is distinct from sha256_value
         or job_row.output ->> 'mime_type' is distinct from mime_type_value
         or job_row.output ->> 'size_bytes'
              is distinct from size_bytes_value::text then
        raise exception using
          errcode = '23505',
          message = 'real_generation_success_replay_conflict';
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
      raise exception using
        errcode = '55000',
        message = 'real_generation_state_transition_invalid';
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
      raise exception using
        errcode = '22023',
        message = 'real_generation_output_metadata_invalid';
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
      raise exception using
        errcode = 'P0002',
        message = 'real_generation_storage_object_invalid';
    end if;

    begin
      storage_size := (storage_metadata ->> 'size')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'real_generation_storage_metadata_invalid';
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
      raise exception using
        errcode = '22023',
        message = 'real_generation_storage_metadata_mismatch';
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
      or media_row.metadata ->> 'model' is distinct from model_value
      or media_row.metadata ->> 'generation_job_id' is distinct from job_row.id::text
    ) then
      raise exception using
        errcode = '23505',
        message = 'real_generation_media_conflict';
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
          'model', model_value,
          'duration_seconds', duration_seconds_value,
          'audio', audio_value,
          'ratio', job_row.input ->> 'ratio',
          'estimated_cost_minor', job_row.estimated_cost_minor,
          'estimated_credits', estimated_credits_value,
          'currency', 'USD',
          'generation_job_id', job_row.id,
          'review_required', true
        ),
        'runway-output:' || job_row.id::text
      )
      returning * into media_row;
    end if;

    update content_factory.generation_jobs job
    set status = 'succeeded',
        actual_cost_minor = job.estimated_cost_minor,
        output = (job.output - 'failure_code') || jsonb_build_object(
          'output_object_name', output_object_name_value,
          'output_media_id', media_row.id,
          'mime_type', 'video/mp4',
          'size_bytes', size_bytes_value,
          'sha256', sha256_value,
          'succeeded_at', now(),
          'actual_cost_minor', job.estimated_cost_minor,
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
          'model', model_value,
          'duration_seconds', duration_seconds_value,
          'audio', audio_value,
          'actual_cost_minor', job_row.estimated_cost_minor,
          'estimated_credits', estimated_credits_value,
          'currency', 'USD'
        )
    where task.id = task_row.id;

  elsif status_value = 'failed' then
    if p_payload - array[
      'job_id', 'status', 'provider_task_id', 'failure_code'
    ]::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'real_generation_failure_payload_invalid';
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
      raise exception using
        errcode = '22023',
        message = 'real_generation_failure_code_invalid';
    end if;

    if job_row.status = 'failed' then
      if job_row.output ->> 'failure_code' is distinct from failure_code_value
         or stored_provider_task_id is distinct from provider_task_id_value then
        raise exception using
          errcode = '23505',
          message = 'real_generation_failure_replay_conflict';
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

    -- Ambiguous provider POST outcomes remain `starting`; this path is only
    -- for definitive provider errors or manual service-role reconciliation.
    if job_row.status not in ('queued', 'starting', 'submitted', 'processing')
       or task_row.status <> 'blocked' then
      raise exception using
        errcode = '55000',
        message = 'real_generation_state_transition_invalid';
    end if;
    if job_row.status in ('submitted', 'processing') and (
      provider_task_id_value is null
      or stored_provider_task_id is distinct from provider_task_id_value
    ) then
      raise exception using
        errcode = '55000',
        message = 'real_generation_provider_task_mismatch';
    end if;
    if job_row.status in ('queued', 'starting')
       and provider_task_id_value is not null then
      raise exception using
        errcode = '55000',
        message = 'real_generation_provider_task_mismatch';
    end if;

    update content_factory.generation_jobs job
    set status = 'failed',
        actual_cost_minor = case
          when stored_provider_task_id is null then 0
          else job.estimated_cost_minor
        end,
        output = (job.output - 'output_media_id' - 'output_object_name') ||
          jsonb_build_object(
            'failure_code', failure_code_value,
            'failed_at', now(),
            'actual_cost_minor', case
              when stored_provider_task_id is null then 0
              else job.estimated_cost_minor
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
          'provider', 'runway',
          'model', model_value,
          'duration_seconds', duration_seconds_value,
          'audio', audio_value,
          'estimated_cost_minor', job_row.estimated_cost_minor,
          'estimated_credits', estimated_credits_value,
          'currency', 'USD'
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
      'model', model_value,
      'duration_seconds', duration_seconds_value,
      'audio', audio_value,
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
      'model', model_value,
      'duration_seconds', duration_seconds_value,
      'audio', audio_value,
      'output_object_name', job_row.output ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'updated_at', job_row.updated_at
    )
  );
  return result;
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
    raise exception using
      errcode = '22023',
      message = 'real_generation_status_payload_invalid';
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
      'audio', coalesce((job_row.input ->> 'audio')::boolean, false),
      'ratio', job_row.input ->> 'ratio',
      'estimated_cost_minor', job_row.estimated_cost_minor,
      'estimated_credits', (job_row.input #>> '{billing,estimated_credits}')::bigint,
      'actual_cost_minor', job_row.actual_cost_minor,
      'output_object_name', job_row.input ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'updated_at', job_row.updated_at
    )
  );
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon;
revoke all on function public.system_update_real_generation(jsonb)
  from public, anon, authenticated;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;
grant execute on function public.system_update_real_generation(jsonb)
  to service_role;

commit;
