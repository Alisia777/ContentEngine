begin;

-- Official YouTube Data API v3 public-metadata ingestion is deliberately kept
-- outside product_research_runs.  A product research run has one explicitly
-- authorized paid provider attempt; this ledger models a separate, manual,
-- quota-only action with its own authorization, transport and retention rules.

-- The canonical provider catalog intentionally remains disabled/planned.  A
-- separate append-only operator gate is required before even a manual canary
-- may use the shared API credential.  This is the global kill switch; the
-- organization rollout below is an additional, narrower gate.
create table if not exists content_factory.research_youtube_global_rollout_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  provider_key text not null check (provider_key = 'youtube_data_api_v3'),
  adapter_version text not null check (
    adapter_version = 'youtube-data-api-v3-public-metadata-v1'
  ),
  decision text not null check (
    decision in (
      'disabled', 'canary_enabled', 'controlled_rollout', 'emergency_paused'
    )
  ),
  terms_version text not null check (
    terms_version = 'youtube-developer-policies-2026-08-03-v1'
  ),
  terms_review_ack boolean not null,
  retention_control_ack boolean not null,
  reason text not null check (length(btrim(reason)) between 3 and 500),
  operator_reference text not null check (
    length(btrim(operator_reference)) between 3 and 160
  ),
  decided_at timestamptz not null default now(),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  unique (idempotency_key),
  unique (decision_hash),
  check (
    decision in ('disabled', 'emergency_paused')
    or (terms_review_ack and retention_control_ack)
  )
);

insert into content_factory.research_youtube_global_rollout_decisions (
  provider_key, adapter_version, decision, terms_version,
  terms_review_ack, retention_control_ack, reason, operator_reference,
  idempotency_key, decision_hash
) values (
  'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
  'disabled', 'youtube-developer-policies-2026-08-03-v1',
  false, false, 'Initial fail-closed state pending reviewed deployment',
  'migration:202608040009', 'youtube-global-disabled-202608040009',
  encode(extensions.digest(
    'youtube-global-disabled-202608040009', 'sha256'
  ), 'hex')
)
on conflict (idempotency_key) do nothing;

create table if not exists content_factory.research_youtube_rollout_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  provider_key text not null check (provider_key = 'youtube_data_api_v3'),
  adapter_version text not null check (
    adapter_version = 'youtube-data-api-v3-public-metadata-v1'
  ),
  decision text not null check (
    decision in ('enable_category_refresh', 'pause_category_refresh')
  ),
  canary_ingestion_id uuid,
  terms_version text not null check (
    terms_version = 'youtube-developer-policies-2026-08-03-v1'
  ),
  retention_days integer not null check (retention_days = 29),
  reason text not null check (length(btrim(reason)) between 3 and 500),
  decided_by uuid not null,
  decided_at timestamptz not null default now(),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  unique (organization_id, id),
  unique (organization_id, idempotency_key),
  unique (organization_id, decision_hash),
  foreign key (organization_id)
    references content_factory.organizations(id),
  foreign key (organization_id, decided_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (decision = 'enable_category_refresh' and canary_ingestion_id is not null)
    or (decision = 'pause_category_refresh' and canary_ingestion_id is null)
  )
);

create table if not exists content_factory.research_youtube_ingestion_runs (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  product_id uuid not null,
  binding_id uuid not null,
  market_category_id uuid not null,
  requested_by uuid not null,
  mode text not null check (mode in ('manual_canary', 'category_refresh')),
  status text not null default 'queued' check (
    status in ('queued', 'processing', 'completed', 'failed')
  ),
  provider_key text not null check (provider_key = 'youtube_data_api_v3'),
  adapter_version text not null check (
    adapter_version = 'youtube-data-api-v3-public-metadata-v1'
  ),
  query_text text not null check (length(btrim(query_text)) between 2 and 200),
  query_hash text not null check (query_hash ~ '^[0-9a-f]{64}$'),
  region_code text check (region_code is null or region_code ~ '^[A-Z]{2}$'),
  relevance_language text check (
    relevance_language is null
    or relevance_language ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$'
  ),
  published_after timestamptz,
  max_results integer not null check (max_results between 1 and 25),
  max_http_requests integer not null check (max_http_requests between 1 and 2),
  max_quota_units integer not null check (max_quota_units between 1 and 2),
  quota_units_started integer not null default 0 check (
    quota_units_started between 0 and max_quota_units
  ),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  terms_version text not null check (
    terms_version = 'youtube-developer-policies-2026-08-03-v1'
  ),
  no_retry boolean not null check (no_retry),
  requested_at timestamptz not null default now(),
  claimed_at timestamptz,
  lease_expires_at timestamptz,
  completed_at timestamptz,
  completion_hash text check (
    completion_hash is null or completion_hash ~ '^[0-9a-f]{64}$'
  ),
  error_code text,
  error_message text,
  unique (organization_id, id),
  unique (organization_id, idempotency_key),
  unique (organization_id, request_hash),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  foreign key (organization_id, market_category_id)
    references content_factory.research_market_categories(organization_id, id),
  foreign key (organization_id, requested_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (mode = 'manual_canary' and max_results = 1
      and max_http_requests = 2 and max_quota_units = 2)
    or (mode = 'category_refresh' and max_http_requests = 2
      and max_quota_units = 2)
  ),
  check (
    (status = 'queued' and claimed_at is null and lease_expires_at is null
      and completed_at is null
      and completion_hash is null and error_code is null and error_message is null)
    or (status = 'processing' and claimed_at is not null
      and lease_expires_at > claimed_at
      and completed_at is null and completion_hash is null
      and error_code is null and error_message is null)
    or (status = 'completed' and claimed_at is not null
      and lease_expires_at is not null
      and completed_at is not null and completion_hash is not null
      and error_code is null and error_message is null)
    or (status = 'failed' and claimed_at is not null
      and lease_expires_at is not null
      and completed_at is not null and completion_hash is not null
      and error_code is not null and error_message is not null)
  ),
  check (error_code is null or error_code in (
    'provider_configuration_error',
    'provider_authentication_failed',
    'provider_quota_exhausted',
    'provider_rate_limited',
    'provider_request_rejected',
    'provider_response_invalid',
    'provider_outcome_unknown',
    'provider_unavailable',
    'retention_control_unavailable',
    'category_binding_stale',
    'rollout_gate_closed',
    'ingestion_lease_expired',
    'internal_error'
  )),
  check (error_message is null or length(error_message) between 1 and 2000)
);

do $youtube_rollout_canary_fk$
begin
  if not exists (
    select 1
    from pg_catalog.pg_constraint constraint_entry
    where constraint_entry.conname = 'research_youtube_rollout_canary_fk'
      and constraint_entry.conrelid =
        'content_factory.research_youtube_rollout_decisions'::regclass
  ) then
    alter table content_factory.research_youtube_rollout_decisions
      add constraint research_youtube_rollout_canary_fk
      foreign key (organization_id, canary_ingestion_id)
      references content_factory.research_youtube_ingestion_runs(organization_id, id)
      deferrable initially deferred;
  end if;
end;
$youtube_rollout_canary_fk$;

create table if not exists content_factory.research_youtube_transport_attempts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  ingestion_id uuid not null,
  request_ordinal integer not null check (request_ordinal between 1 and 2),
  request_kind text not null check (request_kind in ('search.list', 'videos.list')),
  quota_bucket text not null check (quota_bucket in ('search_queries', 'default')),
  quota_units integer not null check (quota_units = 1),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, ingestion_id, request_ordinal),
  unique (organization_id, ingestion_id, request_hash),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(organization_id, id),
  check (
    (request_kind = 'search.list' and quota_bucket = 'search_queries')
    or (request_kind = 'videos.list' and quota_bucket = 'default')
  )
);

create table if not exists content_factory.research_youtube_transport_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  ingestion_id uuid not null,
  transport_id uuid not null,
  status text not null check (status in ('ready', 'degraded', 'blocked', 'unknown')),
  failure_code text,
  response_hash text check (response_hash is null or response_hash ~ '^[0-9a-f]{64}$'),
  item_count integer check (item_count is null or item_count between 0 and 25),
  checked_at timestamptz not null,
  retention_expires_at timestamptz not null,
  recorded_at timestamptz not null default now(),
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  unique (organization_id, id),
  unique (organization_id, transport_id),
  unique (organization_id, receipt_hash),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(organization_id, id),
  foreign key (organization_id, transport_id)
    references content_factory.research_youtube_transport_attempts(organization_id, id),
  check (
    (status = 'ready' and failure_code is null
      and response_hash is not null and item_count is not null)
    or (status <> 'ready' and failure_code is not null)
  ),
  check (failure_code is null or failure_code in (
    'provider_configuration_error',
    'provider_authentication_failed',
    'provider_quota_exhausted',
    'provider_rate_limited',
    'provider_request_rejected',
    'provider_response_invalid',
    'provider_outcome_unknown',
    'provider_unavailable'
  )),
  check (retention_expires_at = checked_at + interval '29 days')
);

create table if not exists content_factory.research_youtube_video_observations (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  ingestion_id uuid not null,
  product_id uuid not null,
  binding_id uuid not null,
  market_category_id uuid not null,
  search_position integer not null check (search_position between 1 and 25),
  video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  channel_id text not null check (channel_id ~ '^UC[A-Za-z0-9_-]{22}$'),
  title text not null check (length(btrim(title)) between 1 and 300),
  channel_title text not null check (length(btrim(channel_title)) between 1 and 300),
  youtube_category_id text not null check (youtube_category_id ~ '^[0-9]{1,3}$'),
  published_at timestamptz not null,
  duration_iso8601 text not null check (
    duration_iso8601 ~ '^P(?:[0-9]+D)?(?:T(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+S)?)?$'
  ),
  privacy_status text not null check (privacy_status = 'public'),
  embeddable boolean not null,
  view_count text check (view_count is null or view_count ~ '^[0-9]{1,30}$'),
  like_count text check (like_count is null or like_count ~ '^[0-9]{1,30}$'),
  comment_count text check (comment_count is null or comment_count ~ '^[0-9]{1,30}$'),
  observed_at timestamptz not null,
  retention_expires_at timestamptz not null,
  observation_hash text not null check (observation_hash ~ '^[0-9a-f]{64}$'),
  unique (organization_id, id),
  unique (organization_id, ingestion_id, video_id),
  unique (organization_id, ingestion_id, search_position),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  check (retention_expires_at = observed_at + interval '29 days')
);

create table if not exists content_factory.research_youtube_candidate_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  ingestion_id uuid not null,
  observation_id uuid not null,
  observation_hash text not null check (observation_hash ~ '^[0-9a-f]{64}$'),
  decision text not null check (decision in ('confirm_candidate', 'exclude_candidate')),
  reason text check (reason is null or length(btrim(reason)) between 3 and 500),
  decided_by uuid not null,
  decided_at timestamptz not null default clock_timestamp(),
  retention_expires_at timestamptz not null,
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  unique (organization_id, id),
  unique (organization_id, idempotency_key),
  unique (organization_id, decision_hash),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(organization_id, id),
  foreign key (organization_id, observation_id)
    references content_factory.research_youtube_video_observations(organization_id, id),
  foreign key (organization_id, decided_by)
    references content_factory.memberships(organization_id, profile_id),
  check (retention_expires_at > decided_at),
  check (retention_expires_at <= decided_at + interval '29 days')
);

create table if not exists content_factory.research_youtube_retention_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  purged_at timestamptz not null default now(),
  cutoff_at timestamptz not null,
  observation_deleted_count integer not null check (
    observation_deleted_count between 0 and 5000
  ),
  candidate_decision_deleted_count integer not null check (
    candidate_decision_deleted_count between 0 and 5000
  ),
  transport_receipt_deleted_count integer not null check (
    transport_receipt_deleted_count between 0 and 5000
  ),
  transport_attempt_deleted_count integer not null check (
    transport_attempt_deleted_count between 0 and 5000
  ),
  overdue_remaining_count integer not null check (overdue_remaining_count >= 0),
  successful boolean not null check (successful),
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  unique (receipt_hash)
);

create index if not exists research_youtube_ingestion_product_idx
  on content_factory.research_youtube_ingestion_runs
  (organization_id, product_id, market_category_id, requested_at desc, id desc);
create index if not exists research_youtube_ingestion_status_idx
  on content_factory.research_youtube_ingestion_runs
  (status, requested_at, id);
create index if not exists research_youtube_transport_daily_idx
  on content_factory.research_youtube_transport_attempts
  (request_kind, started_at, id);
create index if not exists research_youtube_observation_retention_idx
  on content_factory.research_youtube_video_observations
  (retention_expires_at, id);
create index if not exists research_youtube_observation_timeline_idx
  on content_factory.research_youtube_video_observations
  (organization_id, product_id, market_category_id, observed_at desc, id desc);
create index if not exists research_youtube_transport_retention_idx
  on content_factory.research_youtube_transport_receipts
  (retention_expires_at, id);
create index if not exists research_youtube_candidate_retention_idx
  on content_factory.research_youtube_candidate_decisions
  (retention_expires_at, id);
create index if not exists research_youtube_rollout_latest_idx
  on content_factory.research_youtube_rollout_decisions
  (organization_id, decided_at desc, id desc);

alter table content_factory.research_youtube_global_rollout_decisions enable row level security;
alter table content_factory.research_youtube_rollout_decisions enable row level security;
alter table content_factory.research_youtube_ingestion_runs enable row level security;
alter table content_factory.research_youtube_transport_attempts enable row level security;
alter table content_factory.research_youtube_transport_receipts enable row level security;
alter table content_factory.research_youtube_video_observations enable row level security;
alter table content_factory.research_youtube_candidate_decisions enable row level security;
alter table content_factory.research_youtube_retention_receipts enable row level security;

