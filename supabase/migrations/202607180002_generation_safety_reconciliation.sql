begin;

-- P1 remediation for paid generation.  Keep the previously audited command
-- implementations private and place narrow fail-closed adapters in front of
-- them.  This preserves idempotency and campaign accounting while ensuring a
-- platform that cannot pass the downstream approval gate is rejected before
-- a job, reservation, or provider charge can be created.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_campaign_v1;
revoke all on function
  content_factory_private.creator_start_real_generation_campaign_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if lower(btrim(coalesce(p_payload ->> 'platform', ''))) = 'instagram' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_platform_not_supported';
  end if;
  return content_factory_private.creator_start_real_generation_campaign_v1(
    p_payload
  );
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

-- Add one append-only compensating event.  Historical settled entries are
-- never rewritten: a refundable provider failure gets a negative committed
-- delta whose amount exactly offsets the original estimate.
alter table content_factory.generation_spend_ledger
  drop constraint if exists generation_spend_ledger_event_type_check,
  drop constraint if exists generation_spend_ledger_committed_delta_minor_check;

do $$
declare
  constraint_row record;
begin
  for constraint_row in
    select constraint_value.conname
    from pg_catalog.pg_constraint constraint_value
    where constraint_value.conrelid =
      'content_factory.generation_spend_ledger'::regclass
      and constraint_value.contype = 'c'
      and (
        pg_catalog.pg_get_constraintdef(constraint_value.oid)
          like '%event_type%'
        or pg_catalog.pg_get_constraintdef(constraint_value.oid)
          like '%committed_delta_minor%'
      )
  loop
    execute format(
      'alter table content_factory.generation_spend_ledger drop constraint %I',
      constraint_row.conname
    );
  end loop;
end;
$$;

alter table content_factory.generation_spend_ledger
  add constraint generation_spend_ledger_event_type_v2_check
    check (event_type in (
      'reserved', 'settled', 'released', 'frozen', 'refunded'
    )),
  add constraint generation_spend_ledger_committed_delta_v2_check
    check (
      committed_delta_minor >= -estimated_cost_minor
    ),
  add constraint generation_spend_ledger_event_shape_v2_check
    check (
      (
        event_type = 'reserved'
        and reserved_delta_minor = estimated_cost_minor
        and committed_delta_minor = 0
        and actual_cost_minor = 0
      )
      or (
        event_type = 'settled'
        and reserved_delta_minor = -estimated_cost_minor
        and committed_delta_minor = actual_cost_minor
        and actual_cost_minor > 0
      )
      or (
        event_type = 'released'
        and reserved_delta_minor = -estimated_cost_minor
        and committed_delta_minor = 0
        and actual_cost_minor = 0
      )
      or (
        event_type = 'frozen'
        and reserved_delta_minor = 0
        and committed_delta_minor = 0
        and actual_cost_minor = 0
      )
      or (
        event_type = 'refunded'
        and reserved_delta_minor = 0
        and actual_cost_minor between 1 and estimated_cost_minor
        and committed_delta_minor = -actual_cost_minor
      )
    );

