begin;

-- Research provider control plane v1 deliberately contains no transport code.
-- It records the exact human authorization and exact provider adapter selected
-- for a run, then accepts only passive health facts produced by that run.  The
-- catalog cannot dispatch a job, run a canary, choose a fallback, or contact a
-- provider.
create table if not exists content_factory.research_provider_catalog (
  provider_key text primary key check (
    provider_key in ('openai_web_search', 'youtube_data_api_v3')
  ),
  adapter_version text not null check (
    adapter_version ~ '^[a-z0-9][a-z0-9._:-]{2,79}$'
  ),
  display_name text not null check (length(btrim(display_name)) between 2 and 120),
  lifecycle_status text not null check (lifecycle_status in ('active', 'disabled')),
  rollout_stage text not null check (rollout_stage in ('production', 'planned')),
  billing_mode text not null check (billing_mode in ('metered', 'quota')),
  health_mode text not null check (health_mode in ('passive', 'manual')),
  canary_mode text not null check (canary_mode in ('forbidden', 'manual_only')),
  automatic_canary_allowed boolean not null default false
    check (not automatic_canary_allowed),
  automatic_fallback_allowed boolean not null default false
    check (not automatic_fallback_allowed),
  commercial_use_allowed boolean not null,
  arbitrary_public_accounts_allowed boolean not null,
  subject_authorization_required boolean not null,
  capabilities jsonb not null check (
    jsonb_typeof(capabilities) = 'array'
    and jsonb_array_length(capabilities) between 1 and 12
  ),
  platforms jsonb not null check (
    jsonb_typeof(platforms) = 'array'
    and jsonb_array_length(platforms) between 1 and 8
  ),
  credential_reference text not null check (
    credential_reference ~ '^env:[A-Z][A-Z0-9_]{2,79}$'
  ),
  allowed_host text not null check (
    allowed_host ~ '^[a-z0-9]([a-z0-9.-]{1,251}[a-z0-9])?$'
    and allowed_host !~ '(^|[.])localhost$'
  ),
  passive_health_ttl_seconds integer not null check (
    passive_health_ttl_seconds between 300 and 86400
  ),
  max_canary_requests integer not null default 0 check (
    max_canary_requests between 0 and 1
  ),
  max_canary_cost_minor bigint not null default 0 check (
    max_canary_cost_minor = 0
  ),
  catalog_version bigint not null default 1 check (catalog_version >= 1),
  terms_version text not null check (length(btrim(terms_version)) between 3 and 80),
  retention_days integer not null check (retention_days between 1 and 3650),
  created_at timestamptz not null default now(),
  unique (provider_key, adapter_version),
  check (
    (
      provider_key = 'openai_web_search'
      and adapter_version = 'openai-responses-web-search-v1'
      and lifecycle_status = 'active'
      and rollout_stage = 'production'
      and billing_mode = 'metered'
      and health_mode = 'passive'
      and canary_mode = 'forbidden'
      and commercial_use_allowed
      and arbitrary_public_accounts_allowed
      and not subject_authorization_required
      and max_canary_requests = 0
      and credential_reference = 'env:OPENAI_API_KEY'
      and allowed_host = 'api.openai.com'
    )
    or
    (
      provider_key = 'youtube_data_api_v3'
      and adapter_version = 'youtube-data-api-v3-public-metadata-v1'
      and lifecycle_status = 'disabled'
      and rollout_stage = 'planned'
      and billing_mode = 'quota'
      and health_mode = 'manual'
      and canary_mode = 'manual_only'
      and commercial_use_allowed
      and arbitrary_public_accounts_allowed
      and not subject_authorization_required
      and max_canary_requests = 1
      and credential_reference = 'env:YOUTUBE_DATA_API_KEY'
      and allowed_host = 'www.googleapis.com'
    )
  )
);

