begin;

-- Complete the runtime side of flexible video SKUs. The immutable SKU helper
-- from the previous migration is the only source for duration, price and
-- confirmation; legacy validation order remains intact for safe error handling.

-- PostgreSQL's array concatenation keeps the non-null side when the other
-- operand is null. Keep the unknown-model branch explicit so an unsupported
-- paid model can never inherit only the common prompt requirements.
create or replace function
  content_factory_private.generation_mode_prompt_requirements(
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
declare
  model_value text := lower(btrim(coalesce(p_model, '')));
  common_requirements text[] := array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.'
  ]::text[];
begin
  if model_value not in (
    'seedream5_lite',
    'gen4_turbo',
    'seedance2_fast'
  ) then
    return null;
  end if;

  return common_requirements || case model_value
    when 'seedream5_lite' then array[
      'Создай одно квадратное товарное фото 2048 × 2048.',
      'Используй @ProductReference как единственный точный референс товара.',
      'Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.'
    ]::text[]
    when 'gen4_turbo' then array[
      'Без речи, дикторского текста и сгенерированных надписей.'
    ]::text[]
    when 'seedance2_fast' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
  end;
end;
$$;

revoke all on function
  content_factory_private.generation_mode_prompt_requirements(text)
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.creator_start_gen4_turbo_5s(
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
  sku_config jsonb;
  duration_value integer;
  estimated_cost_minor_value integer;
  estimated_credits_value integer;
  spend_confirmation_value text;
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
  sku_config := content_factory_private.real_generation_sku_config(
    p_payload ->> 'model',
    p_payload -> 'duration_seconds',
    coalesce(p_payload -> 'audio', 'false'::jsonb),
    p_payload ->> 'format',
    p_payload ->> 'spend_confirmation'
  );
  if p_payload ->> 'mode' is distinct from 'real'
     or p_payload ->> 'provider' is distinct from 'runway'
     or p_payload ->> 'model' is distinct from 'gen4_turbo'
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or sku_config is null then
    raise exception using
      errcode = '42501',
      message = 'real_generation_spend_confirmation_required';
  end if;
  duration_value := (sku_config ->> 'duration_seconds')::integer;
  estimated_cost_minor_value :=
    (sku_config ->> 'estimated_cost_minor')::integer;
  estimated_credits_value :=
    (sku_config ->> 'estimated_credits')::integer;
  spend_confirmation_value := p_payload ->> 'spend_confirmation';

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
      'duration_seconds', duration_value,
      'format', format_value,
      'ratio', ratio_value,
      'media_id', media_id_value,
      'assigned_to', assignee_id_value,
      'spend_confirmation', spend_confirmation_value,
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', estimated_cost_minor_value,
        'estimated_credits', estimated_credits_value,
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
    estimated_cost_minor_value,
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
      'duration_seconds', duration_value,
      'platform', platform_value,
      'destination_ref', destination_value,
      'spend_confirmation', spend_confirmation_value,
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', estimated_cost_minor_value,
        'estimated_credits', estimated_credits_value,
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
      'duration_seconds', duration_value,
      'estimated_cost_minor', estimated_cost_minor_value,
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
      'duration_seconds', duration_value,
      'ratio', ratio_value,
      'prompt_text', prompt_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', estimated_cost_minor_value,
      'estimated_credits', estimated_credits_value
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
      'duration_seconds', duration_value,
      'estimated_cost_minor', estimated_cost_minor_value,
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
  sku_config jsonb;
  duration_value integer;
  estimated_cost_minor_value integer;
  estimated_credits_value integer;
  spend_confirmation_value text;
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
  sku_config := content_factory_private.real_generation_sku_config(
    p_payload ->> 'model',
    p_payload -> 'duration_seconds',
    p_payload -> 'audio',
    p_payload ->> 'format',
    p_payload ->> 'spend_confirmation'
  );
  if p_payload ->> 'mode' is distinct from 'real'
     or p_payload ->> 'provider' is distinct from 'runway'
     or p_payload ->> 'model' is distinct from 'seedance2_fast'
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or sku_config is null then
    raise exception using
      errcode = '42501',
      message = 'real_generation_spend_confirmation_required';
  end if;
  duration_value := (sku_config ->> 'duration_seconds')::integer;
  estimated_cost_minor_value :=
    (sku_config ->> 'estimated_cost_minor')::integer;
  estimated_credits_value :=
    (sku_config ->> 'estimated_credits')::integer;
  spend_confirmation_value := p_payload ->> 'spend_confirmation';

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
      'duration_seconds', duration_value,
      'audio', true,
      'format', '9:16',
      'ratio', '720:1280',
      'media_id', media_id_value,
      'assigned_to', assignee_id_value,
      'spend_confirmation', spend_confirmation_value,
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', estimated_cost_minor_value,
        'estimated_credits', estimated_credits_value,
        'credit_unit_usd_minor', 1
      )
    ),
    content_factory_private.json_hash(request_payload),
    idempotency_key,
    'runway',
    'seedance2_fast',
    duration_value,
    true,
    estimated_cost_minor_value,
    estimated_credits_value,
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
    estimated_cost_minor_value,
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
      'duration_seconds', duration_value,
      'platform', platform_value,
      'destination_ref', destination_value,
      'spend_confirmation', spend_confirmation_value,
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', estimated_cost_minor_value,
        'estimated_credits', estimated_credits_value,
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
      'duration_seconds', duration_value,
      'audio', true,
      'estimated_cost_minor', estimated_cost_minor_value,
      'estimated_credits', estimated_credits_value,
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
      'duration_seconds', duration_value,
      'audio', true,
      'ratio', '720:1280',
      'prompt_text', prompt_value,
      'input_object_name', media_row.object_name,
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', estimated_cost_minor_value,
      'estimated_credits', estimated_credits_value
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
      'duration_seconds', duration_value,
      'audio', true,
      'estimated_cost_minor', estimated_cost_minor_value,
      'estimated_credits', estimated_credits_value,
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

