begin;

-- Native scheduler support is optional in local PostgreSQL-compatible test
-- engines, but present in the managed Supabase project.  Never embed the
-- project URL or worker secret in a migration: the dispatcher reads both from
-- Vault at execution time and fails closed while either value is absent.
do $bootstrap_extensions$
begin
  if exists (
    select 1 from pg_catalog.pg_available_extensions where name = 'pg_net'
  ) then
    begin
      execute 'create extension if not exists pg_net with schema extensions';
    exception
      when insufficient_privilege or feature_not_supported or undefined_file then
        null;
    end;
  end if;
  if exists (
    select 1 from pg_catalog.pg_available_extensions where name = 'pg_cron'
  ) then
    begin
      execute 'create extension if not exists pg_cron';
    exception
      when insufficient_privilege or feature_not_supported or undefined_file then
        null;
    end;
  end if;
end;
$bootstrap_extensions$;

create table if not exists content_factory.background_worker_runs (
    id uuid primary key default extensions.gen_random_uuid(),
    lease_token uuid not null default extensions.gen_random_uuid(),
    trigger_source text not null default 'edge'
      check (trigger_source in ('edge', 'schedule', 'manual', 'smoke')),
    status text not null default 'running'
      check (status in ('running', 'completed', 'failed', 'expired')),
    started_at timestamptz not null default now(),
    heartbeat_at timestamptz not null default now(),
    lease_expires_at timestamptz not null,
    finished_at timestamptz,
    summary jsonb not null default '{}'::jsonb check (
      jsonb_typeof(summary) = 'object'
      and length(summary::text) <= 32768
    ),
    error_code text check (
      error_code is null or error_code ~ '^[a-z][a-z0-9_]{2,99}$'
    ),
    unique (lease_token),
    check (heartbeat_at >= started_at),
    check (lease_expires_at > started_at),
    check (finished_at is null or finished_at >= started_at),
    check (
      (status = 'running' and finished_at is null and error_code is null)
      or (status = 'completed' and finished_at is not null and error_code is null)
      or (status in ('failed', 'expired')
        and finished_at is not null and error_code is not null)
    )
);

create unique index if not exists background_worker_one_running_uq
  on content_factory.background_worker_runs ((status))
  where status = 'running';
create index if not exists background_worker_runs_recent_idx
  on content_factory.background_worker_runs (started_at desc, id desc);
create index if not exists background_worker_runs_heartbeat_idx
  on content_factory.background_worker_runs (heartbeat_at desc, id desc);

alter table content_factory.background_worker_runs enable row level security;
revoke all on content_factory.background_worker_runs
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.guard_background_worker_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    if old.status in ('completed', 'failed', 'expired')
       and old.finished_at < now() - interval '90 days' then
      return old;
    end if;
    raise exception using
      errcode = '55000',
      message = 'background_worker_run_deletion_forbidden';
  end if;
  if new.id is distinct from old.id
     or new.lease_token is distinct from old.lease_token
     or new.trigger_source is distinct from old.trigger_source
     or new.started_at is distinct from old.started_at then
    raise exception using
      errcode = '55000',
      message = 'background_worker_run_identity_immutable';
  end if;
  if old.status <> 'running' then
    raise exception using
      errcode = '55000',
      message = 'background_worker_run_terminal_immutable';
  end if;
  if new.status not in ('running', 'completed', 'failed', 'expired')
     or new.heartbeat_at < old.heartbeat_at then
    raise exception using
      errcode = '55000',
      message = 'background_worker_run_transition_invalid';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_background_worker_run
  on content_factory.background_worker_runs;
create trigger guard_background_worker_run
before update or delete on content_factory.background_worker_runs
for each row execute function
  content_factory_private.guard_background_worker_run();

alter table content_factory.generation_jobs
  add column if not exists provider_poll_attempt_count integer not null default 0,
  add column if not exists provider_poll_failure_count integer not null default 0,
  add column if not exists provider_last_polled_at timestamptz,
  add column if not exists provider_last_poll_succeeded_at timestamptz,
  add column if not exists provider_next_poll_at timestamptz,
  add column if not exists provider_last_poll_code text,
  add column if not exists provider_stalled_at timestamptz;

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_provider_poll_attempt_count_check,
  drop constraint if exists generation_jobs_provider_poll_failure_count_check,
  drop constraint if exists generation_jobs_provider_last_poll_code_check;
