-- Read-only before/after snapshot for the rollback-only Pika 413 test.
-- Run this exact SELECT immediately before and after the envelope; the two
-- JSON values must be identical and migration_202608210002_count must be zero.
with constants as (
  select
    'df147614-a4ef-4e66-8b79-1b89f5481ddf'::uuid as organization_id,
    '88504197-4f6a-4159-9797-6f89cba92db9'::uuid as generation_job_id,
    'df147614-a4ef-4e66-8b79-1b89f5481ddf/' ||
      '05876b51-19e9-4118-a04b-6987642b147e/generated/strategy/' ||
      '88504197-4f6a-4159-9797-6f89cba92db9.mp4' as output_object_name
), migration_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(history) order by history.version), '[]'::jsonb)::text
    ) as row_hash,
    count(*) filter (
      where history.version = '202608210002'
    )::integer as migration_202608210002_count
  from contentengine_deploy.schema_migrations history
), job_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(job) order by job.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.generation_jobs job
  cross join constants value
  where job.organization_id = value.organization_id
    and job.id = value.generation_job_id
), event_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(event) order by event.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.generation_strategy_provider_status_events event
  cross join constants value
  where event.organization_id = value.organization_id
    and event.generation_job_id = value.generation_job_id
), ledger_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(ledger) order by ledger.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.generation_spend_ledger ledger
  cross join constants value
  where ledger.organization_id = value.organization_id
    and ledger.generation_job_id = value.generation_job_id
), dispatch_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(dispatch) order by dispatch.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.generation_strategy_dispatch_results dispatch
  cross join constants value
  where dispatch.organization_id = value.organization_id
    and dispatch.generation_job_id = value.generation_job_id
), media_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(media) order by media.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.media_objects media
  cross join constants value
  where media.organization_id = value.organization_id
    and media.object_name = value.output_object_name
), storage_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(
        jsonb_agg(to_jsonb(storage_object) order by storage_object.id),
        '[]'::jsonb
      )::text
    ) as row_hash
  from storage.objects storage_object
  cross join constants value
  where storage_object.bucket_id = 'contentengine-private'
    and storage_object.name = value.output_object_name
), task_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(task) order by task.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.creator_tasks task
  cross join constants value
  where task.organization_id = value.organization_id
    and task.generation_job_id = value.generation_job_id
), batch_snapshot as (
  select
    count(*)::integer as row_count,
    md5(
      coalesce(jsonb_agg(to_jsonb(batch) order by batch.id), '[]'::jsonb)::text
    ) as row_hash
  from content_factory.generation_batches batch
  join content_factory.generation_jobs job
    on job.organization_id = batch.organization_id
   and job.batch_id = batch.id
  cross join constants value
  where job.organization_id = value.organization_id
    and job.id = value.generation_job_id
)
select jsonb_build_object(
  'version', 'generation-strategy-413-rollback-invariants-v1',
  'migration_history', to_jsonb(migration_snapshot),
  'job', to_jsonb(job_snapshot),
  'events', to_jsonb(event_snapshot),
  'ledger', to_jsonb(ledger_snapshot),
  'dispatch', to_jsonb(dispatch_snapshot),
  'media', to_jsonb(media_snapshot),
  'storage', to_jsonb(storage_snapshot),
  'task', to_jsonb(task_snapshot),
  'batch', to_jsonb(batch_snapshot)
) as rollback_invariants
from migration_snapshot
cross join job_snapshot
cross join event_snapshot
cross join ledger_snapshot
cross join dispatch_snapshot
cross join media_snapshot
cross join storage_snapshot
cross join task_snapshot
cross join batch_snapshot;
