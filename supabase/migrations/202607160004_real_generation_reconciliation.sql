begin;

-- A Runway create request may be accepted even when the Edge Function loses
-- the response. Such an outcome must never be retried automatically. Keep the
-- paid job in `starting`, add a durable incident marker, and require an
-- owner/admin reconciliation before the organization can spend again.

-- The marker is an organization-wide spend freeze, not just a UI warning.
-- Use the same advisory lock as the paid-start quota path so an insert and a
-- mark/reconcile transition cannot pass each other between check and write.
create or replace function
  content_factory_private.real_generation_reconciliation_unresolved(
    value jsonb
  )
returns boolean
language sql
immutable
parallel safe
set search_path = ''
as $$
  select coalesce(value ? 'reconciliation_required', false)
    and value -> 'reconciliation_required'
      is distinct from 'false'::jsonb
$$;

revoke all on function
  content_factory_private.real_generation_reconciliation_unresolved(jsonb)
  from public, anon, authenticated;

create index if not exists generation_jobs_reconciliation_freeze_idx
  on content_factory.generation_jobs (organization_id)
  where mode = 'real'
    and allow_real_spend
    and content_factory_private.real_generation_reconciliation_unresolved(
      output
    );

create or replace function content_factory_private.guard_real_generation_reconciliation_freeze()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.mode <> 'real' or not new.allow_real_spend then
    return new;
  end if;

  -- Normal updates to an already-paid job must remain possible so the system
  -- can mark and reconcile it. Only a newly inserted/converted paid job spends
  -- a fresh provider slot.
  if tg_op = 'UPDATE'
     and old.mode = 'real'
     and old.allow_real_spend
     and old.organization_id = new.organization_id then
    return new;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('real_generation_quota:organization')
  );

  if exists (
    select 1
    from content_factory.generation_jobs job
    where job.organization_id = new.organization_id
      and job.mode = 'real'
      and job.allow_real_spend
      and content_factory_private.real_generation_reconciliation_unresolved(
        job.output
      )
  ) then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end if;

  return new;
end;
$$;

drop trigger if exists a_generation_jobs_reconciliation_freeze_guard
  on content_factory.generation_jobs;
create trigger a_generation_jobs_reconciliation_freeze_guard
before insert or update of mode, allow_real_spend, organization_id
on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_real_generation_reconciliation_freeze();

revoke all on function
  content_factory_private.guard_real_generation_reconciliation_freeze()
  from public, anon, authenticated;

-- Once a job is unresolved, older provider-state updaters must not move it
-- out of `starting` or clear the marker. Only the two complete reconciliation
-- row shapes below are valid terminal exits.
create or replace function content_factory_private.guard_real_generation_reconciliation_transition()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  old_unresolved boolean;
  resolution_value text;
  incident_id_value uuid;
  resolved_by_value uuid;
  required_at_value timestamptz;
  resolved_at_value timestamptz;
  provider_task_id_value text;
  provider_task_created_at_value timestamptz;
  provider_status_value text;
  evidence_reference_value text;
  reason_value text;
  payload_hash_value text;
  expected_payload_hash text;
