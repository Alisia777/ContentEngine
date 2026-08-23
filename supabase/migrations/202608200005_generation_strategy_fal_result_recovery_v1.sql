begin;

-- 202608200005_generation_strategy_fal_result_recovery_v1
--
-- A FAL queue job can be COMPLETED while the first result reader records the
-- terminal local failure provider_result_http_405.  Retrying submission would
-- create a second paid provider job.  This migration adds one deliberately
-- narrow, service-role-only correction path for the already-uploaded result:
-- the failed provider event remains immutable and a succeeded correction is
-- appended only after the complete claim/receipt/dispatch/task/storage and
-- settled-ledger identity has been re-proved under locks.

do $replace_provider_transition_check$
declare
  constraint_name_value text;
  constraint_count_value integer;
begin
  select count(*), min(constraint_row.conname)
    into constraint_count_value, constraint_name_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
          'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.contype = 'c'
    and lower(pg_get_constraintdef(constraint_row.oid)) like
          '%transition_ordinal = 1%'
    and lower(pg_get_constraintdef(constraint_row.oid)) like
          '%previous_status is null%'
    and lower(pg_get_constraintdef(constraint_row.oid)) like
          '%provider_status = ''submitted''%';

  if constraint_count_value <> 1 or constraint_name_value is null then
    raise exception using
      message = 'provider_status_transition_constraint_not_unique';
  end if;

  execute format(
    'alter table content_factory.generation_strategy_provider_status_events drop constraint %I',
    constraint_name_value
  );
end;
$replace_provider_transition_check$;

alter table content_factory.generation_strategy_provider_status_events
  add constraint generation_strategy_provider_status_transition_v2_check
  check (
    (
      transition_ordinal = 1
      and previous_status is null
      and provider_status = 'submitted'
    )
    or (
      transition_ordinal > 1
      and previous_status in ('submitted', 'processing')
      and provider_status in (
        'processing', 'succeeded', 'failed', 'cancelled'
      )
      and previous_status <> provider_status
    )
    or (
      transition_ordinal > 1
      and previous_status = 'failed'
      and provider_status = 'succeeded'
      and idempotency_key like 'strategy-result-recovery:%'
      and (output_snapshot ->> 'recovery_version') is not distinct from
        'generation-strategy-provider-result-recovery-v1'
      and (output_snapshot ->> 'recovered_failure_code') is not distinct from
        'provider_result_http_405'
    )
  );