revoke all on table content_factory.research_youtube_global_rollout_decisions
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_rollout_decisions
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_ingestion_runs
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_transport_attempts
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_transport_receipts
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_video_observations
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_candidate_decisions
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_retention_receipts
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_youtube_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE'
     and coalesce(
       current_setting('content_factory.youtube_retention_purge', true), ''
     ) = 'on'
     and tg_table_name in (
       'research_youtube_transport_attempts',
       'research_youtube_transport_receipts',
       'research_youtube_candidate_decisions'
     ) then
    return old;
  end if;
  raise exception using errcode = '55000', message = 'research_youtube_ledger_is_append_only';
end;
$$;

drop trigger if exists research_youtube_global_rollout_immutable
  on content_factory.research_youtube_global_rollout_decisions;
create trigger research_youtube_global_rollout_immutable
before update or delete on content_factory.research_youtube_global_rollout_decisions
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_rollout_immutable
  on content_factory.research_youtube_rollout_decisions;
create trigger research_youtube_rollout_immutable
before update or delete on content_factory.research_youtube_rollout_decisions
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_transport_attempt_immutable
  on content_factory.research_youtube_transport_attempts;
create trigger research_youtube_transport_attempt_immutable
before update or delete on content_factory.research_youtube_transport_attempts
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_transport_receipt_immutable
  on content_factory.research_youtube_transport_receipts;
create trigger research_youtube_transport_receipt_immutable
before update or delete on content_factory.research_youtube_transport_receipts
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_candidate_decision_immutable
  on content_factory.research_youtube_candidate_decisions;
create trigger research_youtube_candidate_decision_immutable
before update or delete on content_factory.research_youtube_candidate_decisions
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_retention_receipt_immutable
  on content_factory.research_youtube_retention_receipts;
create trigger research_youtube_retention_receipt_immutable
before update or delete on content_factory.research_youtube_retention_receipts
for each row execute function content_factory_private.reject_research_youtube_mutation();
drop trigger if exists research_youtube_observation_no_update
  on content_factory.research_youtube_video_observations;
create trigger research_youtube_observation_no_update
before update on content_factory.research_youtube_video_observations
for each row execute function content_factory_private.reject_research_youtube_mutation();

create or replace function content_factory_private.research_youtube_global_state()
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((
    select decision_entry.decision
    from content_factory.research_youtube_global_rollout_decisions decision_entry
    where decision_entry.provider_key = 'youtube_data_api_v3'
      and decision_entry.adapter_version =
        'youtube-data-api-v3-public-metadata-v1'
      and decision_entry.terms_version =
        'youtube-developer-policies-2026-08-03-v1'
    order by decision_entry.decided_at desc, decision_entry.id desc
    limit 1
  ), 'disabled');
$$;

create or replace function content_factory_private.research_youtube_global_gate(
  required_mode text
)
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  global_state text;
begin
  global_state := content_factory_private.research_youtube_global_state();
  if required_mode = 'manual_canary' then
    return global_state in ('canary_enabled', 'controlled_rollout');
  end if;
  if required_mode = 'category_refresh' then
    return global_state = 'controlled_rollout';
  end if;
  return false;
end;
$$;

create or replace function content_factory_private.research_youtube_retention_ready()
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  schedule_ready_value boolean := false;
  heartbeat_ready_value boolean := false;
begin
  if not exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) then
    return false;
  end if;
  begin
    execute $query$
      select count(*) = 1
      from cron.job job
      where job.jobname = 'contentengine-youtube-retention-v1'
        and job.active
        and job.schedule = '17 * * * *'
        and position('system_purge_expired_youtube_api_data' in job.command) > 0
    $query$ into schedule_ready_value;
  exception when undefined_table or invalid_schema_name or insufficient_privilege then
    schedule_ready_value := false;
  end;
  select coalesce((
    select receipt.successful
      and receipt.overdue_remaining_count = 0
      and receipt.purged_at >= clock_timestamp() - interval '2 hours'
    from content_factory.research_youtube_retention_receipts receipt
    order by receipt.purged_at desc, receipt.id desc
    limit 1
  ), false) into heartbeat_ready_value;
  return schedule_ready_value and heartbeat_ready_value;
end;
$$;

create or replace function content_factory_private.research_youtube_refresh_gate(
  organization_id_value uuid
)
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  rollout_row content_factory.research_youtube_rollout_decisions%rowtype;
begin
  if not content_factory_private.research_youtube_global_gate(
    'category_refresh'
  ) then
    return false;
  end if;
  if not content_factory_private.research_youtube_retention_ready() then
    return false;
  end if;
  select decision_entry.* into rollout_row
  from content_factory.research_youtube_rollout_decisions decision_entry
  where decision_entry.organization_id = organization_id_value
  order by decision_entry.decided_at desc, decision_entry.id desc
  limit 1;
  if rollout_row.id is null
     or rollout_row.decision <> 'enable_category_refresh'
     or rollout_row.decided_at < clock_timestamp() - interval '24 hours' then
    return false;
  end if;
  return exists (
    select 1
    from content_factory.research_youtube_ingestion_runs ingestion
    join content_factory.research_youtube_transport_attempts transport
      on transport.organization_id = ingestion.organization_id
     and transport.ingestion_id = ingestion.id
     and transport.request_ordinal = 1
     and transport.request_kind = 'search.list'
    join content_factory.research_youtube_transport_receipts receipt
      on receipt.organization_id = transport.organization_id
     and receipt.transport_id = transport.id
     and receipt.status = 'ready'
     and receipt.item_count = 1
    join content_factory.research_youtube_transport_attempts detail_transport
      on detail_transport.organization_id = ingestion.organization_id
     and detail_transport.ingestion_id = ingestion.id
     and detail_transport.request_ordinal = 2
     and detail_transport.request_kind = 'videos.list'
    join content_factory.research_youtube_transport_receipts detail_receipt
      on detail_receipt.organization_id = detail_transport.organization_id
     and detail_receipt.transport_id = detail_transport.id
     and detail_receipt.status = 'ready'
     and detail_receipt.item_count = 1
    where ingestion.organization_id = organization_id_value
      and ingestion.id = rollout_row.canary_ingestion_id
      and ingestion.mode = 'manual_canary'
      and ingestion.status = 'completed'
      and ingestion.completed_at >= clock_timestamp() - interval '24 hours'
  );
end;
$$;

create or replace function content_factory_private.research_youtube_quota_window(
  observed_time timestamptz
)
returns table (
  quota_day date,
  starts_at timestamptz,
  ends_at timestamptz
)
language sql
stable
set search_path = ''
as $$
  select
    local_window.local_day,
    local_window.local_day::timestamp at time zone 'America/Los_Angeles',
    (local_window.local_day + 1)::timestamp at time zone 'America/Los_Angeles'
  from (
    select (observed_time at time zone 'America/Los_Angeles')::date as local_day
  ) local_window;
$$;

