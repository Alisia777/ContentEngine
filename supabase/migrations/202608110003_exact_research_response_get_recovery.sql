begin;

-- A completed background Response can remain retrievable after the ordinary
-- eight-minute parser-revalidation window has closed. Recovery has no upper
-- age cutoff, but is deliberately split into
-- three append-only facts:
--   1. an authorized project member requests recovery of one exact-video run;
--   2. the worker reserves the sole provider GET before receiving the private
--      response id;
--   3. the worker records the resulting authoritative terminal run state.
-- No table stores a provider response body, prompt, credential or bearer token.
alter table content_factory.research_exact_youtube_research_bindings
  add constraint exact_youtube_research_binding_project_run_id_uq
  unique (organization_id, project_id, run_id, id);
alter table content_factory.research_provider_response_bindings
  add constraint research_provider_response_binding_run_id_uq
  unique (organization_id, run_id, id);

create table if not exists
  content_factory.research_provider_response_recovery_authorizations (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    run_id uuid not null,
    exact_binding_id uuid not null,
    provider_response_binding_id uuid not null,
    authorized_by uuid not null,
    idempotency_key text not null check (
      length(idempotency_key) between 8 and 180
    ),
    recovery_ack_snapshot boolean not null check (recovery_ack_snapshot),
    exact_binding_hash_snapshot text not null check (
      exact_binding_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    provider_response_hash_snapshot text not null check (
      provider_response_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    provider_response_accepted_at_snapshot timestamptz not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    authorization_hash text not null check (
      authorization_hash ~ '^[0-9a-f]{64}$'
    ),
    authorized_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, run_id),
    unique (organization_id, project_id, run_id, id),
    unique (organization_id, authorized_by, idempotency_key),
    unique (authorization_hash),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (
      organization_id, project_id, run_id, exact_binding_id
    )
      references content_factory.research_exact_youtube_research_bindings(
        organization_id, project_id, run_id, id
      ),
    foreign key (
      organization_id, run_id, provider_response_binding_id
    )
      references content_factory.research_provider_response_bindings(
        organization_id, run_id, id
      ),
    foreign key (organization_id, authorized_by)
      references content_factory.memberships(organization_id, profile_id)
  );

create table if not exists
  content_factory.research_provider_response_recovery_get_reservations (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    run_id uuid not null,
    authorization_id uuid not null,
    exact_binding_id uuid not null,
    provider_response_binding_id uuid not null,
    authorized_by_snapshot uuid not null,
    maximum_provider_gets integer not null default 1 check (
      maximum_provider_gets = 1
    ),
    provider_get_allowed boolean not null default true check (
      provider_get_allowed
    ),
    provider_post_allowed boolean not null default false check (
      not provider_post_allowed
    ),
    include_web_search_sources boolean not null default true check (
      include_web_search_sources
    ),
    authorization_hash_snapshot text not null check (
      authorization_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    exact_binding_hash_snapshot text not null check (
      exact_binding_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    provider_response_hash_snapshot text not null check (
      provider_response_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    reservation_hash text not null check (
      reservation_hash ~ '^[0-9a-f]{64}$'
    ),
    reserved_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, run_id),
    unique (organization_id, project_id, run_id, id),
    unique (organization_id, authorization_id),
    unique (organization_id, provider_response_binding_id),
    unique (reservation_hash),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (
      organization_id, project_id, run_id, authorization_id
    )
      references
        content_factory.research_provider_response_recovery_authorizations(
          organization_id, project_id, run_id, id
        ),
    foreign key (
      organization_id, project_id, run_id, exact_binding_id
    )
      references content_factory.research_exact_youtube_research_bindings(
        organization_id, project_id, run_id, id
      ),
    foreign key (
      organization_id, run_id, provider_response_binding_id
    )
      references content_factory.research_provider_response_bindings(
        organization_id, run_id, id
      ),
    foreign key (organization_id, authorized_by_snapshot)
      references content_factory.memberships(organization_id, profile_id)
  );

create table if not exists
  content_factory.research_provider_response_recovery_outcomes (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    run_id uuid not null,
    reservation_id uuid not null,
    authorization_id uuid not null,
    terminal_status text not null check (
      terminal_status in ('completed', 'failed')
    ),
    terminal_error_code text,
    completion_hash_snapshot text not null check (
      completion_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    outcome_hash text not null check (outcome_hash ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, reservation_id),
    unique (organization_id, run_id),
    unique (outcome_hash),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (
      organization_id, project_id, run_id, reservation_id
    )
      references
        content_factory.research_provider_response_recovery_get_reservations(
          organization_id, project_id, run_id, id
        ),
    foreign key (
      organization_id, project_id, run_id, authorization_id
    )
      references
        content_factory.research_provider_response_recovery_authorizations(
          organization_id, project_id, run_id, id
        ),
    check (
      (terminal_status = 'completed' and terminal_error_code is null)
      or
      (terminal_status = 'failed' and terminal_error_code is not null)
    )
  );

create index if not exists
  research_response_recovery_authorized_at_idx
  on content_factory.research_provider_response_recovery_authorizations (
    organization_id, project_id, authorized_at desc, id desc
  );
create index if not exists
  research_response_recovery_reserved_at_idx
  on content_factory.research_provider_response_recovery_get_reservations (
    organization_id, project_id, reserved_at desc, id desc
  );
create index if not exists
  research_response_recovery_recorded_at_idx
  on content_factory.research_provider_response_recovery_outcomes (
    organization_id, project_id, recorded_at desc, id desc
  );

alter table
  content_factory.research_provider_response_recovery_authorizations
  enable row level security;
alter table
  content_factory.research_provider_response_recovery_get_reservations
  enable row level security;
alter table
  content_factory.research_provider_response_recovery_outcomes
  enable row level security;

revoke all on table
  content_factory.research_provider_response_recovery_authorizations
  from public, anon, authenticated, service_role;
revoke all on table
  content_factory.research_provider_response_recovery_get_reservations
  from public, anon, authenticated, service_role;
revoke all on table
  content_factory.research_provider_response_recovery_outcomes
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.reject_research_response_recovery_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_append_only';
end;
$$;

revoke all on function
  content_factory_private.reject_research_response_recovery_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists research_response_recovery_authorization_append_only
  on content_factory.research_provider_response_recovery_authorizations;
create trigger research_response_recovery_authorization_append_only
before update or delete
  on content_factory.research_provider_response_recovery_authorizations
for each row execute function
  content_factory_private.reject_research_response_recovery_mutation();

drop trigger if exists research_response_recovery_reservation_append_only
  on content_factory.research_provider_response_recovery_get_reservations;
create trigger research_response_recovery_reservation_append_only
before update or delete
  on content_factory.research_provider_response_recovery_get_reservations
for each row execute function
  content_factory_private.reject_research_response_recovery_mutation();

drop trigger if exists research_response_recovery_outcome_append_only
  on content_factory.research_provider_response_recovery_outcomes;
create trigger research_response_recovery_outcome_append_only
before update or delete
  on content_factory.research_provider_response_recovery_outcomes
for each row execute function
  content_factory_private.reject_research_response_recovery_mutation();

-- Keep the ordinary <=8 minute response-revalidation behavior byte-for-byte
-- compatible while adding a second, narrower trigger invariant for recovery.
-- The recovery GUC alone is insufficient: the trigger also requires the
-- append-only reservation and its exact/provider lineage in the same
-- transaction. Project identity, added after the original run table, is made
-- explicitly immutable for both ordinary and recovery transitions.
create or replace function content_factory_private.guard_research_run_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
#variable_conflict use_variable
declare
  ordinary_response_revalidation boolean :=
    old.status = 'failed'
    and old.error_code = 'provider_response_invalid'
    and new.status = 'processing'
    and coalesce(
      current_setting(
        'content_factory.product_research_response_revalidation', true
      ) = 'on',
      false
    );
  exact_response_recovery boolean :=
    old.status = 'failed'
    and old.error_code = 'provider_response_invalid'
    and new.status = 'processing'
    and coalesce(
      current_setting(
        'content_factory.product_research_exact_response_recovery', true
      ) = 'on',
      false
    );
  response_revalidation boolean :=
    ordinary_response_revalidation or exact_response_recovery;
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000', message = 'research_run_deletion_forbidden';
  end if;
  if new.organization_id <> old.organization_id
     or new.project_id is distinct from old.project_id
     or new.product_id <> old.product_id
     or new.created_by <> old.created_by
     or new.input <> old.input
     or new.request_hash <> old.request_hash
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000', message = 'research_run_identity_immutable';
  end if;
  if exact_response_recovery and not exists (
    select 1
    from content_factory
      .research_provider_response_recovery_get_reservations reservation
    join content_factory
      .research_provider_response_recovery_authorizations recovery_auth
      on recovery_auth.organization_id = reservation.organization_id
     and recovery_auth.project_id = reservation.project_id
     and recovery_auth.run_id = reservation.run_id
     and recovery_auth.id = reservation.authorization_id
     and recovery_auth.authorization_hash =
       reservation.authorization_hash_snapshot
    join content_factory.research_exact_youtube_research_bindings exact_binding
      on exact_binding.organization_id = reservation.organization_id
     and exact_binding.project_id = reservation.project_id
     and exact_binding.run_id = reservation.run_id
     and exact_binding.id = reservation.exact_binding_id
     and exact_binding.binding_hash = reservation.exact_binding_hash_snapshot
    join content_factory.research_provider_response_bindings response
      on response.organization_id = reservation.organization_id
     and response.run_id = reservation.run_id
     and response.id = reservation.provider_response_binding_id
     and response.response_hash =
       reservation.provider_response_hash_snapshot
    where reservation.organization_id = old.organization_id
      and reservation.project_id = old.project_id
      and reservation.run_id = old.id
      and reservation.maximum_provider_gets = 1
      and reservation.provider_get_allowed
      and not reservation.provider_post_allowed
      and reservation.include_web_search_sources
      and exact_binding.product_id = old.product_id
      and exact_binding.media_matches_registered_source
      and exact_binding.paid_analysis_ack_snapshot
      and exact_binding.analysis_scope = 'sampled_frames_only'
      and not exact_binding.full_stream_access
      and not exact_binding.transcript_available
      and response.provider_key = 'openai_web_search'
      and response.adapter_version = 'openai-responses-web-search-v1'
      and coalesce(
        (
          select receipt.provider_status
          from content_factory.research_provider_response_receipts receipt
          where receipt.organization_id = response.organization_id
            and receipt.response_binding_id = response.id
          order by receipt.checked_at desc, receipt.id desc
          limit 1
        ),
        response.initial_status
      ) = 'completed'
  ) then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_transition_invalid';
  end if;
  if old.status in ('completed', 'failed', 'cancelled')
     and new is distinct from old
     and not response_revalidation then
    raise exception using
      errcode = '55000', message = 'research_run_terminal';
  end if;
  if new.status <> old.status and not (
    (old.status = 'queued' and new.status in ('processing', 'cancelled'))
    or (
      old.status = 'processing'
      and new.status in ('completed', 'failed', 'cancelled')
    )
    or response_revalidation
  ) then
    raise exception using
      errcode = '55000', message = 'research_status_transition_invalid';
  end if;
  if old.status = 'queued' and new.status = 'processing' then
    new.started_at := coalesce(new.started_at, now());
    new.lease_expires_at := coalesce(
      new.lease_expires_at, now() + interval '5 minutes'
    );
  elsif response_revalidation then
    if new.error_code is not null
       or new.error_message is not null
       or new.completion_hash is not null
       or new.finished_at is not null
       or new.started_at is distinct from old.started_at
       or new.summary <> '{}'::jsonb
       or new.lease_expires_at is null
       or new.lease_expires_at <= clock_timestamp()
       or new.lease_expires_at > clock_timestamp() + interval '2 minutes' then
      raise exception using
        errcode = '55000', message = 'research_response_revalidation_invalid';
    end if;
  end if;
  if new.status in ('completed', 'failed', 'cancelled')
     and new.status <> old.status then
    new.finished_at := coalesce(new.finished_at, now());
    new.lease_expires_at := null;
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create or replace function
  public.creator_authorize_product_research_response_recovery(
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
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  run_id_value uuid;
  idempotency_key_value text;
  request_hash_value text;
  authorization_hash_value text;
  latest_provider_status_value text;
  authorized_at_value timestamptz := clock_timestamp();
  run_row content_factory.product_research_runs%rowtype;
  exact_row
    content_factory.research_exact_youtube_research_bindings%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  attempt_row content_factory.research_run_provider_bindings%rowtype;
  authorization_row
    content_factory.research_provider_response_recovery_authorizations%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'project_id', 'run_id',
       'idempotency_key', 'recovery_ack'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'run_id', 'idempotency_key', 'recovery_ack'
     ]::text[]
     or p_payload -> 'recovery_ack' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_authorization_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, false, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  perform content_factory_private.require_project_entity(
    organization_id_value, project_id_value, 'research_run', run_id_value
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-research-response-get-recovery-request-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'run_id', run_id_value,
      'recovery_ack', true
    )
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-response-get-recovery:' || run_id_value::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext(
      'research-response-get-recovery-key:'
      || actor_id_value::text || ':' || idempotency_key_value
    )
  );

  select recovery_auth.* into authorization_row
  from content_factory.research_provider_response_recovery_authorizations
    recovery_auth
  where recovery_auth.organization_id = organization_id_value
    and recovery_auth.authorized_by = actor_id_value
    and recovery_auth.idempotency_key = idempotency_key_value;
  if authorization_row.id is not null then
    if authorization_row.request_hash <> request_hash_value then
      raise exception using
        errcode = '23505',
        message = 'research_response_recovery_authorization_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'code', 'research_response_recovery_already_authorized',
      'authorization_id', authorization_row.id,
      'run_id', authorization_row.run_id,
      'project_id', authorization_row.project_id,
      'get_reserved', exists (
        select 1
        from content_factory
          .research_provider_response_recovery_get_reservations reservation
        where reservation.organization_id = authorization_row.organization_id
          and reservation.authorization_id = authorization_row.id
      )
    );
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.project_id = project_id_value
    and run.id = run_id_value
  for share;
  if run_row.id is null
     or run_row.status <> 'failed'
     or run_row.error_code <> 'provider_response_invalid' then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_run_not_eligible';
  end if;

  select exact_binding.* into exact_row
  from content_factory.research_exact_youtube_research_bindings exact_binding
  where exact_binding.organization_id = run_row.organization_id
    and exact_binding.project_id = run_row.project_id
    and exact_binding.run_id = run_row.id
    and exact_binding.product_id = run_row.product_id
    and exact_binding.media_matches_registered_source
    and exact_binding.paid_analysis_ack_snapshot
    and exact_binding.analysis_scope = 'sampled_frames_only'
    and not exact_binding.full_stream_access
    and not exact_binding.transcript_available;
  if exact_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_exact_binding_required';
  end if;

  select response.* into response_row
  from content_factory.research_provider_response_bindings response
  join content_factory.research_run_provider_bindings attempt
    on attempt.organization_id = response.organization_id
   and attempt.run_id = response.run_id
   and attempt.id = response.attempt_id
   and attempt.provider_key = response.provider_key
   and attempt.adapter_version = response.adapter_version
  where response.organization_id = run_row.organization_id
    and response.run_id = run_row.id
    and response.provider_key = 'openai_web_search'
    and response.adapter_version = 'openai-responses-web-search-v1';
  if response_row.id is not null then
    select attempt.* into attempt_row
    from content_factory.research_run_provider_bindings attempt
    where attempt.organization_id = response_row.organization_id
      and attempt.run_id = response_row.run_id
      and attempt.id = response_row.attempt_id
      and attempt.provider_key = response_row.provider_key
      and attempt.adapter_version = response_row.adapter_version;
  end if;
  if response_row.id is not null then
    select receipt.provider_status into latest_provider_status_value
    from content_factory.research_provider_response_receipts receipt
    where receipt.organization_id = response_row.organization_id
      and receipt.response_binding_id = response_row.id
    order by receipt.checked_at desc, receipt.id desc
    limit 1;
  end if;
  if response_row.id is null
     or attempt_row.id is null
     or response_row.accepted_at >
       clock_timestamp() - interval '8 minutes'
     or coalesce(
       latest_provider_status_value, response_row.initial_status
     ) <> 'completed' then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_completed_response_required';
  end if;

  select recovery_auth.* into authorization_row
  from content_factory.research_provider_response_recovery_authorizations
    recovery_auth
  where recovery_auth.organization_id = organization_id_value
    and recovery_auth.run_id = run_id_value;
  if authorization_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'code', 'research_response_recovery_already_authorized',
      'authorization_id', authorization_row.id,
      'run_id', authorization_row.run_id,
      'project_id', authorization_row.project_id,
      'get_reserved', exists (
        select 1
        from content_factory
          .research_provider_response_recovery_get_reservations reservation
        where reservation.organization_id = authorization_row.organization_id
          and reservation.authorization_id = authorization_row.id
      )
    );
  end if;

  authorization_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-research-response-get-recovery-authorization-v1',
      'organization_id', run_row.organization_id,
      'project_id', run_row.project_id,
      'run_id', run_row.id,
      'exact_binding_id', exact_row.id,
      'exact_binding_hash', exact_row.binding_hash,
      'provider_response_binding_id', response_row.id,
      'provider_response_hash', response_row.response_hash,
      'provider_response_accepted_at', response_row.accepted_at,
      'authorized_by', actor_id_value,
      'idempotency_key', idempotency_key_value,
      'request_hash', request_hash_value,
      'recovery_ack', true
    )
  );
  insert into
    content_factory.research_provider_response_recovery_authorizations (
      organization_id, project_id, run_id, exact_binding_id,
      provider_response_binding_id, authorized_by, idempotency_key,
      recovery_ack_snapshot, exact_binding_hash_snapshot,
      provider_response_hash_snapshot,
      provider_response_accepted_at_snapshot, request_hash,
      authorization_hash, authorized_at
    ) values (
      run_row.organization_id, run_row.project_id, run_row.id, exact_row.id,
      response_row.id, actor_id_value, idempotency_key_value,
      true, exact_row.binding_hash, response_row.response_hash,
      response_row.accepted_at, request_hash_value,
      authorization_hash_value, authorized_at_value
    )
  returning * into authorization_row;

  return jsonb_build_object(
    'ok', true,
    'code', 'research_response_recovery_authorized',
    'authorization_id', authorization_row.id,
    'run_id', authorization_row.run_id,
    'project_id', authorization_row.project_id,
    'get_reserved', false
  );
