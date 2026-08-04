begin;

-- A paid research request is submitted once.  OpenAI's background response id
-- is then the only durable handle used by browser and worker status checks.
-- Neither table stores prompts, response bodies, API keys or bearer tokens.
create table if not exists content_factory.research_provider_response_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  attempt_id uuid not null,
  provider_key text not null,
  adapter_version text not null,
  provider_response_id text not null check (
    length(provider_response_id) between 8 and 255
    and provider_response_id ~ '^resp_[A-Za-z0-9_-]+$'
  ),
  initial_status text not null check (
    initial_status in (
      'queued', 'in_progress', 'completed', 'failed', 'cancelled', 'incomplete'
    )
  ),
  accepted_at timestamptz not null default clock_timestamp(),
  response_hash text not null check (response_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, run_id),
  unique (provider_key, provider_response_id),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (
    organization_id, run_id, attempt_id, provider_key, adapter_version
  ) references content_factory.research_run_provider_bindings(
    organization_id, run_id, id, provider_key, adapter_version
  )
);

create table if not exists content_factory.research_provider_response_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  response_binding_id uuid not null,
  attempt_id uuid not null,
  provider_key text not null,
  adapter_version text not null,
  provider_response_id text not null,
  provider_status text not null check (
    provider_status in (
      'queued', 'in_progress', 'completed', 'failed', 'cancelled', 'incomplete'
    )
  ),
  checked_at timestamptz not null default clock_timestamp(),
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, response_binding_id, receipt_hash),
  foreign key (organization_id, response_binding_id)
    references content_factory.research_provider_response_bindings(
      organization_id, id
    ),
  foreign key (
    organization_id, run_id, attempt_id, provider_key, adapter_version
  ) references content_factory.research_run_provider_bindings(
    organization_id, run_id, id, provider_key, adapter_version
  )
);

create index if not exists research_provider_response_poll_idx
  on content_factory.research_provider_response_bindings (
    organization_id, accepted_at, run_id
  );
create index if not exists research_provider_response_receipt_latest_idx
  on content_factory.research_provider_response_receipts (
    organization_id, run_id, checked_at desc, id desc
  );

alter table content_factory.research_provider_response_bindings
  enable row level security;
alter table content_factory.research_provider_response_receipts
  enable row level security;
revoke all on content_factory.research_provider_response_bindings
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_provider_response_receipts
  from public, anon, authenticated, service_role;
grant all on content_factory.research_provider_response_bindings to service_role;
grant all on content_factory.research_provider_response_receipts to service_role;

drop trigger if exists research_provider_response_binding_immutable
  on content_factory.research_provider_response_bindings;
create trigger research_provider_response_binding_immutable
before update or delete on content_factory.research_provider_response_bindings
for each row execute function
  content_factory_private.reject_research_provider_mutation();

drop trigger if exists research_provider_response_receipt_append_only
  on content_factory.research_provider_response_receipts;
create trigger research_provider_response_receipt_append_only
before update or delete on content_factory.research_provider_response_receipts
for each row execute function
  content_factory_private.reject_research_provider_mutation();