create or replace function content_factory_private.expire_research_youtube_ingestion(
  ingestion_id_value uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  completed_time timestamptz := clock_timestamp();
  affected_count integer := 0;
begin
  update content_factory.research_youtube_ingestion_runs ingestion
  set status = 'failed',
      completed_at = completed_time,
      completion_hash = content_factory_private.json_hash(jsonb_build_object(
        'version', 'research-youtube-terminal-v1',
        'ingestion_id', ingestion.id,
        'status', 'failed',
        'error_code', 'ingestion_lease_expired',
        'error_message',
          'The ingestion lease expired; no provider retry was attempted.',
        'lease_expires_at', ingestion.lease_expires_at,
        'completed_at', completed_time
      )),
      error_code = 'ingestion_lease_expired',
      error_message = 'The ingestion lease expired; no provider retry was attempted.'
  where ingestion.id = ingestion_id_value
    and ingestion.status = 'processing'
    and ingestion.lease_expires_at <= completed_time;
  get diagnostics affected_count = row_count;
  return affected_count = 1;
end;
$$;

create or replace function public.system_decide_research_youtube_global_rollout(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  decision_value text;
  terms_version_value text;
  terms_review_ack_value boolean;
  retention_control_ack_value boolean;
  reason_value text;
  operator_reference_value text;
  idempotency_key_value text;
  decision_hash_value text;
  replay_row content_factory.research_youtube_global_rollout_decisions%rowtype;
  decision_row content_factory.research_youtube_global_rollout_decisions%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if auth.role() <> 'service_role'
     or p_payload - array[
       'decision', 'terms_version', 'terms_review_ack',
       'retention_control_ack', 'reason', 'operator_reference',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'terms_review_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'retention_control_ack') <> 'boolean' then
    raise exception using
      errcode = '42501', message = 'research_youtube_global_rollout_forbidden';
  end if;
  decision_value := content_factory_private.require_text(
    p_payload, 'decision', 8, 32
  );
  terms_version_value := content_factory_private.require_text(
    p_payload, 'terms_version', 3, 80
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  operator_reference_value := content_factory_private.require_text(
    p_payload, 'operator_reference', 3, 160
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  terms_review_ack_value := (p_payload ->> 'terms_review_ack')::boolean;
  retention_control_ack_value :=
    (p_payload ->> 'retention_control_ack')::boolean;
  if decision_value not in (
       'disabled', 'canary_enabled', 'controlled_rollout', 'emergency_paused'
     )
     or terms_version_value <>
       'youtube-developer-policies-2026-08-03-v1' then
    raise exception using
      errcode = '22023', message = 'research_youtube_global_rollout_invalid';
  end if;
  select existing.* into replay_row
  from content_factory.research_youtube_global_rollout_decisions existing
  where existing.idempotency_key = idempotency_key_value;
  if replay_row.id is not null then
    if replay_row.decision <> decision_value
       or replay_row.terms_version <> terms_version_value
       or replay_row.terms_review_ack <> terms_review_ack_value
       or replay_row.retention_control_ack <> retention_control_ack_value
       or replay_row.reason <> reason_value
       or replay_row.operator_reference <> operator_reference_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-global-rollout-v1',
      'decision', replay_row.decision,
      'decision_id', replay_row.id,
      'decided_at', replay_row.decided_at
    );
  end if;
  if decision_value in ('canary_enabled', 'controlled_rollout') then
    if not terms_review_ack_value
       or not retention_control_ack_value
       or not content_factory_private.research_youtube_retention_ready() then
      raise exception using
        errcode = '55000',
        message = 'research_youtube_global_prerequisites_required';
    end if;
    if not exists (
      select 1
      from content_factory.research_provider_catalog catalog
      where catalog.provider_key = 'youtube_data_api_v3'
        and catalog.adapter_version = 'youtube-data-api-v3-public-metadata-v1'
        and catalog.lifecycle_status = 'disabled'
        and catalog.rollout_stage = 'planned'
        and catalog.terms_version = 'youtube-data-api-review-required-v1'
        and catalog.canary_mode = 'manual_only'
        and not catalog.automatic_canary_allowed
        and not catalog.automatic_fallback_allowed
    ) then
      raise exception using
        errcode = '55000', message = 'research_youtube_provider_contract_invalid';
    end if;
  end if;
  if decision_value = 'controlled_rollout' and not exists (
    select 1
    from content_factory.research_youtube_ingestion_runs ingestion
    join content_factory.research_youtube_transport_attempts search_transport
      on search_transport.organization_id = ingestion.organization_id
     and search_transport.ingestion_id = ingestion.id
     and search_transport.request_ordinal = 1
     and search_transport.request_kind = 'search.list'
    join content_factory.research_youtube_transport_receipts search_receipt
      on search_receipt.organization_id = search_transport.organization_id
     and search_receipt.transport_id = search_transport.id
     and search_receipt.status = 'ready'
     and search_receipt.item_count = 1
    join content_factory.research_youtube_transport_attempts detail_transport
      on detail_transport.organization_id = ingestion.organization_id
     and detail_transport.ingestion_id = ingestion.id
     and detail_transport.request_ordinal = 2
     and detail_transport.request_kind = 'videos.list'
    join content_factory.research_youtube_transport_receipts detail_receipt
      on detail_receipt.organization_id = detail_transport.organization_id
     and detail_receipt.transport_id = detail_transport.id
     and detail_receipt.status = 'ready'
     and detail_receipt.item_count = 1
    where ingestion.mode = 'manual_canary'
      and ingestion.status = 'completed'
      and ingestion.completed_at >= clock_timestamp() - interval '24 hours'
  ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_global_canary_required';
  end if;
  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-global-rollout-v1',
    'decision', decision_value,
    'terms_version', terms_version_value,
    'terms_review_ack', terms_review_ack_value,
    'retention_control_ack', retention_control_ack_value,
    'reason', reason_value,
    'operator_reference', operator_reference_value,
    'idempotency_key', idempotency_key_value
  ));
  insert into content_factory.research_youtube_global_rollout_decisions (
    provider_key, adapter_version, decision, terms_version,
    terms_review_ack, retention_control_ack, reason, operator_reference,
    idempotency_key, decision_hash
  ) values (
    'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
    decision_value, terms_version_value, terms_review_ack_value,
    retention_control_ack_value, reason_value, operator_reference_value,
    idempotency_key_value, decision_hash_value
  ) returning * into decision_row;
  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-global-rollout-v1',
    'decision', decision_row.decision,
    'decision_id', decision_row.id,
    'decided_at', decision_row.decided_at
  );
end;
$$;

create or replace function content_factory_private.request_research_youtube_ingestion(
  p_payload jsonb,
  mode_value text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  run_id_value uuid;
  product_id_value uuid;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  query_text_value text;
  query_hash_value text;
  region_code_value text;
  relevance_language_value text;
  published_after_value timestamptz;
  max_results_value integer;
  max_http_requests_value integer;
  max_quota_units_value integer;
  terms_version_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  request_hash_value text;
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  command_name_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'query_text', 'region_code',
    'relevance_language', 'published_after', 'max_results',
    'max_http_requests', 'max_quota_units', 'quota_ack',
    'no_retry_ack', 'terms_ack', 'terms_version', 'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or mode_value not in ('manual_canary', 'category_refresh') then
    raise exception using
      errcode = '22023', message = 'research_youtube_request_payload_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'quota_ack') <> 'boolean'
     or (p_payload ->> 'quota_ack')::boolean is not true
     or jsonb_typeof(p_payload -> 'no_retry_ack') <> 'boolean'
     or (p_payload ->> 'no_retry_ack')::boolean is not true
     or jsonb_typeof(p_payload -> 'terms_ack') <> 'boolean'
     or (p_payload ->> 'terms_ack')::boolean is not true then
    raise exception using
      errcode = '22023', message = 'research_youtube_confirmation_required';
  end if;
  if jsonb_typeof(p_payload -> 'max_results') <> 'number'
     or jsonb_typeof(p_payload -> 'max_http_requests') <> 'number'
     or jsonb_typeof(p_payload -> 'max_quota_units') <> 'number'
     or coalesce(p_payload ->> 'max_results', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'max_http_requests', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'max_quota_units', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_youtube_quota_plan_invalid';
  end if;
  begin
    max_results_value := (p_payload ->> 'max_results')::integer;
    max_http_requests_value := (p_payload ->> 'max_http_requests')::integer;
    max_quota_units_value := (p_payload ->> 'max_quota_units')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'research_youtube_quota_plan_invalid';
  end;
  if (mode_value = 'manual_canary' and (
        max_results_value <> 1
        or max_http_requests_value <> 2
        or max_quota_units_value <> 2
      ))
     or (mode_value = 'category_refresh' and (
        max_results_value not between 1 and 25
        or max_http_requests_value <> 2
        or max_quota_units_value <> 2
      )) then
    raise exception using
      errcode = '22023', message = 'research_youtube_quota_plan_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  query_text_value := content_factory_private.require_text(
    p_payload, 'query_text', 2, 200
  );
  if query_text_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023', message = 'research_youtube_query_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  terms_version_value := content_factory_private.require_text(
    p_payload, 'terms_version', 3, 80
  );
  if terms_version_value <> 'youtube-developer-policies-2026-08-03-v1' then
    raise exception using
      errcode = '22023', message = 'research_youtube_terms_version_invalid';
  end if;
  region_code_value := nullif(btrim(coalesce(p_payload ->> 'region_code', '')), '');
  relevance_language_value := nullif(
    btrim(coalesce(p_payload ->> 'relevance_language', '')), ''
  );
  if (p_payload ? 'region_code'
       and jsonb_typeof(p_payload -> 'region_code') not in ('string', 'null'))
     or (p_payload ? 'relevance_language'
       and jsonb_typeof(p_payload -> 'relevance_language') not in ('string', 'null'))
     or (region_code_value is not null and region_code_value !~ '^[A-Z]{2}$')
     or (relevance_language_value is not null
       and relevance_language_value
         !~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$') then
    raise exception using
      errcode = '22023', message = 'research_youtube_locale_invalid';
  end if;
  if p_payload ? 'published_after'
     and jsonb_typeof(p_payload -> 'published_after') <> 'null' then
    if jsonb_typeof(p_payload -> 'published_after') <> 'string' then
      raise exception using
        errcode = '22023', message = 'research_youtube_published_after_invalid';
    end if;
    begin
      published_after_value := (p_payload ->> 'published_after')::timestamptz;
    exception when invalid_datetime_format or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'research_youtube_published_after_invalid';
    end;
    if published_after_value < clock_timestamp() - interval '366 days'
       or published_after_value > clock_timestamp() + interval '1 minute' then
      raise exception using
        errcode = '22023', message = 'research_youtube_published_after_invalid';
    end if;
  end if;

  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where run.organization_id = organization_id_value
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value, false, array['owner', 'admin', 'producer']
  );
  command_name_value := case mode_value
    when 'manual_canary' then 'creator_request_research_youtube_canary'
    else 'creator_request_research_youtube_refresh'
  end;
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id_value,
    command_name_value,
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  join content_factory.research_market_categories category
    on category.organization_id = binding.organization_id
   and category.id = binding.category_id
   and category.status = 'active'
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_youtube_market_category_required';
  end if;
  if not exists (
    select 1
    from content_factory.research_provider_catalog catalog
    where catalog.provider_key = 'youtube_data_api_v3'
      and catalog.adapter_version = 'youtube-data-api-v3-public-metadata-v1'
      and catalog.lifecycle_status = 'disabled'
      and catalog.rollout_stage = 'planned'
      and catalog.terms_version = 'youtube-data-api-review-required-v1'
      and catalog.canary_mode = 'manual_only'
      and not catalog.automatic_canary_allowed
      and not catalog.automatic_fallback_allowed
      and catalog.commercial_use_allowed
      and catalog.arbitrary_public_accounts_allowed
      and not catalog.subject_authorization_required
      and catalog.max_canary_requests = 1
      and catalog.credential_reference = 'env:YOUTUBE_DATA_API_KEY'
      and catalog.allowed_host = 'www.googleapis.com'
      and catalog.retention_days = 30
  ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_provider_contract_invalid';
  end if;
  if not content_factory_private.research_youtube_retention_ready() then
    raise exception using
      errcode = '55000', message = 'research_youtube_retention_control_required';
  end if;
  if not content_factory_private.research_youtube_global_gate(mode_value) then
    raise exception using
      errcode = '55000', message = 'research_youtube_global_rollout_gate_required';
  end if;
  if mode_value = 'category_refresh'
     and not content_factory_private.research_youtube_refresh_gate(
       organization_id_value
     ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_rollout_gate_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-youtube-request:' || product_id_value::text)
  );
  query_hash_value := content_factory_private.json_hash(
    jsonb_build_object('query_text', query_text_value)
  );
  request_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-live-ingestion-v1',
    'organization_id', organization_id_value,
    'run_id', run_id_value,
    'product_id', product_id_value,
    'binding_id', binding_row.id,
    'market_category_id', binding_row.category_id,
    'mode', mode_value,
    'query_text', query_text_value,
    'region_code', region_code_value,
    'relevance_language', relevance_language_value,
    'published_after', published_after_value,
    'max_results', max_results_value,
    'max_http_requests', max_http_requests_value,
    'max_quota_units', max_quota_units_value,
    'terms_version', terms_version_value,
    'idempotency_key', idempotency_key_value
  ));

  insert into content_factory.research_youtube_ingestion_runs (
    organization_id, run_id, product_id, binding_id, market_category_id,
    requested_by, mode, provider_key, adapter_version, query_text,
    query_hash, region_code, relevance_language, published_after,
    max_results, max_http_requests, max_quota_units, request_hash,
    idempotency_key, terms_version, no_retry
  ) values (
    organization_id_value, run_id_value, product_id_value, binding_row.id,
    binding_row.category_id, user_id, mode_value, 'youtube_data_api_v3',
    'youtube-data-api-v3-public-metadata-v1', query_text_value,
    query_hash_value, region_code_value, relevance_language_value,
    published_after_value, max_results_value, max_http_requests_value,
    max_quota_units_value, request_hash_value, idempotency_key_value,
    terms_version_value, true
  ) returning * into ingestion_row;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'ingestion', jsonb_build_object(
      'id', ingestion_row.id,
      'status', ingestion_row.status,
      'mode', ingestion_row.mode,
      'provider_key', ingestion_row.provider_key,
      'adapter_version', ingestion_row.adapter_version,
      'max_http_requests', ingestion_row.max_http_requests,
      'max_quota_units', ingestion_row.max_quota_units,
      'requested_at', ingestion_row.requested_at
    ),
    'guidance', jsonb_build_object(
      'status', 'queued',
      'recommended_next_step', 'invoke_manual_youtube_ingestion',
      'external_call_started', false,
      'automatic_retry_allowed', false,
      'automatic_fallback_allowed', false
    )
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_youtube_ingestion_requested',
    'research_youtube_ingestion',
    ingestion_row.id::text,
    jsonb_build_object(
      'mode', mode_value,
      'product_id', product_id_value,
      'market_category_id', binding_row.category_id,
      'max_http_requests', max_http_requests_value,
      'max_quota_units', max_quota_units_value,
      'external_call_started', false
    ),
    'research-youtube-request:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    command_name_value,
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_request_research_youtube_canary(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  return content_factory_private.request_research_youtube_ingestion(
    p_payload, 'manual_canary'
  );
end;
$$;

create or replace function public.creator_request_research_youtube_refresh(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  return content_factory_private.request_research_youtube_ingestion(
    p_payload, 'category_refresh'
  );
end;
$$;

create or replace function public.creator_decide_research_youtube_rollout(
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
  organization_id_value uuid;
  decision_value text;
  canary_ingestion_id_value uuid;
  terms_version_value text;
  reason_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  decision_hash_value text;
  decision_row content_factory.research_youtube_rollout_decisions%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'decision', 'canary_ingestion_id', 'reason',
    'terms_ack', 'terms_version', 'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'terms_ack') <> 'boolean'
     or (p_payload ->> 'terms_ack')::boolean is not true then
    raise exception using
      errcode = '22023', message = 'research_youtube_rollout_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  decision_value := content_factory_private.require_text(
    p_payload, 'decision', 10, 32
  );
  if decision_value not in ('enable_category_refresh', 'pause_category_refresh') then
    raise exception using
      errcode = '22023', message = 'research_youtube_rollout_decision_invalid';
  end if;
  reason_value := content_factory_private.require_text(p_payload, 'reason', 3, 500);
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  terms_version_value := content_factory_private.require_text(
    p_payload, 'terms_version', 3, 80
  );
  if terms_version_value <> 'youtube-developer-policies-2026-08-03-v1' then
    raise exception using
      errcode = '22023', message = 'research_youtube_terms_version_invalid';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value, false, array['owner', 'admin']
  );
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id_value,
    'creator_decide_research_youtube_rollout',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then return replay; end if;
  if decision_value = 'enable_category_refresh' then
    canary_ingestion_id_value := content_factory_private.require_uuid(
      p_payload, 'canary_ingestion_id'
    );
    if not content_factory_private.research_youtube_retention_ready() then
      raise exception using
        errcode = '55000', message = 'research_youtube_retention_control_required';
    end if;
    if not content_factory_private.research_youtube_global_gate(
      'category_refresh'
    ) then
      raise exception using
        errcode = '55000',
        message = 'research_youtube_global_rollout_gate_required';
    end if;
    if not exists (
      select 1
      from content_factory.research_youtube_ingestion_runs ingestion
      join content_factory.research_youtube_transport_attempts transport
        on transport.organization_id = ingestion.organization_id
       and transport.ingestion_id = ingestion.id
       and transport.request_ordinal = 1
       and transport.request_kind = 'search.list'
      join content_factory.research_youtube_transport_receipts receipt
        on receipt.organization_id = transport.organization_id
       and receipt.transport_id = transport.id
       and receipt.status = 'ready'
       and receipt.item_count = 1
      join content_factory.research_youtube_transport_attempts detail_transport
        on detail_transport.organization_id = ingestion.organization_id
       and detail_transport.ingestion_id = ingestion.id
       and detail_transport.request_ordinal = 2
       and detail_transport.request_kind = 'videos.list'
      join content_factory.research_youtube_transport_receipts detail_receipt
        on detail_receipt.organization_id = detail_transport.organization_id
       and detail_receipt.transport_id = detail_transport.id
       and detail_receipt.status = 'ready'
       and detail_receipt.item_count = 1
      where ingestion.organization_id = organization_id_value
        and ingestion.id = canary_ingestion_id_value
        and ingestion.mode = 'manual_canary'
        and ingestion.status = 'completed'
        and ingestion.completed_at >= clock_timestamp() - interval '24 hours'
    ) then
      raise exception using
        errcode = '55000', message = 'research_youtube_fresh_canary_required';
    end if;
  elsif p_payload ? 'canary_ingestion_id'
        and jsonb_typeof(p_payload -> 'canary_ingestion_id') <> 'null' then
    raise exception using
      errcode = '22023', message = 'research_youtube_rollout_canary_unexpected';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-youtube-rollout')
  );
  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-rollout-decision-v1',
    'organization_id', organization_id_value,
    'decision', decision_value,
    'canary_ingestion_id', canary_ingestion_id_value,
    'terms_version', terms_version_value,
    'reason', reason_value,
    'idempotency_key', idempotency_key_value
  ));
  insert into content_factory.research_youtube_rollout_decisions (
    organization_id, provider_key, adapter_version, decision,
    canary_ingestion_id, terms_version, retention_days, reason,
    decided_by, idempotency_key, decision_hash
  ) values (
    organization_id_value, 'youtube_data_api_v3',
    'youtube-data-api-v3-public-metadata-v1', decision_value,
    canary_ingestion_id_value, terms_version_value,
    29, reason_value, user_id, idempotency_key_value, decision_hash_value
  ) returning * into decision_row;
  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'rollout', jsonb_build_object(
      'decision_id', decision_row.id,
      'decision', decision_row.decision,
      'canary_ingestion_id', decision_row.canary_ingestion_id,
      'decided_at', decision_row.decided_at,
      'refresh_gate_open', decision_row.decision = 'enable_category_refresh'
    )
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_youtube_rollout_decided',
    'research_youtube_rollout',
    decision_row.id::text,
    jsonb_build_object(
      'decision', decision_value,
      'canary_ingestion_id', canary_ingestion_id_value
    ),
    'research-youtube-rollout:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_decide_research_youtube_rollout',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_research_youtube_status(
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
  organization_id_value uuid;
  ingestion_id_value uuid;
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  transport_value jsonb := '[]'::jsonb;
  observation_value jsonb := '[]'::jsonb;
  decision_value jsonb := '[]'::jsonb;
  rollout_value jsonb;
  retention_ready_value boolean;
  current_binding_value boolean := false;
  search_requests_today integer := 0;
  default_requests_today integer := 0;
  quota_now_value timestamptz;
  quota_day_value date;
  quota_starts_at_value timestamptz;
  quota_ends_at_value timestamptz;
  api_data_present_value boolean := false;
  api_data_retention_expired_value boolean := false;
  global_state_value text;
  recommendation_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['ingestion_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_status_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  select ingestion.* into ingestion_row
  from content_factory.research_youtube_ingestion_runs ingestion
  join content_factory.organizations organization
    on organization.id = ingestion.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = ingestion.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where ingestion.id = ingestion_id_value;
  if ingestion_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  perform content_factory_private.membership_role(
    ingestion_row.organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  if ingestion_row.status = 'processing'
     and ingestion_row.lease_expires_at <= clock_timestamp() then
    perform content_factory_private.expire_research_youtube_ingestion(
      ingestion_row.id
    );
    select ingestion.* into ingestion_row
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.id = ingestion_id_value;
  end if;

  select exists (
    select 1
    from content_factory.research_product_market_category_bindings binding
    join content_factory.research_market_categories category
      on category.organization_id = binding.organization_id
     and category.id = binding.category_id
     and category.status = 'active'
    where binding.organization_id = ingestion_row.organization_id
      and binding.product_id = ingestion_row.product_id
      and binding.id = ingestion_row.binding_id
      and not exists (
        select 1
        from content_factory.research_product_market_category_bindings newer
        where newer.organization_id = binding.organization_id
          and newer.product_id = binding.product_id
          and newer.binding_version > binding.binding_version
      )
  ) into current_binding_value;
  retention_ready_value := content_factory_private.research_youtube_retention_ready();
  global_state_value := content_factory_private.research_youtube_global_state();

  select coalesce(jsonb_agg(jsonb_build_object(
    'transport_id', transport.id,
    'request_ordinal', transport.request_ordinal,
    'request_kind', transport.request_kind,
    'quota_bucket', transport.quota_bucket,
    'quota_units', transport.quota_units,
    'request_hash', transport.request_hash,
    'started_at', transport.started_at,
    'receipt', case when receipt.id is null then null else jsonb_build_object(
      'receipt_id', receipt.id,
      'status', receipt.status,
      'failure_code', receipt.failure_code,
      'response_hash', receipt.response_hash,
      'item_count', receipt.item_count,
      'checked_at', receipt.checked_at
    ) end
  ) order by transport.request_ordinal), '[]'::jsonb)
  into transport_value
  from content_factory.research_youtube_transport_attempts transport
  left join content_factory.research_youtube_transport_receipts receipt
    on receipt.organization_id = transport.organization_id
   and receipt.transport_id = transport.id
   and receipt.retention_expires_at > clock_timestamp()
  where transport.organization_id = ingestion_row.organization_id
    and transport.ingestion_id = ingestion_row.id
    and transport.started_at > clock_timestamp() - interval '29 days';

  select coalesce(jsonb_agg(jsonb_build_object(
    'observation_id', observation.id,
    'search_position', observation.search_position,
    'video_id', observation.video_id,
    'channel_id', observation.channel_id,
    'title', observation.title,
    'channel_title', observation.channel_title,
    'youtube_category_id', observation.youtube_category_id,
    'published_at', observation.published_at,
    'duration_iso8601', observation.duration_iso8601,
    'privacy_status', observation.privacy_status,
    'embeddable', observation.embeddable,
    'view_count', observation.view_count,
    'like_count', observation.like_count,
    'comment_count', observation.comment_count,
    'observed_at', observation.observed_at,
    'retention_expires_at', observation.retention_expires_at,
    'observation_hash', observation.observation_hash
  ) order by observation.search_position, observation.id), '[]'::jsonb)
  into observation_value
  from content_factory.research_youtube_video_observations observation
  where observation.organization_id = ingestion_row.organization_id
    and observation.ingestion_id = ingestion_row.id
    and observation.retention_expires_at > clock_timestamp();

  select coalesce(jsonb_agg(jsonb_build_object(
    'decision_id', decision_entry.id,
    'ingestion_id', decision_entry.ingestion_id,
    'observation_id', decision_entry.observation_id,
    'observation_hash', decision_entry.observation_hash,
    'decision', decision_entry.decision,
    'reason', decision_entry.reason,
    'decided_at', decision_entry.decided_at,
    'retention_expires_at', decision_entry.retention_expires_at,
    'decision_hash', decision_entry.decision_hash
  ) order by decision_entry.decided_at desc, decision_entry.id desc), '[]'::jsonb)
  into decision_value
  from (
    select bounded_decision.*
    from content_factory.research_youtube_candidate_decisions bounded_decision
    where bounded_decision.organization_id = ingestion_row.organization_id
      and bounded_decision.ingestion_id = ingestion_row.id
      and bounded_decision.retention_expires_at > clock_timestamp()
    order by bounded_decision.decided_at desc, bounded_decision.id desc
    limit 100
  ) decision_entry;

  select jsonb_build_object(
    'decision_id', rollout.id,
    'decision', rollout.decision,
    'canary_ingestion_id', rollout.canary_ingestion_id,
    'terms_version', rollout.terms_version,
    'retention_days', rollout.retention_days,
    'decided_at', rollout.decided_at,
    'refresh_gate_open', content_factory_private.research_youtube_refresh_gate(
      ingestion_row.organization_id
    )
  ) into rollout_value
  from content_factory.research_youtube_rollout_decisions rollout
  where rollout.organization_id = ingestion_row.organization_id
  order by rollout.decided_at desc, rollout.id desc
  limit 1;

  quota_now_value := clock_timestamp();
  select quota_window.quota_day, quota_window.starts_at, quota_window.ends_at
  into quota_day_value, quota_starts_at_value, quota_ends_at_value
  from content_factory_private.research_youtube_quota_window(
    quota_now_value
  ) quota_window;
  select
    count(*) filter (where transport.request_kind = 'search.list')::integer,
    count(*) filter (where transport.request_kind = 'videos.list')::integer
  into search_requests_today, default_requests_today
  from content_factory.research_youtube_transport_attempts transport
  where transport.organization_id = ingestion_row.organization_id
    and transport.started_at >= quota_starts_at_value
    and transport.started_at < quota_ends_at_value;
  select exists (
    select 1
    from content_factory.research_youtube_transport_receipts receipt
    where receipt.organization_id = ingestion_row.organization_id
      and receipt.ingestion_id = ingestion_row.id
      and receipt.retention_expires_at > quota_now_value
    union all
    select 1
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = ingestion_row.organization_id
      and observation.ingestion_id = ingestion_row.id
      and observation.retention_expires_at > quota_now_value
    union all
    select 1
    from content_factory.research_youtube_candidate_decisions decision_entry
    where decision_entry.organization_id = ingestion_row.organization_id
      and decision_entry.ingestion_id = ingestion_row.id
      and decision_entry.retention_expires_at > quota_now_value
  ) into api_data_present_value;
  if ingestion_row.status = 'completed' and not api_data_present_value then
    select exists (
      select 1
      from content_factory.research_youtube_retention_receipts receipt
      where receipt.successful
        and receipt.cutoff_at >= ingestion_row.requested_at + interval '29 days'
    ) into api_data_retention_expired_value;
  end if;
  recommendation_value := case
    when ingestion_row.status = 'queued' then 'invoke_manual_youtube_ingestion'
    when ingestion_row.status = 'processing' then 'wait_for_manual_ingestion_receipt'
    when ingestion_row.status = 'failed' then 'inspect_transport_receipt_before_new_request'
    when api_data_retention_expired_value
      then 'request_new_ingestion_after_retention'
    when ingestion_row.mode = 'manual_canary'
      and not content_factory_private.research_youtube_refresh_gate(
        ingestion_row.organization_id
      ) then 'review_canary_and_decide_rollout'
    when jsonb_array_length(observation_value) = 0 then 'refine_query_before_next_refresh'
    else 'review_live_competitor_candidates'
  end;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'ingestion', jsonb_build_object(
      'id', ingestion_row.id,
      'status', ingestion_row.status,
      'mode', ingestion_row.mode,
      'run_id', ingestion_row.run_id,
      'product_id', ingestion_row.product_id,
      'binding_id', ingestion_row.binding_id,
      'market_category_id', ingestion_row.market_category_id,
      'provider_key', ingestion_row.provider_key,
      'adapter_version', ingestion_row.adapter_version,
      'query_text', ingestion_row.query_text,
      'region_code', ingestion_row.region_code,
      'relevance_language', ingestion_row.relevance_language,
      'published_after', ingestion_row.published_after,
      'max_results', ingestion_row.max_results,
      'max_http_requests', ingestion_row.max_http_requests,
      'max_quota_units', ingestion_row.max_quota_units,
      'quota_units_started', ingestion_row.quota_units_started,
      'request_hash', ingestion_row.request_hash,
      'requested_at', ingestion_row.requested_at,
      'claimed_at', ingestion_row.claimed_at,
      'lease_expires_at', ingestion_row.lease_expires_at,
      'completed_at', ingestion_row.completed_at,
      'error_code', ingestion_row.error_code,
      'error_message', ingestion_row.error_message,
      'current_binding', current_binding_value
    ),
    'transports', transport_value,
    'observations', observation_value,
    'candidate_decisions', decision_value,
    'global_rollout_state', global_state_value,
    'rollout', rollout_value,
    'quota', jsonb_build_object(
      'provider_day', quota_day_value,
      'provider_timezone', 'America/Los_Angeles',
      'resets_at', quota_ends_at_value,
      'organization_search_requests_started', search_requests_today,
      'organization_search_requests_cap', 20,
      'organization_video_detail_requests_started', default_requests_today,
      'organization_video_detail_requests_cap', 20,
      'monetary_cost_rub', 0
    ),
    'retention', jsonb_build_object(
      'retention_days', 29,
      'provider_policy_limit_days', 30,
      'physical_purge_schedule_ready', retention_ready_value,
      'api_data_present', api_data_present_value,
      'api_data_retention_expired', api_data_retention_expired_value
    ),
    'guidance', jsonb_build_object(
      'status', ingestion_row.status,
      'recommended_next_step', recommendation_value,
      'automatic_retry_allowed', false,
      'automatic_fallback_allowed', false,
      'generation_consumption', 'forbidden',
      'candidate_confirmation_required', true
    )
  );
end;
$$;

create or replace function public.creator_research_youtube_overview(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  run_id_value uuid;
  product_id_value uuid;
  limit_value integer := 12;
  limit_numeric numeric;
  actor_role text;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  category_row content_factory.research_market_categories%rowtype;
  ingestions_value jsonb := '[]'::jsonb;
  rollout_value jsonb;
  search_requests_today integer := 0;
  default_requests_today integer := 0;
  quota_now_value timestamptz;
  quota_day_value date;
  quota_starts_at_value timestamptz;
  quota_ends_at_value timestamptz;
  global_state_value text;
  refresh_gate_value boolean := false;
  retention_ready_value boolean := false;
  recommendation_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id', 'limit']::text[]
       <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_overview_payload_invalid';
  end if;
  if auth.uid() is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number' then
      raise exception using
        errcode = '22023', message = 'research_youtube_overview_limit_invalid';
    end if;
    begin
      limit_numeric := (p_payload ->> 'limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'research_youtube_overview_limit_invalid';
    end;
    if limit_numeric <> trunc(limit_numeric) or limit_numeric not between 1 and 20 then
      raise exception using
        errcode = '22023', message = 'research_youtube_overview_limit_invalid';
    end if;
    limit_value := limit_numeric::integer;
  end if;
  actor_role := content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  where run.organization_id = organization_id_value
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is not null then
    select category.* into category_row
    from content_factory.research_market_categories category
    where category.organization_id = organization_id_value
      and category.id = binding_row.category_id;
  end if;
  retention_ready_value := content_factory_private.research_youtube_retention_ready();
  global_state_value := content_factory_private.research_youtube_global_state();
  refresh_gate_value := content_factory_private.research_youtube_refresh_gate(
    organization_id_value
  );

  select coalesce(jsonb_agg(jsonb_build_object(
    'ingestion_id', ingestion.id,
    'status', ingestion.status,
    'mode', ingestion.mode,
    'binding_id', ingestion.binding_id,
    'market_category_id', ingestion.market_category_id,
    'query_text', ingestion.query_text,
    'region_code', ingestion.region_code,
    'relevance_language', ingestion.relevance_language,
    'published_after', ingestion.published_after,
    'max_results', ingestion.max_results,
    'max_http_requests', ingestion.max_http_requests,
    'max_quota_units', ingestion.max_quota_units,
    'quota_units_started', ingestion.quota_units_started,
    'requested_at', ingestion.requested_at,
    'claimed_at', ingestion.claimed_at,
    'lease_expires_at', ingestion.lease_expires_at,
    'completed_at', ingestion.completed_at,
    'error_code', ingestion.error_code
  ) order by ingestion.requested_at desc, ingestion.id desc), '[]'::jsonb)
  into ingestions_value
  from (
    select bounded.*
    from content_factory.research_youtube_ingestion_runs bounded
    where bounded.organization_id = organization_id_value
      and bounded.product_id = product_id_value
    order by bounded.requested_at desc, bounded.id desc
    limit limit_value
  ) ingestion;

  select jsonb_build_object(
    'decision_id', rollout.id,
    'decision', rollout.decision,
    'canary_ingestion_id', rollout.canary_ingestion_id,
    'terms_version', rollout.terms_version,
    'retention_days', rollout.retention_days,
    'decided_at', rollout.decided_at,
    'refresh_gate_open', refresh_gate_value
  ) into rollout_value
  from content_factory.research_youtube_rollout_decisions rollout
  where rollout.organization_id = organization_id_value
  order by rollout.decided_at desc, rollout.id desc
  limit 1;
  quota_now_value := clock_timestamp();
  select quota_window.quota_day, quota_window.starts_at, quota_window.ends_at
  into quota_day_value, quota_starts_at_value, quota_ends_at_value
  from content_factory_private.research_youtube_quota_window(
    quota_now_value
  ) quota_window;
  select
    count(*) filter (where transport.request_kind = 'search.list')::integer,
    count(*) filter (where transport.request_kind = 'videos.list')::integer
  into search_requests_today, default_requests_today
  from content_factory.research_youtube_transport_attempts transport
  where transport.organization_id = organization_id_value
    and transport.started_at >= quota_starts_at_value
    and transport.started_at < quota_ends_at_value;
  recommendation_value := case
    when binding_row.id is null or coalesce(category_row.status, '') <> 'active'
      then 'confirm_active_market_category'
    when global_state_value in ('disabled', 'emergency_paused')
      then 'await_reviewed_global_youtube_rollout'
    when not retention_ready_value then 'restore_physical_retention_schedule'
    when jsonb_array_length(ingestions_value) = 0 then 'run_manual_canary'
    when global_state_value <> 'controlled_rollout'
      then 'await_reviewed_controlled_rollout'
    when not refresh_gate_value then 'review_canary_and_enable_refresh'
    else 'run_explicit_category_refresh'
  end;
  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'run_id', run_id_value,
    'product_id', product_id_value,
    'global_rollout_state', global_state_value,
    'current_binding', case when binding_row.id is null then null else jsonb_build_object(
      'binding_id', binding_row.id,
      'binding_version', binding_row.binding_version,
      'market_category_id', binding_row.category_id,
      'canonical_name', category_row.canonical_name,
      'category_status', category_row.status
    ) end,
    'can_request_canary', actor_role in ('owner', 'admin', 'producer')
      and binding_row.id is not null and coalesce(category_row.status, '') = 'active'
      and retention_ready_value
      and content_factory_private.research_youtube_global_gate('manual_canary'),
    'can_request_refresh', actor_role in ('owner', 'admin', 'producer')
      and binding_row.id is not null and coalesce(category_row.status, '') = 'active'
      and refresh_gate_value,
    'can_decide_rollout', actor_role in ('owner', 'admin')
      and global_state_value = 'controlled_rollout',
    'can_decide_candidates', actor_role in ('owner', 'admin', 'producer', 'reviewer'),
    'ingestions', ingestions_value,
    'rollout', rollout_value,
    'quota', jsonb_build_object(
      'provider_day', quota_day_value,
      'provider_timezone', 'America/Los_Angeles',
      'resets_at', quota_ends_at_value,
      'organization_search_requests_started', search_requests_today,
      'organization_search_requests_cap', 20,
      'organization_video_detail_requests_started', default_requests_today,
      'organization_video_detail_requests_cap', 20,
      'monetary_cost_rub', 0
    ),
    'retention', jsonb_build_object(
      'retention_days', 29,
      'provider_policy_limit_days', 30,
      'physical_purge_schedule_ready', retention_ready_value
    ),
    'guidance', jsonb_build_object(
      'status', case
        when binding_row.id is null then 'blocked'
        when global_state_value in ('disabled', 'emergency_paused') then 'blocked'
        when refresh_gate_value then 'ready'
        else 'canary_required'
      end,
      'recommended_next_step', recommendation_value,
      'manual_external_action_required', true,
      'automatic_retry_allowed', false,
      'automatic_fallback_allowed', false,
      'generation_consumption', 'forbidden'
    )
  );
end;
$$;

create or replace function content_factory_private.claim_research_youtube_ingestion(
  ingestion_id_value uuid
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  claimed_value boolean := false;
  transition_time timestamptz;
  terminal_error_code text;
  terminal_error_message text;
begin
  select ingestion.* into ingestion_row
  from content_factory.research_youtube_ingestion_runs ingestion
  where ingestion.id = ingestion_id_value
  for update;
  if ingestion_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  if ingestion_row.status = 'processing'
     and ingestion_row.lease_expires_at <= clock_timestamp() then
    perform content_factory_private.expire_research_youtube_ingestion(
      ingestion_row.id
    );
    select ingestion.* into ingestion_row
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.id = ingestion_id_value;
  end if;
  if ingestion_row.status = 'queued' then
    if not exists (
      select 1
      from content_factory.research_product_market_category_bindings binding
      join content_factory.research_market_categories category
        on category.organization_id = binding.organization_id
       and category.id = binding.category_id
       and category.status = 'active'
      where binding.organization_id = ingestion_row.organization_id
        and binding.product_id = ingestion_row.product_id
        and binding.id = ingestion_row.binding_id
        and binding.category_id = ingestion_row.market_category_id
        and not exists (
          select 1
          from content_factory.research_product_market_category_bindings newer
          where newer.organization_id = binding.organization_id
            and newer.product_id = binding.product_id
            and newer.binding_version > binding.binding_version
        )
    ) then
      terminal_error_code := 'category_binding_stale';
      terminal_error_message :=
        'The exact market-category binding changed before provider transport.';
    elsif not content_factory_private.research_youtube_retention_ready() then
      terminal_error_code := 'retention_control_unavailable';
      terminal_error_message :=
        'The physical retention heartbeat was unavailable before transport.';
    elsif not content_factory_private.research_youtube_global_gate(
      ingestion_row.mode
    ) then
      terminal_error_code := 'rollout_gate_closed';
      terminal_error_message :=
        'The global YouTube rollout gate closed before provider transport.';
    elsif ingestion_row.mode = 'category_refresh'
       and not content_factory_private.research_youtube_refresh_gate(
         ingestion_row.organization_id
       ) then
      terminal_error_code := 'rollout_gate_closed';
      terminal_error_message :=
        'The organization refresh gate closed before provider transport.';
    end if;
    transition_time := clock_timestamp();
    if terminal_error_code is not null then
      update content_factory.research_youtube_ingestion_runs ingestion
      set status = 'failed',
          claimed_at = transition_time,
          lease_expires_at = transition_time + interval '5 minutes',
          completed_at = transition_time,
          completion_hash = content_factory_private.json_hash(
            jsonb_build_object(
              'version', 'research-youtube-terminal-v1',
              'ingestion_id', ingestion.id,
              'status', 'failed',
              'error_code', terminal_error_code,
              'error_message', terminal_error_message,
              'completed_at', transition_time
            )
          ),
          error_code = terminal_error_code,
          error_message = terminal_error_message
      where ingestion.id = ingestion_row.id
        and ingestion.status = 'queued'
      returning * into ingestion_row;
    else
      update content_factory.research_youtube_ingestion_runs ingestion
      set status = 'processing',
          claimed_at = transition_time,
          lease_expires_at = transition_time + interval '5 minutes'
      where ingestion.id = ingestion_row.id
        and ingestion.status = 'queued'
      returning * into ingestion_row;
      claimed_value := ingestion_row.id is not null;
    end if;
  end if;
  return jsonb_build_object(
    'ok', true,
    'claimed', claimed_value,
    'ingestion', jsonb_build_object(
      'id', ingestion_row.id,
      'status', ingestion_row.status,
      'mode', ingestion_row.mode,
      'provider_key', ingestion_row.provider_key,
      'adapter_version', ingestion_row.adapter_version,
      'query_text', ingestion_row.query_text,
      'region_code', ingestion_row.region_code,
      'relevance_language', ingestion_row.relevance_language,
      'published_after', ingestion_row.published_after,
      'max_results', ingestion_row.max_results,
      'max_http_requests', ingestion_row.max_http_requests,
      'max_quota_units', ingestion_row.max_quota_units,
      'request_hash', ingestion_row.request_hash,
      'lease_expires_at', ingestion_row.lease_expires_at,
      'error_code', ingestion_row.error_code
    )
  );
end;
$$;

create or replace function public.creator_claim_research_youtube_ingestion(
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
  ingestion_id_value uuid;
  organization_id_value uuid;
  requested_by_value uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['ingestion_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_claim_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  select ingestion.organization_id, ingestion.requested_by
  into organization_id_value, requested_by_value
  from content_factory.research_youtube_ingestion_runs ingestion
  join content_factory.memberships membership
    on membership.organization_id = ingestion.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where ingestion.id = ingestion_id_value;
  if organization_id_value is null or requested_by_value <> user_id then
    raise exception using
      errcode = '42501', message = 'research_youtube_invoke_not_authorized';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value, false, array['owner', 'admin', 'producer']
  );
  result_value := content_factory_private.claim_research_youtube_ingestion(
    ingestion_id_value
  );
  return jsonb_build_object('invoke_authorized', true) || result_value;
end;
$$;

create or replace function public.system_claim_research_youtube_ingestion(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  ingestion_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['ingestion_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_claim_payload_invalid';
  end if;
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  return content_factory_private.claim_research_youtube_ingestion(
    ingestion_id_value
  );
end;
$$;

create or replace function public.system_begin_research_youtube_transport(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  ingestion_id_value uuid;
  request_ordinal_value integer;
  request_kind_value text;
  quota_bucket_value text;
  quota_units_value integer;
  request_hash_value text;
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  transport_row content_factory.research_youtube_transport_attempts%rowtype;
  quota_now_value timestamptz;
  quota_day_value date;
  quota_starts_at_value timestamptz;
  quota_ends_at_value timestamptz;
  global_started_value integer := 0;
  organization_started_value integer := 0;
  requester_started_value integer := 0;
  lease_expired_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'ingestion_id', 'request_ordinal', 'request_kind', 'quota_bucket',
    'quota_units', 'request_hash'
  ]::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'request_ordinal') <> 'number'
     or jsonb_typeof(p_payload -> 'quota_units') <> 'number'
     or coalesce(p_payload ->> 'request_ordinal', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'quota_units', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_payload_invalid';
  end if;
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  request_ordinal_value := (p_payload ->> 'request_ordinal')::integer;
  quota_units_value := (p_payload ->> 'quota_units')::integer;
  request_kind_value := content_factory_private.require_text(
    p_payload, 'request_kind', 9, 16
  );
  quota_bucket_value := content_factory_private.require_text(
    p_payload, 'quota_bucket', 7, 20
  );
  request_hash_value := content_factory_private.require_text(
    p_payload, 'request_hash', 64, 64
  );
  if request_hash_value !~ '^[0-9a-f]{64}$'
     or request_ordinal_value not between 1 and 2
     or quota_units_value <> 1
     or (request_kind_value = 'search.list'
       and quota_bucket_value <> 'search_queries')
     or (request_kind_value = 'videos.list'
       and quota_bucket_value <> 'default')
     or request_kind_value not in ('search.list', 'videos.list') then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_payload_invalid';
  end if;

  select ingestion.* into ingestion_row
  from content_factory.research_youtube_ingestion_runs ingestion
  where ingestion.id = ingestion_id_value
  for update;
  if ingestion_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  if ingestion_row.status = 'processing'
     and ingestion_row.lease_expires_at <= clock_timestamp() then
    lease_expired_value := content_factory_private.expire_research_youtube_ingestion(
      ingestion_row.id
    );
    select ingestion.* into ingestion_row
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.id = ingestion_id_value;
  end if;
  if lease_expired_value then
    return jsonb_build_object(
      'ok', false,
      'version', 'research-youtube-live-ingestion-v1',
      'external_call_allowed', false,
      'ingestion_status', ingestion_row.status,
      'error_code', ingestion_row.error_code
    );
  end if;
  if ingestion_row.status <> 'processing' then
    raise exception using
      errcode = '55000', message = 'research_youtube_ingestion_not_processing';
  end if;
  if not content_factory_private.research_youtube_retention_ready()
     or not content_factory_private.research_youtube_global_gate(
       ingestion_row.mode
     )
     or (ingestion_row.mode = 'category_refresh'
       and not content_factory_private.research_youtube_refresh_gate(
         ingestion_row.organization_id
       )) then
    raise exception using
      errcode = '55000', message = 'research_youtube_transport_gate_closed';
  end if;
  select transport.* into transport_row
  from content_factory.research_youtube_transport_attempts transport
  where transport.organization_id = ingestion_row.organization_id
    and transport.ingestion_id = ingestion_row.id
    and transport.request_ordinal = request_ordinal_value;
  if transport_row.id is not null then
    if transport_row.request_kind <> request_kind_value
       or transport_row.quota_bucket <> quota_bucket_value
       or transport_row.quota_units <> quota_units_value
       or transport_row.request_hash <> request_hash_value then
      raise exception using
        errcode = '23505', message = 'research_youtube_transport_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'transport_id', transport_row.id,
      'external_call_allowed', false,
      'provider_key', ingestion_row.provider_key,
      'adapter_version', ingestion_row.adapter_version,
      'request_ordinal', transport_row.request_ordinal,
      'request_kind', transport_row.request_kind
    );
  end if;
  if request_ordinal_value <> ingestion_row.quota_units_started + 1
     or request_ordinal_value > ingestion_row.max_http_requests
     or ingestion_row.quota_units_started + quota_units_value
        > ingestion_row.max_quota_units
     or (request_ordinal_value = 1 and request_kind_value <> 'search.list')
     or (request_ordinal_value = 2 and request_kind_value <> 'videos.list') then
    raise exception using
      errcode = '55000', message = 'research_youtube_transport_plan_violation';
  end if;
  if request_ordinal_value = 2 and not exists (
    select 1
    from content_factory.research_youtube_transport_attempts prior
    join content_factory.research_youtube_transport_receipts receipt
      on receipt.organization_id = prior.organization_id
     and receipt.transport_id = prior.id
     and receipt.status = 'ready'
     and receipt.item_count between 1 and 25
    where prior.organization_id = ingestion_row.organization_id
      and prior.ingestion_id = ingestion_row.id
      and prior.request_ordinal = 1
      and prior.request_kind = 'search.list'
  ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_search_receipt_required';
  end if;

  quota_now_value := clock_timestamp();
  select quota_window.quota_day, quota_window.starts_at, quota_window.ends_at
  into quota_day_value, quota_starts_at_value, quota_ends_at_value
  from content_factory_private.research_youtube_quota_window(
    quota_now_value
  ) quota_window;
  perform pg_advisory_xact_lock(
    hashtext('youtube_data_api_v3:' || request_kind_value),
    hashtext(quota_day_value::text)
  );
  select
    count(*)::integer,
    count(*) filter (
      where attempt_ingestion.organization_id = ingestion_row.organization_id
    )::integer,
    count(*) filter (
      where attempt_ingestion.requested_by = ingestion_row.requested_by
    )::integer
  into global_started_value, organization_started_value, requester_started_value
  from content_factory.research_youtube_transport_attempts transport
  join content_factory.research_youtube_ingestion_runs attempt_ingestion
    on attempt_ingestion.organization_id = transport.organization_id
   and attempt_ingestion.id = transport.ingestion_id
  where transport.request_kind = request_kind_value
    and transport.started_at >= quota_starts_at_value
    and transport.started_at < quota_ends_at_value;
  if global_started_value >= 90
     or organization_started_value >= 20
     or requester_started_value >= 10 then
    raise exception using
      errcode = '55000', message = 'research_youtube_local_daily_quota_exhausted';
  end if;
  insert into content_factory.research_youtube_transport_attempts (
    organization_id, ingestion_id, request_ordinal, request_kind,
    quota_bucket, quota_units, request_hash, started_at
  ) values (
    ingestion_row.organization_id, ingestion_row.id, request_ordinal_value,
    request_kind_value, quota_bucket_value, quota_units_value,
    request_hash_value, quota_now_value
  ) returning * into transport_row;
  update content_factory.research_youtube_ingestion_runs ingestion
  set quota_units_started = ingestion.quota_units_started + quota_units_value
  where ingestion.id = ingestion_row.id;
  return jsonb_build_object(
    'ok', true,
    'transport_id', transport_row.id,
    'external_call_allowed', true,
    'provider_key', ingestion_row.provider_key,
    'adapter_version', ingestion_row.adapter_version,
    'request_ordinal', transport_row.request_ordinal,
    'request_kind', transport_row.request_kind
  );
end;
$$;

create or replace function public.system_record_research_youtube_transport(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  transport_id_value uuid;
  status_value text;
  failure_code_value text;
  response_hash_value text;
  item_count_value integer;
  checked_at_value timestamptz;
  transport_row content_factory.research_youtube_transport_attempts%rowtype;
  receipt_row content_factory.research_youtube_transport_receipts%rowtype;
  receipt_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'transport_id', 'status', 'failure_code', 'response_hash',
    'item_count', 'checked_at'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_receipt_payload_invalid';
  end if;
  transport_id_value := content_factory_private.require_uuid(
    p_payload, 'transport_id'
  );
  status_value := content_factory_private.require_text(p_payload, 'status', 5, 8);
  failure_code_value := nullif(btrim(coalesce(p_payload ->> 'failure_code', '')), '');
  response_hash_value := nullif(btrim(coalesce(p_payload ->> 'response_hash', '')), '');
  if status_value not in ('ready', 'degraded', 'blocked', 'unknown')
     or (p_payload ? 'failure_code'
       and jsonb_typeof(p_payload -> 'failure_code') not in ('string', 'null'))
     or (p_payload ? 'response_hash'
       and jsonb_typeof(p_payload -> 'response_hash') not in ('string', 'null'))
     or (response_hash_value is not null
       and response_hash_value !~ '^[0-9a-f]{64}$') then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_receipt_payload_invalid';
  end if;
  if p_payload ? 'item_count'
     and jsonb_typeof(p_payload -> 'item_count') <> 'null' then
    if jsonb_typeof(p_payload -> 'item_count') <> 'number'
       or coalesce(p_payload ->> 'item_count', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'research_youtube_transport_receipt_payload_invalid';
    end if;
    item_count_value := (p_payload ->> 'item_count')::integer;
  end if;
  if item_count_value is not null and item_count_value not between 0 and 25 then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_receipt_payload_invalid';
  end if;
  begin
    checked_at_value := content_factory_private.require_text(
      p_payload, 'checked_at', 10, 64
    )::timestamptz;
  exception when invalid_datetime_format or datetime_field_overflow then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_receipt_payload_invalid';
  end;
  if (status_value = 'ready' and (
        failure_code_value is not null
        or response_hash_value is null
        or item_count_value is null
      ))
     or (status_value <> 'ready' and failure_code_value is null)
     or failure_code_value is not null and failure_code_value not in (
       'provider_configuration_error',
       'provider_authentication_failed',
       'provider_quota_exhausted',
       'provider_rate_limited',
       'provider_request_rejected',
       'provider_response_invalid',
       'provider_outcome_unknown',
       'provider_unavailable'
     ) then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_receipt_state_invalid';
  end if;
  select transport.* into transport_row
  from content_factory.research_youtube_transport_attempts transport
  where transport.id = transport_id_value;
  if transport_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_not_found';
  end if;
  if not exists (
    select 1
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.organization_id = transport_row.organization_id
      and ingestion.id = transport_row.ingestion_id
      and ingestion.status = 'processing'
      and ingestion.lease_expires_at > clock_timestamp()
  ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_ingestion_lease_inactive';
  end if;
  if checked_at_value < transport_row.started_at - interval '1 minute'
     or checked_at_value > clock_timestamp() + interval '1 minute'
     or checked_at_value < clock_timestamp() - interval '15 minutes' then
    raise exception using
      errcode = '22023', message = 'research_youtube_transport_checked_at_invalid';
  end if;
  receipt_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-transport-receipt-v1',
    'transport_id', transport_row.id,
    'ingestion_id', transport_row.ingestion_id,
    'status', status_value,
    'failure_code', failure_code_value,
    'response_hash', response_hash_value,
    'item_count', item_count_value,
    'checked_at', checked_at_value
  ));
  select receipt.* into receipt_row
  from content_factory.research_youtube_transport_receipts receipt
  where receipt.organization_id = transport_row.organization_id
    and receipt.transport_id = transport_row.id;
  if receipt_row.id is not null then
    if receipt_row.receipt_hash <> receipt_hash_value then
      raise exception using
        errcode = '23505', message = 'research_youtube_transport_receipt_conflict';
    end if;
    return jsonb_build_object('ok', true, 'receipt_id', receipt_row.id);
  end if;
  insert into content_factory.research_youtube_transport_receipts (
    organization_id, ingestion_id, transport_id, status, failure_code,
    response_hash, item_count, checked_at, retention_expires_at, receipt_hash
  ) values (
    transport_row.organization_id, transport_row.ingestion_id,
    transport_row.id, status_value, failure_code_value,
    response_hash_value, item_count_value, checked_at_value,
    checked_at_value + interval '29 days',
    receipt_hash_value
  ) returning * into receipt_row;
  return jsonb_build_object('ok', true, 'receipt_id', receipt_row.id);
end;
$$;

create or replace function public.system_complete_research_youtube_ingestion(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  ingestion_id_value uuid;
  status_value text;
  observed_at_value timestamptz;
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  search_transport content_factory.research_youtube_transport_attempts%rowtype;
  search_receipt content_factory.research_youtube_transport_receipts%rowtype;
  detail_transport content_factory.research_youtube_transport_attempts%rowtype;
  detail_receipt content_factory.research_youtube_transport_receipts%rowtype;
  search_value jsonb;
  videos_value jsonb;
  canary_value jsonb;
  canary_checked_at_value timestamptz;
  observations_value jsonb;
  observation_value jsonb;
  observation_keys text[] := array[
    'search_position', 'video_id', 'channel_id', 'title', 'channel_title',
    'youtube_category_id', 'published_at', 'duration_iso8601',
    'privacy_status', 'embeddable', 'view_count', 'like_count',
    'comment_count', 'observed_at', 'retention_expires_at'
  ];
  search_position_value integer;
  video_id_value text;
  channel_id_value text;
  title_value text;
  channel_title_value text;
  youtube_category_id_value text;
  published_at_value timestamptz;
  duration_iso8601_value text;
  privacy_status_value text;
  embeddable_value boolean;
  view_count_value text;
  like_count_value text;
  comment_count_value text;
  item_observed_at_value timestamptz;
  retention_expires_at_value timestamptz;
  observation_hash_value text;
  search_response_hash_value text;
  search_item_count_value integer;
  videos_response_hash_value text;
  videos_item_count_value integer;
  completion_hash_value text;
  error_code_value text;
  error_message_value text;
  inserted_count_value integer := 0;
  existing_observation_count_value integer := 0;
  replay_completed_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072
     or not (p_payload ? 'version' and p_payload ? 'ingestion_id'
       and p_payload ? 'status' and p_payload ? 'observed_at')
     or p_payload ->> 'version' <> 'research-youtube-live-ingestion-v1' then
    raise exception using
      errcode = '22023', message = 'research_youtube_completion_payload_invalid';
  end if;
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  status_value := content_factory_private.require_text(p_payload, 'status', 6, 9);
  if status_value not in ('completed', 'failed') then
    raise exception using
      errcode = '22023', message = 'research_youtube_completion_payload_invalid';
  end if;
  begin
    observed_at_value := content_factory_private.require_text(
      p_payload, 'observed_at', 10, 64
    )::timestamptz;
  exception when invalid_datetime_format or datetime_field_overflow then
    raise exception using
      errcode = '22023', message = 'research_youtube_completion_payload_invalid';
  end;
  select ingestion.* into ingestion_row
  from content_factory.research_youtube_ingestion_runs ingestion
  where ingestion.id = ingestion_id_value
  for update;
  if ingestion_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  if ingestion_row.status = 'processing'
     and ingestion_row.lease_expires_at <= clock_timestamp() then
    perform content_factory_private.expire_research_youtube_ingestion(
      ingestion_row.id
    );
    select ingestion.* into ingestion_row
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.id = ingestion_id_value;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-live-ingestion-v1',
      'ingestion', jsonb_build_object(
        'id', ingestion_row.id,
        'status', ingestion_row.status
      )
    );
  end if;
  if observed_at_value < ingestion_row.claimed_at - interval '1 minute'
     or observed_at_value > clock_timestamp() + interval '1 minute'
     or observed_at_value < clock_timestamp() - interval '15 minutes' then
    raise exception using
      errcode = '22023', message = 'research_youtube_completion_observed_at_invalid';
  end if;
  completion_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-youtube-terminal-v1',
      'ingestion_id', ingestion_id_value,
      'status', status_value,
      'observed_at', observed_at_value,
      'error_code', nullif(p_payload ->> 'error_code', ''),
      'error_message', case when status_value = 'failed'
        then nullif(p_payload ->> 'error_message', '')
        else null
      end
    )
  );
  if ingestion_row.status in ('completed', 'failed') then
    if ingestion_row.completion_hash <> completion_hash_value
       or ingestion_row.status <> status_value then
      raise exception using
        errcode = '23505', message = 'research_youtube_completion_conflict';
    end if;
    if ingestion_row.status = 'failed' then
      return jsonb_build_object(
        'ok', true,
        'version', 'research-youtube-live-ingestion-v1',
        'ingestion', jsonb_build_object(
          'id', ingestion_row.id,
          'status', ingestion_row.status
        )
      );
    end if;
    replay_completed_value := true;
  end if;
  if ingestion_row.status not in ('processing', 'completed') then
    raise exception using
      errcode = '55000', message = 'research_youtube_ingestion_not_processing';
  end if;

  if status_value = 'completed'
     and not content_factory_private.research_youtube_retention_ready() then
    if replay_completed_value then
      raise exception using
        errcode = '55000', message = 'research_youtube_retention_control_required';
    end if;
    completion_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-youtube-terminal-v1',
        'ingestion_id', ingestion_id_value,
        'status', 'failed',
        'completed_at', observed_at_value,
        'observed_at', observed_at_value,
        'error_code', 'retention_control_unavailable',
        'error_message',
          'The physical retention heartbeat was unavailable at completion.'
      )
    );
    update content_factory.research_youtube_ingestion_runs ingestion
    set status = 'failed',
        completed_at = observed_at_value,
        completion_hash = completion_hash_value,
        error_code = 'retention_control_unavailable',
        error_message =
          'The physical retention heartbeat was unavailable at completion.'
    where ingestion.id = ingestion_row.id
    returning * into ingestion_row;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-live-ingestion-v1',
      'ingestion', jsonb_build_object(
        'id', ingestion_row.id,
        'status', ingestion_row.status
      )
    );
  end if;

  if status_value = 'failed' then
    if p_payload - array[
      'version', 'ingestion_id', 'status', 'error_code', 'error_message',
      'observed_at'
    ]::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023', message = 'research_youtube_completion_payload_invalid';
    end if;
    error_code_value := content_factory_private.require_text(
      p_payload, 'error_code', 10, 80
    );
    error_message_value := content_factory_private.require_text(
      p_payload, 'error_message', 1, 2000
    );
    if error_code_value not in (
      'provider_configuration_error',
      'provider_authentication_failed',
      'provider_quota_exhausted',
      'provider_rate_limited',
      'provider_request_rejected',
      'provider_response_invalid',
      'provider_outcome_unknown',
      'provider_unavailable',
      'retention_control_unavailable',
      'internal_error'
    ) then
      raise exception using
        errcode = '22023', message = 'research_youtube_completion_error_invalid';
    end if;
    -- A pre-fetch transport row is the authoritative ambiguity marker.  The
    -- best-effort receipt may itself fail to persist after a network timeout;
    -- that must not cause a retry or leave the ingestion pretending to be safe.
    if error_code_value = 'provider_outcome_unknown' and not exists (
      select 1
      from content_factory.research_youtube_transport_attempts transport
      where transport.organization_id = ingestion_row.organization_id
        and transport.ingestion_id = ingestion_row.id
    ) then
      raise exception using
        errcode = '55000', message = 'research_youtube_unknown_receipt_required';
    end if;
    update content_factory.research_youtube_ingestion_runs ingestion
    set status = 'failed',
        completed_at = observed_at_value,
        completion_hash = completion_hash_value,
        error_code = error_code_value,
        error_message = error_message_value
    where ingestion.id = ingestion_row.id
    returning * into ingestion_row;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-live-ingestion-v1',
      'ingestion', jsonb_build_object(
        'id', ingestion_row.id,
        'status', ingestion_row.status
      )
    );
  end if;

  if p_payload - array[
    'version', 'ingestion_id', 'status', 'provider_key',
    'adapter_version', 'observed_at', 'search', 'videos', 'canary',
    'observations'
  ]::text[] <> '{}'::jsonb
     or p_payload ->> 'provider_key' <> 'youtube_data_api_v3'
     or p_payload ->> 'adapter_version'
        <> 'youtube-data-api-v3-public-metadata-v1'
     or not (p_payload ? 'videos')
     or jsonb_typeof(p_payload -> 'search') <> 'object'
     or jsonb_typeof(p_payload -> 'observations') <> 'array' then
    raise exception using
      errcode = '22023', message = 'research_youtube_completion_payload_invalid';
  end if;
  search_value := p_payload -> 'search';
  videos_value := p_payload -> 'videos';
  observations_value := p_payload -> 'observations';
  if search_value - array[
    'response_hash', 'item_count'
  ]::text[] <> '{}'::jsonb
     or jsonb_typeof(search_value -> 'item_count') <> 'number'
     or coalesce(search_value ->> 'item_count', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_youtube_search_summary_invalid';
  end if;
  search_response_hash_value := content_factory_private.require_text(
    search_value, 'response_hash', 64, 64
  );
  search_item_count_value := (search_value ->> 'item_count')::integer;
  if search_response_hash_value !~ '^[0-9a-f]{64}$'
     or search_item_count_value not between 0 and ingestion_row.max_results
     or jsonb_array_length(observations_value) > ingestion_row.max_results then
    raise exception using
      errcode = '22023', message = 'research_youtube_search_summary_invalid';
  end if;
  select transport.* into search_transport
  from content_factory.research_youtube_transport_attempts transport
  where transport.organization_id = ingestion_row.organization_id
    and transport.ingestion_id = ingestion_row.id
    and transport.request_ordinal = 1
    and transport.request_kind = 'search.list';
  select receipt.* into search_receipt
  from content_factory.research_youtube_transport_receipts receipt
  where receipt.organization_id = ingestion_row.organization_id
    and receipt.transport_id = search_transport.id
    and receipt.retention_expires_at > clock_timestamp();
  if search_transport.id is null
     or search_receipt.id is null
     or search_receipt.status <> 'ready'
     or search_receipt.response_hash <> search_response_hash_value
     or search_receipt.item_count <> search_item_count_value then
    raise exception using
      errcode = '55000', message = 'research_youtube_search_receipt_mismatch';
  end if;

  select transport.* into detail_transport
  from content_factory.research_youtube_transport_attempts transport
  where transport.organization_id = ingestion_row.organization_id
    and transport.ingestion_id = ingestion_row.id
    and transport.request_ordinal = 2
    and transport.request_kind = 'videos.list';

  if jsonb_typeof(videos_value) = 'object' then
    if videos_value - array['response_hash', 'item_count']::text[]
         <> '{}'::jsonb
       or jsonb_typeof(videos_value -> 'item_count') <> 'number'
       or coalesce(videos_value ->> 'item_count', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'research_youtube_videos_summary_invalid';
    end if;
    videos_response_hash_value := content_factory_private.require_text(
      videos_value, 'response_hash', 64, 64
    );
    videos_item_count_value := (videos_value ->> 'item_count')::integer;
    if videos_response_hash_value !~ '^[0-9a-f]{64}$'
       or videos_item_count_value not between 0 and search_item_count_value then
      raise exception using
        errcode = '22023', message = 'research_youtube_videos_summary_invalid';
    end if;
    select receipt.* into detail_receipt
    from content_factory.research_youtube_transport_receipts receipt
    where receipt.organization_id = ingestion_row.organization_id
      and receipt.transport_id = detail_transport.id
      and receipt.retention_expires_at > clock_timestamp();
    if detail_transport.id is null
       or detail_receipt.id is null
       or detail_receipt.status <> 'ready'
       or detail_receipt.response_hash <> videos_response_hash_value
       or detail_receipt.item_count <> videos_item_count_value then
      raise exception using
        errcode = '55000', message = 'research_youtube_video_receipt_mismatch';
    end if;
  elsif jsonb_typeof(videos_value) <> 'null' then
    raise exception using
      errcode = '22023', message = 'research_youtube_videos_summary_invalid';
  end if;

  if ingestion_row.mode = 'manual_canary' then
    if search_item_count_value <> 1
       or jsonb_typeof(videos_value) <> 'object'
       or videos_item_count_value <> 1
       or not (p_payload ? 'canary')
       or jsonb_typeof(p_payload -> 'canary') <> 'object'
       or jsonb_array_length(observations_value) <> 0 then
      raise exception using
        errcode = '22023', message = 'research_youtube_canary_completion_invalid';
    end if;
    canary_value := p_payload -> 'canary';
    begin
      canary_checked_at_value := (canary_value ->> 'checked_at')::timestamptz;
    exception when invalid_datetime_format or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'research_youtube_canary_completion_invalid';
    end;
    if canary_value - array[
      'request_kind', 'response_hash', 'item_count', 'checked_at'
    ]::text[] <> '{}'::jsonb
       or canary_value ->> 'request_kind' <> 'videos.list'
       or canary_value ->> 'response_hash' <> videos_response_hash_value
       or coalesce(canary_value ->> 'item_count', '') !~ '^[0-9]+$'
       or (canary_value ->> 'item_count')::integer <> 1
       or canary_checked_at_value <> detail_receipt.checked_at then
      raise exception using
        errcode = '22023', message = 'research_youtube_canary_completion_invalid';
    end if;
  else
    if p_payload ? 'canary'
       and jsonb_typeof(p_payload -> 'canary') <> 'null' then
      raise exception using
        errcode = '22023', message = 'research_youtube_canary_completion_unexpected';
    end if;
    if search_item_count_value = 0 then
      if jsonb_typeof(videos_value) <> 'null'
         or detail_transport.id is not null
         or jsonb_array_length(observations_value) <> 0 then
        raise exception using
          errcode = '55000', message = 'research_youtube_empty_search_completion_invalid';
      end if;
    elsif jsonb_typeof(videos_value) <> 'object'
       or videos_item_count_value <> jsonb_array_length(observations_value) then
      raise exception using
        errcode = '55000', message = 'research_youtube_video_receipt_mismatch';
    end if;
  end if;

  for observation_value in
    select item.value
    from jsonb_array_elements(observations_value) with ordinality item(value, ordinal)
    order by item.ordinal
  loop
    if jsonb_typeof(observation_value) <> 'object'
       or observation_value - observation_keys <> '{}'::jsonb
       or not (
         select bool_and(observation_value ? required_key)
         from unnest(observation_keys) required(required_key)
       )
       or jsonb_typeof(observation_value -> 'search_position') <> 'number'
       or coalesce(observation_value ->> 'search_position', '') !~ '^[0-9]+$'
       or jsonb_typeof(observation_value -> 'embeddable') <> 'boolean' then
      raise exception using
        errcode = '22023', message = 'research_youtube_observation_invalid';
    end if;
    search_position_value := (observation_value ->> 'search_position')::integer;
    video_id_value := content_factory_private.require_text(
      observation_value, 'video_id', 11, 11
    );
    channel_id_value := content_factory_private.require_text(
      observation_value, 'channel_id', 24, 24
    );
    title_value := content_factory_private.require_text(
      observation_value, 'title', 1, 300
    );
    channel_title_value := content_factory_private.require_text(
      observation_value, 'channel_title', 1, 300
    );
    youtube_category_id_value := content_factory_private.require_text(
      observation_value, 'youtube_category_id', 1, 3
    );
    duration_iso8601_value := content_factory_private.require_text(
      observation_value, 'duration_iso8601', 2, 40
    );
    privacy_status_value := content_factory_private.require_text(
      observation_value, 'privacy_status', 6, 12
    );
    embeddable_value := (observation_value ->> 'embeddable')::boolean;
    view_count_value := nullif(btrim(coalesce(observation_value ->> 'view_count', '')), '');
    like_count_value := nullif(btrim(coalesce(observation_value ->> 'like_count', '')), '');
    comment_count_value := nullif(
      btrim(coalesce(observation_value ->> 'comment_count', '')), ''
    );
    if (jsonb_typeof(observation_value -> 'view_count') not in ('string', 'null'))
       or (jsonb_typeof(observation_value -> 'like_count') not in ('string', 'null'))
       or (jsonb_typeof(observation_value -> 'comment_count') not in ('string', 'null'))
       or search_position_value not between 1 and ingestion_row.max_results
       or video_id_value !~ '^[A-Za-z0-9_-]{11}$'
       or channel_id_value !~ '^UC[A-Za-z0-9_-]{22}$'
       or youtube_category_id_value !~ '^[0-9]{1,3}$'
       or duration_iso8601_value
          !~ '^P(?:[0-9]+D)?(?:T(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+S)?)?$'
       or privacy_status_value <> 'public'
       or title_value ~ '[[:cntrl:]]'
       or channel_title_value ~ '[[:cntrl:]]'
       or (view_count_value is not null and view_count_value !~ '^[0-9]{1,30}$')
       or (like_count_value is not null and like_count_value !~ '^[0-9]{1,30}$')
       or (comment_count_value is not null
         and comment_count_value !~ '^[0-9]{1,30}$') then
      raise exception using
        errcode = '22023', message = 'research_youtube_observation_invalid';
    end if;
    begin
      published_at_value := (observation_value ->> 'published_at')::timestamptz;
      item_observed_at_value := (observation_value ->> 'observed_at')::timestamptz;
      retention_expires_at_value :=
        (observation_value ->> 'retention_expires_at')::timestamptz;
    exception when invalid_datetime_format or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'research_youtube_observation_invalid';
    end;
    if published_at_value < '2005-02-14 00:00:00+00'::timestamptz
       or published_at_value > observed_at_value + interval '1 minute'
       or item_observed_at_value <> observed_at_value
       or retention_expires_at_value <> observed_at_value + interval '29 days' then
      raise exception using
        errcode = '22023', message = 'research_youtube_observation_invalid';
    end if;
    observation_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-youtube-video-observation-v1',
        'ingestion_id', ingestion_row.id,
        'search_position', search_position_value,
        'video_id', video_id_value,
        'channel_id', channel_id_value,
        'title', title_value,
        'channel_title', channel_title_value,
        'youtube_category_id', youtube_category_id_value,
        'published_at', published_at_value,
        'duration_iso8601', duration_iso8601_value,
        'privacy_status', privacy_status_value,
        'embeddable', embeddable_value,
        'view_count', view_count_value,
        'like_count', like_count_value,
        'comment_count', comment_count_value,
        'observed_at', observed_at_value,
        'retention_expires_at', retention_expires_at_value
      )
    );
    if replay_completed_value then
      if not exists (
        select 1
        from content_factory.research_youtube_video_observations observation
        where observation.organization_id = ingestion_row.organization_id
          and observation.ingestion_id = ingestion_row.id
          and observation.search_position = search_position_value
          and observation.observation_hash = observation_hash_value
          and observation.retention_expires_at > clock_timestamp()
      ) then
        raise exception using
          errcode = '23505', message = 'research_youtube_completion_conflict';
      end if;
    else
      insert into content_factory.research_youtube_video_observations (
        organization_id, ingestion_id, product_id, binding_id,
        market_category_id, search_position, video_id, channel_id, title,
        channel_title, youtube_category_id, published_at, duration_iso8601,
        privacy_status, embeddable, view_count, like_count, comment_count,
        observed_at, retention_expires_at, observation_hash
      ) values (
        ingestion_row.organization_id, ingestion_row.id,
        ingestion_row.product_id, ingestion_row.binding_id,
        ingestion_row.market_category_id, search_position_value,
        video_id_value, channel_id_value, title_value, channel_title_value,
        youtube_category_id_value, published_at_value,
        duration_iso8601_value, privacy_status_value, embeddable_value,
        view_count_value, like_count_value, comment_count_value,
        observed_at_value, retention_expires_at_value,
        observation_hash_value
      );
    end if;
    inserted_count_value := inserted_count_value + 1;
  end loop;
  if inserted_count_value <> jsonb_array_length(observations_value) then
    raise exception using
      errcode = '55000', message = 'research_youtube_observation_count_mismatch';
  end if;

  if replay_completed_value then
    select count(*)::integer into existing_observation_count_value
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = ingestion_row.organization_id
      and observation.ingestion_id = ingestion_row.id
      and observation.retention_expires_at > clock_timestamp();
    if existing_observation_count_value <> inserted_count_value then
      raise exception using
        errcode = '23505', message = 'research_youtube_completion_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-live-ingestion-v1',
      'ingestion', jsonb_build_object(
        'id', ingestion_row.id,
        'status', ingestion_row.status
      )
    );
  end if;

  update content_factory.research_youtube_ingestion_runs ingestion
  set status = 'completed',
      completed_at = observed_at_value,
      completion_hash = completion_hash_value
  where ingestion.id = ingestion_row.id
  returning * into ingestion_row;
  perform content_factory_private.emit_event(
    ingestion_row.organization_id,
    ingestion_row.requested_by,
    'research_youtube_ingestion_completed',
    'research_youtube_ingestion',
    ingestion_row.id::text,
    jsonb_build_object(
      'mode', ingestion_row.mode,
      'product_id', ingestion_row.product_id,
      'market_category_id', ingestion_row.market_category_id,
      'generation_consumption', 'forbidden'
    ),
    'research-youtube-completion:' || completion_hash_value
  );
  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'ingestion', jsonb_build_object(
      'id', ingestion_row.id,
      'status', ingestion_row.status
    )
  );