create or replace function
  public.system_recover_generation_strategy_provider_result(
    input_payload jsonb default '{}'::jsonb
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
  generation_job_id_value uuid;
  provider_task_id_value text;
  provider_evidence_hash_value text;
  idempotency_key_value text;
  request_hash_value text;
  output_value jsonb;
  output_snapshot_value jsonb;
  output_object_name_value text;
  mime_type_value text;
  sha256_value text;
  size_bytes_value bigint;
  storage_object_id_value uuid;
  storage_metadata_value jsonb;
  storage_user_metadata_value jsonb;
  storage_size_value bigint;
  storage_mime_type_value text;
  storage_sha256_value text;
  next_transition_ordinal_value integer;
  event_hash_value text;
  ledger_count_before_value integer;
  ledger_count_after_value integer;
  ledger_hash_before_value text;
  ledger_hash_after_value text;
  reserved_count_value integer;
  settled_count_value integer;
  frozen_count_value integer;
  replay_value boolean := false;
  claim_row content_factory.generation_strategy_start_claims%rowtype;
  receipt_row
    content_factory.generation_strategy_readiness_receipts%rowtype;
  attempt_row
    content_factory.generation_strategy_dispatch_attempts%rowtype;
  dispatch_row
    content_factory.generation_strategy_dispatch_results%rowtype;
  latest_event_row
    content_factory.generation_strategy_provider_status_events%rowtype;
  event_row
    content_factory.generation_strategy_provider_status_events%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  media_row content_factory.media_objects%rowtype;
begin
  input_payload := content_factory_private.require_payload(input_payload);
  if input_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id',
       'generation_job_id', 'provider_task_id', 'output',
       'provider_evidence_hash', 'confirmation', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not input_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id',
       'generation_job_id', 'provider_task_id', 'output',
       'provider_evidence_hash', 'confirmation', 'idempotency_key'
     ]::text[]
     or (input_payload ->> 'version') is distinct from
       'generation-strategy-provider-result-recovery-request-v1'
     or (input_payload ->> 'confirmation') is distinct from
       'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'
     or jsonb_typeof(input_payload -> 'output') <> 'object'
     or (input_payload -> 'output') - array[
       'output_object_name', 'mime_type', 'size_bytes', 'sha256'
     ]::text[] <> '{}'::jsonb
     or not (input_payload -> 'output') ?& array[
       'output_object_name', 'mime_type', 'size_bytes', 'sha256'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_result_recovery_payload_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    input_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    input_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(
    input_payload, 'actor_id'
  );
  generation_job_id_value := content_factory_private.require_uuid(
    input_payload, 'generation_job_id'
  );
  provider_task_id_value := btrim(input_payload ->> 'provider_task_id');
  provider_evidence_hash_value := lower(btrim(
    input_payload ->> 'provider_evidence_hash'
  ));
  idempotency_key_value := btrim(input_payload ->> 'idempotency_key');
  output_value := input_payload -> 'output';
  output_object_name_value := btrim(output_value ->> 'output_object_name');
  mime_type_value := lower(btrim(output_value ->> 'mime_type'));
  sha256_value := lower(btrim(output_value ->> 'sha256'));

  if provider_task_id_value is null
     or length(provider_task_id_value) not between 8 and 240
     or provider_task_id_value ~ '[[:cntrl:]]'
     or provider_evidence_hash_value is null
     or provider_evidence_hash_value !~ '^[0-9a-f]{64}$'
     or idempotency_key_value is distinct from
       'strategy-result-recovery:' || generation_job_id_value::text || ':' ||
       left(provider_evidence_hash_value, 32)
     or length(idempotency_key_value) not between 8 and 180
     or idempotency_key_value ~ '[[:cntrl:]]'
     or output_object_name_value is null
     or length(output_object_name_value) not between 10 and 1000
     or output_object_name_value ~ '[[:cntrl:]]'
     or mime_type_value is distinct from 'video/mp4'
     or sha256_value is null
     or sha256_value !~ '^[0-9a-f]{64}$'
     or jsonb_typeof(output_value -> 'size_bytes') <> 'number'
     or coalesce(output_value ->> 'size_bytes', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_result_recovery_payload_invalid';
  end if;
  size_bytes_value := (output_value ->> 'size_bytes')::bigint;
  if size_bytes_value not between 1 and 52428800 then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_result_recovery_payload_invalid';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-strategy-result-recovery:' ||
      generation_job_id_value::text)
  );
  request_hash_value := content_factory_private.json_hash(input_payload);

  select existing_event.* into event_row
  from content_factory.generation_strategy_provider_status_events existing_event
  where existing_event.organization_id = organization_id_value
    and existing_event.idempotency_key = idempotency_key_value
  for update;

  if event_row.id is not null then
    if event_row.request_hash is distinct from request_hash_value
       or event_row.generation_job_id is distinct from generation_job_id_value
       or event_row.provider_task_id is distinct from provider_task_id_value
       or event_row.previous_status is distinct from 'failed'
       or event_row.provider_status is distinct from 'succeeded'
       or event_row.failure_code is not null
       or (event_row.output_snapshot ->> 'recovery_version') is distinct from
         'generation-strategy-provider-result-recovery-v1'
       or (event_row.output_snapshot ->> 'recovered_failure_code')
         is distinct from
         'provider_result_http_405'
       or (event_row.output_snapshot ->> 'output_object_name') is distinct from
         output_object_name_value
       or (event_row.output_snapshot ->> 'mime_type') is distinct from
         'video/mp4'
       or (event_row.output_snapshot ->> 'size_bytes') is distinct from
         size_bytes_value::text
       or (event_row.output_snapshot ->> 'sha256') is distinct from
         sha256_value then
      raise exception using errcode = '55000',
        message =
          'generation_strategy_provider_result_recovery_idempotency_conflict';
    end if;
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.id =
        (event_row.output_snapshot ->> 'output_media_id')::uuid;
    if media_row.id is null
       or media_row.status is distinct from 'ready'
       or media_row.mime_type is distinct from 'video/mp4'
       or media_row.size_bytes is distinct from size_bytes_value
       or media_row.sha256 is distinct from sha256_value then
      raise exception using errcode = '55000',
        message = 'generation_strategy_provider_result_recovery_replay_invalid';
    end if;
    replay_value := true;
    return jsonb_build_object(
      'ok', true,
      'version',
        'generation-strategy-provider-result-recovery-response-v1',
      'replay', replay_value,
      'event', jsonb_build_object(
        'generation_job_id', event_row.generation_job_id,
        'provider_task_id', event_row.provider_task_id,
        'previous_status', 'failed',
        'provider_status', 'succeeded'
      ),
      'output', jsonb_build_object(
        'media_id', media_row.id,
        'mime_type', 'video/mp4',
        'size_bytes', media_row.size_bytes
      ),
      'contract', jsonb_build_object(
        'provider_post_retried', false,
        'ledger_mutated', false,
        'manual_human_review_required', true
      )
    );
  end if;

  select claim.* into claim_row
  from content_factory.generation_strategy_start_claims claim
  where claim.organization_id = organization_id_value
    and claim.project_id = project_id_value
    and claim.actor_id = actor_id_value
    and claim.generation_job_id = generation_job_id_value
  for update;

  if claim_row.id is null then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_not_current';
  end if;

  select receipt.* into receipt_row
  from content_factory.generation_strategy_readiness_receipts receipt
  where receipt.organization_id = organization_id_value
    and receipt.id = claim_row.readiness_receipt_id
  for update;

  select attempt.* into attempt_row
  from content_factory.generation_strategy_dispatch_attempts attempt
  where attempt.organization_id = organization_id_value
    and attempt.start_claim_id = claim_row.id
    and attempt.generation_job_id = generation_job_id_value
  for update;

  select dispatch.* into dispatch_row
  from content_factory.generation_strategy_dispatch_results dispatch
  where dispatch.organization_id = organization_id_value
    and dispatch.dispatch_attempt_id = attempt_row.id
    and dispatch.generation_job_id = generation_job_id_value
  for update;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.project_id = project_id_value
    and job.id = generation_job_id_value
  for update;

  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = organization_id_value
    and batch.project_id = project_id_value
    and batch.id = claim_row.batch_id
  for update;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id_value
    and task.project_id = project_id_value
    and task.id = claim_row.review_task_id
  for update;

  select provider_event.* into latest_event_row
  from content_factory.generation_strategy_provider_status_events provider_event
  where provider_event.organization_id = organization_id_value
    and provider_event.generation_job_id = generation_job_id_value
  order by provider_event.transition_ordinal desc
  limit 1
  for update;

  if receipt_row.id is null
     or receipt_row.project_id is distinct from project_id_value
     or receipt_row.checked_by is distinct from actor_id_value
     or receipt_row.ready is distinct from true
     or receipt_row.provider is distinct from 'fal'
     or receipt_row.strategy_id is distinct from 'viral_product_swap'
     or receipt_row.recipe is distinct from 'product_swap'
     or receipt_row.product_id is distinct from job_row.product_id
     or receipt_row.receipt_hash is distinct from claim_row.receipt_hash
     or receipt_row.spec_strategy_binding_id is distinct from
       claim_row.spec_strategy_binding_id
     or receipt_row.binding_hash is distinct from claim_row.binding_hash
     or receipt_row.selection_hash is distinct from claim_row.selection_hash
     or receipt_row.price_hash is distinct from claim_row.price_hash
     or receipt_row.strategy_prompt_hash is distinct from
       claim_row.strategy_prompt_hash
     or receipt_row.spend_confirmation is distinct from
       claim_row.spend_confirmation
     or attempt_row.id is null
     or attempt_row.project_id is distinct from project_id_value
     or attempt_row.actor_id is distinct from actor_id_value
     or attempt_row.claim_hash is distinct from claim_row.claim_hash
     or dispatch_row.id is null
     or dispatch_row.project_id is distinct from project_id_value
     or dispatch_row.actor_id is distinct from actor_id_value
     or dispatch_row.attempt_hash is distinct from attempt_row.attempt_hash
     or dispatch_row.outcome is distinct from 'submitted'
     or dispatch_row.provider_post_started is distinct from true
     or dispatch_row.provider_http_status is null
     or dispatch_row.provider_http_status not between 200 and 299
     or dispatch_row.provider_task_id is distinct from provider_task_id_value
     or dispatch_row.failure_code is not null
     or job_row.id is null
     or job_row.batch_id is distinct from claim_row.batch_id
     or job_row.product_id is distinct from receipt_row.product_id
     or job_row.requested_by is distinct from actor_id_value
     or job_row.mode is distinct from 'real'
     or job_row.provider is distinct from 'fal'
     or job_row.allow_real_spend is distinct from true
     or job_row.status is distinct from 'failed'
     or job_row.estimated_cost_minor is null
     or job_row.estimated_cost_minor <= 0
     or job_row.actual_cost_minor is distinct from job_row.estimated_cost_minor
     or (job_row.input ->> 'provider') is distinct from 'fal'
     or (job_row.input ->> 'strategy_id') is distinct from
       'viral_product_swap'
     or (job_row.input ->> 'strategy_recipe') is distinct from 'product_swap'
     or (job_row.input #>> '{strategy_execution,version}') is distinct from
       'generation-strategy-execution-snapshot-v1'
     or (job_row.input ->> 'output_object_name') is distinct from
       output_object_name_value
     or (job_row.output ->> 'provider_task_id') is distinct from
       provider_task_id_value
     or (job_row.output ->> 'provider_status') is distinct from 'failed'
     or (job_row.output ->> 'failure_code') is distinct from
       'provider_result_http_405'
     or (job_row.output ->> 'provider_failure_code') is distinct from
       'provider_result_http_405'
     or (job_row.output ->> 'provider_billing_outcome') is distinct from
       'unknown'
     or job_row.output ->> 'output_media_id' is not null
     or batch_row.id is null
     or batch_row.product_id is distinct from job_row.product_id
     or batch_row.created_by is distinct from actor_id_value
     or batch_row.mode is distinct from 'real'
     or batch_row.provider is distinct from 'fal'
     or batch_row.allow_real_spend is distinct from true
     or batch_row.status is distinct from 'failed'
     or batch_row.total_requested is distinct from 1
     or batch_row.total_created is distinct from 0
     or batch_row.estimated_cost_minor is distinct from
       job_row.estimated_cost_minor
     or task_row.id is null
     or task_row.generation_job_id is distinct from generation_job_id_value
     or task_row.product_id is distinct from job_row.product_id
     or task_row.assignee_id is distinct from actor_id_value
     or task_row.created_by is distinct from actor_id_value
     or task_row.task_type is distinct from 'video_review'
     or task_row.status is distinct from 'cancelled'
     or (task_row.result ->> 'generation_status') is distinct from 'failed'
     or (task_row.result ->> 'failure_code') is distinct from
       'provider_result_http_405'
     or latest_event_row.id is null
     or latest_event_row.project_id is distinct from project_id_value
     or latest_event_row.actor_id is distinct from actor_id_value
     or latest_event_row.dispatch_result_id is distinct from dispatch_row.id
     or latest_event_row.provider_task_id is distinct from
       provider_task_id_value
     or latest_event_row.provider_status is distinct from 'failed'
     or latest_event_row.failure_code is distinct from
       'provider_result_http_405'
     or latest_event_row.output_snapshot is not null
     or exists (
       select 1
       from content_factory.generation_strategy_dispatch_reconciliations
         reconciliation
       where reconciliation.organization_id = organization_id_value
         and reconciliation.generation_job_id = generation_job_id_value
     )
     or exists (
       select 1
       from content_factory.generation_strategy_provider_status_events
         succeeded_event
       where succeeded_event.organization_id = organization_id_value
         and succeeded_event.generation_job_id = generation_job_id_value
         and succeeded_event.provider_status = 'succeeded'
     ) then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_not_current';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation_spend_budget')
  );
  perform ledger.id
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value
  order by ledger.id
  for update;

  select
    count(*)::integer,
    count(*) filter (where ledger.event_type = 'reserved')::integer,
    count(*) filter (where ledger.event_type = 'settled')::integer,
    count(*) filter (where ledger.event_type = 'frozen')::integer,
    content_factory_private.json_hash(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)
    )
  into
    ledger_count_before_value,
    reserved_count_value,
    settled_count_value,
    frozen_count_value,
    ledger_hash_before_value
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value;

  if reserved_count_value <> 1
     or settled_count_value <> 1
     or frozen_count_value not in (0, 1)
     or ledger_count_before_value <> 2 + frozen_count_value
     or not exists (
       select 1
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id = organization_id_value
         and ledger.generation_job_id = generation_job_id_value
         and ledger.event_type = 'reserved'
         and ledger.estimated_cost_minor = job_row.estimated_cost_minor
         and ledger.actual_cost_minor = 0
         and ledger.reserved_delta_minor = job_row.estimated_cost_minor
         and ledger.committed_delta_minor = 0
         and ledger.currency = 'USD'
     )
     or not exists (
       select 1
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id = organization_id_value
         and ledger.generation_job_id = generation_job_id_value
         and ledger.event_type = 'settled'
         and ledger.estimated_cost_minor = job_row.estimated_cost_minor
         and ledger.actual_cost_minor = job_row.estimated_cost_minor
         and ledger.reserved_delta_minor = -job_row.estimated_cost_minor
         and ledger.committed_delta_minor = job_row.estimated_cost_minor
         and ledger.currency = 'USD'
         and (ledger.metadata ->> 'provider_task_id') is not distinct from
           provider_task_id_value
     )
     or exists (
       select 1
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id = organization_id_value
         and ledger.generation_job_id = generation_job_id_value
         and ledger.event_type = 'frozen'
         and (
           ledger.estimated_cost_minor <> job_row.estimated_cost_minor
           or ledger.actual_cost_minor <> 0
           or ledger.reserved_delta_minor <> 0
           or ledger.committed_delta_minor <> 0
           or ledger.currency <> 'USD'
           or ledger.reason_code <> 'provider_billing_outcome_unknown'
           or (ledger.metadata ->> 'provider_task_id') is distinct from
             provider_task_id_value
         )
     ) then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_ledger_invalid';
  end if;

  perform pg_advisory_xact_lock(
    hashtext('contentengine-private'),
    hashtext(output_object_name_value)
  );
  select storage_object.id, storage_object.metadata,
         storage_object.user_metadata
    into storage_object_id_value, storage_metadata_value,
         storage_user_metadata_value
  from storage.objects storage_object
  where storage_object.bucket_id = 'contentengine-private'
    and storage_object.name = output_object_name_value
  for update;

  if storage_object_id_value is null
     or jsonb_typeof(storage_metadata_value) <> 'object'
     or coalesce(storage_metadata_value ->> 'size', '') !~ '^[0-9]+$' then
    raise exception using errcode = 'P0002',
      message = 'generation_strategy_provider_result_recovery_storage_invalid';
  end if;
  storage_size_value := (storage_metadata_value ->> 'size')::bigint;
  storage_mime_type_value := lower(btrim(
    storage_metadata_value ->> 'mimetype'
  ));
  storage_sha256_value := lower(btrim(coalesce(
    storage_user_metadata_value ->> 'sha256',
    storage_metadata_value ->> 'sha256',
    ''
  )));
  if storage_size_value is distinct from size_bytes_value
     or storage_mime_type_value is distinct from 'video/mp4'
     or storage_sha256_value is distinct from sha256_value then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_result_recovery_storage_mismatch';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.bucket_id = 'contentengine-private'
    and media.object_name = output_object_name_value
  for update;

  if media_row.id is not null and (
    media_row.organization_id is distinct from organization_id_value
    or media_row.project_id is distinct from project_id_value
    or media_row.owner_id is distinct from actor_id_value
    or media_row.task_id is distinct from claim_row.review_task_id
    or media_row.product_id is distinct from job_row.product_id
    or media_row.mime_type is distinct from 'video/mp4'
    or media_row.size_bytes is distinct from size_bytes_value
    or media_row.sha256 is distinct from sha256_value
    or media_row.status is distinct from 'ready'
    or (media_row.metadata ->> 'kind') is distinct from 'generated_video'
    or (media_row.metadata ->> 'provider') is distinct from 'fal'
    or (media_row.metadata ->> 'model') is distinct from receipt_row.recipe
    or (media_row.metadata ->> 'strategy_id') is distinct from
      receipt_row.strategy_id
    or (media_row.metadata ->> 'recipe_version') is distinct from
      receipt_row.recipe_version
    or (media_row.metadata ->> 'generation_job_id') is distinct from
      job_row.id::text
    or media_row.metadata -> 'review_required' is distinct from 'true'::jsonb
  ) then
    raise exception using errcode = '23505',
      message = 'generation_strategy_provider_result_recovery_media_conflict';
  end if;

  if media_row.id is null then
    insert into content_factory.media_objects (
      organization_id, project_id, owner_id, task_id, product_id,
      bucket_id, object_name, mime_type, size_bytes, sha256, status,
      metadata, idempotency_key
    ) values (
      organization_id_value, project_id_value, actor_id_value,
      claim_row.review_task_id, job_row.product_id,
      'contentengine-private', output_object_name_value, 'video/mp4',
      size_bytes_value, sha256_value, 'ready', jsonb_build_object(
        'original_filename', job_row.id::text || '.mp4',
        'kind', 'generated_video',
        'provider', 'fal',
        'model', receipt_row.recipe,
        'strategy_id', receipt_row.strategy_id,
        'recipe_version', receipt_row.recipe_version,
        'duration_seconds',
          receipt_row.selection_snapshot -> 'duration_seconds',
        'audio', receipt_row.selection_snapshot -> 'audio',
        'ratio', receipt_row.price_snapshot -> 'ratio',
        'resolution', receipt_row.price_snapshot -> 'resolution',
        'generation_job_id', job_row.id,
        'review_required', true
      ), 'strategy-output:' || job_row.id::text
    ) returning * into media_row;
  end if;

  output_snapshot_value := jsonb_build_object(
    'output_media_id', media_row.id,
    'output_object_name', output_object_name_value,
    'mime_type', 'video/mp4',
    'size_bytes', size_bytes_value,
    'sha256', sha256_value,
    'recovery_version',
      'generation-strategy-provider-result-recovery-v1',
    'recovered_failure_code', 'provider_result_http_405',
    'provider_evidence_hash', provider_evidence_hash_value,
    'recovered_from_event_id', latest_event_row.id
  );
  next_transition_ordinal_value := latest_event_row.transition_ordinal + 1;
  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-strategy-provider-status-event-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'actor_id', actor_id_value,
    'generation_job_id', generation_job_id_value,
    'dispatch_result_id', dispatch_row.id,
    'provider_task_id', provider_task_id_value,
    'transition_ordinal', next_transition_ordinal_value,
    'previous_status', to_jsonb('failed'::text),
    'provider_status', 'succeeded',
    'output_snapshot', output_snapshot_value,
    'failure_code', to_jsonb(null::text)
  ));

  insert into content_factory.generation_strategy_provider_status_events (
    organization_id, project_id, actor_id, generation_job_id,
    dispatch_result_id, provider_task_id, transition_ordinal,
    previous_status, provider_status, output_snapshot, failure_code,
    request_hash, event_hash, idempotency_key
  ) values (
    organization_id_value, project_id_value, actor_id_value,
    generation_job_id_value, dispatch_row.id, provider_task_id_value,
    next_transition_ordinal_value, 'failed', 'succeeded',
    output_snapshot_value, null, request_hash_value, event_hash_value,
    idempotency_key_value
  ) returning * into event_row;

  update content_factory.generation_jobs job
  set status = 'succeeded',
      actual_cost_minor = job.estimated_cost_minor,
      output = (
        job.output - array[
          'failure_code', 'provider_failure_code',
          'provider_billing_outcome', 'failed_at',
          'error', 'error_code', 'error_message'
        ]::text[]
      ) || output_snapshot_value || jsonb_build_object(
        'provider_status', 'succeeded',
        'provider_evidence_hash', provider_evidence_hash_value,
        'succeeded_at', clock_timestamp(),
        'actual_cost_minor', job.estimated_cost_minor,
        'currency', 'USD'
      )
  where job.organization_id = organization_id_value
    and job.id = generation_job_id_value
    and job.status = 'failed';
  if not found then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_not_current';
  end if;

  update content_factory.generation_batches batch
  set status = 'succeeded', total_created = 1
  where batch.organization_id = organization_id_value
    and batch.id = claim_row.batch_id
    and batch.status = 'failed'
    and batch.total_created = 0;
  if not found then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_not_current';
  end if;

  update content_factory.creator_tasks task
  set status = 'review',
      submitted_at = coalesce(task.submitted_at, clock_timestamp()),
      completed_at = null,
      result = (
        task.result - array[
          'failure_code', 'provider_failure_code',
          'provider_billing_outcome', 'failed_at',
          'error', 'error_code', 'error_message'
        ]::text[]
      ) || jsonb_build_object(
        'generation_status', 'succeeded',
        'review_required', true,
        'review_mode', 'manual_human_review',
        'output_media_id', media_row.id,
        'provider', 'fal',
        'model', receipt_row.recipe,
        'strategy_id', receipt_row.strategy_id,
        'actual_cost_minor', job_row.estimated_cost_minor,
        'currency', 'USD',
        'recovery_version',
          'generation-strategy-provider-result-recovery-v1',
        'recovered_failure_code', 'provider_result_http_405'
      )
  where task.organization_id = organization_id_value
    and task.id = claim_row.review_task_id
    and task.status = 'cancelled';
  if not found then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_not_current';
  end if;

  select
    count(*)::integer,
    content_factory_private.json_hash(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)
    )
  into ledger_count_after_value, ledger_hash_after_value
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value;

  if ledger_count_after_value is distinct from ledger_count_before_value
     or ledger_hash_after_value is distinct from ledger_hash_before_value then
    raise exception using errcode = '55000',
      message = 'generation_strategy_provider_result_recovery_ledger_changed';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-provider-result-recovery-response-v1',
    'replay', replay_value,
    'event', jsonb_build_object(
      'generation_job_id', event_row.generation_job_id,
      'provider_task_id', event_row.provider_task_id,
      'previous_status', 'failed',
      'provider_status', 'succeeded'
    ),
    'output', jsonb_build_object(
      'media_id', media_row.id,
      'mime_type', 'video/mp4',
      'size_bytes', media_row.size_bytes
    ),
    'contract', jsonb_build_object(
      'provider_post_retried', false,
      'ledger_mutated', false,
      'manual_human_review_required', true
    )
  );