alter table content_factory.generation_jobs
  add constraint generation_jobs_provider_poll_attempt_count_check
    check (provider_poll_attempt_count between 0 and 1000000),
  add constraint generation_jobs_provider_poll_failure_count_check
    check (
      provider_poll_failure_count between 0 and provider_poll_attempt_count
    ),
  add constraint generation_jobs_provider_last_poll_code_check
    check (
      provider_last_poll_code is null
      or provider_last_poll_code ~ '^[a-z][a-z0-9_]{2,99}$'
    );

update content_factory.generation_jobs job
set provider_next_poll_at = coalesce(job.provider_next_poll_at, job.updated_at, now())
where job.mode = 'real'
  and job.provider = 'runway'
  and job.status in ('submitted', 'processing')
  and job.provider_next_poll_at is null;

create index if not exists generation_jobs_provider_poll_due_idx
  on content_factory.generation_jobs
  (provider_next_poll_at, updated_at, id)
  where mode = 'real'
    and provider = 'runway'
    and status in ('submitted', 'processing');
create index if not exists generation_jobs_provider_stalled_idx
  on content_factory.generation_jobs
  (provider_stalled_at, organization_id, id)
  where provider_stalled_at is not null;

create or replace function
  content_factory_private.normalize_generation_poll_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.mode = 'real'
     and new.provider = 'runway'
     and new.status in ('submitted', 'processing') then
    new.provider_next_poll_at := coalesce(new.provider_next_poll_at, now());
  else
    new.provider_next_poll_at := null;
  end if;
  return new;
end;
$$;

drop trigger if exists normalize_generation_poll_state
  on content_factory.generation_jobs;
create trigger normalize_generation_poll_state
before insert or update of mode, provider, status
on content_factory.generation_jobs
for each row execute function
  content_factory_private.normalize_generation_poll_state();

create or replace function
  content_factory_private.background_scheduler_status()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  cron_enabled boolean := false;
  schedule_installed boolean := false;
  vault_url_configured boolean := false;
  vault_secret_configured boolean := false;
begin
  select exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) and exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_net'
  ) into cron_enabled;

  if cron_enabled then
    begin
      execute $query$
        select count(*) = 1
        from cron.job job
        where job.jobname = 'contentengine-background-worker-v1'
          and job.active
          and job.schedule = '*/2 * * * *'
          and position(
            'contentengine_background_worker_url' in job.command
          ) > 0
          and position(
            'contentengine_background_worker_secret' in job.command
          ) > 0
          and not exists (
            select 1
            from vault.decrypted_secrets secret
            where secret.name in (
              'contentengine_background_worker_url',
              'contentengine_background_worker_secret'
            )
              and length(coalesce(secret.decrypted_secret, '')) > 0
              and position(secret.decrypted_secret in job.command) > 0
          )
      $query$ into schedule_installed;
    exception
      when invalid_schema_name or undefined_table or undefined_column then
        schedule_installed := false;
    end;
  end if;

  begin
    execute $query$
      select
        count(*) filter (
          where name = 'contentengine_background_worker_url'
            and length(coalesce(decrypted_secret, '')) between 40 and 500
        ) = 1,
        count(*) filter (
          where name = 'contentengine_background_worker_secret'
            and length(coalesce(decrypted_secret, '')) between 32 and 512
        ) = 1
      from vault.decrypted_secrets
      where name in (
        'contentengine_background_worker_url',
        'contentengine_background_worker_secret'
      )
    $query$ into vault_url_configured, vault_secret_configured;
  exception
    when invalid_schema_name or undefined_table then
      vault_url_configured := false;
      vault_secret_configured := false;
  end;

  return jsonb_build_object(
    'extensions_ready', cron_enabled,
    'schedule_installed', schedule_installed,
    'vault_url_configured', vault_url_configured,
    'vault_secret_configured', vault_secret_configured,
    'ready', cron_enabled and schedule_installed
      and vault_url_configured and vault_secret_configured
  );
end;
$$;

create or replace function
  content_factory_private.dispatch_background_worker()
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  worker_url text;
  worker_secret text;
  request_id bigint;