end;
$$;

create or replace function public.creator_decide_research_youtube_candidate(
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
  organization_id_value uuid;
  ingestion_id_value uuid;
  observation_id_value uuid;
  observation_hash_value text;
  decision_value text;
  reason_value text;
  idempotency_key_value text;
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
  observation_row content_factory.research_youtube_video_observations%rowtype;
  decision_row content_factory.research_youtube_candidate_decisions%rowtype;
  decision_hash_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'ingestion_id', 'observation_id', 'observation_hash',
    'decision', 'reason', 'confirmation', 'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or (p_payload ->> 'confirmation')::boolean is not true then
    raise exception using
      errcode = '22023', message = 'research_youtube_candidate_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  observation_id_value := content_factory_private.require_uuid(
    p_payload, 'observation_id'
  );
  observation_hash_value := content_factory_private.require_text(
    p_payload, 'observation_hash', 64, 64
  );
  decision_value := content_factory_private.require_text(
    p_payload, 'decision', 15, 24
  );
  reason_value := nullif(btrim(coalesce(p_payload ->> 'reason', '')), '');
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if observation_hash_value !~ '^[0-9a-f]{64}$'
     or decision_value not in ('confirm_candidate', 'exclude_candidate')
     or (p_payload ? 'reason'
       and jsonb_typeof(p_payload -> 'reason') not in ('string', 'null'))
     or (reason_value is not null and length(reason_value) not between 3 and 500) then
    raise exception using
      errcode = '22023', message = 'research_youtube_candidate_payload_invalid';
  end if;
  select ingestion.* into ingestion_row
  from content_factory.research_youtube_ingestion_runs ingestion
  join content_factory.memberships membership
    on membership.organization_id = ingestion.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where ingestion.id = ingestion_id_value
    and ingestion.organization_id = organization_id_value
    and ingestion.status = 'completed';
  if ingestion_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  perform content_factory_private.membership_role(
    ingestion_row.organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  select existing.* into decision_row
  from content_factory.research_youtube_candidate_decisions existing
  where existing.organization_id = ingestion_row.organization_id
    and existing.idempotency_key = idempotency_key_value;
  if decision_row.id is not null then
    if decision_row.retention_expires_at <= clock_timestamp() then
      raise exception using
        errcode = '55000', message = 'research_youtube_candidate_stale';
    end if;
    if decision_row.ingestion_id <> ingestion_row.id
       or decision_row.observation_id <> observation_id_value
       or decision_row.observation_hash <> observation_hash_value
       or decision_row.decision <> decision_value
       or decision_row.reason is distinct from reason_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-youtube-live-ingestion-v1',
      'decision', jsonb_build_object(
        'decision_id', decision_row.id,
        'ingestion_id', decision_row.ingestion_id,
        'observation_id', decision_row.observation_id,
        'observation_hash', decision_row.observation_hash,
        'decision', decision_row.decision,
        'reason', decision_row.reason,
        'decided_at', decision_row.decided_at,
        'retention_expires_at', decision_row.retention_expires_at,
        'generation_consumption', 'forbidden'
      )
    );
  end if;
  select observation.* into observation_row
  from content_factory.research_youtube_video_observations observation
  where observation.organization_id = ingestion_row.organization_id
    and observation.ingestion_id = ingestion_row.id
    and observation.id = observation_id_value
    and observation.observation_hash = observation_hash_value
    and observation.retention_expires_at > clock_timestamp();
  if observation_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_youtube_candidate_stale';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(ingestion_row.organization_id::text),
    hashtext('research-youtube-candidate:' || observation_id_value::text)
  );
  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-candidate-decision-v1',
    'ingestion_id', ingestion_row.id,
    'observation_id', observation_id_value,
    'observation_hash', observation_hash_value,
    'decision', decision_value,
    'reason', reason_value,
    'idempotency_key', idempotency_key_value
  ));
  insert into content_factory.research_youtube_candidate_decisions (
    organization_id, ingestion_id, observation_id, observation_hash,
    decision, reason, decided_by, retention_expires_at,
    idempotency_key, decision_hash
  ) values (
    ingestion_row.organization_id, ingestion_row.id,
    observation_id_value, observation_hash_value, decision_value,
    reason_value, user_id, observation_row.retention_expires_at,
    idempotency_key_value, decision_hash_value
  ) returning * into decision_row;
  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-live-ingestion-v1',
    'decision', jsonb_build_object(
      'decision_id', decision_row.id,
      'ingestion_id', decision_row.ingestion_id,
      'observation_id', decision_row.observation_id,
      'observation_hash', decision_row.observation_hash,
      'decision', decision_row.decision,
      'reason', decision_row.reason,
      'decided_at', decision_row.decided_at,
      'retention_expires_at', decision_row.retention_expires_at,
      'generation_consumption', 'forbidden'
    )
  );
  perform content_factory_private.emit_event(
    ingestion_row.organization_id,
    user_id,
    'research_youtube_candidate_decided',
    'research_youtube_candidate',
    decision_row.id::text,
    jsonb_build_object(
      'decision', decision_value,
      'generation_consumption', 'forbidden'
    ),
    'research-youtube-candidate:' || idempotency_key_value
  );
  return result_value;
