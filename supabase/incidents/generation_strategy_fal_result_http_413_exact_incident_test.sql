begin;

-- One-shot production-shaped rollback test for the paid Pika incident.
-- Run only before the durable recovery. Every write, including the synthetic
-- storage catalog row, is rolled back by the final statement.

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

create temporary table incident_413_runtime_result (
  wrong_confirmation_sqlstate text not null,
  wrong_confirmation_message text not null,
  fresh_response jsonb not null,
  replay_response jsonb not null,
  ledger_count_before integer not null,
  ledger_count_after integer not null,
  ledger_count_after_replay integer not null,
  ledger_hash_before text not null,
  ledger_hash_after text not null,
  ledger_hash_after_replay text not null,
  event_count_before integer not null,
  event_count_after integer not null,
  event_count_after_replay integer not null,
  media_count_before integer not null,
  media_count_after integer not null,
  media_count_after_replay integer not null,
  dispatch_count_before integer not null,
  dispatch_count_after_replay integer not null
) on commit drop;

do $incident_413_runtime$
declare
  organization_id_value constant uuid :=
    'df147614-a4ef-4e66-8b79-1b89f5481ddf';
  project_id_value constant uuid :=
    '4f0fcfa2-7233-4c0c-9e16-2c20e0aae379';
  actor_id_value constant uuid :=
    '05876b51-19e9-4118-a04b-6987642b147e';
  generation_job_id_value constant uuid :=
    '88504197-4f6a-4159-9797-6f89cba92db9';
  provider_task_id_value constant text :=
    '01a0232c-2253-7553-a95f-316eec7bffe7';
  output_object_name_value constant text :=
    'df147614-a4ef-4e66-8b79-1b89f5481ddf/' ||
    '05876b51-19e9-4118-a04b-6987642b147e/generated/strategy/' ||
    '88504197-4f6a-4159-9797-6f89cba92db9.mp4';
  provider_evidence_hash_value constant text := repeat('e', 64);
  output_sha256_value constant text := repeat('d', 64);
  output_size_value constant bigint := 4096;
  idempotency_key_value constant text :=
    'strategy-result-recovery:' ||
    '88504197-4f6a-4159-9797-6f89cba92db9:' || repeat('e', 32);
  request_base jsonb;
  wrong_confirmation_sqlstate_value text := '';
  wrong_confirmation_message_value text := '';
  fresh_response_value jsonb;
  replay_response_value jsonb;
  ledger_count_before_value integer;
  ledger_count_after_value integer;
  ledger_count_after_replay_value integer;
  ledger_hash_before_value text;
  ledger_hash_after_value text;
  ledger_hash_after_replay_value text;
  event_count_before_value integer;
  event_count_after_value integer;
  event_count_after_replay_value integer;
  media_count_before_value integer;
  media_count_after_value integer;
  media_count_after_replay_value integer;
  dispatch_count_before_value integer;
  dispatch_count_after_replay_value integer;