insert into content_factory.research_provider_catalog (
  provider_key, adapter_version, display_name, lifecycle_status,
  rollout_stage, billing_mode, health_mode, canary_mode,
  automatic_canary_allowed, automatic_fallback_allowed,
  commercial_use_allowed, arbitrary_public_accounts_allowed,
  subject_authorization_required, capabilities, platforms,
  credential_reference, allowed_host, passive_health_ttl_seconds,
  max_canary_requests, max_canary_cost_minor, catalog_version,
  terms_version, retention_days
) values
  (
    'openai_web_search', 'openai-responses-web-search-v1',
    'OpenAI Responses web search', 'active', 'production', 'metered',
    'passive', 'forbidden', false, false, true, true, false,
    '["web_search","category_analysis","competitor_analysis","trend_analysis"]'::jsonb,
    '["instagram","youtube","vk","wildberries","ozon"]'::jsonb,
    'env:OPENAI_API_KEY', 'api.openai.com', 3600, 0, 0, 1,
    'openai-api-approved-v1', 365
  ),
  (
    'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
    'YouTube Data API v3 public metadata', 'disabled', 'planned', 'quota',
    'manual', 'manual_only', false, false, true, true, false,
    '["public_video_metadata"]'::jsonb,
    '["youtube"]'::jsonb,
    'env:YOUTUBE_DATA_API_KEY', 'www.googleapis.com', 86400, 1, 0, 1,
    'youtube-data-api-review-required-v1', 30
  )
on conflict (provider_key) do nothing;

create table if not exists content_factory.research_execution_authorizations (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  authorized_by uuid not null,
  authorization_kind text not null check (
    authorization_kind in ('explicit_paid_analysis', 'legacy_pre_gate')
  ),
  paid_analysis_ack boolean not null,
  provider_key text not null,
  adapter_version text not null,
  run_request_hash text not null check (run_request_hash ~ '^[0-9a-f]{64}$'),
  max_provider_attempts integer not null default 1 check (max_provider_attempts = 1),
  automatic_fallback_allowed boolean not null default false
    check (not automatic_fallback_allowed),
  reason_code text not null check (
    reason_code in ('user_confirmed_paid_analysis', 'migration_legacy_pre_gate')
  ),
  authorized_at timestamptz not null,
  authorization_hash text not null check (authorization_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, run_id),
  unique (organization_id, run_id, id),
  unique (
    organization_id, run_id, id, provider_key, adapter_version
  ),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, authorized_by)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (provider_key, adapter_version)
    references content_factory.research_provider_catalog(
      provider_key, adapter_version
    ),
  check (
    (
      authorization_kind = 'explicit_paid_analysis'
      and paid_analysis_ack
      and reason_code = 'user_confirmed_paid_analysis'
    )
    or
    (
      authorization_kind = 'legacy_pre_gate'
      and not paid_analysis_ack
      and reason_code = 'migration_legacy_pre_gate'
    )
  )
);

create table if not exists content_factory.research_run_provider_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  authorization_id uuid not null,
  provider_key text not null,
  adapter_version text not null,
  model text not null check (
    model ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{1,79}$'
  ),
  attempt_number integer not null default 1 check (attempt_number = 1),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  bound_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, run_id),
  unique (organization_id, run_id, id),
  unique (
    organization_id, run_id, id, provider_key, adapter_version
  ),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (
    organization_id, run_id, authorization_id,
    provider_key, adapter_version
  )
    references content_factory.research_execution_authorizations(
      organization_id, run_id, id, provider_key, adapter_version
    ),
  foreign key (provider_key, adapter_version)
    references content_factory.research_provider_catalog(
      provider_key, adapter_version
    )
);