-- Preserve every existing claim/recompute/provider guard and only lengthen the
-- local lease enough to poll a store=false background Response.  The provider
-- response itself remains the source of truth and the lease is still bounded.
alter function public.system_claim_product_research(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_claim_product_research(jsonb)
  rename to system_claim_product_research_pre_background_v417;

create or replace function public.system_claim_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result_value jsonb;
  run_id_value uuid;
  lease_value timestamptz;
begin
  result_value := content_factory_private
    .system_claim_product_research_pre_background_v417(p_payload);
  if result_value -> 'claimed' = 'true'::jsonb
     and result_value #>> '{run,status}' = 'processing' then
    run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
    -- OpenAI keeps a store=false background response for roughly ten minutes.
    -- Use a one-minute safety buffer so the last GET remains retrievable.
    lease_value := clock_timestamp() + interval '9 minutes';
    update content_factory.product_research_runs run
    set lease_expires_at = greatest(run.lease_expires_at, lease_value)
    where run.id = run_id_value
      and run.status = 'processing'
    returning run.lease_expires_at into lease_value;
    if lease_value is not null then
      result_value := jsonb_set(
        result_value,
        '{run,lease_expires_at}',
        to_jsonb(lease_value),
        true
      );
    end if;
  end if;
  return result_value;
end;
$$;

create or replace function public.system_bind_research_provider_response(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  attempt_id_value uuid;
  response_id_value text;
  status_value text;
  run_row content_factory.product_research_runs%rowtype;
  attempt_row content_factory.research_run_provider_bindings%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  accepted_at_value timestamptz := clock_timestamp();
  response_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'run_id', 'attempt_id', 'provider_response_id', 'provider_status'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_provider_response_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  attempt_id_value := content_factory_private.require_uuid(p_payload, 'attempt_id');
  response_id_value := content_factory_private.require_text(
    p_payload, 'provider_response_id', 8, 255
  );
  status_value := content_factory_private.require_text(
    p_payload, 'provider_status', 5, 32
  );
  if response_id_value !~ '^resp_[A-Za-z0-9_-]+$'
     or status_value not in (
       'queued', 'in_progress', 'completed', 'failed', 'cancelled', 'incomplete'
     ) then
    raise exception using
      errcode = '22023', message = 'research_provider_response_payload_invalid';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null or run_row.status <> 'processing'
     or run_row.lease_expires_at is null
     or run_row.lease_expires_at <= clock_timestamp() then
    raise exception using
      errcode = '55000', message = 'research_provider_response_run_inactive';
  end if;
  select binding.* into attempt_row
  from content_factory.research_run_provider_bindings binding
  where binding.organization_id = run_row.organization_id
    and binding.run_id = run_row.id
    and binding.id = attempt_id_value;
  if attempt_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_provider_attempt_not_found';
  end if;

  response_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-provider-background-response-v1',
    'organization_id', run_row.organization_id,
    'run_id', run_row.id,
    'attempt_id', attempt_row.id,
    'provider_key', attempt_row.provider_key,
    'adapter_version', attempt_row.adapter_version,
    'provider_response_id', response_id_value,
    'initial_status', status_value
  ));
  insert into content_factory.research_provider_response_bindings (
    organization_id, run_id, attempt_id, provider_key, adapter_version,
    provider_response_id, initial_status, accepted_at, response_hash
  ) values (
    run_row.organization_id, run_row.id, attempt_row.id,
    attempt_row.provider_key, attempt_row.adapter_version,
    response_id_value, status_value, accepted_at_value, response_hash_value
  )
  on conflict (organization_id, run_id) do nothing
  returning * into response_row;
  if response_row.id is null then
    select response.* into response_row
    from content_factory.research_provider_response_bindings response
    where response.organization_id = run_row.organization_id
      and response.run_id = run_row.id;
  end if;
  if response_row.id is null
     or response_row.attempt_id <> attempt_row.id
     or response_row.provider_response_id <> response_id_value
     or response_row.response_hash <> response_hash_value then
    raise exception using
      errcode = '23505', message = 'research_provider_response_conflict';
  end if;
  return jsonb_build_object(
    'ok', true,
    'response_binding_id', response_row.id,
    'attempt_id', response_row.attempt_id,
    'provider_response_id', response_row.provider_response_id,
    'provider_status', response_row.initial_status,
    'accepted_at', response_row.accepted_at
  );
end;
$$;