begin
  old_unresolved := old.mode = 'real'
    and old.provider = 'runway'
    and old.allow_real_spend
    and content_factory_private.real_generation_reconciliation_unresolved(
      old.output
    );
  if not old_unresolved then
    return new;
  end if;

  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.product_id is distinct from old.product_id
     or new.batch_id is distinct from old.batch_id
     or new.requested_by is distinct from old.requested_by
     or new.assigned_to is distinct from old.assigned_to
     or new.mode is distinct from old.mode
     or new.provider is distinct from old.provider
     or new.allow_real_spend is distinct from old.allow_real_spend
     or new.estimated_cost_minor is distinct from old.estimated_cost_minor
     or new.input is distinct from old.input
     or new.request_hash is distinct from old.request_hash
     or new.idempotency_key is distinct from old.idempotency_key then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end if;

  -- Harmless metadata maintenance may keep the job unresolved, but cannot
  -- attach a provider task, alter the incident identity, or leave `starting`.
  if new.status = 'starting'
     and new.actual_cost_minor = 0
     and nullif(btrim(new.output ->> 'provider_task_id'), '') is null
     and new.output ? 'reconciliation_required'
     and new.output -> 'reconciliation_required'
       is distinct from 'false'::jsonb
     and new.output -> 'starting_at'
       is not distinct from old.output -> 'starting_at'
     and new.output -> 'reconciliation_incident_id'
       is not distinct from old.output -> 'reconciliation_incident_id'
     and new.output -> 'reconciliation_reason_code'
       is not distinct from old.output -> 'reconciliation_reason_code'
     and new.output -> 'reconciliation_resolution'
       is not distinct from old.output -> 'reconciliation_resolution'
     and new.output -> 'reconciliation_resolved_at'
       is not distinct from old.output -> 'reconciliation_resolved_at'
     and new.output -> 'reconciliation_resolved_by'
       is not distinct from old.output -> 'reconciliation_resolved_by'
     and new.output -> 'reconciliation_evidence_reference'
       is not distinct from old.output -> 'reconciliation_evidence_reference'
     and new.output -> 'reconciliation_reason'
       is not distinct from old.output -> 'reconciliation_reason'
     and new.output -> 'reconciliation_payload_hash'
       is not distinct from old.output -> 'reconciliation_payload_hash' then
    return new;
  end if;

  resolution_value := nullif(
    btrim(new.output ->> 'reconciliation_resolution'),
    ''
  );
  provider_task_id_value := nullif(
    btrim(new.output ->> 'provider_task_id'),
    ''
  );
  provider_status_value := nullif(
    btrim(new.output ->> 'provider_status_at_reconciliation'),
    ''
  );
  evidence_reference_value := nullif(
    btrim(new.output ->> 'reconciliation_evidence_reference'),
    ''
  );
  reason_value := nullif(
    btrim(new.output ->> 'reconciliation_reason'),
    ''
  );
  payload_hash_value := nullif(
    btrim(new.output ->> 'reconciliation_payload_hash'),
    ''
  );

  begin
    incident_id_value :=
      (old.output ->> 'reconciliation_incident_id')::uuid;
    resolved_by_value :=
      (new.output ->> 'reconciliation_resolved_by')::uuid;
    required_at_value :=
      (old.output ->> 'reconciliation_required_at')::timestamptz;
    resolved_at_value :=
      (new.output ->> 'reconciliation_resolved_at')::timestamptz;
    if nullif(
      btrim(new.output ->> 'provider_task_created_at'),
      ''
    ) is not null then
      provider_task_created_at_value :=
        (new.output ->> 'provider_task_created_at')::timestamptz;
    end if;
  exception when others then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end;

  if old.status <> 'starting'
     or old.actual_cost_minor <> 0
     or nullif(btrim(old.output ->> 'provider_task_id'), '') is not null
     or old.output -> 'reconciliation_required'
       is distinct from 'true'::jsonb
     or new.output -> 'reconciliation_required'
       is distinct from 'false'::jsonb
     or new.output -> 'reconciliation_incident_id'
       is distinct from old.output -> 'reconciliation_incident_id'
     or new.output -> 'reconciliation_required_at'
       is distinct from old.output -> 'reconciliation_required_at'
     or new.output -> 'reconciliation_reason_code'
       is distinct from old.output -> 'reconciliation_reason_code'
     or new.output -> 'starting_at'
       is distinct from old.output -> 'starting_at'
     or incident_id_value is null
     or required_at_value is null
     or resolved_at_value is null
     or resolved_at_value < required_at_value
     or resolved_at_value > now() + interval '1 minute'
     or evidence_reference_value is null
     or length(evidence_reference_value) not between 8 and 500
     or reason_value is null
     or length(reason_value) not between 20 and 1000
     or payload_hash_value !~ '^[0-9a-f]{64}$'
     or not exists (
       select 1
       from content_factory.memberships membership
       join content_factory.profiles profile
         on profile.id = membership.profile_id
       where membership.organization_id = old.organization_id
         and membership.profile_id = resolved_by_value
         and membership.status = 'active'
         and membership.role in ('owner', 'admin')
         and profile.status = 'active'
     ) then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end if;

  expected_payload_hash := content_factory_private.json_hash(
    jsonb_build_object(
      'incident_id', incident_id_value,
      'resolution', resolution_value,
      'provider_task_id', provider_task_id_value,
      'provider_task_created_at', provider_task_created_at_value,
      'provider_status', provider_status_value,
      'evidence_reference', evidence_reference_value,
      'reason', reason_value
    )
  );
  if payload_hash_value is distinct from expected_payload_hash then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end if;

  if resolution_value = 'attach_existing_task'
     and new.status = 'submitted'
     and new.actual_cost_minor = new.estimated_cost_minor
     and provider_task_id_value
       ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'
     and provider_task_created_at_value is not null
     and provider_status_value in (
       'PENDING', 'THROTTLED', 'RUNNING', 'SUCCEEDED',
       'FAILED', 'CANCELED', 'CANCELLED'
     )
     and new.output ->> 'submission_state' = 'confirmed_submitted'
     and new.output ->> 'currency' = 'USD'
     and new.output ->> 'failure_code' is null then
    return new;
  end if;

  if resolution_value = 'confirm_no_submission'
     and new.status = 'failed'
     and new.actual_cost_minor = 0
     and provider_task_id_value is null
     and provider_task_created_at_value is null
     and provider_status_value is null
     and new.output ->> 'submission_state' = 'confirmed_not_submitted'
     and new.output ->> 'failure_code'
       = 'provider_submission_not_found'
     and new.output ->> 'output_media_id' is null
     and new.output ->> 'currency' = 'USD' then
    return new;
  end if;

  raise exception using
    errcode = '55000',
    message = 'real_generation_reconciliation_required';