begin
  begin
    execute $query$
      select
        max(decrypted_secret) filter (
          where name = 'contentengine_background_worker_url'
        ),
        max(decrypted_secret) filter (
          where name = 'contentengine_background_worker_secret'
        )
      from vault.decrypted_secrets
      where name in (
        'contentengine_background_worker_url',
        'contentengine_background_worker_secret'
      )
    $query$ into worker_url, worker_secret;
  exception
    when invalid_schema_name or undefined_table then
      return null;
  end;

  worker_url := btrim(coalesce(worker_url, ''));
  worker_secret := coalesce(worker_secret, '');
  if worker_url !~
       '^https://[a-z0-9]{20}\.supabase\.co/functions/v1/creator-background-worker$'
     or length(worker_secret) not between 32 and 512
     or worker_secret <> btrim(worker_secret)
     or worker_secret ~ '[[:cntrl:]]' then
    return null;
  end if;

  begin
    execute $query$
      select net.http_post(
        url := $1,
        headers := $2,
        body := $3,
        timeout_milliseconds := 150000
      )
    $query$
    into request_id
    using
      worker_url,
      jsonb_build_object(
        'content-type', 'application/json',
        'x-contentengine-internal-worker', '1',
        'x-contentengine-worker-secret', worker_secret
      ),
      jsonb_build_object(
        'generation_limit', 4,
        'research_limit', 1,
        'review_limit', 1
      );
  exception
    when invalid_schema_name or undefined_function then
      return null;
  end;
  return request_id;
end;
$$;

revoke all on function
  content_factory_private.background_scheduler_status()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.dispatch_background_worker()
  from public, anon, authenticated, service_role;

do $install_native_schedule$
declare
  existing_job record;
begin
  if exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) and exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_net'
  ) then
    for existing_job in execute $query$
      select jobid
      from cron.job
      where jobname = 'contentengine-background-worker-v1'
      order by jobid
    $query$
    loop
      execute 'select cron.unschedule($1)' using existing_job.jobid;
    end loop;
    execute $query$
      select cron.schedule($1, $2, $3)
    $query$
    using
      'contentengine-background-worker-v1',
      '*/2 * * * *',
      'select content_factory_private.dispatch_background_worker();';
  end if;
end;
$install_native_schedule$;