create or replace function
  content_factory_private.record_real_generation_spend_lifecycle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  reservation_row content_factory.generation_spend_ledger%rowtype;
  has_settlement boolean;
  has_release boolean;
  has_refund boolean;
  has_freeze boolean;
  billing_outcome_value text;
  provider_task_id_value text;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  if new.status is not distinct from old.status
     and new.actual_cost_minor is not distinct from old.actual_cost_minor
     and new.output is not distinct from old.output then
    return new;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );
  select ledger.* into reservation_row
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.generation_job_id = new.id
    and ledger.event_type = 'reserved';
  if reservation_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_budget_reservation_invalid';
  end if;

  select
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'settled'
    ),
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'released'
    ),
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'refunded'
    ),
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'frozen'
    )
  into has_settlement, has_release, has_refund, has_freeze;

  if content_factory_private.real_generation_reconciliation_unresolved(
    new.output
  ) and not has_freeze then
    insert into content_factory.generation_spend_ledger (
      organization_id, generation_job_id, event_type,
      estimated_cost_minor, actual_cost_minor,
      reserved_delta_minor, committed_delta_minor, currency,
      budget_day, budget_month, policy_version, reason_code, metadata
    ) values (
      new.organization_id, new.id, 'frozen',
      reservation_row.estimated_cost_minor, 0, 0, 0, 'USD',
      reservation_row.budget_day, reservation_row.budget_month,
      reservation_row.policy_version, 'provider_submission_ambiguous',
      jsonb_build_object(
        'incident_id', new.output ->> 'reconciliation_incident_id',
        'reason_code', new.output ->> 'reconciliation_reason_code'
      )
    );
    has_freeze := true;
  end if;

  provider_task_id_value := nullif(
    btrim(coalesce(new.output ->> 'provider_task_id', '')),
    ''
  );
  billing_outcome_value := nullif(
    btrim(coalesce(new.output ->> 'provider_billing_outcome', '')),
    ''
  );

  -- The public adapter first executes the legacy state transition and then
  -- attaches the provider billing fact in the same transaction. Do not infer
  -- a refund from that intentionally short-lived intermediate row.
  if new.status = 'failed'
     and provider_task_id_value is not null
     and billing_outcome_value is null
     and current_setting(
       'content_factory.generation_billing_adapter_active',
       true
     ) = '1' then
    return new;
  end if;

  if new.actual_cost_minor > 0 then
    if has_release or has_refund then
      raise exception using
        errcode = '55000',
        message = 'generation_budget_reservation_invalid';
    end if;
    if not has_settlement then
      insert into content_factory.generation_spend_ledger (
        organization_id, generation_job_id, event_type,
        estimated_cost_minor, actual_cost_minor,
        reserved_delta_minor, committed_delta_minor, currency,
        budget_day, budget_month, policy_version, reason_code, metadata
      ) values (
        new.organization_id, new.id, 'settled',
        reservation_row.estimated_cost_minor, new.actual_cost_minor,
        -reservation_row.estimated_cost_minor, new.actual_cost_minor, 'USD',
        reservation_row.budget_day, reservation_row.budget_month,
        reservation_row.policy_version, 'provider_submission_confirmed',
        jsonb_build_object(
          'status', new.status,
          'provider_task_id', provider_task_id_value,
          'accounting_basis', 'provider_sku_estimate'
        )
      );
      has_settlement := true;
    end if;
  end if;

  if new.status in ('failed', 'cancelled')
     and not content_factory_private.real_generation_reconciliation_unresolved(
       new.output
     ) then
    if provider_task_id_value is null then
      if has_settlement or has_refund then
        raise exception using
          errcode = '55000',
          message = 'generation_budget_reservation_invalid';
      end if;
      if not has_release then
        insert into content_factory.generation_spend_ledger (
          organization_id, generation_job_id, event_type,
          estimated_cost_minor, actual_cost_minor,
          reserved_delta_minor, committed_delta_minor, currency,
          budget_day, budget_month, policy_version, reason_code, metadata
        ) values (
          new.organization_id, new.id, 'released',
          reservation_row.estimated_cost_minor, 0,
          -reservation_row.estimated_cost_minor, 0, 'USD',
          reservation_row.budget_day, reservation_row.budget_month,
          reservation_row.policy_version,
          case
            when new.output ->> 'reconciliation_resolution'
              = 'confirm_no_submission'
              then 'reconciliation_confirmed_not_submitted'
            else 'provider_submission_not_created'
          end,
          jsonb_build_object(
            'status', new.status,
            'failure_code', new.output ->> 'failure_code'
          )
        );
      end if;
    elsif billing_outcome_value = 'refundable' then
      if not has_settlement or has_release then
        raise exception using
          errcode = '55000',
          message = 'generation_budget_reservation_invalid';
      end if;
      if not has_refund then
        insert into content_factory.generation_spend_ledger (
          organization_id, generation_job_id, event_type,
          estimated_cost_minor, actual_cost_minor,
          reserved_delta_minor, committed_delta_minor, currency,
          budget_day, budget_month, policy_version, reason_code, metadata
        ) values (
          new.organization_id, new.id, 'refunded',
          reservation_row.estimated_cost_minor,
          reservation_row.estimated_cost_minor,
          0, -reservation_row.estimated_cost_minor, 'USD',
          reservation_row.budget_day, reservation_row.budget_month,
          reservation_row.policy_version, 'provider_task_refunded',
          jsonb_build_object(
            'provider_task_id', provider_task_id_value,
            'provider_failure_code',
              new.output ->> 'provider_failure_code',
            'accounting_basis', 'runway_failure_refund_policy'
          )
        );
      end if;
    elsif billing_outcome_value = 'unknown' and not has_freeze then
      insert into content_factory.generation_spend_ledger (
        organization_id, generation_job_id, event_type,
        estimated_cost_minor, actual_cost_minor,
        reserved_delta_minor, committed_delta_minor, currency,
        budget_day, budget_month, policy_version, reason_code, metadata
      ) values (
        new.organization_id, new.id, 'frozen',
        reservation_row.estimated_cost_minor, 0, 0, 0, 'USD',
        reservation_row.budget_day, reservation_row.budget_month,
        reservation_row.policy_version, 'provider_billing_outcome_unknown',
        jsonb_build_object(
          'provider_task_id', provider_task_id_value,
          'provider_failure_code', new.output ->> 'provider_failure_code'
        )
      );
    elsif billing_outcome_value not in ('non_refundable', 'unknown') then
      raise exception using
        errcode = '55000',
        message = 'generation_billing_outcome_invalid';
    end if;
  end if;
  return new;
end;
$$;