create table if not exists content_factory.research_provider_health_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  run_id uuid not null,
  attempt_id uuid not null,
  provider_key text not null,
  adapter_version text not null,
  status text not null check (
    status in ('ready', 'degraded', 'blocked', 'unknown')
  ),
  failure_code text check (
    failure_code is null
    or failure_code in (
      'provider_configuration_error',
      'provider_authentication_failed',
      'provider_rate_limited',
      'provider_request_rejected',
      'provider_response_invalid',
      'provider_outcome_unknown',
      'provider_unavailable',
      'citation_coverage_insufficient'
    )
  ),
  citation_count integer check (
    citation_count is null or citation_count between 0 and 1000
  ),
  check_kind text not null default 'passive_execution'
    check (check_kind = 'passive_execution'),
  provider_request_created boolean not null default false
    check (not provider_request_created),
  actual_cost_minor bigint not null default 0 check (actual_cost_minor = 0),
  checked_at timestamptz not null,
  expires_at timestamptz not null,
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, attempt_id, status),
  unique (organization_id, attempt_id, receipt_hash),
  foreign key (
    organization_id, run_id, attempt_id, provider_key, adapter_version
  )
    references content_factory.research_run_provider_bindings(
      organization_id, run_id, id, provider_key, adapter_version
    ),
  foreign key (provider_key, adapter_version)
    references content_factory.research_provider_catalog(
      provider_key, adapter_version
    ),
  check (expires_at > checked_at),
  check (
    (
      status = 'ready'
      and failure_code is null
      and coalesce(citation_count, 0) >= 1
    )
    or (status <> 'ready' and failure_code is not null)
  )
);

create index if not exists research_authorizations_org_run_idx
  on content_factory.research_execution_authorizations (
    organization_id, run_id, authorized_at desc
  );
create index if not exists research_provider_bindings_org_provider_idx
  on content_factory.research_run_provider_bindings (
    organization_id, provider_key, bound_at desc, id desc
  );
create index if not exists research_provider_health_latest_idx
  on content_factory.research_provider_health_receipts (
    organization_id, provider_key, checked_at desc, id desc
  );

alter table content_factory.research_provider_catalog enable row level security;
alter table content_factory.research_execution_authorizations enable row level security;
alter table content_factory.research_run_provider_bindings enable row level security;
alter table content_factory.research_provider_health_receipts enable row level security;

revoke all on content_factory.research_provider_catalog
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_execution_authorizations
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_run_provider_bindings
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_provider_health_receipts
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_provider_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_immutable';
end;
$$;

drop trigger if exists research_provider_catalog_immutable
  on content_factory.research_provider_catalog;
create trigger research_provider_catalog_immutable
before update or delete on content_factory.research_provider_catalog
for each row execute function
  content_factory_private.reject_research_provider_mutation();

drop trigger if exists research_execution_authorization_immutable
  on content_factory.research_execution_authorizations;
create trigger research_execution_authorization_immutable
before update or delete on content_factory.research_execution_authorizations
for each row execute function
  content_factory_private.reject_research_provider_mutation();

drop trigger if exists research_run_provider_binding_immutable
  on content_factory.research_run_provider_bindings;
create trigger research_run_provider_binding_immutable
before update or delete on content_factory.research_run_provider_bindings
for each row execute function
  content_factory_private.reject_research_provider_mutation();

drop trigger if exists research_provider_health_append_only
  on content_factory.research_provider_health_receipts;
create trigger research_provider_health_append_only
before update or delete on content_factory.research_provider_health_receipts
for each row execute function
  content_factory_private.reject_research_provider_mutation();

