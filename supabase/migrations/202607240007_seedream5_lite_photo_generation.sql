begin;

-- Add one fixed-price product-photo SKU without weakening the existing video
-- contracts.  The browser can only request one 2K square PNG from one exact,
-- rights-confirmed product reference.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_model_check,
  drop constraint if exists generation_batches_sku_contract_check,
  drop constraint if exists generation_batches_model_v2_check,
  drop constraint if exists generation_batches_sku_contract_v2_check;

alter table content_factory.generation_batches
  add constraint generation_batches_model_v2_check
    check (model in (
      'mock', 'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
  add constraint generation_batches_sku_contract_v2_check
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
          or (
            model = 'seedream5_lite'
            and duration_seconds = 0
            and not audio
            and estimated_cost_minor = 4
            and estimated_credits = 4
          )
        )
      )
    );

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_spend_contract_check,
  drop constraint if exists generation_jobs_spend_contract_v2_check;

alter table content_factory.generation_jobs
  add constraint generation_jobs_spend_contract_v2_check
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
          or (
            input ->> 'model' = 'seedream5_lite'
            and input -> 'duration_seconds' = '0'::jsonb
            and coalesce(input -> 'audio', 'false'::jsonb) = 'false'::jsonb
            and estimated_cost_minor = 4
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
    when p_model = 'seedream5_lite'
      and p_duration = '0'::jsonb
      and coalesce(p_audio, 'false'::jsonb) = 'false'::jsonb
      and p_format = '1:1'
      and p_confirmation = 'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04'
    then jsonb_build_object(
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'audio', false,
      'ratio', '2048:2048',
      'estimated_cost_minor', 4,
      'estimated_credits', 4,
      'currency', 'USD'
    )
    else null
  end
$$;

revoke all on function content_factory_private.real_generation_sku_config(
  text, jsonb, jsonb, text, text
) from public, anon, authenticated;

create or replace function
  content_factory_private.creator_start_seedream5_lite_photo(
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
     or p_payload ->> 'model' is distinct from 'seedream5_lite'
     or p_payload -> 'duration_seconds' is distinct from '0'::jsonb
     or coalesce(p_payload -> 'audio', 'false'::jsonb)
          is distinct from 'false'::jsonb
     or p_payload ->> 'format' is distinct from '1:1'
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or p_payload ->> 'spend_confirmation'
          is distinct from 'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04' then
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
    p_payload, 'idempotency_key', 8, 180
  );
  sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
  product_name_value := content_factory_private.require_text(
    p_payload, 'product_name', 2, 180
  );
  brief_value := btrim(coalesce(p_payload ->> 'brief', ''));
  platform_value := content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  );
  destination_value := content_factory_private.require_text(
    p_payload, 'destination_ref', 2, 240
  );
  media_ids := coalesce(p_payload -> 'media_ids', '[]'::jsonb);

  if nullif(btrim(coalesce(p_payload ->> 'assignee_id', '')), '') is not null
  then
    assignee_id_value := content_factory_private.require_uuid(
      p_payload, 'assignee_id'
    );
  end if;
  if length(brief_value) < 1 or length(brief_value) > 1200 then
    raise exception using errcode = '22023', message = 'brief_invalid';
  end if;
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) then
    raise exception using errcode = '22023', message = 'platform_invalid';
  end if;
  if jsonb_typeof(media_ids) <> 'array'
     or jsonb_array_length(media_ids) <> 1 then
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
    raise exception using
      errcode = '42501',
      message = 'assignee_role_not_allowed';
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
      and membership.role in (
        'owner', 'admin', 'producer', 'reviewer', 'operator'
      )
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
    raise exception using
      errcode = '42501',
      message = 'certified_assignee_required';
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
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.product_id is distinct from product_id_value
     or coalesce(media_row.metadata ->> 'kind', '') not in (
       'product_photo', 'packshot'
     )
     or media_row.mime_type not in ('image/jpeg', 'image/png', 'image/webp')
     or media_row.metadata -> 'rights_confirmed' is distinct from 'true'::jsonb
     or (not team_scope and media_row.owner_id <> user_id) then
    raise exception using
      errcode = '42501',
      message = 'seedream_approved_product_media_required';
  end if;

  output_object_name_value := organization_id::text || '/' ||
    assignee_id_value::text || '/generated/' || job_id_value::text || '.png';

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
    left('Runway Seedream 5 Lite ' || sku_value || ' - 1 photo', 180),
    'real',
    true,
    'queued',
    1,
    0,
    jsonb_build_object(
      'job_id', job_id_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'audio', false,
      'format', '1:1',
      'ratio', '2048:2048',
      'media_id', media_id_value,
      'assigned_to', assignee_id_value,
      'spend_confirmation', 'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 4,
        'estimated_credits', 4,
        'credit_unit_usd_minor', 1
      )
    ),
    content_factory_private.json_hash(request_payload),
    idempotency_key,
    'runway',
    'seedream5_lite',
    0,
    false,
    4,
    4,
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
    4,
    0,
    'queued',
    jsonb_build_object(
      'sku', sku_value,
      'product_name', product_name_value,
      'prompt_text', brief_value,
      'format', '1:1',
      'ratio', '2048:2048',
      'audio', false,
      'input_media_id', media_id_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'review_task_id', task_id_value,
      'provider', 'runway',
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'platform', platform_value,
      'destination_ref', destination_value,
      'spend_confirmation', 'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 4,
        'estimated_credits', 4,
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
    left('Review generated product photo - ' || product_name_value, 240),
    'Generation is in progress. Review product identity, label, geometry, text and artifacts only after this task moves to review.',
    'blocked',
    2,
    payout_value,
    jsonb_build_object(
      'generation_status', 'queued',
      'review_required', true,
      'content_kind', 'photo',
      'provider', 'runway',
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'audio', false,
      'estimated_cost_minor', 4,
      'estimated_credits', 4,
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
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'audio', false,
      'ratio', '2048:2048',
      'prompt_text', brief_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', 4,
      'estimated_credits', 4
    )
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'real_generation_queued',
    'generation_job',
    job_id_value::text,
    jsonb_build_object(
      'content_kind', 'photo',
      'provider', 'runway',
      'model', 'seedream5_lite',
      'duration_seconds', 0,
      'audio', false,
      'estimated_cost_minor', 4,
      'estimated_credits', 4,
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

revoke all on function
  content_factory_private.creator_start_seedream5_lite_photo(jsonb)
  from public, anon, authenticated, service_role;

-- Compose the photo command with the current campaign-aware video command.
-- The campaign GUC is consumed by immutable binding/budget triggers.
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
  organization_id uuid;
  campaign_id_value uuid;
  campaign_row content_factory.generation_campaigns%rowtype;
  result jsonb;
  job_id_value uuid;
  stored_campaign_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if lower(btrim(coalesce(p_payload ->> 'platform', ''))) = 'instagram' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_platform_not_supported';
  end if;
  if p_payload ->> 'model' <> 'seedream5_lite' then
    return content_factory_private.creator_start_real_generation_campaign_v1(
      p_payload
    );
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  if p_payload ? 'campaign_id' then
    campaign_id_value := content_factory_private.require_uuid(
      p_payload, 'campaign_id'
    );
  else
    select campaign.id into campaign_id_value
    from content_factory.generation_campaigns campaign
    where campaign.organization_id = organization_id
      and campaign.kind = 'default';
  end if;
  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = organization_id
    and campaign.id = campaign_id_value;
  if campaign_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;
  if campaign_row.status <> 'active' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_not_active';
  end if;
  perform set_config(
    'content_factory.generation_campaign_id',
    campaign_id_value::text,
    true
  );
  result := content_factory_private.creator_start_seedream5_lite_photo(
    p_payload - 'campaign_id'
  );
  begin
    job_id_value := (result #>> '{job,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000',
      message = 'generation_campaign_binding_invalid';
  end;
  select job.campaign_id into stored_campaign_id
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value;
  if stored_campaign_id is distinct from campaign_id_value then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;
  result := jsonb_set(
    result, '{job,campaign_id}', to_jsonb(campaign_id_value::text), true
  );
  result := jsonb_set(
    result, '{job,campaign_name}', to_jsonb(campaign_row.name), true
  );
  result := jsonb_set(
    result, '{batch,campaign_id}', to_jsonb(campaign_id_value::text), true
  );
  return result;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

-- Generated photos consume the same storage reservation as generated videos.
create or replace function
  content_factory_private.enforce_media_storage_quota()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  generation_job_id_value uuid;
  generation_status_value text;
  reservation_row
    content_factory.generation_storage_reservations%rowtype;
begin
  if new.status in ('uploading', 'ready', 'archived') then
    if new.metadata ->> 'kind' in ('generated_video', 'generated_image')
       and new.metadata ->> 'provider' = 'runway'
       and coalesce(new.metadata ->> 'generation_job_id', '') ~
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    then
      generation_job_id_value :=
        (new.metadata ->> 'generation_job_id')::uuid;
      select job.status into generation_status_value
      from content_factory.generation_jobs job
      where job.organization_id = new.organization_id
        and job.id = generation_job_id_value;
      if generation_status_value in ('starting', 'submitted', 'processing') then
        select reservation.* into reservation_row
        from content_factory.generation_storage_reservations reservation
        where reservation.organization_id = new.organization_id
          and reservation.generation_job_id = generation_job_id_value
        for update;
        if reservation_row.id is null
           or reservation_row.owner_id <> new.owner_id
           or reservation_row.status <> 'active'
           or new.size_bytes > reservation_row.reserved_size_bytes then
          raise exception using
            errcode = '54000',
            message = 'generation_storage_reservation_invalid';
        end if;
        update content_factory.generation_storage_reservations reservation
        set status = 'consumed',
            actual_size_bytes = new.size_bytes,
            consumed_at = now(),
            reason_code = 'generated_output_registered'
        where reservation.id = reservation_row.id;
      end if;
    end if;
    perform content_factory_private.assert_storage_quota(
      new.organization_id, new.owner_id, 1, new.size_bytes
    );
  end if;
  return new;
end;
$$;

create or replace function
  content_factory_private.release_generation_output_capacity()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  reservation_row
    content_factory.generation_storage_reservations%rowtype;
  media_size_value bigint;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or new.status is not distinct from old.status then
    return new;
  end if;
  select reservation.* into reservation_row
  from content_factory.generation_storage_reservations reservation
  where reservation.generation_job_id = new.id
  for update;
  if reservation_row.id is null then
    if new.status in ('succeeded', 'failed', 'cancelled') then
      return new;
    end if;
    raise exception using
      errcode = '55000',
      message = 'generation_storage_reservation_required';
  end if;
  if new.status in ('failed', 'cancelled') then
    return new;
  elsif new.status = 'succeeded' and reservation_row.status = 'active' then
    select media.size_bytes into media_size_value
    from content_factory.media_objects media
    where media.organization_id = new.organization_id
      and media.metadata ->> 'generation_job_id' = new.id::text
      and media.metadata ->> 'kind' in (
        'generated_video', 'generated_image'
      )
      and media.status in ('ready', 'archived')
    limit 1;
    if media_size_value is null
       or media_size_value > reservation_row.reserved_size_bytes then
      raise exception using
        errcode = '55000',
        message = 'generation_storage_reservation_consume_required';
    end if;
    update content_factory.generation_storage_reservations reservation
    set status = 'consumed',
        actual_size_bytes = media_size_value,
        consumed_at = now(),
        reason_code = 'generated_output_registered'
    where reservation.id = reservation_row.id;
  end if;
  return new;
end;
$$;

-- Photo success is the only provider transition whose output contract differs
-- from the audited MP4 state machine. All earlier states and failures continue
-- through system_update_real_generation and its billing adapter.
create or replace function public.system_complete_seedream5_lite_photo(
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
  provider_task_id_value text;
  output_object_name_value text;
  mime_type_value text;
  sha256_value text;
  size_bytes_value bigint;
  storage_metadata jsonb;
  storage_user_metadata jsonb;
  storage_size bigint;
  storage_mime_type text;
  storage_sha256 text;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  media_row content_factory.media_objects%rowtype;
  review_id_value uuid := extensions.gen_random_uuid();
  review_input_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'job_id', 'status', 'provider_task_id', 'output_object_name',
    'mime_type', 'size_bytes', 'sha256'
  ]::text[] <> '{}'::jsonb
     or p_payload ->> 'status' is distinct from 'succeeded' then
    raise exception using
      errcode = '22023',
      message = 'seedream_photo_success_payload_invalid';
  end if;
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  provider_task_id_value := content_factory_private.require_text(
    p_payload, 'provider_task_id', 1, 240
  );
  output_object_name_value := content_factory_private.require_text(
    p_payload, 'output_object_name', 10, 1000
  );
  mime_type_value := lower(content_factory_private.require_text(
    p_payload, 'mime_type', 3, 160
  ));
  sha256_value := lower(content_factory_private.require_text(
    p_payload, 'sha256', 64, 64
  ));
  if provider_task_id_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$'
     or coalesce(p_payload ->> 'size_bytes', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'seedream_photo_success_payload_invalid';
  end if;
  begin
    size_bytes_value := (p_payload ->> 'size_bytes')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'seedream_photo_success_payload_invalid';
  end;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
  for update;
  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend
     or job_row.input ->> 'model' <> 'seedream5_lite'
     or job_row.input ->> 'ratio' <> '2048:2048'
     or job_row.estimated_cost_minor <> 4
     or job_row.input #>> '{billing,estimated_credits}' <> '4' then
    raise exception using
      errcode = 'P0002',
      message = 'seedream_photo_generation_not_found';
  end if;
  if job_row.status = 'succeeded' then
    if job_row.output ->> 'provider_task_id'
         is distinct from provider_task_id_value
       or job_row.output ->> 'output_object_name'
         is distinct from output_object_name_value
       or job_row.output ->> 'sha256' is distinct from sha256_value
       or job_row.output ->> 'mime_type' is distinct from mime_type_value
       or job_row.output ->> 'size_bytes'
         is distinct from size_bytes_value::text then
      raise exception using
        errcode = '23505',
        message = 'seedream_photo_success_replay_conflict';
    end if;
    return jsonb_build_object('ok', true, 'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider_task_id', job_row.output ->> 'provider_task_id',
      'output_object_name', job_row.output ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'updated_at', job_row.updated_at
    ));
  end if;
  if job_row.status <> 'processing'
     or job_row.output ->> 'provider_task_id'
       is distinct from provider_task_id_value then
    raise exception using
      errcode = '55000',
      message = 'real_generation_state_transition_invalid';
  end if;

  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = job_row.organization_id
    and batch.id = job_row.batch_id
  for update;
  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = job_row.organization_id
    and task.id::text = job_row.input ->> 'review_task_id'
    and task.generation_job_id = job_row.id
    and task.task_type = 'video_review'
  for update;
  if batch_row.id is null
     or batch_row.status <> 'processing'
     or batch_row.model <> 'seedream5_lite'
     or batch_row.estimated_cost_minor <> 4
     or task_row.id is null
     or task_row.status <> 'blocked' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_state_transition_invalid';
  end if;

  if output_object_name_value is distinct from
       job_row.input ->> 'output_object_name'
     or split_part(output_object_name_value, '/', 1) <>
       job_row.organization_id::text
     or split_part(output_object_name_value, '/', 2) <>
       job_row.assigned_to::text
     or split_part(output_object_name_value, '/', 3) <> 'generated'
     or output_object_name_value !~
       ('/' || job_row.id::text || '[.]png$')
     or output_object_name_value ~ '(^|/)\.\.(/|$)'
     or mime_type_value <> 'image/png'
     or size_bytes_value < 1
     or size_bytes_value > 52428800
     or sha256_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'seedream_photo_output_metadata_invalid';
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
     or nullif(
       btrim(coalesce(storage_metadata ->> 'mimetype', '')), ''
     ) is null then
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
     or storage_mime_type <> 'image/png'
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
    or media_row.mime_type <> 'image/png'
    or media_row.size_bytes <> size_bytes_value
    or media_row.sha256 <> sha256_value
    or media_row.status <> 'ready'
    or media_row.metadata ->> 'kind' is distinct from 'generated_image'
    or media_row.metadata ->> 'provider' is distinct from 'runway'
    or media_row.metadata ->> 'model' is distinct from 'seedream5_lite'
    or media_row.metadata ->> 'generation_job_id'
      is distinct from job_row.id::text
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
      'image/png',
      size_bytes_value,
      sha256_value,
      'ready',
      jsonb_build_object(
        'original_filename', job_row.id::text || '.png',
        'kind', 'generated_image',
        'content_kind', 'photo',
        'provider', 'runway',
        'model', 'seedream5_lite',
        'ratio', '2048:2048',
        'estimated_cost_minor', 4,
        'estimated_credits', 4,
        'currency', 'USD',
        'generation_job_id', job_row.id,
        'review_required', true
      ),
      'runway-output:' || job_row.id::text
    )
    returning * into media_row;
  end if;

  review_input_value := jsonb_build_object(
    'media_id', media_row.id,
    'platform', job_row.input ->> 'platform',
    'product_category', 'other',
    'product_category_verified', false,
    'product_category_source', 'autonomous_generation',
    'content_kind', 'advertising',
    'generation_job_id', job_row.id,
    'caption_text', '',
    'script_text', job_row.input ->> 'prompt_text',
    'technical_metrics', jsonb_build_object(
      'width', 2048,
      'height', 2048,
      'format', 'png'
    ),
    'people_present', 'unknown',
    'advertiser_name', '',
    'erid', '',
    'ad_label_confirmed', false,
    'ord_confirmed', false,
    'audience_over_10000', false,
    'rkn_registered', false,
    'person_consent_confirmed', false,
    'external_ai_processing_confirmed', true,
    'ai_generated', true,
    'ai_disclosure_confirmed', false,
    'captions_confirmed', false,
    'mandatory_warning_confirmed', false,
    'rights_confirmed', true,
    'claims_verified', false
  );

  update content_factory.generation_jobs job
  set status = 'succeeded',
      actual_cost_minor = job.estimated_cost_minor,
      output = (job.output - 'failure_code') || jsonb_build_object(
        'output_object_name', output_object_name_value,
        'output_media_id', media_row.id,
        'mime_type', 'image/png',
        'size_bytes', size_bytes_value,
        'sha256', sha256_value,
        'content_review_id', review_id_value,
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
        'content_kind', 'photo',
        'content_review_id', review_id_value,
        'content_review_status', 'queued',
        'output_media_id', media_row.id,
        'output_object_name', output_object_name_value,
        'provider', 'runway',
        'model', 'seedream5_lite',
        'duration_seconds', 0,
        'audio', false,
        'actual_cost_minor', 4,
        'estimated_credits', 4,
        'currency', 'USD'
      )
  where task.id = task_row.id;
  insert into content_factory.content_review_runs (
    id, organization_id, media_object_id, requested_by,
    status, media_sha256_snapshot, input, ruleset_version,
    request_hash, idempotency_key
  ) values (
    review_id_value,
    job_row.organization_id,
    media_row.id,
    job_row.requested_by,
    'queued',
    media_row.sha256,
    review_input_value,
    'ru-content-compliance-2026-07-16.1',
    content_factory_private.json_hash(review_input_value),
    'generated-photo-review:' || job_row.id::text
  );
  perform content_factory_private.emit_event(
    job_row.organization_id,
    job_row.requested_by,
    'real_generation_succeeded',
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'status', 'succeeded',
      'content_kind', 'photo',
      'model', 'seedream5_lite',
      'content_review_id', review_id_value,
      'actual_cost_minor', 4
    ),
    'real-generation:' || job_row.id::text || ':succeeded',
    'system'
  );
  return jsonb_build_object('ok', true, 'job', jsonb_build_object(
    'id', job_row.id,
    'batch_id', job_row.batch_id,
    'status', job_row.status,
    'provider', job_row.provider,
    'provider_task_id', job_row.output ->> 'provider_task_id',
    'model', 'seedream5_lite',
    'duration_seconds', 0,
    'audio', false,
    'output_object_name', job_row.output ->> 'output_object_name',
    'output_media_id', job_row.output ->> 'output_media_id',
    'content_review_id', review_id_value,
    'updated_at', job_row.updated_at
  ));
end;
$$;

revoke all on function public.system_complete_seedream5_lite_photo(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_seedream5_lite_photo(jsonb)
  to service_role;

-- Failed output cleanup accepts only the two exact generated file extensions.
do $$
declare
  constraint_row record;
begin
  for constraint_row in
    select constraint_value.conname
    from pg_catalog.pg_constraint constraint_value
    where constraint_value.conrelid =
      'content_factory.generation_storage_cleanup_queue'::regclass
      and constraint_value.contype = 'c'
      and pg_catalog.pg_get_constraintdef(constraint_value.oid) like
        '%generation_job_id%mp4%'
  loop
    execute format(
      'alter table content_factory.generation_storage_cleanup_queue drop constraint %I',
      constraint_row.conname
    );
  end loop;
end;
$$;

alter table content_factory.generation_storage_cleanup_queue
  drop constraint if exists generation_storage_cleanup_object_name_v2_check,
  add constraint generation_storage_cleanup_object_name_v2_check
    check (
      object_name ~ (
        '/' || generation_job_id::text || '[.](mp4|png)$'
      )
    );

create or replace function
  content_factory_private.enqueue_generation_storage_cleanup()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  object_name_value text;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or new.status not in ('failed', 'cancelled')
     or new.status is not distinct from old.status then
    return new;
  end if;
  object_name_value := nullif(
    btrim(coalesce(new.input ->> 'output_object_name', '')),
    ''
  );
  if object_name_value is null
     or split_part(object_name_value, '/', 1) <> new.organization_id::text
     or split_part(object_name_value, '/', 2) <> new.assigned_to::text
     or split_part(object_name_value, '/', 3) <> 'generated'
     or object_name_value !~
       ('/' || new.id::text || '[.](mp4|png)$')
     or object_name_value ~ '(^|/)\.\.(/|$)'
     or exists (
       select 1 from content_factory.media_objects media
       where media.organization_id = new.organization_id
         and media.bucket_id = 'contentengine-private'
         and media.object_name = object_name_value
     ) then
    return new;
  end if;
  insert into content_factory.generation_storage_cleanup_queue (
    organization_id, generation_job_id, bucket_id, object_name
  ) values (
    new.organization_id, new.id, 'contentengine-private', object_name_value
  ) on conflict (generation_job_id) do nothing;
  return new;
end;
$$;

revoke all on function
  content_factory_private.enqueue_generation_storage_cleanup()
  from public, anon, authenticated;

commit;
