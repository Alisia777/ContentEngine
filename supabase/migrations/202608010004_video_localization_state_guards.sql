begin;

create or replace function content_factory_private.valid_video_localization_modes(
  value jsonb
)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
begin
  if jsonb_typeof(value) is distinct from 'array' then
    return false;
  end if;
  if jsonb_array_length(value) not between 1 and 3 then
    return false;
  end if;
  if exists (
    select 1
    from jsonb_array_elements(value) item(element)
    where jsonb_typeof(item.element) <> 'string'
       or item.element #>> '{}' not in (
         'subtitles', 'dub_audio', 'lip_sync'
       )
  ) then
    return false;
  end if;
  return (
    select count(*) = count(distinct mode)
    from jsonb_array_elements_text(value) item(mode)
  );
end;
$$;

create or replace function content_factory_private.valid_video_localization_checklist(
  value jsonb
)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
begin
  if jsonb_typeof(value) is distinct from 'object' then
    return false;
  end if;
  if not (
    value ?& array[
      'product_fidelity', 'language_quality',
      'no_common_defect', 'rights_ok'
    ]::text[]
  ) or value - array[
    'product_fidelity', 'language_quality',
    'no_common_defect', 'rights_ok'
  ]::text[] <> '{}'::jsonb then
    return false;
  end if;
  return not exists (
    select 1
    from jsonb_each(value) item(key, element)
    where jsonb_typeof(item.element) <> 'boolean'
  );
end;
$$;