-- Preserve the complete provider-state transition implementation behind a
-- billing adapter.  Provider task failures must now state whether Runway
-- refunds credits; unknown outcomes remain conservatively charged and are
-- surfaced for reconciliation.
alter function public.system_update_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_update_real_generation(jsonb)
  rename to system_update_real_generation_v1;
revoke all on function
  content_factory_private.system_update_real_generation_v1(jsonb)
  from public, anon, authenticated, service_role;

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
  status_value text;
  provider_task_id_value text;
  provider_failure_code_value text;
  billing_outcome_value text;
  job_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  status_value := lower(btrim(coalesce(p_payload ->> 'status', '')));
  provider_task_id_value := nullif(
    btrim(coalesce(p_payload ->> 'provider_task_id', '')),
    ''
  );
  billing_outcome_value := nullif(
    lower(btrim(coalesce(p_payload ->> 'billing_outcome', ''))),
    ''
  );
  provider_failure_code_value := nullif(
    upper(btrim(coalesce(p_payload ->> 'provider_failure_code', ''))),
    ''
  );

  if status_value = 'failed'
     and provider_task_id_value is not null
     and billing_outcome_value is null then
    billing_outcome_value := case
      when provider_failure_code_value like 'SAFETY.INPUT.%'
        or provider_failure_code_value = 'INPUT_PREPROCESSING.SAFETY.TEXT'
        then 'non_refundable'
      when provider_failure_code_value is not null then 'refundable'
      else 'unknown'
    end;
  end if;

  if status_value <> 'failed' and (
    billing_outcome_value is not null
    or provider_failure_code_value is not null
  ) then
    raise exception using
      errcode = '22023',
      message = 'real_generation_billing_payload_invalid';
  end if;
  if status_value = 'failed' and provider_task_id_value is not null then
    if billing_outcome_value not in (
      'refundable', 'non_refundable', 'unknown'
    ) then
      raise exception using
        errcode = '22023',
        message = 'real_generation_billing_outcome_required';
    end if;
    if provider_failure_code_value is not null and
       provider_failure_code_value !~ '^[A-Z0-9][A-Z0-9._-]{0,159}$' then
      raise exception using
        errcode = '22023',
        message = 'real_generation_provider_failure_code_invalid';
    end if;
    if billing_outcome_value <> 'unknown'
       and provider_failure_code_value is null then
      raise exception using
        errcode = '22023',
        message = 'real_generation_provider_failure_code_required';
    end if;
    if billing_outcome_value = 'non_refundable' and not (
      provider_failure_code_value like 'SAFETY.INPUT.%'
      or provider_failure_code_value = 'INPUT_PREPROCESSING.SAFETY.TEXT'
    ) then
      raise exception using
        errcode = '22023',
        message = 'real_generation_billing_outcome_invalid';
    end if;
    if billing_outcome_value = 'refundable' and (
      provider_failure_code_value like 'SAFETY.INPUT.%'
      or provider_failure_code_value = 'INPUT_PREPROCESSING.SAFETY.TEXT'
    ) then
      raise exception using
        errcode = '22023',
        message = 'real_generation_billing_outcome_invalid';
    end if;
  elsif status_value = 'failed' and (
    billing_outcome_value is not null
    or provider_failure_code_value is not null
  ) then
    raise exception using
      errcode = '22023',
      message = 'real_generation_billing_payload_invalid';
  end if;

  perform set_config(
    'content_factory.generation_billing_adapter_active',
    '1',
    true
  );
  result_value :=
    content_factory_private.system_update_real_generation_v1(
      p_payload - 'billing_outcome' - 'provider_failure_code'
    );
  perform set_config(
    'content_factory.generation_billing_adapter_active',
    '0',
    true
  );

  if status_value = 'failed' and provider_task_id_value is not null then
    job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
    update content_factory.generation_jobs job
    set actual_cost_minor = case
          when billing_outcome_value = 'refundable' then 0
          else job.estimated_cost_minor
        end,
        output = job.output || jsonb_strip_nulls(jsonb_build_object(
          'provider_billing_outcome', billing_outcome_value,
          'provider_failure_code', provider_failure_code_value,
          'provider_refund_recorded_at', case
            when billing_outcome_value = 'refundable' then coalesce(
              job.output -> 'provider_refund_recorded_at',
              to_jsonb(now())
            )
            else null::jsonb
          end,
          'actual_cost_minor', case
            when billing_outcome_value = 'refundable' then 0
            else job.estimated_cost_minor
          end
        ))
    where job.id = job_id_value
      and job.status = 'failed'
      and job.output ->> 'provider_task_id' = provider_task_id_value
    returning * into job_row;
    if job_row.id is null then
      raise exception using
        errcode = '55000',
        message = 'real_generation_billing_reconciliation_failed';
    end if;
    result_value := jsonb_set(
      result_value,
      '{job,billing_outcome}',
      to_jsonb(billing_outcome_value),
      true
    );
    result_value := jsonb_set(
      result_value,
      '{job,actual_cost_minor}',
      to_jsonb(job_row.actual_cost_minor),
      true
    );
  end if;
  return result_value;
