begin;

-- Preserve the existing operational-health response and add an organization-
-- scoped content-review queue snapshot for owners and administrators.  The
-- existing scheduler, worker and generation keys intentionally keep their
-- original names and semantics for backwards-compatible clients.
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
  active_generation_count integer;
  due_count integer;
  stalled_count integer;
  review_queued_count integer := 0;
  review_processing_count integer := 0;
  review_due_count integer := 0;
  review_retry_wait_count integer := 0;
  review_dead_letter_count integer := 0;
  review_outcome_unknown_count integer := 0;
  review_oldest_queued_age_seconds bigint := 0;
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
    count(*)::integer,
    count(*) filter (
      where job.provider_next_poll_at is not null
        and job.provider_next_poll_at <= now()
    )::integer,
    count(*) filter (
      where job.provider_stalled_at is not null
    )::integer
  into active_generation_count, due_count, stalled_count
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.mode = 'real'
    and job.provider = 'runway'
    and job.status in ('submitted', 'processing');

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
      'stalled', stalled_count
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
    )
  );
end;
$$;

revoke all on function public.creator_operational_health(jsonb)
  from public, anon;
grant execute on function public.creator_operational_health(jsonb)
  to authenticated;

commit;
