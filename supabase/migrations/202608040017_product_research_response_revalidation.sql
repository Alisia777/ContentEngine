begin;

-- A completed paid provider response can outlive a local parser version.  Let
-- the worker re-run validation against the already bound response while it is
-- still retrievable, without creating another provider attempt or POST.
create or replace function content_factory_private.guard_research_run_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
#variable_conflict use_variable
declare
  response_revalidation boolean :=
    old.status = 'failed'
    and old.error_code = 'provider_response_invalid'
    and new.status = 'processing'
    and coalesce(
      current_setting(
        'content_factory.product_research_response_revalidation', true
      ) = 'on',
      false
    );
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000', message = 'research_run_deletion_forbidden';
  end if;
  if new.organization_id <> old.organization_id
     or new.product_id <> old.product_id
     or new.created_by <> old.created_by
     or new.input <> old.input
     or new.request_hash <> old.request_hash
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using errcode = '55000', message = 'research_run_identity_immutable';
  end if;
  if old.status in ('completed', 'failed', 'cancelled')
     and new is distinct from old
     and not response_revalidation then
    raise exception using errcode = '55000', message = 'research_run_terminal';
  end if;
  if new.status <> old.status and not (
    (old.status = 'queued' and new.status in ('processing', 'cancelled'))
    or (old.status = 'processing' and new.status in ('completed', 'failed', 'cancelled'))
    or response_revalidation
  ) then
    raise exception using errcode = '55000', message = 'research_status_transition_invalid';
  end if;
  if old.status = 'queued' and new.status = 'processing' then
    new.started_at := coalesce(new.started_at, now());
    new.lease_expires_at := coalesce(new.lease_expires_at, now() + interval '5 minutes');
  elsif response_revalidation then
    if new.error_code is not null
       or new.error_message is not null
       or new.completion_hash is not null
       or new.finished_at is not null
       or new.started_at is distinct from old.started_at
       or new.summary <> '{}'::jsonb
       or new.lease_expires_at is null
       or new.lease_expires_at <= clock_timestamp()
       or new.lease_expires_at > clock_timestamp() + interval '2 minutes' then
      raise exception using
        errcode = '55000', message = 'research_response_revalidation_invalid';
    end if;
  end if;
  if new.status in ('completed', 'failed', 'cancelled') and new.status <> old.status then
    new.finished_at := coalesce(new.finished_at, now());
    new.lease_expires_at := null;
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create or replace function public.system_revalidate_product_research_response(
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
  run_row content_factory.product_research_runs%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  latest_provider_status text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'run_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_response_revalidation_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;
  if run_row.status <> 'failed'
     or run_row.error_code <> 'provider_response_invalid' then
    return jsonb_build_object(
      'ok', false,
      'code', 'research_response_revalidation_not_allowed',
      'run_id', run_row.id,
      'status', run_row.status
    );
  end if;

  select response.* into response_row
  from content_factory.research_provider_response_bindings response
  where response.organization_id = run_row.organization_id
    and response.run_id = run_row.id;
  if response_row.id is not null then
    select receipt.provider_status into latest_provider_status
    from content_factory.research_provider_response_receipts receipt
    where receipt.organization_id = response_row.organization_id
      and receipt.response_binding_id = response_row.id
    order by receipt.checked_at desc, receipt.id desc
    limit 1;
  end if;
  if response_row.id is null
     or response_row.accepted_at <= clock_timestamp() - interval '8 minutes'
     or coalesce(latest_provider_status, response_row.initial_status) <> 'completed' then
    return jsonb_build_object(
      'ok', false,
      'code', 'provider_response_expired',
      'run_id', run_row.id,
      'status', run_row.status
    );
  end if;

  perform set_config(
    'content_factory.product_research_response_revalidation', 'on', true
  );
  update content_factory.product_research_runs run
  set status = 'processing',
      summary = '{}'::jsonb,
      error_code = null,
      error_message = null,
      completion_hash = null,
      finished_at = null,
      lease_expires_at = least(
        response_row.accepted_at + interval '9 minutes',
        clock_timestamp() + interval '90 seconds'
      )
  where run.id = run_row.id;

  return jsonb_build_object(
    'ok', true,
    'code', 'research_response_revalidation_started',
    'run_id', run_row.id,
    'status', 'processing',
    'provider_attempt_created', false,
    'provider_response_id', response_row.provider_response_id
  );
end;
$$;

revoke all on function public.system_revalidate_product_research_response(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_revalidate_product_research_response(jsonb)
  to service_role;

commit;