end;
$$;

drop trigger if exists b_generation_jobs_reconciliation_transition_guard
  on content_factory.generation_jobs;
create trigger b_generation_jobs_reconciliation_transition_guard
before update on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_real_generation_reconciliation_transition();

revoke all on function
  content_factory_private.guard_real_generation_reconciliation_transition()
  from public, anon, authenticated;

create or replace function public.system_mark_real_generation_reconciliation_required(
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
  reason_code_value text;
  incident_id_value uuid;
  starting_at_value timestamptz;
  organization_id_value uuid;
  linked_task_count integer;
  linked_task_id uuid;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  already_required boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['job_id', 'reason_code']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_mark_payload_invalid';
  end if;

  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  reason_code_value := content_factory_private.require_text(
    p_payload, 'reason_code', 8, 80
  );
  if reason_code_value not in (
    'provider_create_timeout',
    'provider_create_http_unknown',
    'provider_create_response_unknown',
    'provider_create_state_stale'
  ) then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_reason_invalid';
  end if;

  select job.organization_id into organization_id_value
  from content_factory.generation_jobs job
  where job.id = job_id_value;

  if organization_id_value is null then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('real_generation_quota:organization')
  );

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
    and job.organization_id = organization_id_value
  for update;

  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;

  already_required :=
    content_factory_private.real_generation_reconciliation_unresolved(
      job_row.output
    );
  if already_required then
    if job_row.status = 'starting'
       and job_row.actual_cost_minor = 0
       and nullif(
         btrim(job_row.output ->> 'provider_task_id'),
         ''
       ) is null
       and job_row.output -> 'reconciliation_required'
         is distinct from 'true'::jsonb then
      update content_factory.generation_jobs job
      set output = jsonb_set(
        job.output,
        '{reconciliation_required}',
        'true'::jsonb,
        true
      )
      where job.id = job_row.id
      returning * into job_row;
    end if;
    return jsonb_build_object(
      'ok', true,
      'marked', false,
      'job', jsonb_build_object(
        'id', job_row.id,
        'status', job_row.status,
        'reconciliation_required', true,
        'reconciliation_incident_id',
          job_row.output ->> 'reconciliation_incident_id',
        'reconciliation_required_at',
          job_row.output ->> 'reconciliation_required_at',
        'reconciliation_reason_code',
          job_row.output ->> 'reconciliation_reason_code'
      )
    );
  end if;

  if job_row.status <> 'starting'
     or nullif(btrim(job_row.output ->> 'provider_task_id'), '') is not null
     or job_row.actual_cost_minor <> 0 then
    return jsonb_build_object(
      'ok', true,
      'marked', false,
      'job', jsonb_build_object(
        'id', job_row.id,
        'status', job_row.status,
        'reconciliation_required', false
      )
    );
  end if;

  begin
    starting_at_value := (job_row.output ->> 'starting_at')::timestamptz;
  exception when others then
    raise exception using
      errcode = '55000',
      message = 'real_generation_starting_timestamp_invalid';
  end;
  if starting_at_value is null then
    raise exception using
      errcode = '55000',
      message = 'real_generation_starting_timestamp_invalid';
  end if;
  if reason_code_value = 'provider_create_state_stale'
     and starting_at_value > now() - interval '90 seconds' then
    return jsonb_build_object(
      'ok', true,
      'marked', false,
      'job', jsonb_build_object(
        'id', job_row.id,
        'status', job_row.status,
        'reconciliation_required', false
      )
    );
  end if;

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
     or batch_row.estimated_cost_minor
          is distinct from job_row.estimated_cost_minor then
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
  if task_row.status <> 'blocked'
     or task_row.product_id is distinct from job_row.product_id
     or task_row.assignee_id is distinct from job_row.assigned_to
     or task_row.created_by is distinct from job_row.requested_by
     or task_row.id::text is distinct from job_row.input ->> 'review_task_id' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_invalid';
  end if;

  incident_id_value := extensions.gen_random_uuid();
  update content_factory.generation_jobs job
  set output = job.output || jsonb_build_object(
    'submission_state', 'unknown',
    'reconciliation_required', true,
    'reconciliation_incident_id', incident_id_value,
    'reconciliation_required_at', now(),
    'reconciliation_reason_code', reason_code_value
  )
  where job.id = job_row.id
  returning * into job_row;

  update content_factory.creator_tasks task
  set result = task.result || jsonb_build_object(
    'generation_status', 'starting',
    'generation_submission_state', 'unknown',
    'generation_reconciliation_required', true,
    'generation_reconciliation_incident_id', incident_id_value
  )
  where task.id = task_row.id;

  perform content_factory_private.emit_event(
    job_row.organization_id,
    job_row.requested_by,
    'real_generation_reconciliation_required',
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'incident_id', incident_id_value,
      'reason_code', reason_code_value,
      'automatic_provider_retry_allowed', false
    ),
    'real-generation:' || job_row.id::text || ':reconciliation-required',
    'system'
  );

  return jsonb_build_object(
    'ok', true,
    'marked', true,
    'job', jsonb_build_object(
      'id', job_row.id,
      'status', job_row.status,
      'reconciliation_required', true,
      'reconciliation_incident_id', incident_id_value,
      'reconciliation_required_at',
        job_row.output ->> 'reconciliation_required_at',
      'reconciliation_reason_code', reason_code_value
    )
  );