end;
$$;

revoke all on function public.system_update_real_generation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_update_real_generation(jsonb)
  to service_role;

-- Historical failures did not retain enough provider detail to infer a
-- refund safely. Mark them unknown (and therefore frozen in the ledger) rather
-- than rewriting or optimistically reversing a real charge.
update content_factory.generation_jobs job
set output = job.output || jsonb_build_object(
  'provider_billing_outcome', 'unknown',
  'billing_reconciliation_required_at', now()
)
where job.mode = 'real'
  and job.provider = 'runway'
  and job.status = 'failed'
  and nullif(btrim(job.output ->> 'provider_task_id'), '') is not null
  and not (job.output ? 'provider_billing_outcome');

-- A queued->starting transition now schedules a one-shot durable watchdog.
-- Once an incident marker is written, next_poll_at is cleared so no worker can
-- re-dispatch the paid provider create request.
create or replace function
  content_factory_private.normalize_generation_poll_state()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  starting_at_value timestamptz;
begin
  if new.mode = 'real'
     and new.provider = 'runway'
     and new.status = 'starting' then
    if content_factory_private.real_generation_reconciliation_unresolved(
      new.output
    ) then
      new.provider_next_poll_at := null;
    else
      begin
        starting_at_value := (new.output ->> 'starting_at')::timestamptz;
      exception when others then
        starting_at_value := now();
      end;
      new.provider_next_poll_at := coalesce(
        new.provider_next_poll_at,
        starting_at_value + interval '90 seconds'
      );
    end if;
  elsif new.mode = 'real'
        and new.provider = 'runway'
        and new.status in ('submitted', 'processing') then
    new.provider_next_poll_at := coalesce(new.provider_next_poll_at, now());
  else
    new.provider_next_poll_at := null;
  end if;
  return new;
end;
$$;

drop trigger if exists normalize_generation_poll_state
  on content_factory.generation_jobs;
create trigger normalize_generation_poll_state
before insert or update of mode, provider, status, output
on content_factory.generation_jobs
for each row execute function
  content_factory_private.normalize_generation_poll_state();

drop index if exists content_factory.generation_jobs_provider_poll_due_idx;
create index generation_jobs_provider_poll_due_idx
  on content_factory.generation_jobs
  (provider_next_poll_at, updated_at, id)
  where mode = 'real'
    and provider = 'runway'
    and status in ('starting', 'submitted', 'processing');

update content_factory.generation_jobs job
set provider_next_poll_at = case
  when content_factory_private.real_generation_reconciliation_unresolved(
    job.output
  ) then null
  else coalesce(
    job.provider_next_poll_at,
    (job.output ->> 'starting_at')::timestamptz + interval '90 seconds',
    job.updated_at + interval '90 seconds'
  )
end
where job.mode = 'real'
  and job.provider = 'runway'
  and job.status = 'starting';

-- One quota implementation now covers creator uploads, generated videos and
-- durable review frames.  All callers use the existing advisory lock keys, so
-- concurrent uploads and provider completions cannot oversubscribe capacity.
create table if not exists content_factory.generation_storage_reservations (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  generation_job_id uuid not null,
  owner_id uuid not null,
  reserved_object_count integer not null default 1
    check (reserved_object_count = 1),
  reserved_size_bytes bigint not null default 52428800
    check (reserved_size_bytes = 52428800),
  actual_size_bytes bigint not null default 0
    check (actual_size_bytes between 0 and reserved_size_bytes),
  status text not null default 'active'
    check (status in ('active', 'consumed', 'released')),
  reason_code text check (
    reason_code is null or reason_code ~ '^[a-z][a-z0-9_]{2,99}$'
  ),
  created_at timestamptz not null default now(),
  consumed_at timestamptz,
  released_at timestamptz,
  unique (organization_id, id),
  unique (generation_job_id),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id)
    on delete restrict,
  foreign key (organization_id, owner_id)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (status = 'active'
      and actual_size_bytes = 0
      and consumed_at is null
      and released_at is null
      and reason_code is null)
    or (status = 'consumed'
      and actual_size_bytes > 0
      and consumed_at is not null
      and released_at is null
      and reason_code = 'generated_output_registered')
    or (status = 'released'
      and actual_size_bytes = 0
      and consumed_at is null
      and released_at is not null
      and reason_code is not null)
  )
);

create index if not exists generation_storage_reservations_active_idx
  on content_factory.generation_storage_reservations
  (organization_id, owner_id, created_at, generation_job_id)
  where status = 'active';

alter table content_factory.generation_storage_reservations
  enable row level security;
revoke all on content_factory.generation_storage_reservations
  from public, anon, authenticated;
