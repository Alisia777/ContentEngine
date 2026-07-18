begin;

-- Extend the manager-only operational snapshot with bounded, read-only
-- generation queue and registered-media capacity metrics. Existing response
-- keys retain their names and semantics so already deployed clients remain
-- compatible. Storage totals intentionally use the authoritative media
-- registry only; this health RPC never scans, deletes or repairs bucket data.
create or replace function public.creator_operational_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  active_row content_factory.background_worker_runs%rowtype;
  latest_row content_factory.background_worker_runs%rowtype;
  active_generation_count integer := 0;
  generation_queued_count integer := 0;
  generation_starting_count integer := 0;
  generation_submitted_count integer := 0;
  generation_processing_count integer := 0;
  due_count integer := 0;
  stalled_count integer := 0;
  generation_oldest_active_age_seconds bigint := 0;
  generation_oldest_queued_age_seconds bigint := 0;
  generation_oldest_starting_age_seconds bigint := 0;
  review_queued_count integer := 0;
  review_processing_count integer := 0;
  review_due_count integer := 0;
  review_retry_wait_count integer := 0;
  review_dead_letter_count integer := 0;
  review_outcome_unknown_count integer := 0;
  review_oldest_queued_age_seconds bigint := 0;
  storage_registered_count bigint := 0;
  storage_registered_bytes bigint := 0;
  storage_quota_bytes constant bigint := 107374182400;
  storage_remaining_bytes bigint := 107374182400;
  storage_utilization_percent numeric := 0;
  scheduler_value jsonb;
  heartbeat_value timestamptz;
  heartbeat_fresh_value boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 2048
     or p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'creator_operational_health_payload_invalid';
  end if;
  perform content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin']
  );

  select run.* into active_row
  from content_factory.background_worker_runs run
  where run.status = 'running'
    and run.lease_expires_at > now()
  order by run.started_at, run.id
  limit 1;
  select run.* into latest_row
  from content_factory.background_worker_runs run
  order by run.started_at desc, run.id desc
  limit 1;

  select
    count(*) filter (
      where job.status in ('submitted', 'processing')
    )::integer,
    count(*) filter (where job.status = 'queued')::integer,
    count(*) filter (where job.status = 'starting')::integer,
    count(*) filter (where job.status = 'submitted')::integer,
    count(*) filter (where job.status = 'processing')::integer,
    count(*) filter (
      where job.status in ('submitted', 'processing')
        and job.provider_next_poll_at is not null
        and job.provider_next_poll_at <= now()
    )::integer,
    count(*) filter (
      where job.status in ('submitted', 'processing')
        and job.provider_stalled_at is not null
    )::integer,
    greatest(
      coalesce(
        floor(extract(epoch from (
          now() - min(job.created_at) filter (
            where job.status in ('submitted', 'processing')
          )
        ))),
        0
      ),
      0
    )::bigint,
    greatest(
      coalesce(
        floor(extract(epoch from (
          now() - min(job.created_at) filter (
            where job.status = 'queued'
          )
        ))),
        0
      ),
      0
    )::bigint,
    greatest(
      coalesce(
        floor(extract(epoch from (
          now() - min(job.created_at) filter (
            where job.status = 'starting'
          )
        ))),
        0
      ),
      0
    )::bigint
  into
    active_generation_count,
    generation_queued_count,
    generation_starting_count,
    generation_submitted_count,
    generation_processing_count,
    due_count,
    stalled_count,
    generation_oldest_active_age_seconds,
    generation_oldest_queued_age_seconds,
    generation_oldest_starting_age_seconds
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.mode = 'real'
    and job.provider = 'runway';

  -- One row per review is retained by the lateral lookup so historical retry
  -- attempts never inflate the current queue counters.
  select
    count(*) filter (
      where review.status = 'queued'
    )::integer,
    count(*) filter (
      where review.status = 'processing'
    )::integer,
    count(*) filter (
      where review.status = 'queued'
        and review.next_attempt_at is not null
        and review.next_attempt_at <= now()
    )::integer,
    count(*) filter (
      where review.status = 'queued'
        and review.next_attempt_at > now()
        and latest_attempt.status = 'retry_wait'
    )::integer,
    count(*) filter (
      where latest_attempt.status = 'dead_letter'
    )::integer,
    count(*) filter (
      where latest_attempt.status = 'outcome_unknown'
    )::integer,
    greatest(
      coalesce(
        floor(extract(epoch from (
          now() - min(review.created_at) filter (
            where review.status = 'queued'
          )
        ))),
        0
      ),
      0
    )::bigint
  into
    review_queued_count,
    review_processing_count,
    review_due_count,
    review_retry_wait_count,
    review_dead_letter_count,
    review_outcome_unknown_count,
    review_oldest_queued_age_seconds
  from content_factory.content_review_runs review
  left join lateral (
    select attempt.status
    from content_factory.content_review_attempts attempt
    where attempt.organization_id = review.organization_id
      and attempt.review_id = review.id
    order by attempt.attempt_no desc, attempt.id desc
    limit 1
  ) latest_attempt on true
  where review.organization_id = organization_id_value;

  -- Match the same registered states used by the authoritative organization
  -- storage quota check. Deleted and failed registrations consume no quota.
  select
    count(*)::bigint,
    coalesce(sum(media.size_bytes), 0)::bigint
  into storage_registered_count, storage_registered_bytes
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.status in ('uploading', 'ready', 'archived');

  storage_remaining_bytes := greatest(
    storage_quota_bytes - storage_registered_bytes,
    0
  );
  storage_utilization_percent := round(
    storage_registered_bytes::numeric * 100 / storage_quota_bytes,
    2
  );

  scheduler_value := content_factory_private.background_scheduler_status();
  heartbeat_value := coalesce(active_row.heartbeat_at, latest_row.heartbeat_at);
  heartbeat_fresh_value := heartbeat_value is not null
    and heartbeat_value >= now() - interval '10 minutes';

  return jsonb_build_object(
    'ok', true,
    'organization_id', organization_id_value,
    'scheduler', jsonb_build_object(
      'ready', scheduler_value -> 'ready',
      'extensions_ready', scheduler_value -> 'extensions_ready',
      'schedule_installed', scheduler_value -> 'schedule_installed',
      'configuration_ready',
        (scheduler_value ->> 'vault_url_configured')::boolean
        and (scheduler_value ->> 'vault_secret_configured')::boolean
    ),
    'worker', jsonb_build_object(
      'running', active_row.id is not null,
      'ready', heartbeat_fresh_value and (
        active_row.id is not null or latest_row.status = 'completed'
      ),
      'heartbeat_fresh', heartbeat_fresh_value,
      'heartbeat_at', heartbeat_value,
      'latest_status', latest_row.status,
      'latest_finished_at', latest_row.finished_at,
      'latest_error_code', latest_row.error_code
    ),
    'generation', jsonb_build_object(
      'active', active_generation_count,
      'due', due_count,
      'stalled', stalled_count,
      'queued', generation_queued_count,
      'starting', generation_starting_count,
      'submitted', generation_submitted_count,
      'processing', generation_processing_count,
      'oldest_active_age_seconds', generation_oldest_active_age_seconds,
      'oldest_queued_age_seconds', generation_oldest_queued_age_seconds,
      'oldest_starting_age_seconds', generation_oldest_starting_age_seconds
    ),
    'content_review', jsonb_build_object(
      'queued', review_queued_count,
      'processing', review_processing_count,
      'due', review_due_count,
      'retry_wait', review_retry_wait_count,
      'dead_letter', review_dead_letter_count,
      'outcome_unknown', review_outcome_unknown_count,
      'terminal_scope', 'all_time',
      'oldest_queued_age_seconds', review_oldest_queued_age_seconds
    ),
    'storage', jsonb_build_object(
      'registered_count', storage_registered_count,
      'registered_bytes', storage_registered_bytes,
      'quota_bytes', storage_quota_bytes,
      'remaining_bytes', storage_remaining_bytes,
      'utilization_percent', storage_utilization_percent
    )
  );
end;
$$;

revoke all on function public.creator_operational_health(jsonb)
  from public, anon;
grant execute on function public.creator_operational_health(jsonb)
  to authenticated;

commit;