end;
$$;

create or replace function public.creator_real_generation_reconciliation_context(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid;
  organization_id uuid;
  actor_role text;
  job_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'job_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_context_payload_invalid';
  end if;

  actor_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin']
  );
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
    and job.mode = 'real'
    and job.provider = 'runway';

  if job_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;
  if job_row.status <> 'starting'
     or nullif(btrim(job_row.output ->> 'provider_task_id'), '') is not null
     or not content_factory_private.real_generation_reconciliation_unresolved(
       job_row.output
     )
     or coalesce(
       job_row.output ->> 'reconciliation_incident_id',
       ''
     ) !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_not_required';
  end if;

  return jsonb_build_object(
    'ok', true,
    'actor_id', actor_id,
    'actor_role', actor_role,
    'job', jsonb_build_object(
      'id', job_row.id,
      'organization_id', job_row.organization_id,
      'status', job_row.status,
      'model', job_row.input ->> 'model',
      'duration_seconds', (job_row.input ->> 'duration_seconds')::integer,
      'starting_at', job_row.output ->> 'starting_at',
      'reconciliation_incident_id',
        job_row.output ->> 'reconciliation_incident_id',
      'reconciliation_required_at',
        job_row.output ->> 'reconciliation_required_at'
    )
  );
end;
$$;