end;
$$;

-- Completion remains owned by system_complete_product_research. This AFTER
-- trigger adds the recovery outcome in that same transaction, so a committed
-- terminal run cannot be separated from its audit receipt by a worker crash.
-- The service RPC below remains an idempotent reconciliation/read seam.
create or replace function
  content_factory_private.capture_research_response_recovery_outcome()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  reservation_row
    content_factory.research_provider_response_recovery_get_reservations%rowtype;
  outcome_row
    content_factory.research_provider_response_recovery_outcomes%rowtype;
  outcome_hash_value text;
begin
  if old.status <> 'processing'
     or new.status not in ('completed', 'failed')
     or new.completion_hash is null then
    return new;
  end if;
  select reservation.* into reservation_row
  from content_factory.research_provider_response_recovery_get_reservations
    reservation
  where reservation.organization_id = new.organization_id
    and reservation.project_id = new.project_id
    and reservation.run_id = new.id;
  if reservation_row.id is null then
    return new;
  end if;

  outcome_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-research-response-get-recovery-outcome-v1',
      'organization_id', reservation_row.organization_id,
      'project_id', reservation_row.project_id,
      'run_id', reservation_row.run_id,
      'authorization_id', reservation_row.authorization_id,
      'reservation_id', reservation_row.id,
      'terminal_status', new.status,
      'terminal_error_code', new.error_code,
      'completion_hash', new.completion_hash
    )
  );
  insert into content_factory.research_provider_response_recovery_outcomes (
    organization_id, project_id, run_id, reservation_id,
    authorization_id, terminal_status, terminal_error_code,
    completion_hash_snapshot, outcome_hash, recorded_at
  ) values (
    reservation_row.organization_id, reservation_row.project_id,
    reservation_row.run_id, reservation_row.id,
    reservation_row.authorization_id, new.status, new.error_code,
    new.completion_hash, outcome_hash_value, clock_timestamp()
  )
  on conflict (organization_id, reservation_id) do nothing
  returning * into outcome_row;
  if outcome_row.id is null then
    select outcome.* into outcome_row
    from content_factory.research_provider_response_recovery_outcomes outcome
    where outcome.organization_id = reservation_row.organization_id
      and outcome.reservation_id = reservation_row.id;
  end if;
  if outcome_row.id is null
     or outcome_row.project_id <> reservation_row.project_id
     or outcome_row.run_id <> reservation_row.run_id
     or outcome_row.authorization_id <> reservation_row.authorization_id
     or outcome_row.terminal_status <> new.status
     or outcome_row.terminal_error_code is distinct from new.error_code
     or outcome_row.completion_hash_snapshot <> new.completion_hash
     or outcome_row.outcome_hash <> outcome_hash_value then
    raise exception using
      errcode = '23505',
      message = 'research_response_recovery_outcome_conflict';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.capture_research_response_recovery_outcome()
  from public, anon, authenticated, service_role;

