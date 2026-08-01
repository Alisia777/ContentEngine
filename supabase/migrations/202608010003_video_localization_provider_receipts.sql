begin;

create or replace function public.system_update_video_localization_assignment(
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
  assignment_id_value uuid;
  idempotency_key text;
  request_hash_value text;
  requested_status text;
  provider_task_hash_value text;
  output_media_id_value uuid;
  actual_cost_value bigint;
  failure_code_value text;
  assignment_row content_factory.video_localization_assignments%rowtype;
  batch_row content_factory.video_localization_batches%rowtype;
  operation_row content_factory_private.video_localization_provider_operations%rowtype;
  expected_batch_statuses text[];
  mapped_operation_status text;
  mapped_assignment_status text;
  batch_status_value text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'assignment_id', 'idempotency_key',
    'request_hash', 'status', 'provider_task_ref_hash',
    'output_media_id', 'actual_cost_microusd', 'failure_code'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'localization_operation_payload_invalid';
  end if;

  organization_id := content_factory_private.require_uuid(
    p_payload,
    'organization_id'
  );
  assignment_id_value := content_factory_private.require_uuid(
    p_payload,
    'assignment_id'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  request_hash_value := content_factory_private.require_text(
    p_payload,
    'request_hash',
    64,
    64
  );
  requested_status := content_factory_private.require_text(
    p_payload,
    'status',
    6,
    20
  );
  provider_task_hash_value := nullif(
    btrim(coalesce(p_payload ->> 'provider_task_ref_hash', '')),
    ''
  );
  failure_code_value := nullif(
    btrim(coalesce(p_payload ->> 'failure_code', '')),
    ''
  );

  if request_hash_value !~ '^[0-9a-f]{64}$'
     or requested_status not in (
       'reserved', 'submitted', 'processing',
       'succeeded', 'failed', 'unknown', 'released'
     )
     or (
       provider_task_hash_value is not null
       and provider_task_hash_value !~ '^[0-9a-f]{64}$'
     )
     or (
       failure_code_value is not null
       and length(failure_code_value) not between 3 and 120
     ) then
    raise exception using
      errcode = '22023',
      message = 'localization_operation_payload_invalid';
  end if;

  if requested_status in ('submitted', 'processing', 'succeeded')
     and provider_task_hash_value is null then
    raise exception using
      errcode = '22023',
      message = 'localization_provider_task_receipt_required';
  end if;
  if requested_status in ('failed', 'unknown')
     and failure_code_value is null then
    raise exception using
      errcode = '22023',
      message = 'localization_failure_code_required';
  end if;
  if requested_status = 'released'
     and provider_task_hash_value is not null then
    raise exception using
      errcode = '22023',
      message = 'localization_release_after_provider_forbidden';
  end if;

  if p_payload ? 'actual_cost_microusd' then
    if coalesce(p_payload ->> 'actual_cost_microusd', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'localization_actual_cost_invalid';
    end if;
    begin
      actual_cost_value := (p_payload ->> 'actual_cost_microusd')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'localization_actual_cost_invalid';
    end;
    if actual_cost_value > 100000000000 then
      raise exception using
        errcode = '22023',
        message = 'localization_actual_cost_invalid';
    end if;
  end if;

  if p_payload ? 'output_media_id' then
    output_media_id_value := content_factory_private.require_uuid(
      p_payload,
      'output_media_id'
    );
  end if;
  if requested_status = 'succeeded' and output_media_id_value is null then
    raise exception using
      errcode = '22023',
      message = 'localization_output_media_required';
  end if;
  if requested_status <> 'succeeded' and output_media_id_value is not null then
    raise exception using
      errcode = '22023',
      message = 'localization_output_media_not_allowed';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_assignment:' || assignment_id_value::text)
  );

  select assignment.* into assignment_row
  from content_factory.video_localization_assignments assignment
  where assignment.organization_id = organization_id
    and assignment.id = assignment_id_value
  for update;
  if assignment_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'localization_assignment_not_found';
  end if;

  select batch.* into batch_row
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = assignment_row.batch_id
  for update;
  if batch_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'localization_batch_not_found';
  end if;

  expected_batch_statuses := case assignment_row.wave
    when 1 then array['wave1_ready', 'wave1_running']::text[]
    else array['wave2_ready', 'wave2_running']::text[]
  end;

  select operation.* into operation_row
  from content_factory_private.video_localization_provider_operations operation
  where operation.organization_id = organization_id
    and operation.assignment_id = assignment_id_value
  for update;

  if operation_row.assignment_id is not null
     and (
       operation_row.idempotency_key <> idempotency_key
       or operation_row.request_hash <> request_hash_value
     ) then
    raise exception using
      errcode = '55000',
      message = 'localization_operation_request_mismatch';
  end if;

  mapped_operation_status := case requested_status
    when 'succeeded' then 'settled'
    when 'unknown' then 'frozen'
    else requested_status
  end;
  mapped_assignment_status := case requested_status
    when 'released' then 'ready'
    else requested_status
  end;

  if operation_row.assignment_id is not null
     and operation_row.status = mapped_operation_status
     and assignment_row.status = mapped_assignment_status then
    if requested_status = 'succeeded'
       and assignment_row.output_media_id is distinct from output_media_id_value then
      raise exception using
        errcode = '55000',
        message = 'localization_operation_replay_mismatch';
    end if;
    return jsonb_build_object(
      'ok', true,
      'assignment_id', assignment_id_value,
      'batch_id', assignment_row.batch_id,
      'assignment_status', assignment_row.status,
      'batch_status', batch_row.status,
      'replay', true,
      'provider_outcome_replay_forbidden',
        operation_row.status = 'frozen'
    );
  end if;

  if operation_row.assignment_id is null then
    if requested_status <> 'reserved'
       or assignment_row.status <> 'ready'
       or not (batch_row.status = any(expected_batch_statuses)) then
      raise exception using
        errcode = '55000',
        message = 'localization_operation_reservation_required';
    end if;
    if exists (
      select 1
      from content_factory.video_localization_assignments other
      where other.organization_id = organization_id
        and other.batch_id = assignment_row.batch_id
        and other.id <> assignment_id_value
        and other.status in (
          'reserved', 'submitted', 'processing', 'unknown'
        )
    ) then
      raise exception using
        errcode = '55000',
        message = 'localization_batch_has_inflight_assignment';
    end if;

    insert into content_factory_private.video_localization_provider_operations (
      organization_id,
      assignment_id,
      provider,
      idempotency_key,
      request_hash,
      status,
      reserved_cost_microusd
    ) values (
      organization_id,
      assignment_id_value,
      assignment_row.provider,
      idempotency_key,
      request_hash_value,
      'reserved',
      assignment_row.estimated_cost_microusd
    );

    update content_factory.video_localization_assignments assignment
    set status = 'reserved',
        failure_code = null
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;

    update content_factory.video_localization_batches batch
    set status = case assignment_row.wave
          when 1 then 'wave1_running'
          else 'wave2_running'
        end,
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = assignment_row.batch_id;

    return jsonb_build_object(
      'ok', true,
      'assignment_id', assignment_id_value,
      'batch_id', assignment_row.batch_id,
      'assignment_status', 'reserved',
      'batch_status', case assignment_row.wave
        when 1 then 'wave1_running'
        else 'wave2_running'
      end,
      'reserved_cost_microusd', assignment_row.estimated_cost_microusd,
      'provider_outcome_replay_forbidden', false
    );
  end if;

  if operation_row.status in ('settled', 'frozen', 'failed') then
    raise exception using
      errcode = '55000',
      message = 'localization_operation_terminal';
  end if;

  if operation_row.status = 'released' then
    if requested_status <> 'reserved'
       or assignment_row.status <> 'ready'
       or not (batch_row.status = any(expected_batch_statuses)) then
      raise exception using
        errcode = '55000',
        message = 'localization_operation_transition_invalid';
    end if;
    if exists (
      select 1
      from content_factory.video_localization_assignments other
      where other.organization_id = organization_id
        and other.batch_id = assignment_row.batch_id
        and other.id <> assignment_id_value
        and other.status in (
          'reserved', 'submitted', 'processing', 'unknown'
        )
    ) then
      raise exception using
        errcode = '55000',
        message = 'localization_batch_has_inflight_assignment';
    end if;

    update content_factory_private.video_localization_provider_operations operation
    set status = 'reserved',
        provider_task_ref_hash = null,
        actual_cost_microusd = null,
        failure_code = null
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = 'reserved',
        actual_cost_microusd = null,
        failure_code = null
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;

    update content_factory.video_localization_batches batch
    set status = case assignment_row.wave
          when 1 then 'wave1_running'
          else 'wave2_running'
        end,
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = assignment_row.batch_id;

    return jsonb_build_object(
      'ok', true,
      'assignment_id', assignment_id_value,
      'batch_id', assignment_row.batch_id,
      'assignment_status', 'reserved',
      'batch_status', case assignment_row.wave
        when 1 then 'wave1_running'
        else 'wave2_running'
      end,
      'replay', false,
      'provider_outcome_replay_forbidden', false
    );
  end if;

  if operation_row.status = 'reserved'
     and requested_status not in (
       'submitted', 'released', 'failed', 'unknown'
     ) then
    raise exception using
      errcode = '55000',
      message = 'localization_operation_transition_invalid';
  end if;
  if operation_row.status = 'submitted'
     and requested_status not in (
       'processing', 'succeeded', 'failed', 'unknown'
     ) then
    raise exception using
      errcode = '55000',
      message = 'localization_operation_transition_invalid';
  end if;
  if operation_row.status = 'processing'
     and requested_status not in ('succeeded', 'failed', 'unknown') then
    raise exception using
      errcode = '55000',
      message = 'localization_operation_transition_invalid';
  end if;

  if requested_status = 'released' then
    update content_factory_private.video_localization_provider_operations operation
    set status = 'released',
        provider_task_ref_hash = null,
        actual_cost_microusd = null,
        failure_code = null
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = 'ready',
        actual_cost_microusd = null,
        failure_code = null
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;

    if not exists (
      select 1
      from content_factory.video_localization_assignments other
      where other.organization_id = organization_id
        and other.batch_id = assignment_row.batch_id
        and other.id <> assignment_id_value
        and other.status in ('reserved', 'submitted', 'processing')
    ) then
      update content_factory.video_localization_batches batch
      set status = case assignment_row.wave
            when 1 then 'wave1_ready'
            else 'wave2_ready'
          end,
          version = batch.version + 1
      where batch.organization_id = organization_id
        and batch.id = assignment_row.batch_id;
    end if;
  elsif requested_status in ('submitted', 'processing') then
    update content_factory_private.video_localization_provider_operations operation
    set status = requested_status,
        provider_task_ref_hash = provider_task_hash_value,
        failure_code = null
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = requested_status,
        failure_code = null
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;
  elsif requested_status = 'succeeded' then
    if not exists (
      select 1
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = output_media_id_value
        and media.product_id = assignment_row.product_id
        and media.status = 'ready'
        and media.mime_type like 'video/%'
    ) then
      raise exception using
        errcode = '55000',
        message = 'localization_output_media_invalid';
    end if;

    actual_cost_value := coalesce(
      actual_cost_value,
      assignment_row.estimated_cost_microusd
    );

    update content_factory_private.video_localization_provider_operations operation
    set status = 'settled',
        provider_task_ref_hash = provider_task_hash_value,
        actual_cost_microusd = actual_cost_value,
        failure_code = null
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = 'succeeded',
        output_media_id = output_media_id_value,
        actual_cost_microusd = actual_cost_value,
        failure_code = null
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;

    if assignment_row.wave = 1 and not exists (
      select 1
      from content_factory.video_localization_assignments other
      where other.organization_id = organization_id
        and other.batch_id = assignment_row.batch_id
        and other.wave = 1
        and other.status <> 'succeeded'
    ) then
      update content_factory.video_localization_batches batch
      set status = 'qa_required',
          version = batch.version + 1
      where batch.organization_id = organization_id
        and batch.id = assignment_row.batch_id;
    elsif assignment_row.wave = 2 and not exists (
      select 1
      from content_factory.video_localization_assignments other
      where other.organization_id = organization_id
        and other.batch_id = assignment_row.batch_id
        and other.status <> 'succeeded'
    ) then
      update content_factory.video_localization_batches batch
      set status = 'completed',
          version = batch.version + 1
      where batch.organization_id = organization_id
        and batch.id = assignment_row.batch_id;
    end if;
  elsif requested_status in ('failed', 'unknown') then
    update content_factory_private.video_localization_provider_operations operation
    set status = case requested_status
          when 'unknown' then 'frozen'
          else 'failed'
        end,
        provider_task_ref_hash = coalesce(
          provider_task_hash_value,
          operation.provider_task_ref_hash
        ),
        actual_cost_microusd = actual_cost_value,
        failure_code = failure_code_value
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = requested_status,
        actual_cost_microusd = actual_cost_value,
        failure_code = failure_code_value
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;

    update content_factory.video_localization_assignments assignment
    set status = 'blocked',
        failure_code = case requested_status
          when 'unknown' then 'batch_paused_for_reconciliation'
          else 'batch_paused_after_provider_failure'
        end
    where assignment.organization_id = organization_id
      and assignment.batch_id = assignment_row.batch_id
      and assignment.id <> assignment_id_value
      and assignment.status in ('planned', 'ready');

    update content_factory.video_localization_batches batch
    set status = 'paused',
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = assignment_row.batch_id;
  end if;

  select batch.status into batch_status_value
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = assignment_row.batch_id;

  result := jsonb_build_object(
    'ok', true,
    'assignment_id', assignment_id_value,
    'batch_id', assignment_row.batch_id,
    'assignment_status', mapped_assignment_status,
    'batch_status', batch_status_value,
    'replay', false,
    'provider_outcome_replay_forbidden', requested_status = 'unknown'
  );

  return result;
end;
$$;

revoke all on function public.system_update_video_localization_assignment(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_update_video_localization_assignment(jsonb)
  to service_role;

commit;