create or replace function content_factory_private.guard_video_localization_batch_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.organization_id <> old.organization_id
     or new.id <> old.id
     or new.product_id <> old.product_id
     or new.created_by <> old.created_by
     or new.target_language <> old.target_language
     or new.target_count <> old.target_count
     or new.source_count <> old.source_count
     or new.modes <> old.modes
     or new.qa_gate_after_sequence <> old.qa_gate_after_sequence
     or new.rate_card_snapshot_id <> old.rate_card_snapshot_id
     or new.rate_card_snapshot <> old.rate_card_snapshot
     or new.plan_hash <> old.plan_hash
     or new.total_estimated_cost_microusd <> old.total_estimated_cost_microusd
     or new.full_generation_baseline_microusd <> old.full_generation_baseline_microusd
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'video_localization_batch_plan_immutable';
  end if;

  if new.status = old.status then
    return new;
  end if;
  if old.status = 'wave1_ready'
     and new.status not in ('wave1_running', 'paused', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status = 'wave1_running'
     and new.status not in ('wave1_ready', 'qa_required', 'paused', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status = 'qa_required'
     and new.status not in ('wave2_ready', 'paused', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status = 'wave2_ready'
     and new.status not in ('wave2_running', 'paused', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status = 'wave2_running'
     and new.status not in ('wave2_ready', 'completed', 'paused', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status = 'paused' and new.status <> 'cancelled' then
    raise exception using errcode = '55000', message = 'localization_batch_transition_invalid';
  elsif old.status in ('completed', 'failed', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_batch_terminal';
  end if;
  return new;
end;
$$;

create or replace function content_factory_private.guard_video_localization_assignment_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.organization_id <> old.organization_id
     or new.id <> old.id
     or new.batch_id <> old.batch_id
     or new.product_id <> old.product_id
     or new.source_media_id <> old.source_media_id
     or new.sequence <> old.sequence
     or new.wave <> old.wave
     or new.mode <> old.mode
     or new.provider <> old.provider
     or new.source_language <> old.source_language
     or new.target_language <> old.target_language
     or new.duration_seconds <> old.duration_seconds
     or new.source_asset_sha256 <> old.source_asset_sha256
     or new.assignment_hash <> old.assignment_hash
     or new.estimated_cost_microusd <> old.estimated_cost_microusd
     or new.requires_manual_text_edit <> old.requires_manual_text_edit
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'video_localization_assignment_plan_immutable';
  end if;

  if new.status = old.status then
    return new;
  end if;
  if old.status = 'planned'
     and new.status not in ('ready', 'blocked', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status = 'ready'
     and new.status not in ('reserved', 'blocked', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status = 'reserved'
     and new.status not in ('submitted', 'ready', 'failed', 'unknown') then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status = 'submitted'
     and new.status not in ('processing', 'succeeded', 'failed', 'unknown') then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status = 'processing'
     and new.status not in ('succeeded', 'failed', 'unknown') then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status = 'blocked' and new.status <> 'cancelled' then
    raise exception using errcode = '55000', message = 'localization_assignment_transition_invalid';
  elsif old.status in ('succeeded', 'failed', 'unknown', 'cancelled') then
    raise exception using errcode = '55000', message = 'localization_assignment_terminal';
  end if;
  return new;
end;
$$;

create or replace function content_factory_private.guard_video_localization_provider_operation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.organization_id <> old.organization_id
     or new.assignment_id <> old.assignment_id
     or new.provider <> old.provider
     or new.idempotency_key <> old.idempotency_key
     or new.request_hash <> old.request_hash
     or new.reserved_cost_microusd <> old.reserved_cost_microusd
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'localization_provider_receipt_identity_immutable';
  end if;
  if old.provider_task_ref_hash is not null
     and new.provider_task_ref_hash is distinct from old.provider_task_ref_hash then
    raise exception using
      errcode = '55000',
      message = 'localization_provider_task_receipt_mismatch';
  end if;
  if new.status in ('submitted', 'processing', 'settled')
     and new.provider_task_ref_hash is null then
    raise exception using
      errcode = '55000',
      message = 'localization_provider_task_receipt_required';
  end if;
  if new.status in ('failed', 'frozen') and new.failure_code is null then
    raise exception using
      errcode = '55000',
      message = 'localization_failure_code_required';
  end if;
  if new.status = 'settled' and new.actual_cost_microusd is null then
    raise exception using
      errcode = '55000',
      message = 'localization_actual_cost_required';
  end if;

  if new.status = old.status then
    if new is distinct from old then
      raise exception using
        errcode = '55000',
        message = 'localization_provider_receipt_replay_mismatch';
    end if;
    return new;
  end if;
  if old.status = 'reserved'
     and new.status not in ('submitted', 'released', 'failed', 'frozen') then
    raise exception using errcode = '55000', message = 'localization_provider_transition_invalid';
  elsif old.status = 'released' and new.status <> 'reserved' then
    raise exception using errcode = '55000', message = 'localization_provider_transition_invalid';
  elsif old.status = 'submitted'
     and new.status not in ('processing', 'settled', 'failed', 'frozen') then
    raise exception using errcode = '55000', message = 'localization_provider_transition_invalid';
  elsif old.status = 'processing'
     and new.status not in ('settled', 'failed', 'frozen') then
    raise exception using errcode = '55000', message = 'localization_provider_transition_invalid';
  elsif old.status in ('settled', 'failed', 'frozen') then
    raise exception using errcode = '55000', message = 'localization_provider_operation_terminal';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_video_localization_batch_state
  on content_factory.video_localization_batches;
create trigger guard_video_localization_batch_state
before update on content_factory.video_localization_batches
for each row execute function content_factory_private.guard_video_localization_batch_state();

drop trigger if exists guard_video_localization_assignment_state
  on content_factory.video_localization_assignments;
create trigger guard_video_localization_assignment_state
before update on content_factory.video_localization_assignments
for each row execute function content_factory_private.guard_video_localization_assignment_state();

drop trigger if exists guard_video_localization_provider_operation
  on content_factory_private.video_localization_provider_operations;
create trigger guard_video_localization_provider_operation
before update on content_factory_private.video_localization_provider_operations
for each row execute function content_factory_private.guard_video_localization_provider_operation();

commit;