create or replace function public.system_begin_background_worker(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  lease_seconds_value integer := 210;
  trigger_source_value text := 'edge';
  active_row content_factory.background_worker_runs%rowtype;
  run_row content_factory.background_worker_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 2048
     or p_payload - array[
       'trigger_source', 'lease_seconds'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_worker_begin_payload_invalid';
  end if;
  trigger_source_value := lower(btrim(coalesce(
    p_payload ->> 'trigger_source', 'edge'
  )));
  if trigger_source_value not in ('edge', 'schedule', 'manual', 'smoke') then
    raise exception using
      errcode = '22023',
      message = 'background_worker_trigger_source_invalid';
  end if;
  if p_payload ? 'lease_seconds' then
    if jsonb_typeof(p_payload -> 'lease_seconds') <> 'number'
       or coalesce(p_payload ->> 'lease_seconds', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'background_worker_lease_seconds_invalid';
    end if;
    lease_seconds_value := (p_payload ->> 'lease_seconds')::integer;
  end if;
  if lease_seconds_value not between 60 and 420 then
    raise exception using
      errcode = '22023',
      message = 'background_worker_lease_seconds_invalid';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(731947, 812205);

  update content_factory.background_worker_runs run
  set status = 'expired',
      finished_at = now(),
      error_code = 'worker_lease_expired',
      summary = run.summary || jsonb_build_object(
        'watchdog', 'lease_expired_before_next_begin'
      )
  where run.status = 'running'
    and run.lease_expires_at <= now();

  delete from content_factory.background_worker_runs run
  where run.status in ('completed', 'failed', 'expired')
    and run.finished_at < now() - interval '90 days';

  select run.* into active_row
  from content_factory.background_worker_runs run
  where run.status = 'running'
    and run.lease_expires_at > now()
  order by run.started_at, run.id
  limit 1
  for update;

  if active_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'acquired', false,
      'active_run', jsonb_build_object(
        'id', active_row.id,
        'started_at', active_row.started_at,
        'heartbeat_at', active_row.heartbeat_at,
        'lease_expires_at', active_row.lease_expires_at
      )
    );
  end if;

  insert into content_factory.background_worker_runs (
    trigger_source, lease_expires_at
  ) values (
    trigger_source_value,
    now() + make_interval(secs => lease_seconds_value)
  ) returning * into run_row;

  return jsonb_build_object(
    'ok', true,
    'acquired', true,
    'run', jsonb_build_object(
      'id', run_row.id,
      'lease_token', run_row.lease_token,
      'started_at', run_row.started_at,
      'heartbeat_at', run_row.heartbeat_at,
      'lease_expires_at', run_row.lease_expires_at
    )
  );
end;
$$;

create or replace function public.system_heartbeat_background_worker(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  lease_token_value uuid;
  lease_seconds_value integer := 210;
  run_row content_factory.background_worker_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 2048
     or p_payload - array[
       'run_id', 'lease_token', 'lease_seconds'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_worker_heartbeat_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  if p_payload ? 'lease_seconds' then
    if jsonb_typeof(p_payload -> 'lease_seconds') <> 'number'
       or coalesce(p_payload ->> 'lease_seconds', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'background_worker_lease_seconds_invalid';
    end if;
    lease_seconds_value := (p_payload ->> 'lease_seconds')::integer;
  end if;
  if lease_seconds_value not between 60 and 420 then
    raise exception using
      errcode = '22023',
      message = 'background_worker_lease_seconds_invalid';
  end if;

  select run.* into run_row
  from content_factory.background_worker_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'background_worker_run_not_found';
  end if;
  if run_row.lease_token is distinct from lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'background_worker_lease_mismatch';
  end if;
  if run_row.status <> 'running' then
    return jsonb_build_object(
      'ok', true,
      'idempotent', true,
      'run_id', run_row.id,
      'status', run_row.status
    );
  end if;
  if run_row.lease_expires_at <= now() then
    update content_factory.background_worker_runs run
    set status = 'expired',
        finished_at = now(),
        error_code = 'worker_lease_expired'
    where run.id = run_row.id
    returning * into run_row;
    return jsonb_build_object(
      'ok', false,
      'code', 'background_worker_lease_expired',
      'run_id', run_row.id,
      'status', run_row.status
    );
  end if;

  update content_factory.background_worker_runs run
  set heartbeat_at = now(),
      lease_expires_at = now() + make_interval(secs => lease_seconds_value)
  where run.id = run_row.id
  returning * into run_row;

  return jsonb_build_object(
    'ok', true,
    'idempotent', false,
    'run', jsonb_build_object(
      'id', run_row.id,
      'heartbeat_at', run_row.heartbeat_at,
      'lease_expires_at', run_row.lease_expires_at
    )
  );
end;
$$;

create or replace function public.system_finish_background_worker(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  lease_token_value uuid;
  status_value text;
  error_code_value text;
  summary_value jsonb := '{}'::jsonb;
  run_row content_factory.background_worker_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 35000
     or p_payload - array[
       'run_id', 'lease_token', 'status', 'summary', 'error_code'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_worker_finish_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  status_value := lower(btrim(coalesce(p_payload ->> 'status', '')));
  error_code_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'error_code', ''
  ))), '');
  if status_value not in ('completed', 'failed')
     or (status_value = 'completed' and error_code_value is not null)
     or (status_value = 'failed' and (
       error_code_value is null
       or error_code_value !~ '^[a-z][a-z0-9_]{2,99}$'
     )) then
    raise exception using
      errcode = '22023',
      message = 'background_worker_finish_state_invalid';
  end if;
  if p_payload ? 'summary' then
    if jsonb_typeof(p_payload -> 'summary') <> 'object'
       or length((p_payload -> 'summary')::text) > 32768 then
      raise exception using
        errcode = '22023',
        message = 'background_worker_finish_summary_invalid';
    end if;
    summary_value := p_payload -> 'summary';
  end if;

  select run.* into run_row
  from content_factory.background_worker_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'background_worker_run_not_found';
  end if;
  if run_row.lease_token is distinct from lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'background_worker_lease_mismatch';
  end if;
  if run_row.status <> 'running' then
    if run_row.status = status_value
       and run_row.summary = summary_value
       and run_row.error_code is not distinct from error_code_value then
      return jsonb_build_object(
        'ok', true,
        'idempotent', true,
        'run_id', run_row.id,
        'status', run_row.status
      );
    end if;
    raise exception using
      errcode = '55000',
      message = 'background_worker_run_terminal_conflict';
  end if;
  if run_row.lease_expires_at <= now() then
    update content_factory.background_worker_runs run
    set status = 'expired',
        finished_at = now(),
        error_code = 'worker_lease_expired',
        summary = summary_value
    where run.id = run_row.id
    returning * into run_row;
    return jsonb_build_object(
      'ok', false,
      'code', 'background_worker_lease_expired',
      'run_id', run_row.id,
      'status', run_row.status
    );
  end if;

  update content_factory.background_worker_runs run
  set status = status_value,
      heartbeat_at = now(),
      finished_at = now(),
      summary = summary_value,
      error_code = error_code_value
  where run.id = run_row.id
  returning * into run_row;

  return jsonb_build_object(
    'ok', true,
    'idempotent', false,
    'run_id', run_row.id,
    'status', run_row.status,
    'finished_at', run_row.finished_at
  );
end;
$$;

create or replace function public.system_record_generation_poll_outcome(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  lease_token_value uuid;
  job_id_value uuid;
  outcome_value text;
  error_code_value text;
  run_row content_factory.background_worker_runs%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  attempt_count_value integer;
  failure_count_value integer;
  retry_seconds integer;
  should_stall boolean := false;
  newly_stalled boolean := false;
  next_poll_value timestamptz;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 4096
     or p_payload - array[
       'run_id', 'lease_token', 'job_id', 'outcome', 'error_code'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_poll_outcome_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  outcome_value := lower(btrim(coalesce(p_payload ->> 'outcome', '')));
  error_code_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'error_code', ''
  ))), '');
  if outcome_value not in ('success_pending', 'success_terminal', 'failed')
     or (outcome_value <> 'failed' and error_code_value is not null)
     or (outcome_value = 'failed' and (
       error_code_value is null
       or error_code_value !~ '^[a-z][a-z0-9_]{2,99}$'
     )) then
    raise exception using
      errcode = '22023',
      message = 'generation_poll_outcome_invalid';
  end if;

  select run.* into run_row
  from content_factory.background_worker_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null
     or run_row.status <> 'running'
     or run_row.lease_expires_at <= now()
     or run_row.lease_token is distinct from lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'background_worker_active_lease_required';
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
  for update;
  if job_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'generation_poll_job_not_found';
  end if;
  if job_row.mode <> 'real' or job_row.provider <> 'runway' then
    raise exception using
      errcode = '55000',
      message = 'generation_poll_job_not_runway';
  end if;
  if outcome_value = 'success_terminal'
     and job_row.status not in ('succeeded', 'failed', 'cancelled') then
    raise exception using
      errcode = '55000',
      message = 'generation_poll_terminal_state_required';
  end if;
  if outcome_value <> 'success_terminal'
     and job_row.status not in ('submitted', 'processing') then
    raise exception using
      errcode = '55000',
      message = 'generation_poll_active_state_required';
  end if;

  attempt_count_value := job_row.provider_poll_attempt_count + 1;
  if outcome_value = 'failed' then
    failure_count_value := job_row.provider_poll_failure_count + 1;
    retry_seconds := least(
      900,
      (30 * power(2, least(failure_count_value - 1, 5)))::integer
    );
    should_stall := failure_count_value >= 5;
    next_poll_value := now() + make_interval(
      secs => case when should_stall then 900 else retry_seconds end
    );
  elsif outcome_value = 'success_pending' then
    failure_count_value := 0;
    should_stall := now() - job_row.created_at >= interval '2 hours';
    next_poll_value := now() + make_interval(
      secs => case when should_stall then 900 else 60 end
    );
  else
    failure_count_value := 0;
    next_poll_value := null;
  end if;
  newly_stalled := should_stall and job_row.provider_stalled_at is null;

  update content_factory.generation_jobs job
  set provider_poll_attempt_count = attempt_count_value,
      provider_poll_failure_count = failure_count_value,
      provider_last_polled_at = now(),
      provider_last_poll_succeeded_at = case
        when outcome_value in ('success_pending', 'success_terminal')
          then now()
        else job.provider_last_poll_succeeded_at
      end,
      provider_next_poll_at = next_poll_value,
      provider_last_poll_code = error_code_value,
      provider_stalled_at = case
        when should_stall then coalesce(job.provider_stalled_at, now())
        when outcome_value in ('success_pending', 'success_terminal') then null
        else job.provider_stalled_at
      end
  where job.id = job_row.id
  returning * into job_row;

  update content_factory.background_worker_runs run
  set heartbeat_at = now(),
      lease_expires_at = greatest(
        run.lease_expires_at,
        now() + interval '210 seconds'
      )
  where run.id = run_row.id;

  if newly_stalled then
    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      job_row.organization_id,
      job_row.requested_by,
      'background_generation_stalled',
      'warning',
      'Runway-задача требует внимания',
      'Фоновый опрос не смог подтвердить продвижение задачи. Новый платный запуск не выполнен; откройте генерацию и проверьте текущий Runway task.',
      '#/workspace/generation',
      'generation_job',
      job_row.id::text,
      jsonb_build_object(
        'source', 'native_worker_watchdog',
        'status', job_row.status,
        'poll_failure_count', failure_count_value,
        'last_poll_code', error_code_value
      ),
      content_factory_private.json_hash(jsonb_build_object(
        'recipient_id', job_row.requested_by,
        'kind', 'background_generation_stalled',
        'entity_id', job_row.id,
        'poll_failure_count', failure_count_value,
        'last_poll_code', error_code_value
      )),
      left(
        'background-worker:generation-stalled:' || job_row.id::text,
        180
      )
    )
    on conflict (organization_id, recipient_id, dedupe_key) do nothing;
  end if;

  return jsonb_build_object(
    'ok', true,
    'job_id', job_row.id,
    'outcome', outcome_value,
    'poll_attempt_count', job_row.provider_poll_attempt_count,
    'poll_failure_count', job_row.provider_poll_failure_count,
    'next_poll_at', job_row.provider_next_poll_at,
    'stalled_at', job_row.provider_stalled_at,
    'newly_stalled', newly_stalled
  );