create or replace function public.system_reconcile_real_generation(
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
  actor_id_value uuid;
  incident_id_value uuid;
  idempotency_key_value text;
  resolution_value text;
  evidence_reference_value text;
  reason_value text;
  provider_task_id_value text;
  provider_task_created_at_value timestamptz;
  provider_status_value text;
  actor_role text;
  organization_id_value uuid;
  starting_at_value timestamptz;
  required_at_value timestamptz;
  payload_hash text;
  existing_resolution text;
  existing_payload_hash text;
  linked_task_count integer;
  linked_task_id uuid;
  stored_result jsonb;
  result jsonb;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'job_id', 'actor_id', 'incident_id', 'idempotency_key', 'resolution',
    'evidence_reference', 'reason', 'provider_task_id',
    'provider_task_created_at', 'provider_status'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_payload_invalid';
  end if;

  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  incident_id_value := content_factory_private.require_uuid(
    p_payload, 'incident_id'
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  resolution_value := content_factory_private.require_text(
    p_payload, 'resolution', 10, 40
  );
  evidence_reference_value := content_factory_private.require_text(
    p_payload, 'evidence_reference', 8, 500
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 20, 1000
  );
  if resolution_value not in (
    'attach_existing_task',
    'confirm_no_submission'
  ) then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_resolution_invalid';
  end if;
  if evidence_reference_value ~* '(bearer[[:space:]]+[a-z0-9._-]+|api[_ -]?key|secret=|token=)'
     or reason_value ~* '(bearer[[:space:]]+[a-z0-9._-]+|api[_ -]?key|secret=|token=)' then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_evidence_invalid';
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'provider_task_id', '')), '') is not null then
    provider_task_id_value := content_factory_private.require_text(
      p_payload, 'provider_task_id', 1, 128
    );
    if provider_task_id_value !~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$' then
      raise exception using
        errcode = '22023',
        message = 'provider_task_id_invalid';
    end if;
  end if;
  if nullif(
    btrim(coalesce(p_payload ->> 'provider_task_created_at', '')),
    ''
  ) is not null then
    begin
      provider_task_created_at_value :=
        (p_payload ->> 'provider_task_created_at')::timestamptz;
    exception when others then
      raise exception using
        errcode = '22023',
        message = 'provider_task_created_at_invalid';
    end;
  end if;
  if nullif(btrim(coalesce(p_payload ->> 'provider_status', '')), '') is not null then
    provider_status_value := upper(content_factory_private.require_text(
      p_payload, 'provider_status', 3, 32
    ));
  end if;

  if resolution_value = 'attach_existing_task' then
    if provider_task_id_value is null
       or provider_task_created_at_value is null
       or provider_status_value not in (
         'PENDING', 'THROTTLED', 'RUNNING', 'SUCCEEDED',
         'FAILED', 'CANCELED', 'CANCELLED'
       ) then
      raise exception using
        errcode = '22023',
        message = 'real_generation_reconciliation_provider_task_invalid';
    end if;
  elsif provider_task_id_value is not null
        or provider_task_created_at_value is not null
        or provider_status_value is not null then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_no_submission_invalid';
  end if;

  select job.organization_id into organization_id_value
  from content_factory.generation_jobs job
  where job.id = job_id_value;
  if organization_id_value is null then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('real_generation_quota:organization')
  );

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
    and job.organization_id = organization_id_value
  for update;
  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;

  select membership.role into actor_role
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
  where membership.organization_id = job_row.organization_id
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin')
    and profile.status = 'active';
  if actor_role is null then
    raise exception using
      errcode = '42501',
      message = 'real_generation_reconciliation_role_not_allowed';
  end if;

  if job_row.output ->> 'reconciliation_incident_id'
       is distinct from incident_id_value::text then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_incident_mismatch';
  end if;

  payload_hash := content_factory_private.json_hash(jsonb_build_object(
    'incident_id', incident_id_value,
    'resolution', resolution_value,
    'provider_task_id', provider_task_id_value,
    'provider_task_created_at', provider_task_created_at_value,
    'provider_status', provider_status_value,
    'evidence_reference', evidence_reference_value,
    'reason', reason_value
  ));
  existing_resolution := nullif(
    btrim(job_row.output ->> 'reconciliation_resolution'),
    ''
  );
  existing_payload_hash := nullif(
    btrim(job_row.output ->> 'reconciliation_payload_hash'),
    ''
  );
  if existing_resolution is not null then
    if existing_resolution is distinct from resolution_value
       or existing_payload_hash is distinct from payload_hash then
      raise exception using
        errcode = '23505',
        message = 'real_generation_reconciliation_already_resolved';
    end if;
    return jsonb_build_object(
      'ok', true,
      'replayed', true,
      'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider_task_id', job_row.output ->> 'provider_task_id',
        'failure_code', job_row.output ->> 'failure_code',
        'reconciliation_required', false,
        'reconciliation_resolution', existing_resolution,
        'updated_at', job_row.updated_at
      )
    );
  end if;

  if not content_factory_private.real_generation_reconciliation_unresolved(
       job_row.output
     )
     or job_row.status <> 'starting'
     or nullif(btrim(job_row.output ->> 'provider_task_id'), '') is not null
     or job_row.actual_cost_minor <> 0 then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_not_required';
  end if;

  -- A fail-closed malformed marker still blocks spend, but an authorized
  -- owner/admin can normalize it inside the locked reconciliation command.
  if job_row.output -> 'reconciliation_required'
       is distinct from 'true'::jsonb then
    update content_factory.generation_jobs job
    set output = jsonb_set(
      job.output,
      '{reconciliation_required}',
      'true'::jsonb,
      true
    )
    where job.id = job_row.id
    returning * into job_row;
  end if;

  begin
    starting_at_value := (job_row.output ->> 'starting_at')::timestamptz;
    required_at_value :=
      (job_row.output ->> 'reconciliation_required_at')::timestamptz;
  exception when others then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_timestamp_invalid';
  end;
  if starting_at_value is null or required_at_value is null then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_timestamp_invalid';
  end if;
  if resolution_value = 'confirm_no_submission'
     and required_at_value > now() - interval '2 minutes' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_wait_required';
  end if;
  if resolution_value = 'attach_existing_task'
     and (
       provider_task_created_at_value < starting_at_value - interval '2 minutes'
       or provider_task_created_at_value > starting_at_value + interval '10 minutes'
       or provider_task_created_at_value > now() + interval '1 minute'
     ) then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_task_time_mismatch';
  end if;

  stored_result := content_factory_private.begin_command(
    job_row.organization_id,
    'system_reconcile_real_generation',
    idempotency_key_value,
    p_payload
  );
  if stored_result is not null then
    return stored_result;
  end if;

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
     or batch_row.estimated_cost_minor
          is distinct from job_row.estimated_cost_minor then
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
  if task_row.status <> 'blocked'
     or task_row.product_id is distinct from job_row.product_id
     or task_row.assignee_id is distinct from job_row.assigned_to
     or task_row.created_by is distinct from job_row.requested_by
     or task_row.id::text is distinct from job_row.input ->> 'review_task_id' then
    raise exception using
      errcode = '55000',
      message = 'real_generation_review_task_invalid';
  end if;

  if resolution_value = 'attach_existing_task' then
    update content_factory.generation_jobs job
    set status = 'submitted',
        actual_cost_minor = job.estimated_cost_minor,
        output = (job.output - 'failure_code') || jsonb_build_object(
          'provider_task_id', provider_task_id_value,
          'provider_status_at_reconciliation', provider_status_value,
          'provider_task_created_at', provider_task_created_at_value,
          'submitted_at', coalesce(
            job.output ->> 'submitted_at',
            provider_task_created_at_value::text
          ),
          'actual_cost_minor', job.estimated_cost_minor,
          'currency', 'USD',
          'submission_state', 'confirmed_submitted',
          'reconciliation_required', false,
          'reconciliation_resolution', resolution_value,
          'reconciliation_resolved_at', now(),
          'reconciliation_resolved_by', actor_id_value,
          'reconciliation_evidence_reference', evidence_reference_value,
          'reconciliation_reason', reason_value,
          'reconciliation_payload_hash', payload_hash
        )
    where job.id = job_row.id
    returning * into job_row;

    update content_factory.generation_batches batch
    set status = 'submitted'
    where batch.id = batch_row.id;

    update content_factory.creator_tasks task
    set result = task.result || jsonb_build_object(
      'generation_status', 'submitted',
      'generation_submission_state', 'confirmed_submitted',
      'generation_reconciliation_required', false,
      'generation_reconciliation_resolution', resolution_value
    )
    where task.id = task_row.id;
  else
    update content_factory.generation_jobs job
    set status = 'failed',
        actual_cost_minor = 0,
        output = (
          job.output
          - 'provider_task_id'
          - 'output_media_id'
          - 'output_object_name'
        ) || jsonb_build_object(
          'failure_code', 'provider_submission_not_found',
          'failed_at', now(),
          'actual_cost_minor', 0,
          'currency', 'USD',
          'submission_state', 'confirmed_not_submitted',
          'reconciliation_required', false,
          'reconciliation_resolution', resolution_value,
          'reconciliation_resolved_at', now(),
          'reconciliation_resolved_by', actor_id_value,
          'reconciliation_evidence_reference', evidence_reference_value,
          'reconciliation_reason', reason_value,
          'reconciliation_payload_hash', payload_hash
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
        result = task.result || jsonb_build_object(
          'generation_status', 'failed',
          'failure_code', 'provider_submission_not_found',
          'review_required', false,
          'generation_submission_state', 'confirmed_not_submitted',
          'generation_reconciliation_required', false,
          'generation_reconciliation_resolution', resolution_value
        )
    where task.id = task_row.id;
  end if;

  perform content_factory_private.emit_event(
    job_row.organization_id,
    actor_id_value,
    case resolution_value
      when 'attach_existing_task'
        then 'real_generation_reconciled_existing_task'
      else 'real_generation_reconciled_no_submission'
    end,
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'incident_id', incident_id_value,
      'resolution', resolution_value,
      'provider_task_id', provider_task_id_value,
      'provider_task_created_at', provider_task_created_at_value,
      'provider_status', provider_status_value,
      'evidence_reference', evidence_reference_value,
      'reason', reason_value,
      'automatic_provider_retry_used', false
    ),
    'real-generation:' || job_row.id::text || ':reconciliation:' ||
      incident_id_value::text
  );

  result := jsonb_build_object(
    'ok', true,
    'replayed', false,
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider_task_id', job_row.output ->> 'provider_task_id',
      'failure_code', job_row.output ->> 'failure_code',
      'reconciliation_required', false,
      'reconciliation_resolution', resolution_value,
      'updated_at', job_row.updated_at
    )
  );
  return content_factory_private.finish_command(
    job_row.organization_id,
    actor_id_value,
    'system_reconcile_real_generation',
    idempotency_key_value,
    p_payload,
    result
  );