begin
  if not exists (
    select 1
    from content_factory.generation_jobs job
    where job.organization_id = organization_id_value
      and job.project_id = project_id_value
      and job.id = generation_job_id_value
      and job.status = 'failed'
      and job.provider = 'fal'
      and job.estimated_cost_minor = 47
      and job.actual_cost_minor = 47
      and (job.output ->> 'provider_task_id') = provider_task_id_value
      and (job.output ->> 'failure_code') = 'provider_result_http_413'
      and (job.output ->> 'provider_failure_code') =
        'provider_result_http_413'
      and (job.output ->> 'provider_billing_outcome') = 'unknown'
  ) then
    raise exception using message =
      'exact_incident_413_failed_precondition_missing';
  end if;

  if exists (
    select 1 from storage.objects storage_object
    where storage_object.bucket_id = 'contentengine-private'
      and storage_object.name = output_object_name_value
  ) then
    raise exception using message =
      'exact_incident_413_storage_precondition_not_empty';
  end if;

  request_base := jsonb_build_object(
    'version', 'generation-strategy-provider-result-recovery-request-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'actor_id', actor_id_value,
    'generation_job_id', generation_job_id_value,
    'provider_task_id', provider_task_id_value,
    'output', jsonb_build_object(
      'output_object_name', output_object_name_value,
      'mime_type', 'video/mp4',
      'size_bytes', output_size_value,
      'sha256', output_sha256_value
    ),
    'provider_evidence_hash', provider_evidence_hash_value,
    'idempotency_key', idempotency_key_value
  );

  begin
    perform public.system_recover_generation_strategy_provider_result(
      request_base || jsonb_build_object(
        'confirmation', 'FAL_RESULT_HTTP_405_RECOVERY_VERIFIED'
      )
    );
    wrong_confirmation_sqlstate_value := 'unexpected_success';
    wrong_confirmation_message_value := 'unexpected_success';
  exception when others then
    get stacked diagnostics
      wrong_confirmation_sqlstate_value = returned_sqlstate,
      wrong_confirmation_message_value = message_text;
  end;

  select
    count(*)::integer,
    content_factory_private.json_hash(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)
    )
    into ledger_count_before_value, ledger_hash_before_value
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value;
  select count(*)::integer into event_count_before_value
  from content_factory.generation_strategy_provider_status_events event
  where event.organization_id = organization_id_value
    and event.generation_job_id = generation_job_id_value;
  select count(*)::integer into media_count_before_value
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.object_name = output_object_name_value;
  select count(*)::integer into dispatch_count_before_value
  from content_factory.generation_strategy_dispatch_results dispatch
  where dispatch.organization_id = organization_id_value
    and dispatch.generation_job_id = generation_job_id_value;

  insert into storage.objects (
    bucket_id, name, owner, metadata, owner_id, user_metadata
  ) values (
    'contentengine-private', output_object_name_value, actor_id_value,
    jsonb_build_object(
      'size', output_size_value::text,
      'mimetype', 'video/mp4'
    ), actor_id_value::text,
    jsonb_build_object('sha256', output_sha256_value)
  );

  select public.system_recover_generation_strategy_provider_result(
    request_base || jsonb_build_object(
      'confirmation', 'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'
    )
  ) into strict fresh_response_value;

  select
    count(*)::integer,
    content_factory_private.json_hash(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)
    )
    into ledger_count_after_value, ledger_hash_after_value
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value;
  select count(*)::integer into event_count_after_value
  from content_factory.generation_strategy_provider_status_events event
  where event.organization_id = organization_id_value
    and event.generation_job_id = generation_job_id_value;
  select count(*)::integer into media_count_after_value
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.object_name = output_object_name_value;

  select public.system_recover_generation_strategy_provider_result(
    request_base || jsonb_build_object(
      'confirmation', 'FAL_RESULT_HTTP_413_RECOVERY_VERIFIED'
    )
  ) into strict replay_response_value;

  select
    count(*)::integer,
    content_factory_private.json_hash(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)
    )
    into ledger_count_after_replay_value, ledger_hash_after_replay_value
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.generation_job_id = generation_job_id_value;
  select count(*)::integer into event_count_after_replay_value
  from content_factory.generation_strategy_provider_status_events event
  where event.organization_id = organization_id_value
    and event.generation_job_id = generation_job_id_value;
  select count(*)::integer into media_count_after_replay_value
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.object_name = output_object_name_value;
  select count(*)::integer into dispatch_count_after_replay_value
  from content_factory.generation_strategy_dispatch_results dispatch
  where dispatch.organization_id = organization_id_value
    and dispatch.generation_job_id = generation_job_id_value;

  insert into incident_413_runtime_result values (
    wrong_confirmation_sqlstate_value,
    wrong_confirmation_message_value,
    fresh_response_value,
    replay_response_value,
    ledger_count_before_value,
    ledger_count_after_value,
    ledger_count_after_replay_value,
    ledger_hash_before_value,
    ledger_hash_after_value,
    ledger_hash_after_replay_value,
    event_count_before_value,
    event_count_after_value,
    event_count_after_replay_value,
    media_count_before_value,
    media_count_after_value,
    media_count_after_replay_value,
    dispatch_count_before_value,
    dispatch_count_after_replay_value
  );