grant all on content_factory.generation_storage_reservations to service_role;

create or replace function
  content_factory_private.guard_generation_storage_reservation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000',
      message = 'generation_storage_reservation_deletion_forbidden';
  end if;
  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.generation_job_id is distinct from old.generation_job_id
     or new.owner_id is distinct from old.owner_id
     or new.reserved_object_count is distinct from old.reserved_object_count
     or new.reserved_size_bytes is distinct from old.reserved_size_bytes
     or new.created_at is distinct from old.created_at then
    raise exception using errcode = '55000',
      message = 'generation_storage_reservation_identity_immutable';
  end if;
  if old.status <> 'active' or new.status not in ('consumed', 'released') then
    raise exception using errcode = '55000',
      message = 'generation_storage_reservation_transition_invalid';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_generation_storage_reservation
  on content_factory.generation_storage_reservations;
create trigger guard_generation_storage_reservation
before update or delete on content_factory.generation_storage_reservations
for each row execute function
  content_factory_private.guard_generation_storage_reservation();

create or replace function content_factory_private.assert_storage_quota(
  organization_id_value uuid,
  owner_id_value uuid,
  additional_object_count integer,
  additional_size_bytes bigint
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  user_objects_24h bigint;
  user_bytes_24h bigint;
  user_objects_total bigint;
  user_bytes_total bigint;
  organization_objects bigint;
  organization_bytes bigint;
begin
  if additional_object_count not between 0 and 100
     or additional_size_bytes not between 0 and 524288000 then
    raise exception using
      errcode = '22023',
      message = 'storage_quota_delta_invalid';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('media_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text || ':' || owner_id_value::text),
    hashtext('media_quota:user')
  );

  with accounted_objects as (
    select media.owner_id, media.size_bytes, media.created_at
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.status in ('uploading', 'ready', 'archived')
    union all
    select evidence.created_by, frame.size_bytes, frame.created_at
    from content_factory.content_review_evidence_frames frame
    join content_factory.content_review_evidence_sets evidence
      on evidence.organization_id = frame.organization_id
     and evidence.id = frame.evidence_set_id
    where frame.organization_id = organization_id_value
    union all
    select
      reservation.owner_id,
      reservation.reserved_size_bytes,
      reservation.created_at
    from content_factory.generation_storage_reservations reservation
    where reservation.organization_id = organization_id_value
      and reservation.status = 'active'
  )
  select
    count(*) filter (
      where accounted.owner_id = owner_id_value
        and accounted.created_at >= now() - interval '24 hours'
    )::bigint,
    coalesce(sum(accounted.size_bytes) filter (
      where accounted.owner_id = owner_id_value
        and accounted.created_at >= now() - interval '24 hours'
    ), 0)::bigint,
    count(*) filter (
      where accounted.owner_id = owner_id_value
    )::bigint,
    coalesce(sum(accounted.size_bytes) filter (
      where accounted.owner_id = owner_id_value
    ), 0)::bigint,
    count(*)::bigint,
    coalesce(sum(accounted.size_bytes), 0)::bigint
  into
    user_objects_24h, user_bytes_24h,
    user_objects_total, user_bytes_total,
    organization_objects, organization_bytes
  from accounted_objects accounted;

  if user_objects_24h + additional_object_count > 200 then
    raise exception using errcode = '54000',
      message = 'media_user_daily_object_quota_exceeded';
  end if;
  if user_bytes_24h + additional_size_bytes > 2147483648 then
    raise exception using errcode = '54000',
      message = 'media_user_daily_bytes_quota_exceeded';
  end if;
  if user_objects_total + additional_object_count > 2000 then
    raise exception using errcode = '54000',
      message = 'media_user_total_object_quota_exceeded';
  end if;
  if user_bytes_total + additional_size_bytes > 10737418240 then
    raise exception using errcode = '54000',
      message = 'media_user_total_storage_quota_exceeded';
  end if;
  if organization_objects + additional_object_count > 20000 then
    raise exception using errcode = '54000',
      message = 'media_organization_object_quota_exceeded';
  end if;
  if organization_bytes + additional_size_bytes > 107374182400 then
    raise exception using errcode = '54000',
      message = 'media_organization_storage_quota_exceeded';
  end if;
end;
$$;

create or replace function
  content_factory_private.reserve_generation_output_capacity()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  reservation_row
    content_factory.generation_storage_reservations%rowtype;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or new.status not in ('starting', 'submitted', 'processing')
     or (tg_op = 'UPDATE' and old.status is not distinct from new.status) then
    return new;
  end if;

  select reservation.* into reservation_row
  from content_factory.generation_storage_reservations reservation
  where reservation.generation_job_id = new.id
  for update;
  if reservation_row.id is not null then
    if reservation_row.organization_id <> new.organization_id
       or reservation_row.owner_id <> new.assigned_to
       or reservation_row.status <> 'active' then
      raise exception using errcode = '55000',
        message = 'generation_storage_reservation_invalid';
    end if;
    return new;
  end if;

  perform content_factory_private.assert_storage_quota(
    new.organization_id,
    new.assigned_to,
    1,
    52428800
  );
  insert into content_factory.generation_storage_reservations (
    organization_id,
    generation_job_id,
    owner_id,
    reserved_object_count,
    reserved_size_bytes,
    status
  ) values (
    new.organization_id,
    new.id,
    new.assigned_to,
    1,
    52428800,
    'active'
  );
  return new;
end;
$$;

drop trigger if exists d_generation_storage_capacity_reservation
  on content_factory.generation_jobs;
create trigger d_generation_storage_capacity_reservation
after insert or update of status
on content_factory.generation_jobs
for each row execute function
  content_factory_private.reserve_generation_output_capacity();

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
    if new.metadata ->> 'kind' = 'generated_video'
       and new.metadata ->> 'provider' = 'runway'
       and coalesce(new.metadata ->> 'generation_job_id', '') ~
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
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
          raise exception using errcode = '54000',
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

drop trigger if exists a_media_storage_quota_guard
  on content_factory.media_objects;
create trigger a_media_storage_quota_guard
before insert on content_factory.media_objects
for each row execute function
  content_factory_private.enforce_media_storage_quota();

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
    raise exception using errcode = '55000',
      message = 'generation_storage_reservation_required';
  end if;

  -- A failed provider call may already have uploaded the object but failed
  -- before media registration. Keep the reservation active (fail closed)
  -- until the durable cleanup queue confirms that the private object is gone.
  -- This prevents a transient terminal failure from making the same capacity
  -- immediately available to another paid generation.
  if new.status in ('failed', 'cancelled') then
    return new;
  elsif new.status = 'succeeded' and reservation_row.status = 'active' then
    select media.size_bytes into media_size_value
    from content_factory.media_objects media
    where media.organization_id = new.organization_id
      and media.metadata ->> 'generation_job_id' = new.id::text
      and media.metadata ->> 'kind' = 'generated_video'
      and media.status in ('ready', 'archived')
    limit 1;
    if media_size_value is null
       or media_size_value > reservation_row.reserved_size_bytes then
      raise exception using errcode = '55000',
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

drop trigger if exists generation_storage_reservation_lifecycle
  on content_factory.generation_jobs;
create trigger generation_storage_reservation_lifecycle
after update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.release_generation_output_capacity();

-- Existing in-flight jobs predate the capacity gate. Account for them without
-- issuing a provider request or mutating their state; any over-capacity
-- organization consequently fails closed for the next paid start.
insert into content_factory.generation_storage_reservations (
  organization_id, generation_job_id, owner_id,
  reserved_object_count, reserved_size_bytes, status
)
select
  job.organization_id, job.id, job.assigned_to,
  1, 52428800, 'active'
from content_factory.generation_jobs job
where job.mode = 'real'
  and job.provider = 'runway'
  and job.allow_real_spend
  and job.status in ('starting', 'submitted', 'processing')
on conflict (generation_job_id) do nothing;

-- Storage upload precedes the transactional media registration. Any terminal
-- failure therefore creates a durable, idempotent cleanup obligation. The
-- background worker removes the private object (a missing object is success)
-- and only then makes this row terminal.
create table if not exists content_factory.generation_storage_cleanup_queue (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  generation_job_id uuid not null,
  bucket_id text not null default 'contentengine-private'
    check (bucket_id = 'contentengine-private'),
  object_name text not null check (length(object_name) between 40 and 1000),
  status text not null default 'pending'
    check (status in ('pending', 'processing', 'completed', 'dead_letter')),
  attempt_count integer not null default 0
    check (attempt_count between 0 and 5),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid,
  processing_started_at timestamptz,
  last_error_code text check (
    last_error_code is null
      or last_error_code ~ '^[a-z][a-z0-9_]{2,99}$'
  ),
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (generation_job_id),
  unique (bucket_id, object_name),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id)
    on delete restrict,
  check (split_part(object_name, '/', 1) = organization_id::text),
  check (split_part(object_name, '/', 3) = 'generated'),
  check (object_name ~ ('/' || generation_job_id::text || '[.]mp4$')),
  check (object_name !~ '(^|/)\.\.(/|$)'),
  check (
    (status = 'pending'
      and lease_token is null
      and processing_started_at is null
      and completed_at is null)
    or (status = 'processing'
      and lease_token is not null
      and processing_started_at is not null
      and completed_at is null)
    or (status = 'completed'
      and lease_token is null
      and processing_started_at is null
      and completed_at is not null
      and last_error_code is null)
    or (status = 'dead_letter'
      and lease_token is null
      and processing_started_at is null
      and completed_at is null
      and last_error_code is not null)
  )
);