-- Preserve the complete production implementations. Their validation,
-- idempotency, quota and lease behavior remains authoritative behind the new
-- acknowledgement and authorization checks. Retire the previous entrypoints
-- before taking the legacy snapshot so the migration's ordinary execution
-- order cannot itself create an unreceipted run between those two operations.
do $preserve_research_provider_control_rpcs$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_product_research_pre_provider_control(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_start_product_research(jsonb)') is null then
      raise exception using
        errcode = '42883',
        message = 'creator_start_product_research_missing';
    end if;
    execute 'alter function public.creator_start_product_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_start_product_research(jsonb) '
      || 'rename to creator_start_product_research_pre_provider_control';
  end if;

  if to_regprocedure(
    'content_factory_private.system_claim_product_research_pre_provider_control(jsonb)'
  ) is null then
    if to_regprocedure('public.system_claim_product_research(jsonb)') is null then
      raise exception using
        errcode = '42883',
        message = 'system_claim_product_research_missing';
    end if;
    execute 'alter function public.system_claim_product_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.system_claim_product_research(jsonb) '
      || 'rename to system_claim_product_research_pre_provider_control';
  end if;
end;
$preserve_research_provider_control_rpcs$;

-- Every pre-gate run receives an explicit, inspectable legacy authorization.
-- This preserves queued and processing work without pretending that the new
-- acknowledgement existed at the time. New runs can only receive the explicit
-- authorization written by the wrapper below.
insert into content_factory.research_execution_authorizations (
  organization_id, run_id, authorized_by, authorization_kind,
  paid_analysis_ack, provider_key, adapter_version, run_request_hash,
  max_provider_attempts, automatic_fallback_allowed, reason_code,
  authorized_at, authorization_hash
)
select
  run.organization_id,
  run.id,
  run.created_by,
  'legacy_pre_gate',
  false,
  'openai_web_search',
  'openai-responses-web-search-v1',
  run.request_hash,
  1,
  false,
  'migration_legacy_pre_gate',
  run.created_at,
  content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-execution-authorization-v1',
    'organization_id', run.organization_id,
    'run_id', run.id,
    'authorized_by', run.created_by,
    'authorization_kind', 'legacy_pre_gate',
    'paid_analysis_ack', false,
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'run_request_hash', run.request_hash,
    'max_provider_attempts', 1,
    'automatic_fallback_allowed', false,
    'reason_code', 'migration_legacy_pre_gate',
    'authorized_at', run.created_at
  ))
from content_factory.product_research_runs run
on conflict (organization_id, run_id) do nothing;

create or replace function public.creator_start_product_research(
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
  delegated_payload jsonb;
  result_value jsonb;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  authorized_at_value timestamptz;
  authorization_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'paid_analysis_ack')
     or jsonb_typeof(p_payload -> 'paid_analysis_ack') <> 'boolean'
     or p_payload -> 'paid_analysis_ack' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'paid_analysis_ack_required';
  end if;

  delegated_payload := p_payload - 'paid_analysis_ack';
  user_id := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(delegated_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer']
  );

  result_value := content_factory_private
    .creator_start_product_research_pre_provider_control(delegated_payload);
  begin
    run_id_value := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end;
  if run_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end if;

  authorized_at_value := clock_timestamp();
  authorization_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-execution-authorization-v1',
      'organization_id', organization_id_value,
      'run_id', run_id_value,
      'authorized_by', user_id,
      'authorization_kind', 'explicit_paid_analysis',
      'paid_analysis_ack', true,
      'provider_key', 'openai_web_search',
      'adapter_version', 'openai-responses-web-search-v1',
      'run_request_hash', run_row.request_hash,
      'max_provider_attempts', 1,
      'automatic_fallback_allowed', false,
      'reason_code', 'user_confirmed_paid_analysis',
      'authorized_at', authorized_at_value
    )
  );

  insert into content_factory.research_execution_authorizations (
    organization_id, run_id, authorized_by, authorization_kind,
    paid_analysis_ack, provider_key, adapter_version, run_request_hash,
    max_provider_attempts, automatic_fallback_allowed, reason_code,
    authorized_at, authorization_hash
  ) values (
    organization_id_value, run_id_value, user_id, 'explicit_paid_analysis',
    true, 'openai_web_search', 'openai-responses-web-search-v1',
    run_row.request_hash, 1, false, 'user_confirmed_paid_analysis',
    authorized_at_value, authorization_hash_value
  )
  on conflict on constraint
    research_execution_authorizations_organization_id_run_id_key
  do nothing;

  if not exists (
    select 1
    from content_factory.research_execution_authorizations authorization_entry
    where authorization_entry.organization_id = organization_id_value
      and authorization_entry.run_id = run_id_value
      and authorization_entry.run_request_hash = run_row.request_hash
      and authorization_entry.provider_key = 'openai_web_search'
      and authorization_entry.adapter_version = 'openai-responses-web-search-v1'
      and authorization_entry.max_provider_attempts = 1
      and not authorization_entry.automatic_fallback_allowed
  ) then
    raise exception using
      errcode = '55000',
      message = 'research_execution_authorization_conflict';
  end if;

  return result_value;
