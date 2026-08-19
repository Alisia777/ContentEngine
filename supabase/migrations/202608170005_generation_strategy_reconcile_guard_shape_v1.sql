begin;

-- Strategy dispatch reconciliation must satisfy the legacy job guard.
-- guard_real_generation_reconciliation_transition (202607180002) fires on every
-- update of an unresolved real runway job and only admits transitions that
-- carry the full legacy resolution shape in job.output: reconciliation_required
-- flips true -> false (never removed), resolved_at/resolved_by are present,
-- evidence reference and reason are recorded, reconciliation_payload_hash is
-- recomputable from those fields, currency is stamped, and the failure code for
-- a confirmed non-submission is 'provider_submission_not_found'.  The strategy
-- reconcile RPC from 202608130007 instead removed the flag, skipped the
-- resolved/evidence fields, used a different payload-hash formula and the code
-- 'provider_submission_not_created', so every strategy reconciliation died on
-- the guard with real_generation_reconciliation_required and ambiguous paid
-- dispatches could never be resolved.  This migration re-issues the RPC with
-- guard-compatible job updates for both resolutions and changes nothing else.

create or replace function
  public.system_reconcile_generation_strategy_dispatch(
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
  organization_id_value uuid;
  project_id_value uuid;
  actor_id_value uuid;
  result_id_value uuid;
  generation_job_id_value uuid;
  incident_id_value uuid;
  resolution_value text;
  provider_task_id_value text;
  provider_task_created_at_value timestamptz;
  provider_status_value text;
  evidence_hash_value text;
  confirmation_value text;
  idempotency_key_value text;
  request_hash_value text;
  reconciliation_hash_value text;
  starting_at_value timestamptz;
  required_at_value timestamptz;
  replay_value boolean := false;
  result_row
    content_factory.generation_strategy_dispatch_results%rowtype;
  claim_row content_factory.generation_strategy_start_claims%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  reconciliation_row
    content_factory.generation_strategy_dispatch_reconciliations%rowtype;
  existing_row
    content_factory.generation_strategy_dispatch_reconciliations%rowtype;
  event_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id',
       'dispatch_result_id', 'generation_job_id', 'incident_id', 'resolution',
       'provider_task_id', 'provider_task_created_at', 'provider_status',
       'external_evidence_hash', 'confirmation', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id',
       'dispatch_result_id', 'generation_job_id', 'incident_id', 'resolution',
       'provider_task_id', 'provider_task_created_at', 'provider_status',
       'external_evidence_hash', 'confirmation', 'idempotency_key'
     ]::text[]
     or p_payload ->> 'version' <>
       'generation-strategy-dispatch-reconciliation-request-v1'
     or jsonb_typeof(p_payload -> 'provider_task_id')
          not in ('string', 'null')
     or jsonb_typeof(p_payload -> 'provider_task_created_at')
          not in ('string', 'null')
     or jsonb_typeof(p_payload -> 'provider_status')
          not in ('string', 'null') then
    raise exception using errcode = '22023',
      message = 'generation_strategy_dispatch_reconciliation_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  result_id_value := content_factory_private.require_uuid(
    p_payload, 'dispatch_result_id'
  );
  generation_job_id_value := content_factory_private.require_uuid(
    p_payload, 'generation_job_id'
  );
  incident_id_value := content_factory_private.require_uuid(
    p_payload, 'incident_id'
  );
  resolution_value := lower(btrim(p_payload ->> 'resolution'));
  provider_task_id_value := nullif(btrim(
    coalesce(p_payload ->> 'provider_task_id', '')
  ), '');
  provider_status_value := nullif(lower(btrim(
    coalesce(p_payload ->> 'provider_status', '')
  )), '');
  if p_payload -> 'provider_task_created_at' <> 'null'::jsonb then
    begin
      provider_task_created_at_value :=
        (p_payload ->> 'provider_task_created_at')::timestamptz;
    exception when invalid_datetime_format or datetime_field_overflow then
      raise exception using errcode = '22023',
        message = 'generation_strategy_dispatch_reconciliation_payload_invalid';
    end;
  end if;
  evidence_hash_value := lower(btrim(
    p_payload ->> 'external_evidence_hash'
  ));
  confirmation_value := btrim(p_payload ->> 'confirmation');
  idempotency_key_value := btrim(p_payload ->> 'idempotency_key');
  if resolution_value not in (
       'provider_task_attached', 'confirmed_not_submitted'
     )
     or evidence_hash_value !~ '^[0-9a-f]{64}$'
     or length(idempotency_key_value) not between 8 and 180
     or idempotency_key_value ~ '[[:cntrl:]]'
     or (
       resolution_value = 'provider_task_attached' and (
         provider_task_id_value is null
         or length(provider_task_id_value) not between 8 and 240
         or provider_task_created_at_value is null
         or provider_status_value not in (
           'submitted', 'processing', 'succeeded', 'failed', 'cancelled'
         )
         or confirmation_value <> 'RUNWAY_TASK_ID_VERIFIED'
       )
     )
     or (
       resolution_value = 'confirmed_not_submitted' and (
         provider_task_id_value is not null
         or provider_task_created_at_value is not null
         or provider_status_value is not null
         or confirmation_value <> 'RUNWAY_NO_TASK_VERIFIED'
       )
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_dispatch_reconciliation_payload_invalid';
  end if;
  perform 1
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin');
  if not found
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_dispatch_reconciliation_access_required';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation_spend_budget')
  );
  request_hash_value := content_factory_private.json_hash(p_payload);
  select reconciliation.* into existing_row
  from content_factory.generation_strategy_dispatch_reconciliations
    reconciliation
  where reconciliation.organization_id = organization_id_value
    and (
      reconciliation.dispatch_result_id = result_id_value
      or reconciliation.idempotency_key = idempotency_key_value
    );
  if existing_row.id is not null then
    if existing_row.request_hash <> request_hash_value then
      raise exception using errcode = '55000',
        message =
          'generation_strategy_dispatch_reconciliation_idempotency_conflict';
    end if;
    reconciliation_row := existing_row;
    replay_value := true;
  else
    select result.* into result_row
    from content_factory.generation_strategy_dispatch_results result
    where result.organization_id = organization_id_value
      and result.project_id = project_id_value
      and result.id = result_id_value
      and result.generation_job_id = generation_job_id_value
      and result.outcome = 'ambiguous'
      and result.provider_post_started;
    select claim.* into claim_row
    from content_factory.generation_strategy_start_claims claim
    join content_factory.generation_strategy_dispatch_attempts attempt
      on attempt.organization_id = claim.organization_id
     and attempt.start_claim_id = claim.id
    where claim.organization_id = organization_id_value
      and attempt.id = result_row.dispatch_attempt_id;
    select job.* into job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id_value
      and job.project_id = project_id_value
      and job.id = generation_job_id_value
    for update;
    begin
      starting_at_value := (job_row.output ->> 'starting_at')::timestamptz;
      required_at_value :=
        (job_row.output ->> 'reconciliation_required_at')::timestamptz;
    exception when invalid_datetime_format or datetime_field_overflow then
      raise exception using errcode = '55000',
        message = 'generation_strategy_dispatch_reconciliation_not_current';
    end;
    if result_row.id is null or claim_row.id is null or job_row.id is null
       or job_row.status <> 'starting'
       or job_row.actual_cost_minor <> 0
       or job_row.output ->> 'reconciliation_incident_id' <>
            incident_id_value::text
       or not content_factory_private.real_generation_reconciliation_unresolved(
         job_row.output
       )
       or starting_at_value is null or required_at_value is null
       or (
         resolution_value = 'confirmed_not_submitted'
         and required_at_value > clock_timestamp() - interval '2 minutes'
       )
       or (
         resolution_value = 'provider_task_attached' and (
           provider_task_created_at_value <
             starting_at_value - interval '2 minutes'
           or provider_task_created_at_value >
             starting_at_value + interval '10 minutes'
           or provider_task_created_at_value >
             clock_timestamp() + interval '1 minute'
           or exists (
             select 1
             from content_factory.generation_strategy_dispatch_results other
             where other.provider_task_id = provider_task_id_value
             union all
             select 1
             from content_factory.generation_strategy_dispatch_reconciliations
               other
             where other.provider_task_id = provider_task_id_value
           )
         )
       ) then
      raise exception using errcode = '55000',
        message = 'generation_strategy_dispatch_reconciliation_not_current';
    end if;
    reconciliation_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'generation-strategy-dispatch-reconciliation-v1',
        'organization_id', organization_id_value,
        'project_id', project_id_value,
        'actor_id', actor_id_value,
        'dispatch_result_id', result_id_value,
        'generation_job_id', generation_job_id_value,
        'resolution', resolution_value,
        'provider_task_id', to_jsonb(provider_task_id_value),
        'provider_task_created_at',
          to_jsonb(provider_task_created_at_value),
        'provider_status', to_jsonb(provider_status_value),
        'external_evidence_hash', evidence_hash_value
      )
    );
    insert into content_factory.generation_strategy_dispatch_reconciliations (
      organization_id, project_id, actor_id, dispatch_result_id,
      generation_job_id, resolution, provider_task_id,
      provider_task_created_at, provider_status, external_evidence_hash,
      request_hash, reconciliation_hash, idempotency_key
    ) values (
      organization_id_value, project_id_value, actor_id_value,
      result_id_value, generation_job_id_value, resolution_value,
      provider_task_id_value, provider_task_created_at_value,
      provider_status_value, evidence_hash_value, request_hash_value,
      reconciliation_hash_value, idempotency_key_value
    ) returning * into reconciliation_row;
    if resolution_value = 'provider_task_attached' then
      update content_factory.generation_jobs job
      set status = 'submitted', actual_cost_minor = job.estimated_cost_minor,
          output = job.output || jsonb_build_object(
              'reconciliation_required', false,
              'provider_task_id', provider_task_id_value,
              'provider_task_created_at', provider_task_created_at_value,
              'provider_status_at_reconciliation',
                case provider_status_value
                  when 'submitted' then 'PENDING'
                  when 'processing' then 'RUNNING'
                  when 'succeeded' then 'SUCCEEDED'
                  when 'failed' then 'FAILED'
                  else 'CANCELLED'
                end,
              'submission_state', 'confirmed_submitted',
              'reconciliation_resolution', 'attach_existing_task',
              'reconciliation_resolved_at', clock_timestamp(),
              'reconciliation_resolved_by', actor_id_value,
              'reconciliation_evidence_reference',
                'strategy-external-evidence:' || evidence_hash_value,
              'reconciliation_reason',
                'Strategy dispatch reconciliation: an owner or admin confirmed the provider outcome with external evidence.',
              'reconciliation_payload_hash',
                content_factory_private.json_hash(jsonb_build_object(
                  'incident_id', incident_id_value,
                  'resolution', 'attach_existing_task',
                  'provider_task_id', provider_task_id_value,
                  'provider_task_created_at', provider_task_created_at_value,
                  'provider_status',
                    case provider_status_value
                      when 'submitted' then 'PENDING'
                      when 'processing' then 'RUNNING'
                      when 'succeeded' then 'SUCCEEDED'
                      when 'failed' then 'FAILED'
                      else 'CANCELLED'
                    end,
                  'evidence_reference',
                    'strategy-external-evidence:' || evidence_hash_value,
                  'reason',
                    'Strategy dispatch reconciliation: an owner or admin confirmed the provider outcome with external evidence.'
                )),
              'external_evidence_hash', evidence_hash_value,
              'currency', 'USD',
              'submitted_at', clock_timestamp()
            )
      where job.organization_id = organization_id_value
        and job.id = generation_job_id_value;
      update content_factory.generation_batches batch
      set status = 'submitted'
      where batch.organization_id = organization_id_value
        and batch.id = claim_row.batch_id;
      update content_factory.creator_tasks task
      set result = task.result || jsonb_build_object(
        'generation_status', 'submitted',
        'provider_task_id', provider_task_id_value,
        'reconciliation_required', false,
        'reconciliation_resolution', 'attach_existing_task'
      )
      where task.organization_id = organization_id_value
        and task.id = claim_row.review_task_id;
      event_hash_value := content_factory_private.json_hash(
        jsonb_build_object(
          'version', 'generation-strategy-provider-status-event-v1',
          'organization_id', organization_id_value,
          'project_id', project_id_value,
          'actor_id', actor_id_value,
          'generation_job_id', generation_job_id_value,
          'dispatch_result_id', result_id_value,
          'provider_task_id', provider_task_id_value,
          'transition_ordinal', 1,
          'previous_status', 'null'::jsonb,
          'provider_status', 'submitted',
          'output_snapshot', null,
          'failure_code', 'null'::jsonb
        )
      );
      insert into content_factory.generation_strategy_provider_status_events (
        organization_id, project_id, actor_id, generation_job_id,
        dispatch_result_id, provider_task_id, transition_ordinal,
        previous_status, provider_status, output_snapshot, failure_code,
        request_hash, event_hash, idempotency_key
      ) values (
        organization_id_value, project_id_value, actor_id_value,
        generation_job_id_value, result_id_value, provider_task_id_value, 1,
        null, 'submitted', null, null, request_hash_value, event_hash_value,
        'strategy-provider-reconciled:' || reconciliation_hash_value
      );
    else
      update content_factory.generation_jobs job
      set status = 'failed', actual_cost_minor = 0,
          output = job.output || jsonb_build_object(
              'reconciliation_required', false,
              'submission_state', 'confirmed_not_submitted',
              'reconciliation_resolution', 'confirm_no_submission',
              'reconciliation_resolved_at', clock_timestamp(),
              'reconciliation_resolved_by', actor_id_value,
              'reconciliation_evidence_reference',
                'strategy-external-evidence:' || evidence_hash_value,
              'reconciliation_reason',
                'Strategy dispatch reconciliation: an owner or admin confirmed the provider outcome with external evidence.',
              'reconciliation_payload_hash',
                content_factory_private.json_hash(jsonb_build_object(
                  'incident_id', incident_id_value,
                  'resolution', 'confirm_no_submission',
                  'provider_task_id', null,
                  'provider_task_created_at', null,
                  'provider_status', null,
                  'evidence_reference',
                    'strategy-external-evidence:' || evidence_hash_value,
                  'reason',
                    'Strategy dispatch reconciliation: an owner or admin confirmed the provider outcome with external evidence.'
                )),
              'external_evidence_hash', evidence_hash_value,
              'failure_code', 'provider_submission_not_found',
              'currency', 'USD',
              'failed_at', clock_timestamp()
            )
      where job.organization_id = organization_id_value
        and job.id = generation_job_id_value;
      update content_factory.generation_batches batch
      set status = 'failed'
      where batch.organization_id = organization_id_value
        and batch.id = claim_row.batch_id;
      update content_factory.creator_tasks task
      set status = 'cancelled',
          result = task.result || jsonb_build_object(
            'generation_status', 'failed',
            'reconciliation_required', false,
            'reconciliation_resolution', 'confirm_no_submission',
            'failure_code', 'provider_submission_not_found',
            'review_required', false
          )
      where task.organization_id = organization_id_value
        and task.id = claim_row.review_task_id;
    end if;
  end if;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.id = reconciliation_row.generation_job_id;
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-dispatch-reconciliation-response-v1',
    'replay', replay_value,
    'reconciliation', jsonb_build_object(
      'id', reconciliation_row.id,
      'reconciliation_hash', reconciliation_row.reconciliation_hash,
      'dispatch_result_id', reconciliation_row.dispatch_result_id,
      'generation_job_id', reconciliation_row.generation_job_id,
      'resolution', reconciliation_row.resolution,
      'provider_task_id', to_jsonb(reconciliation_row.provider_task_id),
      'provider_task_created_at',
        to_jsonb(reconciliation_row.provider_task_created_at),
      'provider_status', to_jsonb(reconciliation_row.provider_status),
      'reconciled_at', reconciliation_row.reconciled_at
    ),
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider_task_id', to_jsonb(job_row.output ->> 'provider_task_id'),
      'reconciliation_required', false
    ),
    'contract', jsonb_build_object(
      'second_post_allowed', false,
      'owner_admin_evidence_required', true,
      'reservation_settled_or_released', true
    )
  );
end;
$$;

do $generation_strategy_reconcile_guard_shape_verify$
declare
  function_source_value text;
begin
  select prosrc into function_source_value
  from pg_proc
  where oid =
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'::regprocedure;
  if function_source_value is null
     or function_source_value not like '%provider_submission_not_found%'
     or function_source_value not like '%reconciliation_resolved_at%'
     or function_source_value not like '%reconciliation_evidence_reference%'
     or function_source_value like '%provider_submission_not_created%'
     or function_source_value not like '%''currency'', ''USD''%' then
    raise exception using errcode = 'P0001',
      message = 'generation_strategy_reconcile_guard_shape_invalid';
  end if;
end;
$generation_strategy_reconcile_guard_shape_verify$;

commit;