create index if not exists generation_storage_cleanup_due_idx
  on content_factory.generation_storage_cleanup_queue
  (next_attempt_at, created_at, id)
  where status = 'pending';
create index if not exists generation_storage_cleanup_processing_idx
  on content_factory.generation_storage_cleanup_queue
  (processing_started_at, id)
  where status = 'processing';

alter table content_factory.generation_storage_cleanup_queue
  enable row level security;
revoke all on content_factory.generation_storage_cleanup_queue
  from public, anon, authenticated;
grant all on content_factory.generation_storage_cleanup_queue to service_role;

create or replace function
  content_factory_private.guard_generation_storage_cleanup()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000',
      message = 'generation_storage_cleanup_deletion_forbidden';
  end if;
  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.generation_job_id is distinct from old.generation_job_id
     or new.bucket_id is distinct from old.bucket_id
     or new.object_name is distinct from old.object_name
     or new.created_at is distinct from old.created_at then
    raise exception using errcode = '55000',
      message = 'generation_storage_cleanup_identity_immutable';
  end if;
  if not (
    (old.status = 'pending' and new.status = 'processing'
      and (
        new.attempt_count = old.attempt_count + 1
        or (
          old.attempt_count = 5
          and new.attempt_count = 5
          and old.last_error_code is not null
        )
      ))
    or (old.status = 'processing'
      and new.status in ('pending', 'completed', 'dead_letter')
      and new.attempt_count = old.attempt_count)
  ) then
    raise exception using errcode = '55000',
      message = 'generation_storage_cleanup_transition_invalid';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists guard_generation_storage_cleanup
  on content_factory.generation_storage_cleanup_queue;