end;
$$;

-- Extend the existing authenticated status response with the durable
-- reconciliation state. Non-managers can see that a manual check is pending,
-- but only owners/admins receive the action capability.
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
  reconciliation_required_value boolean;
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
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;

  reconciliation_required_value :=
    content_factory_private.real_generation_reconciliation_unresolved(
      job_row.output
    );

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
      'estimated_credits',
        (job_row.input #>> '{billing,estimated_credits}')::bigint,
      'actual_cost_minor', job_row.actual_cost_minor,
      'output_object_name', job_row.input ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'submission_state', job_row.output ->> 'submission_state',
      'reconciliation_required', reconciliation_required_value,
      'reconciliation_incident_id',
        job_row.output ->> 'reconciliation_incident_id',
      'reconciliation_required_at',
        job_row.output ->> 'reconciliation_required_at',
      'reconciliation_reason_code',
        job_row.output ->> 'reconciliation_reason_code',
      'reconciliation_resolution',
        job_row.output ->> 'reconciliation_resolution',
      'can_reconcile',
        actor_role in ('owner', 'admin')
        and reconciliation_required_value
        and job_row.status = 'starting',
      'updated_at', job_row.updated_at
    )
  );
end;
$$;

revoke all on function public.creator_real_generation_reconciliation_context(jsonb)
  from public, anon;
grant execute on function public.creator_real_generation_reconciliation_context(jsonb)
  to authenticated;

revoke all on function public.system_mark_real_generation_reconciliation_required(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_mark_real_generation_reconciliation_required(jsonb)
  to service_role;

revoke all on function public.system_reconcile_real_generation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_reconcile_real_generation(jsonb)
  to service_role;

revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;

commit;