create or replace function public.system_read_research_provider_response(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  attempt_row content_factory.research_run_provider_bindings%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  latest_status text;
  latest_checked_at timestamptz;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'run_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_provider_response_read_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value;
  if run_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  select binding.* into attempt_row
  from content_factory.research_run_provider_bindings binding
  where binding.organization_id = run_row.organization_id
    and binding.run_id = run_row.id;
  if attempt_row.id is not null then
    select response.* into response_row
    from content_factory.research_provider_response_bindings response
    where response.organization_id = run_row.organization_id
      and response.run_id = run_row.id;
  end if;
  if response_row.id is not null then
    select receipt.provider_status, receipt.checked_at
    into latest_status, latest_checked_at
    from content_factory.research_provider_response_receipts receipt
    where receipt.organization_id = response_row.organization_id
      and receipt.response_binding_id = response_row.id
    order by receipt.checked_at desc, receipt.id desc
    limit 1;
  end if;
  return jsonb_build_object(
    'ok', true,
    'run_id', run_row.id,
    'run_status', run_row.status,
    'lease_expires_at', run_row.lease_expires_at,
    'attempt', case when attempt_row.id is null then null else
      jsonb_build_object(
        'attempt_id', attempt_row.id,
        'model', attempt_row.model,
        'provider_key', attempt_row.provider_key,
        'adapter_version', attempt_row.adapter_version,
        'bound_at', attempt_row.bound_at
      ) end,
    'response', case when response_row.id is null then null else
      jsonb_build_object(
        'response_binding_id', response_row.id,
        'provider_response_id', response_row.provider_response_id,
        'provider_status', coalesce(latest_status, response_row.initial_status),
        'initial_status', response_row.initial_status,
        'accepted_at', response_row.accepted_at,
        'last_checked_at', latest_checked_at
      ) end
  );
end;
$$;

create or replace function public.system_record_research_provider_response_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  attempt_id_value uuid;
  response_id_value text;
  status_value text;
  run_row content_factory.product_research_runs%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  checked_at_value timestamptz := clock_timestamp();
  lease_value timestamptz;
  receipt_hash_value text;
  receipt_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'run_id', 'attempt_id', 'provider_response_id', 'provider_status'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_provider_response_status_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  attempt_id_value := content_factory_private.require_uuid(p_payload, 'attempt_id');
  response_id_value := content_factory_private.require_text(
    p_payload, 'provider_response_id', 8, 255
  );
  status_value := content_factory_private.require_text(
    p_payload, 'provider_status', 5, 32
  );
  if response_id_value !~ '^resp_[A-Za-z0-9_-]+$'
     or status_value not in (
       'queued', 'in_progress', 'completed', 'failed', 'cancelled', 'incomplete'
     ) then
    raise exception using
      errcode = '22023', message = 'research_provider_response_status_invalid';
  end if;
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  select response.* into response_row
  from content_factory.research_provider_response_bindings response
  where response.organization_id = run_row.organization_id
    and response.run_id = run_row.id
    and response.attempt_id = attempt_id_value
    and response.provider_response_id = response_id_value;
  if response_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_provider_response_not_found';
  end if;

  if status_value in ('queued', 'in_progress')
     and run_row.status = 'processing'
     and response_row.accepted_at + interval '9 minutes' > checked_at_value then
    lease_value := least(
      response_row.accepted_at + interval '9 minutes',
      checked_at_value + interval '5 minutes'
    );
    update content_factory.product_research_runs run
    set lease_expires_at = greatest(run.lease_expires_at, lease_value)
    where run.organization_id = run_row.organization_id
      and run.id = run_row.id
      and run.status = 'processing'
    returning run.lease_expires_at into lease_value;
  else
    lease_value := run_row.lease_expires_at;
  end if;

  receipt_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-provider-background-status-v1',
    'organization_id', run_row.organization_id,
    'run_id', run_row.id,
    'response_binding_id', response_row.id,
    'attempt_id', response_row.attempt_id,
    'provider_response_id', response_row.provider_response_id,
    'provider_status', status_value,
    'checked_at', checked_at_value
  ));
  insert into content_factory.research_provider_response_receipts (
    organization_id, run_id, response_binding_id, attempt_id,
    provider_key, adapter_version, provider_response_id,
    provider_status, checked_at, receipt_hash
  ) values (
    run_row.organization_id, run_row.id, response_row.id,
    response_row.attempt_id, response_row.provider_key,
    response_row.adapter_version, response_row.provider_response_id,
    status_value, checked_at_value, receipt_hash_value
  )
  returning id into receipt_id_value;
  return jsonb_build_object(
    'ok', true,
    'receipt_id', receipt_id_value,
    'provider_status', status_value,
    'checked_at', checked_at_value,
    'lease_expires_at', lease_value
  );
end;
$$;

-- The legacy browser status RPC owns an expiry update of its own. Rewrite that
-- transition before the general mutation guard sees it: once a provider
-- attempt exists, an expired lease is an unknown paid outcome, never proof
-- that it is safe to repeat the POST. Because this is a BEFORE trigger, the
-- legacy `update ... returning` also returns the corrected code to the browser.
create or replace function
  content_factory_private.classify_attempted_research_expiry()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  unknown_message_value text :=
    'Провайдер мог принять платный запрос, но результат не подтверждён. Автоматического повтора платного запроса нет.';
begin
  if old.status = 'processing'
     and new.status = 'failed'
     and new.error_code = 'processing_lease_expired'
     and exists (
       select 1
       from content_factory.research_run_provider_bindings attempt
       where attempt.organization_id = old.organization_id
         and attempt.run_id = old.id
     ) then
    new.error_code := 'provider_outcome_unknown';
    new.error_message := unknown_message_value;
    new.completion_hash := content_factory_private.json_hash(
      jsonb_build_object(
        'status', 'failed',
        'error_code', 'provider_outcome_unknown',
        'error_message', unknown_message_value
      )
    );
  end if;
  return new;
end;
$$;

drop trigger if exists classify_attempted_research_expiry
  on content_factory.product_research_runs;
create trigger classify_attempted_research_expiry
before update on content_factory.product_research_runs
for each row execute function
  content_factory_private.classify_attempted_research_expiry();