create trigger guard_generation_storage_cleanup
before update or delete on content_factory.generation_storage_cleanup_queue
for each row execute function
  content_factory_private.guard_generation_storage_cleanup();

create or replace function
  content_factory_private.release_capacity_after_storage_cleanup()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.status = 'processing' and new.status = 'completed' then
    update content_factory.generation_storage_reservations reservation
    set status = 'released',
        released_at = now(),
        reason_code = 'terminal_storage_cleaned'
    where reservation.generation_job_id = new.generation_job_id
      and reservation.organization_id = new.organization_id
      and reservation.status = 'active';
  end if;
  return new;
end;
$$;

drop trigger if exists release_capacity_after_storage_cleanup
  on content_factory.generation_storage_cleanup_queue;
create trigger release_capacity_after_storage_cleanup
after update of status on content_factory.generation_storage_cleanup_queue
for each row execute function
  content_factory_private.release_capacity_after_storage_cleanup();

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
     or object_name_value !~ ('/' || new.id::text || '[.]mp4$')
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

drop trigger if exists generation_storage_cleanup_enqueue
  on content_factory.generation_jobs;
create trigger generation_storage_cleanup_enqueue
after update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.enqueue_generation_storage_cleanup();

insert into content_factory.generation_storage_cleanup_queue (
  organization_id, generation_job_id, bucket_id, object_name
)
select
  job.organization_id,
  job.id,
  'contentengine-private',
  job.input ->> 'output_object_name'
from content_factory.generation_jobs job
where job.mode = 'real'
  and job.provider = 'runway'
  and job.status in ('failed', 'cancelled')
  and nullif(btrim(job.input ->> 'output_object_name'), '') is not null
  and split_part(job.input ->> 'output_object_name', '/', 1) =
    job.organization_id::text
  and split_part(job.input ->> 'output_object_name', '/', 2) =
    job.assigned_to::text
  and split_part(job.input ->> 'output_object_name', '/', 3) = 'generated'
  and job.input ->> 'output_object_name' ~
    ('/' || job.id::text || '[.]mp4$')
  and job.input ->> 'output_object_name' !~ '(^|/)\.\.(/|$)'
  and not exists (
    select 1 from content_factory.media_objects media
    where media.organization_id = job.organization_id
      and media.bucket_id = 'contentengine-private'
      and media.object_name = job.input ->> 'output_object_name'
  )
on conflict (generation_job_id) do nothing;

create or replace function
  content_factory_private.enforce_review_evidence_storage_quota()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  owner_id_value uuid;
begin
  select evidence.created_by into owner_id_value
  from content_factory.content_review_evidence_sets evidence
  where evidence.organization_id = new.organization_id
    and evidence.id = new.evidence_set_id;
  if owner_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_set_missing';
  end if;
  perform content_factory_private.assert_storage_quota(
    new.organization_id, owner_id_value, 1, new.size_bytes
  );
  return new;
end;
$$;

drop trigger if exists a_content_review_evidence_storage_quota_guard
  on content_factory.content_review_evidence_frames;
create trigger a_content_review_evidence_storage_quota_guard
before insert on content_factory.content_review_evidence_frames
for each row execute function
  content_factory_private.enforce_review_evidence_storage_quota();