drop trigger if exists capture_research_response_recovery_outcome
  on content_factory.product_research_runs;
create trigger capture_research_response_recovery_outcome
after update on content_factory.product_research_runs
for each row execute function
  content_factory_private.capture_research_response_recovery_outcome();

create or replace function
  public.system_claim_product_research_response_recovery(
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
  authorization_id_value uuid;
  latest_provider_status_value text;
  reserved_at_value timestamptz := clock_timestamp();
  lease_expires_at_value timestamptz;
  previous_revalidation_setting text;
  reservation_hash_value text;
  changed_count_value integer := 0;
  authorization_row
    content_factory.research_provider_response_recovery_authorizations%rowtype;
  reservation_row
    content_factory.research_provider_response_recovery_get_reservations%rowtype;
  run_row content_factory.product_research_runs%rowtype;
  exact_row
    content_factory.research_exact_youtube_research_bindings%rowtype;
  response_row content_factory.research_provider_response_bindings%rowtype;
  attempt_row content_factory.research_run_provider_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'authorization_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_claim_payload_invalid';
  end if;
  authorization_id_value := content_factory_private.require_uuid(
    p_payload, 'authorization_id'
  );

  select recovery_auth.* into authorization_row
  from content_factory.research_provider_response_recovery_authorizations
    recovery_auth
  where recovery_auth.id = authorization_id_value
  for update;
  if authorization_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_authorization_not_found';
  end if;

  select reservation.* into reservation_row
  from content_factory.research_provider_response_recovery_get_reservations
    reservation
  where reservation.organization_id = authorization_row.organization_id
    and reservation.run_id = authorization_row.run_id;
  if reservation_row.id is not null then
    return jsonb_build_object(
      'ok', false,
      'code', 'research_response_recovery_get_already_reserved',
      'get_allowed', false,
      'provider_post_allowed', false,
      'reservation_id', reservation_row.id,
      'run_id', reservation_row.run_id
    );
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = authorization_row.organization_id
    and run.project_id = authorization_row.project_id
    and run.id = authorization_row.run_id
  for update;
  if run_row.id is null
     or run_row.status <> 'failed'
     or run_row.error_code <> 'provider_response_invalid' then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_run_not_eligible';
  end if;

  select exact_binding.* into exact_row
  from content_factory.research_exact_youtube_research_bindings exact_binding
  where exact_binding.organization_id = authorization_row.organization_id
    and exact_binding.project_id = authorization_row.project_id
    and exact_binding.run_id = authorization_row.run_id
    and exact_binding.product_id = run_row.product_id
    and exact_binding.id = authorization_row.exact_binding_id
    and exact_binding.binding_hash =
      authorization_row.exact_binding_hash_snapshot
    and exact_binding.media_matches_registered_source
    and exact_binding.paid_analysis_ack_snapshot
    and exact_binding.analysis_scope = 'sampled_frames_only'
    and not exact_binding.full_stream_access
    and not exact_binding.transcript_available;
  if exact_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_exact_binding_mismatch';
  end if;

  select response.* into response_row
  from content_factory.research_provider_response_bindings response
  join content_factory.research_run_provider_bindings attempt
    on attempt.organization_id = response.organization_id
   and attempt.run_id = response.run_id
   and attempt.id = response.attempt_id
   and attempt.provider_key = response.provider_key
   and attempt.adapter_version = response.adapter_version
  where response.organization_id = authorization_row.organization_id
    and response.run_id = authorization_row.run_id
    and response.id = authorization_row.provider_response_binding_id
    and response.response_hash =
      authorization_row.provider_response_hash_snapshot
    and response.accepted_at =
      authorization_row.provider_response_accepted_at_snapshot
    and response.provider_key = 'openai_web_search'
    and response.adapter_version = 'openai-responses-web-search-v1';
  if response_row.id is not null then
    select attempt.* into attempt_row
    from content_factory.research_run_provider_bindings attempt
    where attempt.organization_id = response_row.organization_id
      and attempt.run_id = response_row.run_id
      and attempt.id = response_row.attempt_id
      and attempt.provider_key = response_row.provider_key
      and attempt.adapter_version = response_row.adapter_version;
  end if;
  if response_row.id is not null then
    select receipt.provider_status into latest_provider_status_value
    from content_factory.research_provider_response_receipts receipt
    where receipt.organization_id = response_row.organization_id
      and receipt.response_binding_id = response_row.id
    order by receipt.checked_at desc, receipt.id desc
    limit 1;
  end if;
  if response_row.id is null
     or attempt_row.id is null
     or response_row.accepted_at >
       clock_timestamp() - interval '8 minutes'
     or coalesce(
       latest_provider_status_value, response_row.initial_status
     ) <> 'completed' then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_completed_response_required';
  end if;

  reservation_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-research-response-provider-get-reservation-v1',
      'organization_id', authorization_row.organization_id,
      'project_id', authorization_row.project_id,
      'run_id', authorization_row.run_id,
      'authorization_id', authorization_row.id,
      'authorization_hash', authorization_row.authorization_hash,
      'exact_binding_id', exact_row.id,
      'exact_binding_hash', exact_row.binding_hash,
      'provider_response_binding_id', response_row.id,
      'provider_response_hash', response_row.response_hash,
      'authorized_by', authorization_row.authorized_by,
      'maximum_provider_gets', 1,
      'provider_get_allowed', true,
      'provider_post_allowed', false,
      'include_web_search_sources', true,
      'reserved_at', reserved_at_value
    )
  );
  insert into
    content_factory.research_provider_response_recovery_get_reservations (
      organization_id, project_id, run_id, authorization_id,
      exact_binding_id, provider_response_binding_id,
      authorized_by_snapshot, maximum_provider_gets,
      provider_get_allowed, provider_post_allowed,
      include_web_search_sources, authorization_hash_snapshot,
      exact_binding_hash_snapshot, provider_response_hash_snapshot,
      reservation_hash, reserved_at
    ) values (
      authorization_row.organization_id, authorization_row.project_id,
      authorization_row.run_id, authorization_row.id, exact_row.id,
      response_row.id, authorization_row.authorized_by, 1, true, false, true,
      authorization_row.authorization_hash, exact_row.binding_hash,
      response_row.response_hash, reservation_hash_value, reserved_at_value
    )
  returning * into reservation_row;

  lease_expires_at_value := clock_timestamp() + interval '90 seconds';
  previous_revalidation_setting := current_setting(
    'content_factory.product_research_exact_response_recovery', true
  );
  perform set_config(
    'content_factory.product_research_exact_response_recovery', 'on', true
  );
  begin
    update content_factory.product_research_runs run
    set status = 'processing',
        summary = '{}'::jsonb,
        error_code = null,
        error_message = null,
        completion_hash = null,
        finished_at = null,
        lease_expires_at = lease_expires_at_value
    where run.organization_id = authorization_row.organization_id
      and run.project_id = authorization_row.project_id
      and run.id = authorization_row.run_id
      and run.status = 'failed'
      and run.error_code = 'provider_response_invalid';
    get diagnostics changed_count_value = row_count;
  exception when others then
    perform set_config(
      'content_factory.product_research_exact_response_recovery',
      coalesce(previous_revalidation_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'content_factory.product_research_exact_response_recovery',
    coalesce(previous_revalidation_setting, ''), true
  );
  if changed_count_value <> 1 then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_transition_conflict';
  end if;

  return jsonb_build_object(
    'ok', true,
    'code', 'research_response_recovery_get_reserved',
    'get_allowed', true,
    'provider_post_allowed', false,
    'include_web_search_sources', true,
    'reservation_id', reservation_row.id,
    'run_id', reservation_row.run_id,
    'status', 'processing',
    'lease_expires_at', lease_expires_at_value,
    'provider_response_id', response_row.provider_response_id,
    'attempt_id', attempt_row.id,
    'model', attempt_row.model,
    'accepted_at', response_row.accepted_at
  );
end;
$$;

-- Generic background continuation normally reads the bound response on every
-- status request. Recovery must not do that: after this ledger says a GET was
-- reserved, only the same in-memory Edge request that received the fresh
-- reservation may issue it. This service-only read exposes no provider id and
-- lets every later request fail closed before the legacy continuation read.
create or replace function
  public.system_read_product_research_response_recovery_reservation(
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
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  reservation_row
    content_factory.research_provider_response_recovery_get_reservations%rowtype;
  outcome_recorded_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'run_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_reservation_read_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value;
  if run_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  select reservation.* into reservation_row
  from content_factory.research_provider_response_recovery_get_reservations
    reservation
  where reservation.organization_id = run_row.organization_id
    and reservation.run_id = run_row.id;
  if reservation_row.id is not null then
    outcome_recorded_value := exists (
      select 1
      from content_factory.research_provider_response_recovery_outcomes outcome
      where outcome.organization_id = reservation_row.organization_id
        and outcome.reservation_id = reservation_row.id
    );
  end if;
  return jsonb_build_object(
    'ok', true,
    'run_id', run_row.id,
    'get_reserved', reservation_row.id is not null,
    'reservation_id', reservation_row.id,
    'outcome_recorded', outcome_recorded_value
  );
end;
$$;

create or replace function
  public.system_record_product_research_response_recovery_outcome(
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
  reservation_id_value uuid;
  recorded_at_value timestamptz := clock_timestamp();
  outcome_hash_value text;
  reservation_row
    content_factory.research_provider_response_recovery_get_reservations%rowtype;
  authorization_row
    content_factory.research_provider_response_recovery_authorizations%rowtype;
  outcome_row
    content_factory.research_provider_response_recovery_outcomes%rowtype;
  run_row content_factory.product_research_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'reservation_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_outcome_payload_invalid';
  end if;
  reservation_id_value := content_factory_private.require_uuid(
    p_payload, 'reservation_id'
  );

  select reservation.* into reservation_row
  from content_factory.research_provider_response_recovery_get_reservations
    reservation
  where reservation.id = reservation_id_value
  for update;
  if reservation_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_response_recovery_reservation_not_found';
  end if;
  select recovery_auth.* into authorization_row
  from content_factory.research_provider_response_recovery_authorizations
    recovery_auth
  where recovery_auth.organization_id = reservation_row.organization_id
    and recovery_auth.id = reservation_row.authorization_id;
  if authorization_row.id is null
     or authorization_row.run_id <> reservation_row.run_id
     or authorization_row.project_id <> reservation_row.project_id then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_authorization_mismatch';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = reservation_row.organization_id
    and run.project_id = reservation_row.project_id
    and run.id = reservation_row.run_id
  for share;
  if run_row.id is null
     or run_row.status not in ('completed', 'failed')
     or run_row.completion_hash is null then
    raise exception using
      errcode = '55000',
      message = 'research_response_recovery_terminal_run_required';
  end if;

  select outcome.* into outcome_row
  from content_factory.research_provider_response_recovery_outcomes outcome
  where outcome.organization_id = reservation_row.organization_id
    and outcome.reservation_id = reservation_row.id;
  if outcome_row.id is not null then
    if outcome_row.terminal_status <> run_row.status
       or outcome_row.terminal_error_code is distinct from run_row.error_code
       or outcome_row.completion_hash_snapshot <> run_row.completion_hash then
      raise exception using
        errcode = '23505',
        message = 'research_response_recovery_outcome_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'code', 'research_response_recovery_outcome_already_recorded',
      'outcome_id', outcome_row.id,
      'reservation_id', outcome_row.reservation_id,
      'run_id', outcome_row.run_id,
      'status', outcome_row.terminal_status,
      'error_code', outcome_row.terminal_error_code
    );
  end if;

  outcome_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-research-response-get-recovery-outcome-v1',
      'organization_id', reservation_row.organization_id,
      'project_id', reservation_row.project_id,
      'run_id', reservation_row.run_id,
      'authorization_id', reservation_row.authorization_id,
      'reservation_id', reservation_row.id,
      'terminal_status', run_row.status,
      'terminal_error_code', run_row.error_code,
      'completion_hash', run_row.completion_hash
    )
  );
  insert into content_factory.research_provider_response_recovery_outcomes (
    organization_id, project_id, run_id, reservation_id,
    authorization_id, terminal_status, terminal_error_code,
    completion_hash_snapshot, outcome_hash, recorded_at
  ) values (
    reservation_row.organization_id, reservation_row.project_id,
    reservation_row.run_id, reservation_row.id,
    reservation_row.authorization_id, run_row.status, run_row.error_code,
    run_row.completion_hash, outcome_hash_value, recorded_at_value
  )
  returning * into outcome_row;

  return jsonb_build_object(
    'ok', true,
    'code', 'research_response_recovery_outcome_recorded',
    'outcome_id', outcome_row.id,
    'reservation_id', outcome_row.reservation_id,
    'run_id', outcome_row.run_id,
    'status', outcome_row.terminal_status,
    'error_code', outcome_row.terminal_error_code
  );