end;
$$;

create or replace function public.system_purge_expired_youtube_api_data(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  limit_value integer := 5000;
  cutoff_value timestamptz := clock_timestamp();
  observation_deleted_count_value integer := 0;
  candidate_deleted_count_value integer := 0;
  receipt_deleted_count_value integer := 0;
  attempt_deleted_count_value integer := 0;
  overdue_remaining_count_value integer := 0;
  receipt_hash_value text;
  receipt_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_purge_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'research_youtube_purge_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
    if limit_value not between 1 and 5000 then
      raise exception using
        errcode = '22023', message = 'research_youtube_purge_limit_invalid';
    end if;
  end if;
  perform set_config('content_factory.youtube_retention_purge', 'on', true);

  update content_factory.research_youtube_ingestion_runs ingestion
  set status = 'failed',
      claimed_at = coalesce(ingestion.claimed_at, cutoff_value),
      lease_expires_at = coalesce(
        ingestion.lease_expires_at, cutoff_value + interval '5 minutes'
      ),
      completed_at = cutoff_value,
      completion_hash = content_factory_private.json_hash(jsonb_build_object(
        'version', 'research-youtube-terminal-v1',
        'ingestion_id', ingestion.id,
        'status', 'failed',
        'error_code', 'ingestion_lease_expired',
        'error_message',
          'The ingestion lease expired; no provider retry was attempted.',
        'lease_expires_at', coalesce(
          ingestion.lease_expires_at, cutoff_value + interval '5 minutes'
        ),
        'completed_at', cutoff_value
      )),
      error_code = 'ingestion_lease_expired',
      error_message =
        'The ingestion lease expired; no provider retry was attempted.'
  where (ingestion.status = 'processing'
      and ingestion.lease_expires_at <= cutoff_value)
     or (ingestion.status = 'queued'
      and ingestion.requested_at <= cutoff_value - interval '15 minutes');

  with due as (
    select decision_entry.id
    from content_factory.research_youtube_candidate_decisions decision_entry
    where decision_entry.retention_expires_at <= cutoff_value
    order by decision_entry.retention_expires_at, decision_entry.id
    limit limit_value
    for update skip locked
  ), deleted as (
    delete from content_factory.research_youtube_candidate_decisions decision_entry
    using due
    where decision_entry.id = due.id
    returning decision_entry.id
  )
  select count(*)::integer into candidate_deleted_count_value from deleted;

  with due as (
    select observation.id
    from content_factory.research_youtube_video_observations observation
    where observation.retention_expires_at <= cutoff_value
      and not exists (
        select 1
        from content_factory.research_youtube_candidate_decisions decision_entry
        where decision_entry.organization_id = observation.organization_id
          and decision_entry.observation_id = observation.id
      )
    order by observation.retention_expires_at, observation.id
    limit limit_value
    for update skip locked
  ), deleted as (
    delete from content_factory.research_youtube_video_observations observation
    using due
    where observation.id = due.id
    returning observation.id
  )
  select count(*)::integer into observation_deleted_count_value from deleted;

  with due as (
    select receipt.id
    from content_factory.research_youtube_transport_receipts receipt
    where receipt.retention_expires_at <= cutoff_value
    order by receipt.retention_expires_at, receipt.id
    limit limit_value
    for update skip locked
  ), deleted as (
    delete from content_factory.research_youtube_transport_receipts receipt
    using due
    where receipt.id = due.id
    returning receipt.id
  )
  select count(*)::integer into receipt_deleted_count_value from deleted;

  with due as (
    select transport.id
    from content_factory.research_youtube_transport_attempts transport
    where transport.started_at + interval '29 days' <= cutoff_value
      and not exists (
        select 1
        from content_factory.research_youtube_transport_receipts receipt
        where receipt.organization_id = transport.organization_id
          and receipt.transport_id = transport.id
      )
    order by transport.started_at, transport.id
    limit limit_value
    for update skip locked
  ), deleted as (
    delete from content_factory.research_youtube_transport_attempts transport
    using due
    where transport.id = due.id
    returning transport.id
  )
  select count(*)::integer into attempt_deleted_count_value from deleted;

  select
    (select count(*)
     from content_factory.research_youtube_candidate_decisions decision_entry
     where decision_entry.retention_expires_at <= cutoff_value)
    + (select count(*)
       from content_factory.research_youtube_video_observations observation
       where observation.retention_expires_at <= cutoff_value)
    + (select count(*)
       from content_factory.research_youtube_transport_receipts receipt
       where receipt.retention_expires_at <= cutoff_value)
    + (select count(*)
       from content_factory.research_youtube_transport_attempts transport
       where transport.started_at + interval '29 days' <= cutoff_value)
  into overdue_remaining_count_value;
  receipt_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-retention-receipt-v1',
    'cutoff_at', cutoff_value,
    'observation_deleted_count', observation_deleted_count_value,
    'candidate_decision_deleted_count', candidate_deleted_count_value,
    'transport_receipt_deleted_count', receipt_deleted_count_value,
    'transport_attempt_deleted_count', attempt_deleted_count_value,
    'overdue_remaining_count', overdue_remaining_count_value,
    'successful', true
  ));
  insert into content_factory.research_youtube_retention_receipts (
    cutoff_at, observation_deleted_count,
    candidate_decision_deleted_count, transport_receipt_deleted_count,
    transport_attempt_deleted_count, overdue_remaining_count,
    successful, receipt_hash
  ) values (
    cutoff_value, observation_deleted_count_value,
    candidate_deleted_count_value, receipt_deleted_count_value,
    attempt_deleted_count_value, overdue_remaining_count_value,
    true, receipt_hash_value
  ) returning id into receipt_id_value;
  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-retention-v1',
    'observation_deleted_count', observation_deleted_count_value,
    'candidate_decision_deleted_count', candidate_deleted_count_value,
    'transport_receipt_deleted_count', receipt_deleted_count_value,
    'transport_attempt_deleted_count', attempt_deleted_count_value,
    'overdue_remaining_count', overdue_remaining_count_value,
    'cutoff_at', cutoff_value,
    'receipt_id', receipt_id_value
  );