end;
$$;

create or replace function public.system_background_worker_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  active_row content_factory.background_worker_runs%rowtype;
  latest_row content_factory.background_worker_runs%rowtype;
  due_count integer;
  active_generation_count integer;
  stalled_count integer;
  scheduler_value jsonb;
  heartbeat_value timestamptz;
  heartbeat_fresh_value boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_worker_health_payload_invalid';
  end if;

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
  where job.mode = 'real'
    and job.provider = 'runway'
    and job.status in ('submitted', 'processing');
  scheduler_value := content_factory_private.background_scheduler_status();
  heartbeat_value := coalesce(active_row.heartbeat_at, latest_row.heartbeat_at);
  heartbeat_fresh_value := heartbeat_value is not null
    and heartbeat_value >= now() - interval '10 minutes';

  return jsonb_build_object(
    'ok', true,
    'scheduler', scheduler_value,
    'worker', jsonb_build_object(
      'running', active_row.id is not null,
      'ready', heartbeat_fresh_value and (
        active_row.id is not null or latest_row.status = 'completed'
      ),
      'heartbeat_fresh', heartbeat_fresh_value,
      'active_run_id', active_row.id,
      'active_started_at', active_row.started_at,
      'heartbeat_at', active_row.heartbeat_at,
      'lease_expires_at', active_row.lease_expires_at,
      'latest_run_id', latest_row.id,
      'latest_status', latest_row.status,
      'latest_started_at', latest_row.started_at,
      'latest_finished_at', latest_row.finished_at,
      'latest_error_code', latest_row.error_code
    ),
    'generation', jsonb_build_object(
      'active', active_generation_count,
      'due', due_count,
      'stalled', stalled_count
    )
  );
end;
$$;

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
    )
  );
end;
$$;

revoke all on function public.system_begin_background_worker(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_heartbeat_background_worker(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_finish_background_worker(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_record_generation_poll_outcome(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_background_worker_health(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_operational_health(jsonb)
  from public, anon;

grant execute on function public.system_begin_background_worker(jsonb)
  to service_role;
grant execute on function public.system_heartbeat_background_worker(jsonb)
  to service_role;
grant execute on function public.system_finish_background_worker(jsonb)
  to service_role;
grant execute on function public.system_record_generation_poll_outcome(jsonb)
  to service_role;
grant execute on function public.system_background_worker_health(jsonb)
  to service_role;
grant execute on function public.creator_operational_health(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.guard_background_worker_run()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.normalize_generation_poll_state()
  from public, anon, authenticated;

commit;