end;
$incident_413_runtime$;

select is(
  wrong_confirmation_sqlstate,
  '55000',
  '405 confirmation cannot authorize recovery of immutable 413 failure'
) from incident_413_runtime_result;
select is(
  wrong_confirmation_message,
  'generation_strategy_provider_result_recovery_not_current',
  'wrong-code confirmation fails at the current-state gate'
) from incident_413_runtime_result;

select ok(
  fresh_response ->> 'version' =
    'generation-strategy-provider-result-recovery-response-v1'
  and fresh_response -> 'replay' = 'false'::jsonb
  and fresh_response #>> '{event,previous_status}' = 'failed'
  and fresh_response #>> '{event,provider_status}' = 'succeeded'
  and fresh_response #>> '{contract,provider_post_retried}' = 'false'
  and fresh_response #>> '{contract,ledger_mutated}' = 'false'
  and fresh_response #>> '{contract,manual_human_review_required}' = 'true',
  'fresh 413 recovery returns the no-repost, no-ledger-mutation review receipt'
) from incident_413_runtime_result;

select ok(
  replay_response ->> 'version' =
    'generation-strategy-provider-result-recovery-response-v1'
  and replay_response -> 'replay' = 'true'::jsonb
  and replay_response #>> '{event,previous_status}' = 'failed'
  and replay_response #>> '{event,provider_status}' = 'succeeded'
  and replay_response #>> '{output,media_id}' =
    fresh_response #>> '{output,media_id}',
  'exact replay returns the same recovered media without another event'
) from incident_413_runtime_result;

select ok(
  ledger_count_before = ledger_count_after
  and ledger_count_after = ledger_count_after_replay
  and ledger_hash_before = ledger_hash_after
  and ledger_hash_after = ledger_hash_after_replay,
  'full spend-ledger count and hash stay byte-identical across fresh and replay'
) from incident_413_runtime_result;

select ok(
  event_count_before = 3
  and event_count_after = event_count_before + 1
  and event_count_after_replay = event_count_after
  and media_count_before = 0
  and media_count_after = 1
  and media_count_after_replay = 1
  and dispatch_count_before = 1
  and dispatch_count_after_replay = dispatch_count_before,
  'fresh appends one success/media while replay duplicates nothing'
) from incident_413_runtime_result;

select ok(
  event.previous_status = 'failed'
  and event.provider_status = 'succeeded'
  and event.failure_code is null
  and event.transition_ordinal = 4
  and event.output_snapshot ->> 'recovered_failure_code' =
    'provider_result_http_413'
  and event.output_snapshot ->> 'recovery_version' =
    'generation-strategy-provider-result-recovery-v1',
  'the immutable failed 413 event is corrected by one bound success append'
)
from content_factory.generation_strategy_provider_status_events event
where event.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
  and event.generation_job_id = '88504197-4f6a-4159-9797-6f89cba92db9'
  and event.provider_status = 'succeeded';

select ok(
  job.status = 'succeeded'
  and job.actual_cost_minor = 47
  and not job.output ? 'failure_code'
  and not job.output ? 'provider_failure_code'
  and not job.output ? 'provider_billing_outcome'
  and job.output ->> 'provider_status' = 'succeeded'
  and job.output ->> 'recovered_failure_code' = 'provider_result_http_413'
  and job.output ->> 'output_media_id' =
    result.fresh_response #>> '{output,media_id}'
  and batch.status = 'succeeded'
  and batch.total_created = 1
  and task.status = 'review'
  and task.result ->> 'generation_status' = 'succeeded'
  and task.result ->> 'review_mode' = 'manual_human_review'
  and task.result ->> 'recovered_failure_code' = 'provider_result_http_413'
  and task.result ->> 'output_media_id' =
    result.fresh_response #>> '{output,media_id}',
  'job, batch and manual-review task projections are restored exactly'
)
from content_factory.generation_jobs job
join content_factory.generation_batches batch
  on batch.organization_id = job.organization_id
 and batch.id = job.batch_id