-- OpenAI retains store=false background Responses for only a short window.
-- Keep the number of actually submitted requests in the shared provider pool
-- within the four GET slots polled every worker tick. Extra browser starts stay queued:
-- no provider POST and no charge occurs until capacity is available.
create or replace function
  content_factory_private.enforce_research_processing_capacity()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  active_count_value integer;
begin
  if old.status = 'queued' and new.status = 'processing' then
    perform pg_advisory_xact_lock(
      hashtext('contentengine_openai_research_pool'),
      hashtext('product_research_processing_capacity_v417')
    );
    select count(*)::integer into active_count_value
    from content_factory.product_research_runs active
    where active.status = 'processing'
      and active.id <> old.id;
    if active_count_value >= 4 then
      raise exception using
        errcode = '55000',
        message = 'research_processing_capacity_full';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists enforce_research_processing_capacity
  on content_factory.product_research_runs;
create trigger enforce_research_processing_capacity
before update on content_factory.product_research_runs
for each row execute function
  content_factory_private.enforce_research_processing_capacity();

-- The legacy watchdog labels every expired research lease as a definite local
-- timeout. Once a provider attempt exists that is financially unsafe: the POST
-- may already have been accepted. Classify those rows as outcome-unknown before
-- delegating the remaining review/research reconciliation, so neither UI nor a
-- later worker can suggest an ordinary paid retry.
alter function public.system_reconcile_background_leases(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.system_reconcile_background_leases(jsonb)
  rename to system_reconcile_background_leases_pre_response_v417;

create or replace function public.system_reconcile_background_leases(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer := 50;
  unknown_count_value integer := 0;
  delegated_value jsonb;
  delegated_research_count integer := 0;
  unknown_message_value text :=
    'Провайдер мог принять платный запрос, но результат не подтверждён. Автоматического повтора платного запроса нет.';
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 1024
     or p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'background_reconcile_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    begin
      limit_value := (p_payload ->> 'limit')::integer;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023', message = 'background_reconcile_limit_invalid';
    end;
  end if;
  if limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'background_reconcile_limit_invalid';
  end if;

  with expired as (
    select run.id
    from content_factory.product_research_runs run
    where run.status = 'processing'
      and run.lease_expires_at <= clock_timestamp()
      and exists (
        select 1
        from content_factory.research_run_provider_bindings attempt
        where attempt.organization_id = run.organization_id
          and attempt.run_id = run.id
      )
    order by run.lease_expires_at, run.id
    for update skip locked
    limit limit_value
  )
  update content_factory.product_research_runs run
  set status = 'failed',
      error_code = 'provider_outcome_unknown',
      error_message = unknown_message_value,
      completion_hash = content_factory_private.json_hash(
        jsonb_build_object(
          'status', 'failed',
          'error_code', 'provider_outcome_unknown',
          'error_message', unknown_message_value
        )
      )
  from expired
  where run.id = expired.id
    and run.status = 'processing'
    and run.lease_expires_at <= clock_timestamp();
  get diagnostics unknown_count_value = row_count;

  delegated_value := content_factory_private
    .system_reconcile_background_leases_pre_response_v417(p_payload);
  if delegated_value -> 'ok' is distinct from 'true'::jsonb
     or jsonb_typeof(delegated_value #> '{expired}') <> 'object' then
    raise exception using
      errcode = '55000', message = 'background_reconcile_response_invalid';
  end if;
  begin
    delegated_research_count := coalesce(
      (delegated_value #>> '{expired,research}')::integer, 0
    );
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '55000', message = 'background_reconcile_response_invalid';
  end;
  return jsonb_set(
    delegated_value || jsonb_build_object(
      'research_outcome_unknown', unknown_count_value
    ),
    '{expired,research}',
    to_jsonb(delegated_research_count + unknown_count_value),
    true
  );
end;
$$;

revoke all on function
  content_factory_private.system_claim_product_research_pre_background_v417(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_claim_product_research(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_bind_research_provider_response(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_read_research_provider_response(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_record_research_provider_response_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private
    .system_reconcile_background_leases_pre_response_v417(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.classify_attempted_research_expiry()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.enforce_research_processing_capacity()
  from public, anon, authenticated, service_role;
revoke all on function public.system_reconcile_background_leases(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_claim_product_research(jsonb)
  to service_role;
grant execute on function public.system_bind_research_provider_response(jsonb)
  to service_role;
grant execute on function public.system_read_research_provider_response(jsonb)
  to service_role;
grant execute on function
  public.system_record_research_provider_response_status(jsonb)
  to service_role;
grant execute on function public.system_reconcile_background_leases(jsonb)
  to service_role;

notify pgrst, 'reload schema';

commit;