create or replace function content_factory_private.creator_start_real_generation_campaign_v1(
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
  sku_config jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  if p_payload ? 'campaign_id' then
    campaign_id_value := content_factory_private.require_uuid(
      p_payload,
      'campaign_id'
    );
  else
    -- Compatibility for already deployed clients: omission is bound to the
    -- one immutable organization default, never to an unaccounted NULL.  The
    -- updated portal requires an explicit selector for every new real launch.
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

  if p_payload ->> 'model' = 'seedance2_fast' then
    result := content_factory_private.creator_start_seedance2_fast_8s(
      p_payload - 'campaign_id'
    );
  elsif p_payload ->> 'model' = 'gen4_turbo' then
    if p_payload ? 'audio'
       and p_payload -> 'audio' is distinct from 'false'::jsonb then
      raise exception using
        errcode = '42501',
        message = 'real_generation_spend_confirmation_required';
    end if;
    result := content_factory_private.creator_start_gen4_turbo_5s(
      p_payload - 'audio' - 'campaign_id'
    );
    sku_config := content_factory_private.real_generation_sku_config(
      p_payload ->> 'model',
      p_payload -> 'duration_seconds',
      coalesce(p_payload -> 'audio', 'false'::jsonb),
      p_payload ->> 'format',
      p_payload ->> 'spend_confirmation'
    );
    if sku_config is null then
      raise exception using
        errcode = '42501',
        message = 'real_generation_spend_confirmation_required';
    end if;
    result := jsonb_set(result, '{job,audio}', 'false'::jsonb, true);
    result := jsonb_set(
      result,
      '{job,estimated_credits}',
      sku_config -> 'estimated_credits',
      true
    );
  else
    raise exception using
      errcode = '42501',
      message = 'real_generation_spend_confirmation_required';
  end if;

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
  -- The older private command hash cannot include the wrapper-only field.
  -- This check makes a replay with the same idempotency key but another
  -- campaign fail instead of misreporting or reattributing the paid job.
  if stored_campaign_id is distinct from campaign_id_value then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  result := jsonb_set(
    result,
    '{job,campaign_id}',
    to_jsonb(campaign_id_value::text),
    true
  );
  result := jsonb_set(
    result,
    '{job,campaign_name}',
    to_jsonb(campaign_row.name),
    true
  );
  result := jsonb_set(
    result,
    '{batch,campaign_id}',
    to_jsonb(campaign_id_value::text),
    true
  );
  return result;
end;
$$;

create or replace function
  content_factory_private
    .creator_start_real_generation_pre_review_autostart_v11(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  model_value text;
  duration_value integer;
  brief_value text;
  product_name_value text;
  sku_value text;
  identity_requirement text;
  duration_requirement text;
  requirements text[];
  requirement_value text;
  spoken_value text;
  spoken_word_count integer;
  spoken_word_limit integer;
  result_value jsonb;
begin
  result_value := content_factory_private
    .creator_start_real_generation_pre_mode_prompt_v10(p_payload);
  p_payload := content_factory_private.require_payload(p_payload);
  model_value := lower(btrim(coalesce(p_payload ->> 'model', '')));
  if jsonb_typeof(p_payload -> 'duration_seconds') <> 'number'
     or p_payload ->> 'duration_seconds' !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'generation_mode_prompt_binding_invalid';
  end if;
  duration_value := (p_payload ->> 'duration_seconds')::integer;
  brief_value := btrim(coalesce(p_payload ->> 'brief', ''));
  product_name_value := btrim(coalesce(p_payload ->> 'product_name', ''));
  sku_value := btrim(coalesce(p_payload ->> 'sku', ''));
  requirements :=
    content_factory_private.generation_mode_prompt_requirements(model_value);
  identity_requirement := format(
    'Точный товар: %s, артикул %s.',
    product_name_value,
    sku_value
  );

  if requirements is null
     or product_name_value = ''
     or sku_value = ''
     or position(identity_requirement in brief_value) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_mode_prompt_binding_invalid';
  end if;
  foreach requirement_value in array requirements
  loop
    if position(requirement_value in brief_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
  end loop;

  if model_value = 'gen4_turbo' then
    duration_requirement := format(
      'Создай один непрерывный вертикальный ролик длительностью %s секунд.',
      duration_value
    );
  elsif model_value = 'seedance2_fast' then
    duration_requirement := format(
      'Создай один непрерывный вертикальный UGC-ролик длительностью %s секунд.',
      duration_value
    );
  else
    duration_requirement := null;
  end if;
  if duration_requirement is not null
     and position(duration_requirement in brief_value) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_mode_prompt_binding_invalid';
  end if;

  spoken_value := substring(
    brief_value
    from 'Реплика героя дословно:[[:space:]]*«([^»]+)»'
  );
  if model_value = 'seedance2_fast' then
    if spoken_value is null
       or position('[СОКРАТИТЕ' in spoken_value) > 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
    select count(*)::integer into spoken_word_count
    from regexp_matches(
      spoken_value,
      '[[:alnum:]]+([-’''][[:alnum:]]+)*',
      'g'
    );
    spoken_word_limit := greatest(
      10,
      least(42, floor(duration_value * 22.0 / 8.0)::integer)
    );
    if spoken_word_count not between 1 and spoken_word_limit then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
  elsif spoken_value is not null
        or position('Реплика героя дословно:' in brief_value) > 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_mode_prompt_binding_invalid';
  end if;

  return result_value;
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
declare
  sku_config jsonb;
  result_value jsonb;
begin
  result_value := content_factory_private
    .creator_start_real_generation_pre_flexible_duration_v12(p_payload);
  p_payload := content_factory_private.require_payload(p_payload);
  sku_config := content_factory_private.real_generation_sku_config(
    lower(btrim(coalesce(p_payload ->> 'model', ''))),
    p_payload -> 'duration_seconds',
    p_payload -> 'audio',
    btrim(coalesce(p_payload ->> 'format', '')),
    btrim(coalesce(p_payload ->> 'spend_confirmation', ''))
  );
  if sku_config is null then
    raise exception using
      errcode = '22023',
      message = 'real_generation_sku_invalid';
  end if;

  if result_value #> '{job,duration_seconds}'
       is distinct from sku_config -> 'duration_seconds'
     or result_value #> '{job,audio}'
       is distinct from sku_config -> 'audio'
     or result_value #> '{job,estimated_cost_minor}'
       is distinct from sku_config -> 'estimated_cost_minor'
     or result_value #> '{job,estimated_credits}'
       is distinct from sku_config -> 'estimated_credits'
     or result_value #>> '{job,model}'
       is distinct from sku_config ->> 'model' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_sku_binding_invalid';
  end if;
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.creator_start_gen4_turbo_5s(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.creator_start_seedance2_fast_8s(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.creator_start_real_generation_campaign_v1(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_review_autostart_v11(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