end;
$$;

do $install_youtube_retention_schedule$
declare
  existing_job record;
begin
  if exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) then
    for existing_job in execute $query$
      select jobid
      from cron.job
      where jobname = 'contentengine-youtube-retention-v1'
      order by jobid
    $query$
    loop
      execute 'select cron.unschedule($1)' using existing_job.jobid;
    end loop;
    execute $query$
      select cron.schedule($1, $2, $3)
    $query$
    using
      'contentengine-youtube-retention-v1',
      '17 * * * *',
      'select public.system_purge_expired_youtube_api_data(''{"limit":5000}''::jsonb);';
  end if;
exception
  when undefined_table or invalid_schema_name or insufficient_privilege then
    null;
end;
$install_youtube_retention_schedule$;

revoke all on function
  content_factory_private.reject_research_youtube_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_global_state()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_global_gate(text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_retention_ready()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_refresh_gate(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_quota_window(timestamptz)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.expire_research_youtube_ingestion(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.claim_research_youtube_ingestion(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.request_research_youtube_ingestion(jsonb, text)
  from public, anon, authenticated, service_role;

revoke all on function public.creator_request_research_youtube_canary(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_request_research_youtube_refresh(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_decide_research_youtube_rollout(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_research_youtube_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_research_youtube_overview(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_decide_research_youtube_candidate(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_claim_research_youtube_ingestion(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_request_research_youtube_canary(jsonb)
  to authenticated;
grant execute on function public.creator_request_research_youtube_refresh(jsonb)
  to authenticated;
grant execute on function public.creator_decide_research_youtube_rollout(jsonb)
  to authenticated;
grant execute on function public.creator_research_youtube_status(jsonb)
  to authenticated;
grant execute on function public.creator_research_youtube_overview(jsonb)
  to authenticated;
grant execute on function public.creator_decide_research_youtube_candidate(jsonb)
  to authenticated;
grant execute on function public.creator_claim_research_youtube_ingestion(jsonb)
  to authenticated;

revoke all on function public.system_decide_research_youtube_global_rollout(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_claim_research_youtube_ingestion(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_begin_research_youtube_transport(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_record_research_youtube_transport(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_complete_research_youtube_ingestion(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_purge_expired_youtube_api_data(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_claim_research_youtube_ingestion(jsonb)
  to service_role;
grant execute on function public.system_decide_research_youtube_global_rollout(jsonb)
  to service_role;
grant execute on function public.system_begin_research_youtube_transport(jsonb)
  to service_role;
grant execute on function public.system_record_research_youtube_transport(jsonb)
  to service_role;
grant execute on function public.system_complete_research_youtube_ingestion(jsonb)
  to service_role;
grant execute on function public.system_purge_expired_youtube_api_data(jsonb)
  to service_role;

select pg_notify('pgrst', 'reload schema');

commit;