end;
$$;

create or replace function public.system_claim_product_research(
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
  run_row content_factory.product_research_runs%rowtype;
  authorization_row content_factory.research_execution_authorizations%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_claim_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_run_not_found';
  end if;

  select authorization_entry.* into authorization_row
  from content_factory.research_execution_authorizations authorization_entry
  where authorization_entry.organization_id = run_row.organization_id
    and authorization_entry.run_id = run_row.id;
  if authorization_row.id is null
     or authorization_row.run_request_hash <> run_row.request_hash
     or authorization_row.provider_key <> 'openai_web_search'
     or authorization_row.adapter_version <>
       'openai-responses-web-search-v1'
     or authorization_row.max_provider_attempts <> 1
     or authorization_row.automatic_fallback_allowed then
    raise exception using
      errcode = '55000',
      message = 'research_execution_authorization_required';
  end if;

  return content_factory_private
    .system_claim_product_research_pre_provider_control(p_payload);
end;
$$;

create or replace function public.system_begin_research_provider_attempt(
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
  provider_key_value text;
  adapter_version_value text;
  model_value text;
  run_row content_factory.product_research_runs%rowtype;
  authorization_row content_factory.research_execution_authorizations%rowtype;
  catalog_row content_factory.research_provider_catalog%rowtype;
  binding_row content_factory.research_run_provider_bindings%rowtype;
  binding_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'run_id', 'provider_key', 'adapter_version', 'model'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'run_id'
       and p_payload ? 'provider_key'
       and p_payload ? 'adapter_version'
       and p_payload ? 'model'
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_attempt_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  provider_key_value := content_factory_private.require_text(
    p_payload, 'provider_key', 3, 80
  );
  adapter_version_value := content_factory_private.require_text(
    p_payload, 'adapter_version', 3, 80
  );
  model_value := content_factory_private.require_text(
    p_payload, 'model', 2, 80
  );
  if provider_key_value !~ '^[a-z0-9][a-z0-9_]{2,79}$'
     or adapter_version_value !~ '^[a-z0-9][a-z0-9._:-]{2,79}$'
     or model_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{1,79}$' then
    raise exception using
      errcode = '22023',
      message = 'research_provider_attempt_payload_invalid';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_run_not_found';
  end if;
  if run_row.status <> 'processing'
     or run_row.lease_expires_at is null
     or run_row.lease_expires_at <= now() then
    raise exception using
      errcode = '55000',
      message = 'research_provider_attempt_run_not_processing';
  end if;

  select authorization_entry.* into authorization_row
  from content_factory.research_execution_authorizations authorization_entry
  where authorization_entry.organization_id = run_row.organization_id
    and authorization_entry.run_id = run_row.id;
  if authorization_row.id is null
     or authorization_row.run_request_hash <> run_row.request_hash
     or authorization_row.provider_key <> provider_key_value
     or authorization_row.adapter_version <> adapter_version_value
     or authorization_row.max_provider_attempts <> 1
     or authorization_row.automatic_fallback_allowed then
    raise exception using
      errcode = '55000',
      message = 'research_provider_attempt_not_authorized';
  end if;

  select catalog.* into catalog_row
  from content_factory.research_provider_catalog catalog
  where catalog.provider_key = provider_key_value
    and catalog.adapter_version = adapter_version_value;
  if catalog_row.provider_key is null
     or catalog_row.lifecycle_status <> 'active'
     or catalog_row.rollout_stage <> 'production'
     or not catalog_row.commercial_use_allowed
     or catalog_row.automatic_fallback_allowed then
    raise exception using
      errcode = '55000',
      message = 'research_provider_not_active';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(run_row.organization_id::text),
    hashtext('research-provider-attempt:' || run_row.id::text)
  );
  binding_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-provider-binding-v1',
      'organization_id', run_row.organization_id,
      'run_id', run_row.id,
      'authorization_id', authorization_row.id,
      'provider_key', provider_key_value,
      'adapter_version', adapter_version_value,
      'model', model_value,
      'attempt_number', 1
    )
  );

  insert into content_factory.research_run_provider_bindings (
    organization_id, run_id, authorization_id, provider_key,
    adapter_version, model, attempt_number, binding_hash
  ) values (
    run_row.organization_id, run_row.id, authorization_row.id,
    provider_key_value, adapter_version_value, model_value, 1,
    binding_hash_value
  )
  on conflict (organization_id, run_id) do nothing
  returning * into binding_row;

  if binding_row.id is null then
    select binding.* into binding_row
    from content_factory.research_run_provider_bindings binding
    where binding.organization_id = run_row.organization_id
      and binding.run_id = run_row.id;
  end if;
  if binding_row.id is null
     or binding_row.authorization_id <> authorization_row.id
     or binding_row.provider_key <> provider_key_value
     or binding_row.adapter_version <> adapter_version_value
     or binding_row.model <> model_value
     or binding_row.binding_hash <> binding_hash_value then
    raise exception using
      errcode = '23505',
      message = 'research_provider_attempt_conflict';
  end if;

  return jsonb_build_object(
    'ok', true,
    'attempt_id', binding_row.id,
    'provider_key', binding_row.provider_key,
    'adapter_version', binding_row.adapter_version
  );