join content_factory.creator_tasks task
  on task.organization_id = job.organization_id
 and task.generation_job_id = job.id
cross join incident_413_runtime_result result
where job.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
  and job.id = '88504197-4f6a-4159-9797-6f89cba92db9';

select ok(
  media.id::text = result.fresh_response #>> '{output,media_id}'
  and media.status = 'ready'
  and media.mime_type = 'video/mp4'
  and media.size_bytes = 4096
  and media.sha256 = repeat('d', 64)
  and media.metadata ->> 'provider' = 'fal'
  and media.metadata ->> 'kind' = 'generated_video'
  and media.metadata ->> 'review_required' = 'true',
  'registered output media is exact, ready and review-gated'
)
from content_factory.media_objects media
cross join incident_413_runtime_result result
where media.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
  and media.object_name =
    'df147614-a4ef-4e66-8b79-1b89f5481ddf/' ||
    '05876b51-19e9-4118-a04b-6987642b147e/generated/strategy/' ||
    '88504197-4f6a-4159-9797-6f89cba92db9.mp4';

-- pgTAP reports are useful locally, but the Management API can expose only the
-- last command result. Repeat every safety property as fail-hard checks so an
-- HTTP-success response cannot conceal a `not ok` assertion.
do $incident_413_fail_hard$
declare
  runtime_result incident_413_runtime_result%rowtype;
  recovered_event_count integer;
  recovered_event_ok boolean;
  original_failure_count integer;
  projection_count integer;
  projection_ok boolean;
  media_projection_count integer;
  media_projection_ok boolean;
