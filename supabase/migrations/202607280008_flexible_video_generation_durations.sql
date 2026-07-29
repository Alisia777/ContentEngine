begin;

-- Video price and duration are one atomic SKU. Gen-4 Turbo is billed at
-- 5 credits/second for 2-10 seconds; Seedance 2 Fast is billed at
-- 29 credits/second for 4-15 seconds. Photo and dry-run contracts are
-- unchanged.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_sku_contract_v2_check;

alter table content_factory.generation_batches
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
          and duration_seconds between 2 and 10
          and not audio
          and estimated_cost_minor = duration_seconds * 5
          and estimated_credits = duration_seconds * 5
        )
        or (
          model = 'seedance2_fast'
          and duration_seconds between 4 and 15
          and audio
          and estimated_cost_minor = duration_seconds * 29
          and estimated_credits = duration_seconds * 29
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
          and coalesce(input -> 'audio', 'false'::jsonb) = 'false'::jsonb
          and case
            when jsonb_typeof(input -> 'duration_seconds') = 'number'
              and input ->> 'duration_seconds' ~ '^[0-9]+$'
            then (input ->> 'duration_seconds')::integer between 2 and 10
              and estimated_cost_minor =
                (input ->> 'duration_seconds')::integer * 5
            else false
          end
        )
        or (
          input ->> 'model' = 'seedance2_fast'
          and input -> 'audio' = 'true'::jsonb
          and case
            when jsonb_typeof(input -> 'duration_seconds') = 'number'
              and input ->> 'duration_seconds' ~ '^[0-9]+$'
            then (input ->> 'duration_seconds')::integer between 4 and 15
              and estimated_cost_minor =
                (input ->> 'duration_seconds')::integer * 29
            else false
          end
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
language plpgsql
immutable
set search_path = ''
as $$
declare
  model_value text := lower(btrim(coalesce(p_model, '')));
  duration_value integer;
  credits_value integer;
  usd_value text;
  expected_confirmation text;
begin
  if jsonb_typeof(p_duration) <> 'number'
     or p_duration #>> '{}' !~ '^[0-9]+$' then
    return null;
  end if;
  begin
    duration_value := (p_duration #>> '{}')::integer;
  exception when numeric_value_out_of_range then
    return null;
  end;

  if model_value = 'gen4_turbo'
     and duration_value between 2 and 10
     and coalesce(p_audio, 'false'::jsonb) = 'false'::jsonb
     and p_format in ('9:16', '16:9', '1:1') then
    credits_value := duration_value * 5;
    usd_value := to_char(
      credits_value::numeric / 100,
      'FM999999990.00'
    );
    expected_confirmation := format(
      'RUNWAY_GEN4_TURBO_%sS_USD_%s',
      duration_value,
      usd_value
    );
    if p_confirmation is distinct from expected_confirmation then
      return null;
    end if;
    return jsonb_build_object(
      'model', model_value,
      'duration_seconds', duration_value,
      'audio', false,
      'ratio', case p_format
        when '9:16' then '720:1280'
        when '16:9' then '1280:720'
        else '960:960'
      end,
      'estimated_cost_minor', credits_value,
      'estimated_credits', credits_value,
      'currency', 'USD'
    );
  end if;

  if model_value = 'seedance2_fast'
     and duration_value between 4 and 15
     and p_audio = 'true'::jsonb
     and p_format = '9:16' then
    credits_value := duration_value * 29;
    usd_value := to_char(
      credits_value::numeric / 100,
      'FM999999990.00'
    );
    expected_confirmation := format(
      'RUNWAY_SEEDANCE2_FAST_%sS_AUDIO_USD_%s',
      duration_value,
      usd_value
    );
    if p_confirmation is distinct from expected_confirmation then
      return null;
    end if;
    return jsonb_build_object(
      'model', model_value,
      'duration_seconds', duration_value,
      'audio', true,
      'ratio', '720:1280',
      'estimated_cost_minor', credits_value,
      'estimated_credits', credits_value,
      'currency', 'USD'
    );
  end if;

  if model_value = 'seedream5_lite'
     and duration_value = 0
     and coalesce(p_audio, 'false'::jsonb) = 'false'::jsonb
     and p_format = '1:1'
     and p_confirmation =
       'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04' then
    return jsonb_build_object(
      'model', model_value,
      'duration_seconds', 0,
      'audio', false,
      'ratio', '2048:2048',
      'estimated_cost_minor', 4,
      'estimated_credits', 4,
      'currency', 'USD'
    );
  end if;
  return null;
end;
$$;

revoke all on function content_factory_private.real_generation_sku_config(
  text, jsonb, jsonb, text, text
) from public, anon, authenticated, service_role;

-- Duration is checked against the payload separately so the reusable
-- requirements list no longer hard-codes the historical 5/8 second defaults.
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
  common_requirements text[] := array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.'
  ]::text[];
begin
  return common_requirements || case lower(btrim(coalesce(p_model, '')))
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
    else null::text[]
  end;
end;
$$;

-- Replace the private v10 prompt layer in place because the public v11
-- consent layer calls it by name. All v1-v9 monetary, identity, learning,
-- repair and policy-snapshot gates remain below it.
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
begin
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

  return content_factory_private
    .creator_start_real_generation_pre_mode_prompt_v10(p_payload);
end;
$$;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_review_autostart_v11(jsonb)
  from public, anon, authenticated, service_role;

-- The outer v12 layer binds payload and returned job to the same dynamic SKU.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_flexible_duration_v12;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_flexible_duration_v12(jsonb)
  from public, anon, authenticated, service_role;

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

  result_value := content_factory_private
    .creator_start_real_generation_pre_flexible_duration_v12(p_payload);
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

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

-- Readiness receipts are keyed by model and duration. Historical receipts
-- are retained at their old default durations.
drop trigger if exists generation_provider_readiness_receipt_append_only
  on content_factory.generation_provider_readiness_receipts;

alter table content_factory.generation_provider_readiness_receipts
  add column if not exists duration_seconds integer;

update content_factory.generation_provider_readiness_receipts
set duration_seconds = case model
  when 'gen4_turbo' then 5
  when 'seedance2_fast' then 8
  when 'seedream5_lite' then 0
end
where duration_seconds is null;

do $$
declare
  constraint_name text;
begin
  for constraint_name in
    select constraint_row.conname
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_provider_readiness_receipts'::regclass
      and constraint_row.contype = 'c'
      and position(
        'estimated_credits'
        in lower(pg_catalog.pg_get_constraintdef(constraint_row.oid))
      ) > 0
  loop
    execute format(
      'alter table content_factory.generation_provider_readiness_receipts drop constraint %I',
      constraint_name
    );
  end loop;
end;
$$;

alter table content_factory.generation_provider_readiness_receipts
  alter column duration_seconds set not null,
  add constraint generation_provider_readiness_duration_credits_check
  check (
    (
      model = 'gen4_turbo'
      and duration_seconds between 2 and 10
      and estimated_credits = duration_seconds * 5
    )
    or (
      model = 'seedance2_fast'
      and duration_seconds between 4 and 15
      and estimated_credits = duration_seconds * 29
    )
    or (
      model = 'seedream5_lite'
      and duration_seconds = 0
      and estimated_credits = 4
    )
  );

drop index if exists
  content_factory.generation_provider_readiness_receipts_latest_idx;
create index generation_provider_readiness_receipts_latest_idx
  on content_factory.generation_provider_readiness_receipts (
    organization_id,
    provider,
    model,
    duration_seconds,
    checked_at desc,
    id desc
  );

create trigger generation_provider_readiness_receipt_append_only
before update or delete
  on content_factory.generation_provider_readiness_receipts
for each row execute function
  content_factory_private
    .guard_generation_provider_readiness_receipt_append_only();

create or replace function
  public.system_record_generation_provider_readiness(
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
  organization_id uuid;
  checked_by_value uuid;
  provider_value text;
  model_value text;
  duration_value integer;
  ready_value boolean;
  estimated_credits_value integer;
  expected_credits integer;
  balance_sufficient_value boolean;
  model_available_value boolean;
  daily_quota_available_value boolean;
  failure_code_value text;
  learning_gate_version_value text;
  checked_at_value timestamptz;
  expires_at_value timestamptz;
  receipt_body jsonb;
  receipt_hash_value text;
  receipt_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id',
    'checked_by',
    'provider',
    'model',
    'duration_seconds',
    'ready',
    'estimated_credits',
    'balance_sufficient',
    'model_available',
    'daily_quota_available',
    'failure_code',
    'learning_gate_version'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'organization_id'
       and p_payload ? 'checked_by'
       and p_payload ? 'provider'
       and p_payload ? 'model'
       and p_payload ? 'duration_seconds'
       and p_payload ? 'ready'
       and p_payload ? 'estimated_credits'
       and p_payload ? 'balance_sufficient'
       and p_payload ? 'model_available'
       and p_payload ? 'daily_quota_available'
       and p_payload ? 'failure_code'
       and p_payload ? 'learning_gate_version'
     )
     or jsonb_typeof(p_payload -> 'duration_seconds') <> 'number'
     or p_payload ->> 'duration_seconds' !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'ready') <> 'boolean'
     or jsonb_typeof(p_payload -> 'estimated_credits') <> 'number'
     or p_payload ->> 'estimated_credits' !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'balance_sufficient') <> 'boolean'
     or jsonb_typeof(p_payload -> 'model_available') <> 'boolean'
     or jsonb_typeof(p_payload -> 'daily_quota_available') <> 'boolean'
     or jsonb_typeof(p_payload -> 'failure_code')
          not in ('string', 'null') then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end if;

  organization_id :=
    content_factory_private.require_uuid(p_payload, 'organization_id');
  checked_by_value :=
    content_factory_private.require_uuid(p_payload, 'checked_by');
  provider_value :=
    lower(btrim(coalesce(p_payload ->> 'provider', '')));
  model_value :=
    lower(btrim(coalesce(p_payload ->> 'model', '')));
  learning_gate_version_value :=
    btrim(coalesce(p_payload ->> 'learning_gate_version', ''));
  ready_value := (p_payload ->> 'ready')::boolean;
  balance_sufficient_value :=
    (p_payload ->> 'balance_sufficient')::boolean;
  model_available_value :=
    (p_payload ->> 'model_available')::boolean;
  daily_quota_available_value :=
    (p_payload ->> 'daily_quota_available')::boolean;
  begin
    duration_value := (p_payload ->> 'duration_seconds')::integer;
    estimated_credits_value :=
      (p_payload ->> 'estimated_credits')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end;
  expected_credits := case
    when model_value = 'gen4_turbo'
      and duration_value between 2 and 10
      then duration_value * 5
    when model_value = 'seedance2_fast'
      and duration_value between 4 and 15
      then duration_value * 29
    when model_value = 'seedream5_lite'
      and duration_value = 0
      then 4
    else null
  end;
  failure_code_value := nullif(
    btrim(coalesce(p_payload ->> 'failure_code', '')),
    ''
  );

  if provider_value <> 'runway'
     or expected_credits is null
     or estimated_credits_value <> expected_credits
     or learning_gate_version_value !~
       '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]v[0-9]+$'
     or ready_value is distinct from (
       balance_sufficient_value
       and model_available_value
       and daily_quota_available_value
     )
     or (ready_value and failure_code_value is not null)
     or (
       not ready_value
       and failure_code_value not in (
         'provider_configuration_error',
         'provider_authentication_failed',
         'provider_credits_unavailable',
         'provider_rate_limited',
         'provider_request_rejected',
         'provider_request_failed',
         'provider_response_invalid'
       )
     )
     or not exists (
       select 1
       from content_factory.memberships membership
       where membership.organization_id = organization_id
         and membership.profile_id = checked_by_value
         and membership.status = 'active'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end if;

  checked_at_value := clock_timestamp();
  expires_at_value := checked_at_value + interval '15 minutes';
  receipt_body := jsonb_build_object(
    'version', 'generation-provider-readiness-receipt-v2',
    'organization_id', organization_id,
    'provider', provider_value,
    'model', model_value,
    'duration_seconds', duration_value,
    'ready', ready_value,
    'estimated_credits', estimated_credits_value,
    'balance_sufficient', balance_sufficient_value,
    'model_available', model_available_value,
    'daily_quota_available', daily_quota_available_value,
    'failure_code', failure_code_value,
    'learning_gate_version', learning_gate_version_value,
    'checked_at', checked_at_value,
    'expires_at', expires_at_value
  );
  receipt_hash_value :=
    content_factory_private.json_hash(receipt_body);

  insert into content_factory.generation_provider_readiness_receipts (
    organization_id,
    provider,
    model,
    duration_seconds,
    ready,
    estimated_credits,
    balance_sufficient,
    model_available,
    daily_quota_available,
    failure_code,
    learning_gate_version,
    checked_by,
    checked_at,
    expires_at,
    receipt_hash
  ) values (
    organization_id,
    provider_value,
    model_value,
    duration_value,
    ready_value,
    estimated_credits_value,
    balance_sufficient_value,
    model_available_value,
    daily_quota_available_value,
    failure_code_value,
    learning_gate_version_value,
    checked_by_value,
    checked_at_value,
    expires_at_value,
    receipt_hash_value
  )
  returning id into receipt_id;

  return receipt_body || jsonb_build_object(
    'receipt_id', receipt_id,
    'receipt_hash', receipt_hash_value,
    'status', case when ready_value then 'ready' else 'blocked' end,
    'fresh', true
  );
end;
$$;

revoke all on function
  public.system_record_generation_provider_readiness(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_record_generation_provider_readiness(jsonb)
  to service_role;

create or replace function
  content_factory_private.generation_provider_readiness(
    p_organization_id uuid,
    p_evaluated_at timestamptz default now()
  )
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with skus(model, duration_seconds, estimated_credits, position) as (
    values
      ('seedream5_lite'::text, 0, 4, 1),
      ('gen4_turbo'::text, 2, 10, 2),
      ('gen4_turbo'::text, 5, 25, 3),
      ('gen4_turbo'::text, 8, 40, 4),
      ('gen4_turbo'::text, 10, 50, 5),
      ('seedance2_fast'::text, 4, 116, 6),
      ('seedance2_fast'::text, 8, 232, 7),
      ('seedance2_fast'::text, 12, 348, 8),
      ('seedance2_fast'::text, 15, 435, 9)
  ),
  latest as (
    select
      sku.model,
      sku.duration_seconds,
      sku.estimated_credits,
      sku.position,
      receipt.id as receipt_id,
      receipt.ready,
      receipt.balance_sufficient,
      receipt.model_available,
      receipt.daily_quota_available,
      receipt.failure_code,
      receipt.learning_gate_version,
      receipt.checked_at,
      receipt.expires_at,
      receipt.receipt_hash
    from skus sku
    left join lateral (
      select candidate.*
      from content_factory.generation_provider_readiness_receipts candidate
      where candidate.organization_id = p_organization_id
        and candidate.provider = 'runway'
        and candidate.model = sku.model
        and candidate.duration_seconds = sku.duration_seconds
      order by candidate.checked_at desc, candidate.id desc
      limit 1
    ) receipt on true
  )
  select coalesce(
    jsonb_agg(
      jsonb_strip_nulls(jsonb_build_object(
        'provider', 'runway',
        'model', model,
        'duration_seconds', duration_seconds,
        'receipt_version',
          'generation-provider-readiness-receipt-v2',
        'status', case
          when receipt_id is null then 'unknown'
          when expires_at <= p_evaluated_at then 'stale'
          when ready then 'ready'
          else 'blocked'
        end,
        'ready', coalesce(
          ready and expires_at > p_evaluated_at,
          false
        ),
        'fresh', coalesce(expires_at > p_evaluated_at, false),
        'estimated_credits', estimated_credits,
        'balance_sufficient', balance_sufficient,
        'model_available', model_available,
        'daily_quota_available', daily_quota_available,
        'failure_code', failure_code,
        'reason_code', case
          when receipt_id is null then 'provider_readiness_receipt_missing'
          when expires_at <= p_evaluated_at
            then 'provider_readiness_receipt_stale'
          when ready then 'provider_ready'
          else failure_code
        end,
        'learning_gate_version', learning_gate_version,
        'checked_at', checked_at,
        'expires_at', expires_at,
        'receipt_id', receipt_id,
        'receipt_hash', receipt_hash
      ))
      order by position
    ),
    '[]'::jsonb
  )
  from latest;
$$;

revoke all on function
  content_factory_private.generation_provider_readiness(uuid, timestamptz)
  from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';

commit;