end;
$$;

revoke all on function
  public.creator_authorize_product_research_response_recovery(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.creator_authorize_product_research_response_recovery(jsonb)
  to authenticated;

revoke all on function
  public.system_claim_product_research_response_recovery(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_claim_product_research_response_recovery(jsonb)
  to service_role;

revoke all on function
  public.system_read_product_research_response_recovery_reservation(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_read_product_research_response_recovery_reservation(jsonb)
  to service_role;

revoke all on function
  public.system_record_product_research_response_recovery_outcome(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_record_product_research_response_recovery_outcome(jsonb)
  to service_role;

comment on table
  content_factory.research_provider_response_recovery_authorizations is
  'Append-only human authorization to revalidate one exact-video research run by GET of its already-bound completed provider Response.';
comment on table
  content_factory.research_provider_response_recovery_get_reservations is
  'Append-only, one-per-run reservation for the sole recovery GET; explicitly forbids provider POST and new paid work.';
comment on table
  content_factory.research_provider_response_recovery_outcomes is
  'Append-only terminal run receipt after an authorized saved-response GET recovery; stores no provider body.';
comment on function
  public.creator_authorize_product_research_response_recovery(jsonb) is
  'Owner/admin/producer project-scoped authorization for one GET-only recovery of an exact-video provider_response_invalid run.';
comment on function
  public.system_claim_product_research_response_recovery(jsonb) is
  'Service-only one-GET reservation and bounded failed-to-processing transition; returns the private bound Response id once and can never create a provider POST or attempt.';
comment on function
  public.system_read_product_research_response_recovery_reservation(jsonb) is
  'Service-only no-provider-id guard used before generic continuation GET; a reserved run requires the fresh matching reservation from the same Edge request.';
comment on function
  public.system_record_product_research_response_recovery_outcome(jsonb) is
  'Service-only idempotent append-only receipt of the authoritative completed or failed run after saved-response recovery.';

notify pgrst, 'reload schema';

commit;