create index if not exists content_review_evidence_retention_due_idx
  on content_factory.content_review_evidence_sets (consumed_at, id)
  where status = 'consumed';

-- Extend health without copying the large existing operational-health RPC.
-- The retained private implementation still authenticates and authorizes the
-- manager; the adapter adds evidence bytes, combined quota usage, retention
-- candidates, and unknown provider-billing outcomes.
alter function public.creator_operational_health(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_operational_health(jsonb)
  rename to creator_operational_health_storage_v1;
revoke all on function
  content_factory_private.creator_operational_health_storage_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_operational_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  base_value jsonb;
  organization_id_value uuid;
  evidence_count_value bigint;
  evidence_bytes_value bigint;
  retention_count_value bigint;
  retention_bytes_value bigint;
  reserved_count_value bigint;
  reserved_bytes_value bigint;
  cleanup_pending_value bigint;
  cleanup_processing_value bigint;
  cleanup_dead_letter_value bigint;
  billing_unknown_value bigint;
  media_bytes_value bigint;
  total_bytes_value bigint;
  quota_bytes_value constant bigint := 107374182400;
begin
  base_value :=
    content_factory_private.creator_operational_health_storage_v1(p_payload);
  organization_id_value := (base_value ->> 'organization_id')::uuid;

  select
    count(frame.id)::bigint,
    coalesce(sum(frame.size_bytes), 0)::bigint,
    count(distinct evidence.id) filter (
      where evidence.status = 'consumed'
        and evidence.consumed_at <= now() - interval '30 days'
    )::bigint,
    coalesce(sum(frame.size_bytes) filter (
      where evidence.status = 'consumed'
        and evidence.consumed_at <= now() - interval '30 days'
    ), 0)::bigint
  into evidence_count_value, evidence_bytes_value,
    retention_count_value, retention_bytes_value
  from content_factory.content_review_evidence_sets evidence
  left join content_factory.content_review_evidence_frames frame
    on frame.organization_id = evidence.organization_id
   and frame.evidence_set_id = evidence.id
  where evidence.organization_id = organization_id_value;

  select
    count(*)::bigint,
    coalesce(sum(reservation.reserved_size_bytes), 0)::bigint
  into reserved_count_value, reserved_bytes_value
  from content_factory.generation_storage_reservations reservation
  where reservation.organization_id = organization_id_value
    and reservation.status = 'active';

  select
    count(*) filter (where cleanup.status = 'pending')::bigint,
    count(*) filter (where cleanup.status = 'processing')::bigint,
    count(*) filter (where cleanup.status = 'dead_letter')::bigint
  into cleanup_pending_value, cleanup_processing_value,
    cleanup_dead_letter_value
  from content_factory.generation_storage_cleanup_queue cleanup
  where cleanup.organization_id = organization_id_value;

  select count(*)::bigint into billing_unknown_value
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.mode = 'real'
    and job.provider = 'runway'
    and job.status = 'failed'
    and job.output ->> 'provider_billing_outcome' = 'unknown';

  media_bytes_value := coalesce(
    (base_value #>> '{storage,registered_bytes}')::bigint,
    0
  );
  total_bytes_value :=
    media_bytes_value + evidence_bytes_value + reserved_bytes_value;
  return base_value || jsonb_build_object(
    'storage', (base_value -> 'storage') || jsonb_build_object(
      'evidence_count', evidence_count_value,
      'evidence_bytes', evidence_bytes_value,
      'active_reservation_count', reserved_count_value,
      'active_reserved_bytes', reserved_bytes_value,
      'accounted_bytes', total_bytes_value,
      'remaining_bytes', greatest(quota_bytes_value - total_bytes_value, 0),
      'utilization_percent', round(
        total_bytes_value::numeric * 100 / quota_bytes_value,
        2
      ),
      'retention_policy_days', 30,
      'retention_due_count', retention_count_value,
      'retention_due_bytes', retention_bytes_value,
      'retention_mode', 'manual_review_required',
      'cleanup_pending', cleanup_pending_value,
      'cleanup_processing', cleanup_processing_value,
      'cleanup_dead_letter', cleanup_dead_letter_value
    ),
    'billing', jsonb_build_object(
      'unknown_failure_outcomes', billing_unknown_value,
      'requires_reconciliation', billing_unknown_value > 0
    )
  );
end;
$$;

revoke all on function public.creator_operational_health(jsonb)
  from public, anon;
grant execute on function public.creator_operational_health(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.assert_storage_quota(uuid, uuid, integer, bigint)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.enforce_media_storage_quota()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.enforce_review_evidence_storage_quota()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_generation_storage_reservation()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.reserve_generation_output_capacity()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.release_generation_output_capacity()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_generation_storage_cleanup()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.release_capacity_after_storage_cleanup()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.enqueue_generation_storage_cleanup()
  from public, anon, authenticated;

commit;