end;
$$;

revoke all on function
  public.system_recover_generation_strategy_provider_result(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_recover_generation_strategy_provider_result(jsonb)
  to service_role;

comment on function
  public.system_recover_generation_strategy_provider_result(jsonb) is
  'Service-only append-only correction for one paid FAL provider_result_http_405 after provider completion. It verifies an existing uploaded MP4 and the immutable settled ledger, never resubmits or rebills, and returns the recovered task to manual human review.';

do $verify_provider_result_recovery$
declare
  definition_value text;
  transition_constraint_value text;
begin
  select pg_get_functiondef(
    'public.system_recover_generation_strategy_provider_result(jsonb)'::regprocedure
  ) into definition_value;
  if definition_value is null
     or position($v$receipt_row.provider is distinct from 'fal'$v$
          in definition_value) = 0
     or position($v$latest_event_row.provider_status is distinct from 'failed'$v$
          in definition_value) = 0
     or position($v$latest_event_row.failure_code is distinct from$v$
          in definition_value) = 0
     or position($v$ledger_hash_after_value is distinct from ledger_hash_before_value$v$
          in definition_value) = 0
     or position($v$insert into content_factory.generation_spend_ledger$v$
          in lower(definition_value)) > 0
     or position($v$update content_factory.generation_strategy_provider_status_events$v$
          in lower(definition_value)) > 0
     or position($v$delete from content_factory.generation_strategy_provider_status_events$v$
          in lower(definition_value)) > 0 then
    raise exception using message = 'provider_result_recovery_definition_invalid';
  end if;

  select pg_get_constraintdef(constraint_row.oid)
    into transition_constraint_value
  from pg_constraint constraint_row
  where constraint_row.conrelid =
          'content_factory.generation_strategy_provider_status_events'::regclass
    and constraint_row.conname =
      'generation_strategy_provider_status_transition_v2_check';
  if transition_constraint_value is null
     or position(
       'previous_status = ''failed''' in transition_constraint_value
     ) = 0
     or position(
       'provider_status = ''succeeded''' in transition_constraint_value
     ) = 0
     or position(
       'recovery_version' in transition_constraint_value
     ) = 0
     or position('IS DISTINCT FROM' in transition_constraint_value) = 0
     or position('NOT (' in transition_constraint_value) = 0
     or position('provider_result_http_405' in transition_constraint_value) = 0
     or position('strategy-result-recovery:' in transition_constraint_value) = 0
  then
    raise exception using message =
      'provider_result_recovery_transition_constraint_invalid';
  end if;

  if has_function_privilege(
       'authenticated',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'anon',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     )
     or not has_function_privilege(
       'service_role',
       'public.system_recover_generation_strategy_provider_result(jsonb)',
       'execute'
     ) then
    raise exception using message = 'provider_result_recovery_grants_invalid';
  end if;
end;
$verify_provider_result_recovery$;

commit;