begin
  select * into strict runtime_result
  from incident_413_runtime_result;

  if (
    runtime_result.wrong_confirmation_sqlstate = '55000'
    and runtime_result.wrong_confirmation_message =
      'generation_strategy_provider_result_recovery_not_current'
  ) is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_wrong_confirmation';
  end if;

  if (
    runtime_result.fresh_response ->> 'version' =
      'generation-strategy-provider-result-recovery-response-v1'
    and runtime_result.fresh_response -> 'replay' = 'false'::jsonb
    and runtime_result.fresh_response #>> '{event,previous_status}' = 'failed'
    and runtime_result.fresh_response #>> '{event,provider_status}' =
      'succeeded'
    and runtime_result.fresh_response #>>
      '{contract,provider_post_retried}' = 'false'
    and runtime_result.fresh_response #>> '{contract,ledger_mutated}' = 'false'
    and runtime_result.fresh_response #>>
      '{contract,manual_human_review_required}' = 'true'
  ) is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_fresh_receipt';
  end if;

  if (
    runtime_result.replay_response ->> 'version' =
      'generation-strategy-provider-result-recovery-response-v1'
    and runtime_result.replay_response -> 'replay' = 'true'::jsonb
    and runtime_result.replay_response #>> '{event,previous_status}' = 'failed'
    and runtime_result.replay_response #>> '{event,provider_status}' =
      'succeeded'
    and runtime_result.replay_response #>> '{output,media_id}' =
      runtime_result.fresh_response #>> '{output,media_id}'
  ) is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_replay_receipt';
  end if;

  if (
    runtime_result.ledger_count_before = runtime_result.ledger_count_after
    and runtime_result.ledger_count_after =
      runtime_result.ledger_count_after_replay
    and runtime_result.ledger_hash_before = runtime_result.ledger_hash_after
    and runtime_result.ledger_hash_after =
      runtime_result.ledger_hash_after_replay
  ) is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_ledger_changed';
  end if;

  if (
    runtime_result.event_count_before = 3
    and runtime_result.event_count_after =
      runtime_result.event_count_before + 1
    and runtime_result.event_count_after_replay =
      runtime_result.event_count_after
    and runtime_result.media_count_before = 0
    and runtime_result.media_count_after = 1
    and runtime_result.media_count_after_replay = 1
    and runtime_result.dispatch_count_before = 1
    and runtime_result.dispatch_count_after_replay =
      runtime_result.dispatch_count_before
  ) is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_cardinality';
  end if;

  select
    count(*)::integer,
    bool_and(
      event.previous_status = 'failed'
      and event.provider_status = 'succeeded'
      and event.failure_code is null
      and event.transition_ordinal = 4
      and event.output_snapshot ->> 'recovered_failure_code' =
        'provider_result_http_413'
      and event.output_snapshot ->> 'recovery_version' =
        'generation-strategy-provider-result-recovery-v1'
    )
    into recovered_event_count, recovered_event_ok
  from content_factory.generation_strategy_provider_status_events event
  where event.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
    and event.generation_job_id = '88504197-4f6a-4159-9797-6f89cba92db9'
    and event.provider_status = 'succeeded';

  if recovered_event_count <> 1 or recovered_event_ok is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_recovered_event_projection';
  end if;

  select count(*)::integer into original_failure_count
  from content_factory.generation_strategy_provider_status_events event
  where event.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
    and event.generation_job_id = '88504197-4f6a-4159-9797-6f89cba92db9'
    and event.provider_status = 'failed'
    and event.failure_code = 'provider_result_http_413'
    and event.transition_ordinal = 3;

  if original_failure_count <> 1 then
    raise exception using message =
      'exact_incident_413_fail_hard_original_failure_changed';
  end if;

  select
    count(*)::integer,
    bool_and(
      job.status = 'succeeded'
      and job.actual_cost_minor = 47
      and not job.output ? 'failure_code'
      and not job.output ? 'provider_failure_code'
      and not job.output ? 'provider_billing_outcome'
      and job.output ->> 'provider_status' = 'succeeded'
      and job.output ->> 'recovered_failure_code' =
        'provider_result_http_413'
      and job.output ->> 'output_media_id' =
        runtime_result.fresh_response #>> '{output,media_id}'
      and batch.status = 'succeeded'
      and batch.total_created = 1
      and task.status = 'review'
      and task.result ->> 'generation_status' = 'succeeded'
      and task.result ->> 'review_mode' = 'manual_human_review'
      and task.result ->> 'recovered_failure_code' =
        'provider_result_http_413'
      and task.result ->> 'output_media_id' =
        runtime_result.fresh_response #>> '{output,media_id}'
    )
    into projection_count, projection_ok
  from content_factory.generation_jobs job
  join content_factory.generation_batches batch
    on batch.organization_id = job.organization_id
   and batch.id = job.batch_id
  join content_factory.creator_tasks task
    on task.organization_id = job.organization_id
   and task.generation_job_id = job.id
  where job.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
    and job.id = '88504197-4f6a-4159-9797-6f89cba92db9';

  if projection_count <> 1 or projection_ok is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_job_batch_task_projection';
  end if;

  select
    count(*)::integer,
    bool_and(
      media.id::text = runtime_result.fresh_response #>> '{output,media_id}'
      and media.status = 'ready'
      and media.mime_type = 'video/mp4'
      and media.size_bytes = 4096
      and media.sha256 = repeat('d', 64)
      and media.metadata ->> 'provider' = 'fal'
      and media.metadata ->> 'kind' = 'generated_video'
      and media.metadata ->> 'review_required' = 'true'
    )
    into media_projection_count, media_projection_ok
  from content_factory.media_objects media
  where media.organization_id = 'df147614-a4ef-4e66-8b79-1b89f5481ddf'
    and media.object_name =
      'df147614-a4ef-4e66-8b79-1b89f5481ddf/' ||
      '05876b51-19e9-4118-a04b-6987642b147e/generated/strategy/' ||
      '88504197-4f6a-4159-9797-6f89cba92db9.mp4';

  if media_projection_count <> 1 or media_projection_ok is not true then
    raise exception using message =
      'exact_incident_413_fail_hard_media_projection';
  end if;
end;
$incident_413_fail_hard$;

select * from finish();
rollback;