end;
$$;

create or replace function public.system_record_research_provider_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  attempt_id_value uuid;
  status_value text;
  failure_code_value text;
  citation_count_value integer;
  checked_at_value timestamptz;
  expires_at_value timestamptz;
  binding_row content_factory.research_run_provider_bindings%rowtype;
  catalog_row content_factory.research_provider_catalog%rowtype;
  receipt_row content_factory.research_provider_health_receipts%rowtype;
  receipt_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'attempt_id', 'status', 'failure_code', 'citation_count', 'checked_at'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'attempt_id'
       and p_payload ? 'status'
       and p_payload ? 'checked_at'
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;
  attempt_id_value := content_factory_private.require_uuid(
    p_payload, 'attempt_id'
  );
  status_value := content_factory_private.require_text(
    p_payload, 'status', 5, 16
  );
  failure_code_value := nullif(
    btrim(coalesce(p_payload ->> 'failure_code', '')),
    ''
  );
  if status_value not in ('ready', 'degraded', 'blocked', 'unknown')
     or (
       p_payload ? 'failure_code'
       and jsonb_typeof(p_payload -> 'failure_code') not in ('string', 'null')
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;

  if p_payload ? 'citation_count'
     and jsonb_typeof(p_payload -> 'citation_count') <> 'null' then
    if jsonb_typeof(p_payload -> 'citation_count') <> 'number'
       or coalesce(p_payload ->> 'citation_count', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'research_provider_health_payload_invalid';
    end if;
    begin
      citation_count_value := (p_payload ->> 'citation_count')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'research_provider_health_payload_invalid';
    end;
  end if;
  if citation_count_value is not null
     and citation_count_value not between 0 and 1000 then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;

  begin
    checked_at_value := content_factory_private.require_text(
      p_payload, 'checked_at', 10, 64
    )::timestamptz;
  exception when invalid_datetime_format or datetime_field_overflow then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end;

  select binding.* into binding_row
  from content_factory.research_run_provider_bindings binding
  where binding.id = attempt_id_value;
  if binding_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_provider_attempt_not_found';
  end if;
  select catalog.* into catalog_row
  from content_factory.research_provider_catalog catalog
  where catalog.provider_key = binding_row.provider_key
    and catalog.adapter_version = binding_row.adapter_version;
  if catalog_row.provider_key is null then
    raise exception using
      errcode = '55000',
      message = 'research_provider_catalog_missing';
  end if;
  if checked_at_value < binding_row.bound_at - interval '1 minute'
     or checked_at_value > clock_timestamp() + interval '1 minute'
     or checked_at_value < clock_timestamp() - interval '24 hours' then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_checked_at_invalid';
  end if;
  if (status_value = 'ready' and (
        failure_code_value is not null
        or coalesce(citation_count_value, 0) < 1
      ))
     or (status_value <> 'ready' and failure_code_value is null)
     or failure_code_value is not null and failure_code_value not in (
       'provider_configuration_error',
       'provider_authentication_failed',
       'provider_rate_limited',
       'provider_request_rejected',
       'provider_response_invalid',
       'provider_outcome_unknown',
       'provider_unavailable',
       'citation_coverage_insufficient'
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_state_invalid';
  end if;

  expires_at_value := checked_at_value
    + make_interval(secs => catalog_row.passive_health_ttl_seconds);
  receipt_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-provider-health-receipt-v1',
      'organization_id', binding_row.organization_id,
      'run_id', binding_row.run_id,
      'attempt_id', binding_row.id,
      'provider_key', binding_row.provider_key,
      'adapter_version', binding_row.adapter_version,
      'status', status_value,
      'failure_code', failure_code_value,
      'citation_count', citation_count_value,
      'check_kind', 'passive_execution',
      'provider_request_created', false,
      'actual_cost_minor', 0,
      'checked_at', checked_at_value,
      'expires_at', expires_at_value
    )
  );

  perform pg_advisory_xact_lock(
    hashtext(binding_row.organization_id::text),
    hashtext('research-provider-health:' || binding_row.id::text || ':' || status_value)
  );
  select receipt.* into receipt_row
  from content_factory.research_provider_health_receipts receipt
  where receipt.organization_id = binding_row.organization_id
    and receipt.attempt_id = binding_row.id
    and receipt.status = status_value;
  if receipt_row.id is not null then
    if receipt_row.receipt_hash <> receipt_hash_value then
      raise exception using
        errcode = '23505',
        message = 'research_provider_health_conflict';
    end if;
    return jsonb_build_object('ok', true, 'receipt_id', receipt_row.id);
  end if;

  insert into content_factory.research_provider_health_receipts (
    organization_id, run_id, attempt_id, provider_key, adapter_version,
    status, failure_code, citation_count, check_kind,
    provider_request_created, actual_cost_minor, checked_at, expires_at,
    receipt_hash
  ) values (
    binding_row.organization_id, binding_row.run_id, binding_row.id,
    binding_row.provider_key, binding_row.adapter_version, status_value,
    failure_code_value, citation_count_value, 'passive_execution', false, 0,
    checked_at_value, expires_at_value, receipt_hash_value
  )
  returning * into receipt_row;

  return jsonb_build_object('ok', true, 'receipt_id', receipt_row.id);
end;
$$;

create or replace function public.creator_research_provider_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  run_id_value uuid;
  providers_value jsonb;
  run_control_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_provider_status_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );

  if nullif(btrim(coalesce(p_payload ->> 'run_id', '')), '') is not null then
    run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
    if not exists (
      select 1
      from content_factory.product_research_runs run
      where run.organization_id = organization_id
        and run.id = run_id_value
    ) then
      raise exception using
        errcode = '22023',
        message = 'research_run_not_found';
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'provider_key', catalog.provider_key,
    'display_name', catalog.display_name,
    'adapter_version', catalog.adapter_version,
    'lifecycle_status', catalog.lifecycle_status,
    'rollout_stage', catalog.rollout_stage,
    'billing_mode', catalog.billing_mode,
    'health_mode', catalog.health_mode,
    'canary_mode', catalog.canary_mode,
    'automatic_canary_allowed', catalog.automatic_canary_allowed,
    'automatic_fallback_allowed', catalog.automatic_fallback_allowed,
    'commercial_use_allowed', catalog.commercial_use_allowed,
    'arbitrary_public_accounts_allowed',
      catalog.arbitrary_public_accounts_allowed,
    'subject_authorization_required',
      catalog.subject_authorization_required,
    'capabilities', catalog.capabilities,
    'platforms', catalog.platforms,
    'health', jsonb_strip_nulls(jsonb_build_object(
      'status', case
        when latest.id is null then 'unknown'
        when latest.expires_at <= now() then 'stale'
        else latest.status
      end,
      'fresh', coalesce(latest.expires_at > now(), false),
      'failure_code', latest.failure_code,
      'citation_count', latest.citation_count,
      'checked_at', latest.checked_at,
      'expires_at', latest.expires_at,
      'receipt_id', latest.id
    ))
  ) order by catalog.provider_key), '[]'::jsonb)
  into providers_value
  from content_factory.research_provider_catalog catalog
  left join lateral (
    select receipt.*
    from content_factory.research_provider_health_receipts receipt
    where receipt.organization_id = organization_id
      and receipt.provider_key = catalog.provider_key
      and receipt.adapter_version = catalog.adapter_version
    order by receipt.checked_at desc, receipt.id desc
    limit 1
  ) latest on true;

  if run_id_value is not null then
    select jsonb_build_object(
      'run_id', run.id,
      'run_status', run.status,
      'authorized', authorization_entry.id is not null,
      'authorization', case when authorization_entry.id is null then null else
        jsonb_build_object(
          'id', authorization_entry.id,
          'kind', authorization_entry.authorization_kind,
          'paid_analysis_ack', authorization_entry.paid_analysis_ack,
          'provider_key', authorization_entry.provider_key,
          'adapter_version', authorization_entry.adapter_version,
          'max_provider_attempts', authorization_entry.max_provider_attempts,
          'automatic_fallback_allowed',
            authorization_entry.automatic_fallback_allowed,
          'reason_code', authorization_entry.reason_code,
          'authorized_at', authorization_entry.authorized_at
        ) end,
      'attempt', case when binding.id is null then null else
        jsonb_build_object(
          'attempt_id', binding.id,
          'provider_key', binding.provider_key,
          'adapter_version', binding.adapter_version,
          'model', binding.model,
          'attempt_number', binding.attempt_number,
          'bound_at', binding.bound_at
        ) end
    ) into run_control_value
    from content_factory.product_research_runs run
    left join content_factory.research_execution_authorizations authorization_entry
      on authorization_entry.organization_id = run.organization_id
     and authorization_entry.run_id = run.id
    left join content_factory.research_run_provider_bindings binding
      on binding.organization_id = run.organization_id
     and binding.run_id = run.id
    where run.organization_id = organization_id
      and run.id = run_id_value;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-provider-control-plane-v1',
    'organization_id', organization_id,
    'providers', providers_value,
    'run_control', run_control_value,
    'controls', jsonb_build_object(
      'explicit_paid_analysis_required', true,
      'creates_research_runs', false,
      'automatic_canary', false,
      'automatic_fallback', false,
      'external_call_performed', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private.creator_start_product_research_pre_provider_control(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.system_claim_product_research_pre_provider_control(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_research_provider_mutation()
  from public, anon, authenticated, service_role;

revoke all on function public.creator_start_product_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_product_research(jsonb)
  to authenticated;

revoke all on function public.system_claim_product_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_claim_product_research(jsonb)
  to service_role;

revoke all on function public.system_begin_research_provider_attempt(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_begin_research_provider_attempt(jsonb)
  to service_role;

revoke all on function public.system_record_research_provider_health(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_record_research_provider_health(jsonb)
  to service_role;

revoke all on function public.creator_research_provider_status(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_provider_status(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
