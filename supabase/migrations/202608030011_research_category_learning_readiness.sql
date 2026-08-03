begin;

-- Category learning is represented as evidence readiness, never as model IQ.
-- This control plane stores durable source lineage, append-only analysis
-- corrections, deterministic readiness snapshots and fail-closed collection
-- intents.  It never performs provider HTTP, starts transport or retries work.

create or replace function content_factory_private.research_analysis_has_forbidden_keys(
  value jsonb
)
returns boolean
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  entry record;
  item jsonb;
begin
  if jsonb_typeof(value) = 'object' then
    for entry in
      select object_entry.key, object_entry.value
      from jsonb_each(value) object_entry(key, value)
    loop
      if lower(entry.key) in (
        'caption', 'captions', 'raw_caption', 'raw_captions',
        'transcript', 'transcripts', 'raw_transcript', 'raw_transcripts',
        'raw_text', 'source_text', 'full_text'
      ) then
        return true;
      end if;
      if content_factory_private.research_analysis_has_forbidden_keys(
        entry.value
      ) then
        return true;
      end if;
    end loop;
  elsif jsonb_typeof(value) = 'array' then
    for item in select array_item from jsonb_array_elements(value) array_item
    loop
      if content_factory_private.research_analysis_has_forbidden_keys(item) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function content_factory_private.research_source_analysis_is_valid(
  value jsonb
)
returns boolean
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  item jsonb;
  seen_signals text[] := array[]::text[];
  signal_value text;
begin
  if jsonb_typeof(value) <> 'object'
     or value - array[
       'schema_version', 'classification', 'relevance_score', 'confidence',
       'summary', 'structural_signal_keys', 'limitations'
     ]::text[] <> '{}'::jsonb
     or not value ?& array[
       'schema_version', 'classification', 'relevance_score', 'confidence',
       'summary', 'structural_signal_keys', 'limitations'
     ]::text[]
     or value ->> 'schema_version' <> 'research-source-interpretation-v1'
     or value ->> 'classification' not in (
       'competitor', 'adjacent', 'trend_signal', 'reference',
       'irrelevant', 'unknown'
     )
     or jsonb_typeof(value -> 'relevance_score') <> 'number'
     or coalesce(value ->> 'relevance_score', '') !~ '^[0-9]{1,3}$'
     or (value ->> 'relevance_score')::integer not between 0 and 100
     or value ->> 'confidence' not in ('low', 'medium', 'high')
     or jsonb_typeof(value -> 'summary') <> 'string'
     or length(btrim(value ->> 'summary')) not between 20 and 2000
     or jsonb_typeof(value -> 'structural_signal_keys') <> 'array'
     or jsonb_array_length(value -> 'structural_signal_keys') > 20
     or jsonb_typeof(value -> 'limitations') <> 'array'
     or jsonb_array_length(value -> 'limitations') > 20
     or length(value::text) > 32768
     or content_factory_private.research_analysis_has_forbidden_keys(value) then
    return false;
  end if;

  for item in select signal from jsonb_array_elements(
    value -> 'structural_signal_keys'
  ) signal
  loop
    if jsonb_typeof(item) <> 'string' then
      return false;
    end if;
    signal_value := btrim(item #>> '{}');
    if signal_value !~ '^[a-z][a-z0-9_]*[.][a-z][a-z0-9_.]*$'
       or length(signal_value) not between 3 and 100
       or signal_value = any(seen_signals) then
      return false;
    end if;
    seen_signals := array_append(seen_signals, signal_value);
  end loop;
  for item in select limitation from jsonb_array_elements(
    value -> 'limitations'
  ) limitation
  loop
    if jsonb_typeof(item) <> 'string'
       or length(btrim(item #>> '{}')) not between 3 and 500 then
      return false;
    end if;
  end loop;
  return true;
exception when invalid_text_representation or numeric_value_out_of_range then
  return false;
end;
$$;

create or replace function content_factory_private.research_source_identity_key(
  source_url_value text,
  content_hash_value text
)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  normalized_url_value text;
begin
  normalized_url_value := nullif(btrim(source_url_value), '');
  if normalized_url_value is not null then
    normalized_url_value := regexp_replace(
      normalized_url_value, '#.*$', '', 'g'
    );
    if strpos(normalized_url_value, '?') = 0 then
      normalized_url_value := regexp_replace(
        normalized_url_value, '/+$', '', 'g'
      );
    end if;
    return content_factory_private.json_hash(jsonb_build_object(
      'kind', 'normalized_url', 'value', normalized_url_value
    ));
  end if;
  return content_factory_private.json_hash(jsonb_build_object(
    'kind', 'content_hash', 'value', content_hash_value
  ));
end;
$$;

create table if not exists content_factory.research_category_source_ledger (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  market_category_id uuid not null,
  product_id uuid not null,
  binding_id uuid not null,
  run_id uuid not null,
  source_id uuid not null,
  source_type text not null check (source_type in (
    'user_input', 'product_photo', 'marketplace_page', 'review',
    'competitor', 'social_video', 'market_data', 'other'
  )),
  title text not null check (length(btrim(title)) between 2 and 300),
  source_url text,
  provider_key text not null check (
    provider_key ~ '^[a-z][a-z0-9_.-]{1,79}$'
  ),
  platform text not null check (platform in (
    'youtube', 'instagram', 'marketplace', 'web', 'first_party', 'other'
  )),
  trust_level text not null check (
    trust_level in ('first_party', 'official', 'public', 'unverified')
  ),
  source_identity_key text not null check (
    source_identity_key ~ '^[0-9a-f]{64}$'
  ),
  source_content_hash text not null check (
    source_content_hash ~ '^[0-9a-f]{64}$'
  ),
  fetched_at timestamptz,
  published_at timestamptz,
  registered_by uuid not null,
  registered_at timestamptz not null default now(),
  lineage_hash text not null check (lineage_hash ~ '^[0-9a-f]{64}$'),
  constraint research_category_source_ledger_org_id_uq
    unique (organization_id, id),
  constraint research_category_source_ledger_category_content_uq
    unique (organization_id, market_category_id, source_content_hash),
  foreign key (organization_id, market_category_id)
    references content_factory.research_market_categories(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  foreign key (organization_id, run_id, source_id)
    references content_factory.product_research_sources(
      organization_id, run_id, id
    ),
  foreign key (organization_id, registered_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    source_url is null or (
      length(source_url) between 10 and 2048
      and source_url ~* '^https://[^[:space:]]+$'
    )
  )
);

create index if not exists research_category_source_ledger_timeline_idx
  on content_factory.research_category_source_ledger
  (organization_id, market_category_id, registered_at desc, id desc);
create index if not exists research_category_source_ledger_run_idx
  on content_factory.research_category_source_ledger
  (organization_id, run_id, source_id, registered_at desc);

create table if not exists content_factory.research_source_analysis_events (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  source_ledger_id uuid not null,
  analysis_version integer not null check (
    analysis_version between 1 and 100000
  ),
  parent_event_id uuid,
  expected_parent_hash text check (
    expected_parent_hash is null
    or expected_parent_hash ~ '^[0-9a-f]{64}$'
  ),
  origin text not null check (origin in ('system_parser', 'human_correction')),
  actor_id uuid,
  parser_key text not null check (
    parser_key ~ '^[a-z][a-z0-9_.-]{1,79}$'
  ),
  parser_version text not null check (
    length(btrim(parser_version)) between 1 and 120
  ),
  analysis jsonb not null check (
    content_factory_private.research_source_analysis_is_valid(analysis)
  ),
  correction_reason text check (
    correction_reason is null
    or length(btrim(correction_reason)) between 3 and 1000
  ),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  created_at timestamptz not null default now(),
  constraint research_source_analysis_events_org_id_uq
    unique (organization_id, id),
  constraint research_source_analysis_events_ledger_id_uq
    unique (organization_id, source_ledger_id, id),
  constraint research_source_analysis_events_version_uq
    unique (organization_id, source_ledger_id, analysis_version),
  constraint research_source_analysis_events_hash_uq
    unique (organization_id, event_hash),
  constraint research_source_analysis_events_key_uq
    unique (organization_id, idempotency_key),
  foreign key (organization_id, source_ledger_id)
    references content_factory.research_category_source_ledger(
      organization_id, id
    ),
  foreign key (organization_id, source_ledger_id, parent_event_id)
    references content_factory.research_source_analysis_events(
      organization_id, source_ledger_id, id
    ),
  foreign key (organization_id, actor_id)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (analysis_version = 1 and parent_event_id is null
      and expected_parent_hash is null)
    or (analysis_version > 1 and parent_event_id is not null
      and expected_parent_hash is not null)
  ),
  check (
    (origin = 'system_parser' and actor_id is null
      and correction_reason is null)
    or (origin = 'human_correction' and actor_id is not null
      and correction_reason is not null)
  )
);

create index if not exists research_source_analysis_events_head_idx
  on content_factory.research_source_analysis_events
  (organization_id, source_ledger_id, analysis_version desc, id desc);

create table if not exists content_factory.research_category_readiness_snapshots (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  market_category_id uuid not null,
  product_id uuid not null,
  binding_id uuid not null,
  run_id uuid not null,
  definition_version text not null check (
    definition_version = 'category-evidence-readiness-v1'
  ),
  score integer not null check (score between 0 and 100),
  dimensions jsonb not null check (
    jsonb_typeof(dimensions) = 'array'
    and jsonb_array_length(dimensions) = 6
    and length(dimensions::text) <= 32768
  ),
  evidence_hash text not null check (evidence_hash ~ '^[0-9a-f]{64}$'),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  snapshot_hash text not null check (snapshot_hash ~ '^[0-9a-f]{64}$'),
  captured_by uuid not null,
  capture_kind text not null check (capture_kind = 'creator_explicit'),
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  captured_at timestamptz not null default now(),
  constraint research_category_readiness_snapshots_org_id_uq
    unique (organization_id, id),
  constraint research_category_readiness_snapshots_evidence_uq
    unique (organization_id, market_category_id, evidence_hash),
  constraint research_category_readiness_snapshots_hash_uq
    unique (organization_id, snapshot_hash),
  constraint research_category_readiness_snapshots_key_uq
    unique (organization_id, idempotency_key),
  foreign key (organization_id, market_category_id)
    references content_factory.research_market_categories(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, captured_by)
    references content_factory.memberships(organization_id, profile_id)
);

create index if not exists research_category_readiness_timeline_idx
  on content_factory.research_category_readiness_snapshots
  (organization_id, market_category_id, captured_at desc, id desc);

create table if not exists content_factory.research_source_collection_policies (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  product_id uuid not null,
  run_id uuid not null,
  binding_id uuid not null,
  market_category_id uuid not null,
  platform text not null check (platform in ('youtube', 'instagram')),
  provider_key text not null check (
    provider_key ~ '^[a-z][a-z0-9_.-]{1,79}$'
  ),
  policy_version integer not null check (policy_version between 1 and 100000),
  previous_policy_id uuid,
  status text not null check (status in ('paused', 'enabled')),
  automatic_collection_ack boolean not null,
  terms_version text not null check (length(btrim(terms_version)) between 3 and 80),
  terms_ack boolean not null,
  quota_ack boolean not null,
  no_retry_ack boolean not null,
  cadence_hours integer not null check (cadence_hours between 24 and 720),
  max_records integer not null check (max_records between 1 and 25),
  monthly_hard_budget_units integer not null check (
    monthly_hard_budget_units between 0 and 100
  ),
  legal_review_reference text check (
    legal_review_reference is null
    or length(btrim(legal_review_reference)) between 3 and 160
  ),
  reason text not null check (length(btrim(reason)) between 3 and 500),
  created_by uuid not null,
  created_at timestamptz not null default now(),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  policy_hash text not null check (policy_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  constraint research_source_collection_policies_org_id_uq
    unique (organization_id, id),
  constraint research_source_collection_policies_chain_id_uq
    unique (organization_id, product_id, platform, id),
  constraint research_source_collection_policies_version_uq
    unique (organization_id, product_id, platform, policy_version),
  constraint research_source_collection_policies_hash_uq
    unique (organization_id, policy_hash),
  constraint research_source_collection_policies_key_uq
    unique (organization_id, idempotency_key),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  foreign key (organization_id, product_id, platform, previous_policy_id)
    references content_factory.research_source_collection_policies(
      organization_id, product_id, platform, id
    ),
  foreign key (organization_id, created_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (policy_version = 1 and previous_policy_id is null)
    or (policy_version > 1 and previous_policy_id is not null)
  ),
  check (
    status = 'paused'
    or (
      platform = 'youtube'
      and provider_key = 'youtube_data_api_v3'
      and automatic_collection_ack
      and terms_version = 'youtube-developer-policies-2026-08-03-v1'
      and terms_ack and quota_ack and no_retry_ack
      and monthly_hard_budget_units >= 2
      and legal_review_reference is not null
    )
  ),
  -- Instagram stays fail-closed until a provider and legal policy are selected.
  check (platform <> 'instagram' or status = 'paused')
);

create index if not exists research_source_collection_policy_current_idx
  on content_factory.research_source_collection_policies
  (organization_id, product_id, platform, policy_version desc, id desc);

create table if not exists content_factory.research_source_collection_intents (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  policy_id uuid not null,
  policy_hash text not null check (policy_hash ~ '^[0-9a-f]{64}$'),
  product_id uuid not null,
  run_id uuid not null,
  binding_id uuid not null,
  market_category_id uuid not null,
  platform text not null check (platform in ('youtube', 'instagram')),
  provider_key text not null check (
    provider_key ~ '^[a-z][a-z0-9_.-]{1,79}$'
  ),
  ingestion_id uuid,
  status text not null check (status in ('queued', 'blocked')),
  capability text not null check (capability in (
    'automatic_youtube_enqueue', 'automatic_collection_unavailable'
  )),
  blocked_reason text check (blocked_reason is null or blocked_reason in (
    'category_binding_stale', 'provider_contract_closed',
    'retention_control_unavailable', 'global_rollout_gate_closed',
    'organization_rollout_gate_closed', 'monthly_hard_budget_exhausted',
    'instagram_provider_legal_choice_required', 'policy_creator_inactive',
    'category_inactive', 'policy_ack_invalid'
  )),
  query_text text not null check (length(btrim(query_text)) between 2 and 200),
  max_records integer not null check (max_records between 1 and 25),
  planned_quota_units integer not null check (
    planned_quota_units between 0 and 2
  ),
  monthly_hard_budget_units integer not null check (
    monthly_hard_budget_units between 0 and 100
  ),
  monthly_reserved_units integer not null check (
    monthly_reserved_units between 0 and 100000
  ),
  scheduled_for timestamptz not null,
  automatic_enqueue_supported boolean not null,
  external_call_started boolean not null check (not external_call_started),
  no_retry boolean not null check (no_retry),
  no_fallback boolean not null check (no_fallback),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  intent_hash text not null check (intent_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  created_at timestamptz not null default now(),
  constraint research_source_collection_intents_org_id_uq
    unique (organization_id, id),
  constraint research_source_collection_intents_policy_due_uq
    unique (organization_id, policy_id, scheduled_for),
  constraint research_source_collection_intents_hash_uq
    unique (organization_id, intent_hash),
  constraint research_source_collection_intents_key_uq
    unique (organization_id, idempotency_key),
  foreign key (organization_id, policy_id)
    references content_factory.research_source_collection_policies(
      organization_id, id
    ),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(
      organization_id, id
    ),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  check (
    (status = 'queued' and blocked_reason is null
      and capability = 'automatic_youtube_enqueue'
      and platform = 'youtube' and provider_key = 'youtube_data_api_v3'
      and planned_quota_units = 2 and ingestion_id is not null
      and automatic_enqueue_supported)
    or (status = 'blocked' and blocked_reason is not null
      and capability = 'automatic_collection_unavailable'
      and planned_quota_units = 0 and ingestion_id is null
      and not automatic_enqueue_supported)
  )
);

create index if not exists research_source_collection_intent_timeline_idx
  on content_factory.research_source_collection_intents
  (organization_id, market_category_id, created_at desc, id desc);

alter table content_factory.research_category_source_ledger
  enable row level security;
alter table content_factory.research_source_analysis_events
  enable row level security;
alter table content_factory.research_category_readiness_snapshots
  enable row level security;
alter table content_factory.research_source_collection_policies
  enable row level security;
alter table content_factory.research_source_collection_intents
  enable row level security;

revoke all on table content_factory.research_category_source_ledger
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_source_analysis_events
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_category_readiness_snapshots
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_source_collection_policies
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_source_collection_intents
  from public, anon, authenticated, service_role;

grant all on table content_factory.research_category_source_ledger to service_role;
grant all on table content_factory.research_source_analysis_events to service_role;
grant all on table content_factory.research_category_readiness_snapshots to service_role;
grant all on table content_factory.research_source_collection_policies to service_role;
grant all on table content_factory.research_source_collection_intents to service_role;

create or replace function content_factory_private.reject_research_category_learning_mutation()
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

create trigger reject_research_category_source_ledger_mutation
before update or delete on content_factory.research_category_source_ledger
for each row execute function
  content_factory_private.reject_research_category_learning_mutation();
create trigger reject_research_source_analysis_event_mutation
before update or delete on content_factory.research_source_analysis_events
for each row execute function
  content_factory_private.reject_research_category_learning_mutation();
create trigger reject_research_category_readiness_snapshot_mutation
before update or delete on content_factory.research_category_readiness_snapshots
for each row execute function
  content_factory_private.reject_research_category_learning_mutation();
create trigger reject_research_source_collection_policy_mutation
before update or delete on content_factory.research_source_collection_policies
for each row execute function
  content_factory_private.reject_research_category_learning_mutation();
create trigger reject_research_source_collection_intent_mutation
before update or delete on content_factory.research_source_collection_intents
for each row execute function
  content_factory_private.reject_research_category_learning_mutation();

create or replace function content_factory_private.research_readiness_dimension(
  dimension_key_value text,
  label_value text,
  weight_value integer,
  current_value integer,
  target_value integer,
  next_action_value text
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'key', dimension_key_value,
    'label', label_value,
    'weight', weight_value,
    'current', greatest(current_value, 0),
    'target', target_value,
    'score', least(
      100,
      floor(100.0 * greatest(current_value, 0) / target_value)::integer
    ),
    'weighted_points', least(
      weight_value,
      floor(
        weight_value::numeric * least(
          100,
          floor(100.0 * greatest(current_value, 0) / target_value)::integer
        ) / 100.0
      )::integer
    ),
    'missing', greatest(target_value - greatest(current_value, 0), 0),
    'next_action', case
      when current_value >= target_value then null
      else next_action_value
    end
  )
$$;

create or replace function content_factory_private.research_category_evidence_readiness(
  organization_id_value uuid,
  market_category_id_value uuid,
  as_of_value timestamptz default clock_timestamp()
)
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  source_count_value integer := 0;
  platform_count_value integer := 0;
  competitor_count_value integer := 0;
  trend_count_value integer := 0;
  analysis_count_value integer := 0;
  human_validation_count_value integer := 0;
  youtube_source_count_value integer := 0;
  youtube_channel_count_value integer := 0;
  youtube_confirmed_count_value integer := 0;
  durable_youtube_present_value boolean := false;
  source_hashes_value jsonb := '[]'::jsonb;
  analysis_hashes_value jsonb := '[]'::jsonb;
  trend_hashes_value jsonb := '[]'::jsonb;
  youtube_observation_hashes_value jsonb := '[]'::jsonb;
  youtube_decision_hashes_value jsonb := '[]'::jsonb;
  dimensions_value jsonb;
  score_value integer;
  evidence_hash_value text;
begin
  with current_analysis as (
    select distinct on (event.source_ledger_id)
      event.source_ledger_id,
      event.analysis ->> 'classification' as classification
    from content_factory.research_source_analysis_events event
    where event.organization_id = organization_id_value
    order by event.source_ledger_id, event.analysis_version desc, event.id desc
  ), current_sources as (
    select distinct on (ledger.source_identity_key) ledger.*
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = market_category_id_value
    order by ledger.source_identity_key, ledger.registered_at desc,
      ledger.id desc
  ), eligible_sources as (
    select ledger.id, ledger.source_identity_key, ledger.platform,
      ledger.source_type, ledger.lineage_hash, analysis.classification
    from current_sources ledger
    left join current_analysis analysis
      on analysis.source_ledger_id = ledger.id
    where analysis.classification is distinct from 'irrelevant'
  )
  select count(*)::integer,
         count(distinct source.platform)::integer,
         count(distinct source.source_identity_key) filter (
           where source.classification = 'competitor'
         )::integer,
         coalesce(
           jsonb_agg(source.lineage_hash order by source.lineage_hash),
           '[]'::jsonb
         ),
         coalesce(bool_or(source.platform = 'youtube'), false)
  into source_count_value, platform_count_value, competitor_count_value,
       source_hashes_value, durable_youtube_present_value
  from eligible_sources source;

  with current_sources as (
    select distinct on (ledger.source_identity_key) ledger.id
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = market_category_id_value
    order by ledger.source_identity_key, ledger.registered_at desc,
      ledger.id desc
  ), current_analysis as (
    select distinct on (event.source_ledger_id)
      event.source_ledger_id, event.origin, event.event_hash
    from content_factory.research_source_analysis_events event
    join current_sources source on source.id = event.source_ledger_id
    where event.organization_id = organization_id_value
    order by event.source_ledger_id, event.analysis_version desc, event.id desc
  )
  select count(*)::integer,
         count(*) filter (
           where current_analysis.origin = 'human_correction'
         )::integer,
         coalesce(
           jsonb_agg(
             current_analysis.event_hash order by current_analysis.event_hash
           ),
           '[]'::jsonb
         )
  into analysis_count_value, human_validation_count_value,
       analysis_hashes_value
  from current_analysis;

  with latest_observations as (
    select distinct on (observation.video_id)
      observation.*
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = organization_id_value
      and observation.market_category_id = market_category_id_value
      and observation.retention_expires_at > as_of_value
      and observation.observed_at <= as_of_value
    order by observation.video_id, observation.observed_at desc,
      observation.id desc
  ), observed_with_decision as (
    select observation.*,
      decision.decision, decision.decision_hash
    from latest_observations observation
    left join lateral (
      select candidate.decision, candidate.decision_hash
      from content_factory.research_youtube_candidate_decisions candidate
      where candidate.organization_id = observation.organization_id
        and candidate.observation_id = observation.id
        and candidate.retention_expires_at > as_of_value
        and candidate.decided_at <= as_of_value
      order by candidate.decided_at desc, candidate.id desc
      limit 1
    ) decision on true
  ), eligible as (
    select observed.*
    from observed_with_decision observed
    where observed.decision is distinct from 'exclude_candidate'
  )
  select
    (select count(distinct evidence.video_id)::integer from eligible evidence),
    (select count(distinct evidence.channel_id)::integer from eligible evidence),
    (select count(distinct evidence.video_id)::integer
     from eligible evidence
     where evidence.decision = 'confirm_candidate'),
    (select coalesce(
       jsonb_agg(observed.observation_hash order by observed.observation_hash),
       '[]'::jsonb
     ) from observed_with_decision observed),
    (select coalesce(
       jsonb_agg(observed.decision_hash order by observed.decision_hash)
         filter (where observed.decision_hash is not null),
       '[]'::jsonb
     ) from observed_with_decision observed)
  into youtube_source_count_value, youtube_channel_count_value,
       youtube_confirmed_count_value, youtube_observation_hashes_value,
       youtube_decision_hashes_value;

  source_count_value := source_count_value + youtube_source_count_value;
  if youtube_source_count_value > 0 and not durable_youtube_present_value then
    platform_count_value := platform_count_value + 1;
  end if;
  competitor_count_value :=
    competitor_count_value + youtube_channel_count_value;
  analysis_count_value := analysis_count_value + youtube_source_count_value;
  human_validation_count_value :=
    human_validation_count_value + youtube_confirmed_count_value;

  with recent_signals as (
    select signal.signal_key, signal.evidence_hash
    from content_factory.research_watchlist_snapshot_trend_signals signal
    where signal.organization_id = organization_id_value
      and signal.market_category_id = market_category_id_value
      and signal.observed_at >= as_of_value - interval '30 days'
      and signal.observed_at <= as_of_value
  ), distinct_hashes as (
    select distinct signal.evidence_hash
    from recent_signals signal
  )
  select (select count(distinct signal.signal_key)::integer
          from recent_signals signal),
         (select coalesce(
            jsonb_agg(hash.evidence_hash order by hash.evidence_hash),
            '[]'::jsonb
          ) from distinct_hashes hash)
  into trend_count_value, trend_hashes_value
  ;

  dimensions_value := jsonb_build_array(
    content_factory_private.research_readiness_dimension(
      'source_volume', 'Current reviewable source volume', 20,
      source_count_value, 12, 'collect_more_reviewable_sources'
    ),
    content_factory_private.research_readiness_dimension(
      'platform_diversity', 'Platform diversity', 15,
      platform_count_value, 3, 'add_an_independent_platform'
    ),
    content_factory_private.research_readiness_dimension(
      'competitor_observations',
      'Competitor observations / retained YouTube channels', 20,
      competitor_count_value, 5, 'collect_competitor_observations'
    ),
    content_factory_private.research_readiness_dimension(
      'trend_recency', 'Recent canonical trend evidence', 15,
      trend_count_value, 6, 'refresh_canonical_trend_evidence'
    ),
    content_factory_private.research_readiness_dimension(
      'analysis_coverage', 'Structured / normalized source coverage', 15,
      analysis_count_value, 8, 'analyze_unreviewed_sources'
    ),
    content_factory_private.research_readiness_dimension(
      'human_validation', 'Human-validated evidence', 15,
      human_validation_count_value, 4, 'review_and_correct_source_analysis'
    )
  );

  select coalesce(sum((dimension ->> 'weighted_points')::integer), 0)::integer
  into score_value
  from jsonb_array_elements(dimensions_value) dimension;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'definition_version', 'category-evidence-readiness-v1',
    'organization_id', organization_id_value,
    'market_category_id', market_category_id_value,
    'source_lineage_hashes', source_hashes_value,
    'analysis_event_hashes', analysis_hashes_value,
    'current_retained_youtube_observation_hashes',
      youtube_observation_hashes_value,
    'current_retained_youtube_decision_hashes', youtube_decision_hashes_value,
    'recent_trend_evidence_hashes', trend_hashes_value,
    'dimensions', dimensions_value
  ));

  return jsonb_build_object(
    'metric_kind', 'category_evidence_readiness_not_model_iq',
    'definition_version', 'category-evidence-readiness-v1',
    'score', score_value,
    'dimensions', dimensions_value,
    'weights_total', 100,
    'evidence_hash', evidence_hash_value,
    'as_of', as_of_value,
    'limits', jsonb_build_object(
      'is_model_iq', false,
      'is_quality_guarantee', false,
      'competitor_metric_is_unique_publishers', false,
      'retained_youtube_uses_unique_channel_ids', true,
      'youtube_retention_days', 29,
      'meaning',
        'Coverage of durable evidence plus current retention-bound YouTube metadata'
    )
  );
end;
$$;

create or replace function public.creator_research_category_learning_status(
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
  run_id_value uuid;
  product_id_value uuid;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  category_row content_factory.research_market_categories%rowtype;
  readiness_value jsonb;
  sources_value jsonb := '[]'::jsonb;
  snapshots_value jsonb := '[]'::jsonb;
  policies_value jsonb := '[]'::jsonb;
  intents_value jsonb := '[]'::jsonb;
  youtube_evidence_value jsonb := '[]'::jsonb;
  gaps_value jsonb := '[]'::jsonb;
  as_of_value timestamptz := clock_timestamp();
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_category_learning_status_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

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
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );

  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_required';
  end if;
  select category.* into category_row
  from content_factory.research_market_categories category
  where category.organization_id = organization_id_value
    and category.id = binding_row.category_id
    and category.status = 'active';
  if category_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_inactive';
  end if;

  readiness_value :=
    content_factory_private.research_category_evidence_readiness(
      organization_id_value, binding_row.category_id, as_of_value
    );

  with bounded_sources as (
    select distinct on (ledger.source_identity_key) ledger.*
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = binding_row.category_id
    order by ledger.source_identity_key, ledger.registered_at desc,
      ledger.id desc
  ), limited_sources as (
    select source.*
    from bounded_sources source
    order by source.registered_at desc, source.id desc
    limit 50
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'source_ledger_id', source.id,
    'source_id', source.source_id,
    'run_id', source.run_id,
    'product_id', source.product_id,
    'source_type', source.source_type,
    'title', source.title,
    'source_url', source.source_url,
    'provider_key', source.provider_key,
    'platform', source.platform,
    'trust_level', source.trust_level,
    'source_identity_key', source.source_identity_key,
    'fetched_at', source.fetched_at,
    'published_at', source.published_at,
    'lineage_hash', source.lineage_hash,
    'registered_at', source.registered_at,
    'lineage_history', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_ledger_id', lineage.id,
        'source_id', lineage.source_id,
        'source_content_hash', lineage.source_content_hash,
        'lineage_hash', lineage.lineage_hash,
        'fetched_at', lineage.fetched_at,
        'published_at', lineage.published_at,
        'registered_at', lineage.registered_at
      ) order by lineage.registered_at desc, lineage.id desc), '[]'::jsonb)
      from (
        select version.*
        from content_factory.research_category_source_ledger version
        where version.organization_id = source.organization_id
          and version.market_category_id = source.market_category_id
          and version.source_identity_key = source.source_identity_key
        order by version.registered_at desc, version.id desc
        limit 10
      ) lineage
    ),
    'current_analysis', (
      select jsonb_build_object(
        'event_id', head.id,
        'analysis_version', head.analysis_version,
        'origin', head.origin,
        'parser_key', head.parser_key,
        'parser_version', head.parser_version,
        'analysis', head.analysis,
        'correction_reason', head.correction_reason,
        'event_hash', head.event_hash,
        'created_at', head.created_at
      )
      from content_factory.research_source_analysis_events head
      where head.organization_id = source.organization_id
        and head.source_ledger_id = source.id
      order by head.analysis_version desc, head.id desc
      limit 1
    ),
    'analysis_history', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', history.id,
        'analysis_version', history.analysis_version,
        'parent_event_id', history.parent_event_id,
        'origin', history.origin,
        'actor_id', history.actor_id,
        'parser_key', history.parser_key,
        'parser_version', history.parser_version,
        'analysis', history.analysis,
        'correction_reason', history.correction_reason,
        'event_hash', history.event_hash,
        'created_at', history.created_at
      ) order by history.analysis_version desc), '[]'::jsonb)
      from (
        select event.*
        from content_factory.research_source_analysis_events event
        where event.organization_id = source.organization_id
          and event.source_ledger_id = source.id
        order by event.analysis_version desc, event.id desc
        limit 10
      ) history
    )
  ) order by source.registered_at desc, source.id desc), '[]'::jsonb)
  into sources_value
  from limited_sources source;

  with latest_observations as (
    select distinct on (observation.video_id) observation.*
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = organization_id_value
      and observation.market_category_id = binding_row.category_id
      and observation.retention_expires_at > as_of_value
      and observation.observed_at <= as_of_value
    order by observation.video_id, observation.observed_at desc,
      observation.id desc
  ), bounded_observations as (
    select observation.*
    from latest_observations observation
    order by observation.observed_at desc, observation.id desc
    limit 50
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'source_kind', 'retained_youtube_observation',
    'observation_id', observation.id,
    'ingestion_id', observation.ingestion_id,
    'source_url', 'https://www.youtube.com/watch?v=' || observation.video_id,
    'provider_key', 'youtube_data_api_v3',
    'platform', 'youtube',
    'video_id', observation.video_id,
    'channel_id', observation.channel_id,
    'title', observation.title,
    'channel_title', observation.channel_title,
    'published_at', observation.published_at,
    'observed_at', observation.observed_at,
    'retention_expires_at', observation.retention_expires_at,
    'observation_hash', observation.observation_hash,
    'latest_decision', (
      select jsonb_build_object(
        'decision_id', decision.id,
        'decision', decision.decision,
        'reason', decision.reason,
        'decided_by', decision.decided_by,
        'decided_at', decision.decided_at,
        'decision_hash', decision.decision_hash
      )
      from content_factory.research_youtube_candidate_decisions decision
      where decision.organization_id = observation.organization_id
        and decision.observation_id = observation.id
        and decision.retention_expires_at > as_of_value
        and decision.decided_at <= as_of_value
      order by decision.decided_at desc, decision.id desc
      limit 1
    ),
    'included_in_readiness', coalesce((
      select decision.decision <> 'exclude_candidate'
      from content_factory.research_youtube_candidate_decisions decision
      where decision.organization_id = observation.organization_id
        and decision.observation_id = observation.id
        and decision.retention_expires_at > as_of_value
        and decision.decided_at <= as_of_value
      order by decision.decided_at desc, decision.id desc
      limit 1
    ), true)
  ) order by observation.observed_at desc, observation.id desc), '[]'::jsonb)
  into youtube_evidence_value
  from bounded_observations observation;

  select coalesce(jsonb_agg(jsonb_build_object(
    'snapshot_id', snapshot.id,
    'definition_version', snapshot.definition_version,
    'score', snapshot.score,
    'dimensions', snapshot.dimensions,
    'evidence_hash', snapshot.evidence_hash,
    'snapshot_hash', snapshot.snapshot_hash,
    'captured_by', snapshot.captured_by,
    'captured_at', snapshot.captured_at
  ) order by snapshot.captured_at desc, snapshot.id desc), '[]'::jsonb)
  into snapshots_value
  from (
    select bounded_snapshot.*
    from content_factory.research_category_readiness_snapshots bounded_snapshot
    where bounded_snapshot.organization_id = organization_id_value
      and bounded_snapshot.market_category_id = binding_row.category_id
    order by bounded_snapshot.captured_at desc, bounded_snapshot.id desc
    limit 24
  ) snapshot;

  with current_policies as (
    select distinct on (policy.platform) policy.*
    from content_factory.research_source_collection_policies policy
    where policy.organization_id = organization_id_value
      and policy.product_id = product_id_value
    order by policy.platform, policy.policy_version desc, policy.id desc
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'policy_id', policy.id,
    'policy_hash', policy.policy_hash,
    'policy_version', policy.policy_version,
    'platform', policy.platform,
    'provider_key', policy.provider_key,
    'status', policy.status,
    'automatic_collection_ack', policy.automatic_collection_ack,
    'terms_version', policy.terms_version,
    'terms_ack', policy.terms_ack,
    'quota_ack', policy.quota_ack,
    'no_retry_ack', policy.no_retry_ack,
    'cadence_hours', policy.cadence_hours,
    'max_records', policy.max_records,
    'monthly_hard_budget_units', policy.monthly_hard_budget_units,
    'legal_review_reference', policy.legal_review_reference,
    'reason', policy.reason,
    'created_at', policy.created_at,
    'automatic_enqueue_supported', (
      policy.status = 'enabled'
      and policy.platform = 'youtube'
      and policy.provider_key = 'youtube_data_api_v3'
      and policy.automatic_collection_ack
      and policy.terms_version = 'youtube-developer-policies-2026-08-03-v1'
      and policy.terms_ack and policy.quota_ack and policy.no_retry_ack
    ),
    'handoff', case
      when policy.status = 'enabled' and policy.platform = 'youtube'
        then 'automatic_youtube_ingestion_queue'
      when policy.platform = 'instagram'
        then 'provider_and_legal_choice_required'
      else null
    end
  ) order by policy.platform), '[]'::jsonb)
  into policies_value
  from current_policies policy;

  select coalesce(jsonb_agg(jsonb_build_object(
    'intent_id', intent.id,
    'policy_id', intent.policy_id,
    'platform', intent.platform,
    'provider_key', intent.provider_key,
    'ingestion_id', intent.ingestion_id,
    'status', intent.status,
    'capability', intent.capability,
    'blocked_reason', intent.blocked_reason,
    'query_text', intent.query_text,
    'max_records', intent.max_records,
    'planned_quota_units', intent.planned_quota_units,
    'monthly_hard_budget_units', intent.monthly_hard_budget_units,
    'monthly_reserved_units', intent.monthly_reserved_units,
    'scheduled_for', intent.scheduled_for,
    'automatic_enqueue_supported', intent.automatic_enqueue_supported,
    'external_call_started', intent.external_call_started,
    'no_retry', intent.no_retry,
    'no_fallback', intent.no_fallback,
    'intent_hash', intent.intent_hash,
    'created_at', intent.created_at,
    'ingestion_status', ingestion.status,
    'ingestion_error_code', ingestion.error_code,
    'ingestion_requested_at', ingestion.requested_at,
    'ingestion_completed_at', ingestion.completed_at,
    'transport_attempt_count', coalesce((
      select count(*)::integer
      from content_factory.research_youtube_transport_attempts transport
      where transport.organization_id = intent.organization_id
        and transport.ingestion_id = intent.ingestion_id
    ), 0)
  ) order by intent.created_at desc, intent.id desc), '[]'::jsonb)
  into intents_value
  from (
    select bounded_intent.*
    from content_factory.research_source_collection_intents bounded_intent
    where bounded_intent.organization_id = organization_id_value
      and bounded_intent.product_id = product_id_value
      and bounded_intent.market_category_id = binding_row.category_id
    order by bounded_intent.created_at desc, bounded_intent.id desc
    limit 24
  ) intent
  left join content_factory.research_youtube_ingestion_runs ingestion
    on ingestion.organization_id = intent.organization_id
   and ingestion.id = intent.ingestion_id;

  select coalesce(jsonb_agg(dimension order by ordinal), '[]'::jsonb)
  into gaps_value
  from jsonb_array_elements(readiness_value -> 'dimensions')
    with ordinality missing_dimension(dimension, ordinal)
  where (dimension ->> 'missing')::integer > 0;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-category-learning-readiness-v1',
    'organization_id', organization_id_value,
    'run_id', run_id_value,
    'metric', jsonb_build_object(
      'label', 'Category evidence readiness',
      'kind', 'category_evidence_readiness_not_model_iq',
      'is_ai_iq', false,
      'readiness', readiness_value
    ),
    'category', jsonb_build_object(
      'category_id', category_row.id,
      'canonical_name', category_row.canonical_name,
      'definition', category_row.definition,
      'binding_id', binding_row.id,
      'binding_version', binding_row.binding_version
    ),
    'source_ledger', jsonb_build_object(
      'items', sources_value,
      'item_limit', 50,
      'analysis_history_limit_per_source', 10,
      'lineage_history_limit_per_source', 10,
      'raw_captions_stored', false
    ),
    'retained_youtube_evidence', jsonb_build_object(
      'items', youtube_evidence_value,
      'item_limit', 50,
      'retention_days', 29,
      'raw_captions_stored', false,
      'corrected_by', 'creator_decide_research_youtube_candidate'
    ),
    'readiness_history', jsonb_build_object(
      'items', snapshots_value,
      'item_limit', 24,
      'captured_only_by_mutation', true
    ),
    'collection', jsonb_build_object(
      'default_status', 'paused',
      'policies', policies_value,
      'history', intents_value,
      'history_limit', 24,
      'scheduler_starts_external_calls', false,
      'automatic_retry_allowed', false,
      'automatic_fallback_allowed', false,
      'instagram_automatic_collection', 'blocked_pending_provider_and_legal_choice'
    ),
    'guidance', jsonb_build_object(
      'status', case
        when (readiness_value ->> 'score')::integer >= 80 then 'strong_evidence'
        when (readiness_value ->> 'score')::integer >= 50 then 'developing_evidence'
        else 'insufficient_evidence'
      end,
      'gaps', gaps_value,
      'expected_evidence_hash', readiness_value ->> 'evidence_hash',
      'score_is_not_model_iq', true
    )
  );
end;
$$;

create or replace function public.creator_capture_research_category_readiness(
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
  run_id_value uuid;
  product_id_value uuid;
  expected_evidence_hash_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  before_value jsonb;
  readiness_value jsonb;
  snapshot_row content_factory.research_category_readiness_snapshots%rowtype;
  registered_count_value integer := 0;
  result_value jsonb;
  as_of_value timestamptz := clock_timestamp();
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'expected_evidence_hash', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_category_readiness_capture_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  expected_evidence_hash_value := content_factory_private.require_text(
    p_payload, 'expected_evidence_hash', 64, 64
  );
  if expected_evidence_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'expected_evidence_hash_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

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
    organization_id_value,
    false,
    array['owner', 'admin', 'producer']
  );
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id_value,
    'creator_capture_research_category_readiness',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-category-readiness:' || product_id_value::text)
  );
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_required';
  end if;

  before_value := content_factory_private.research_category_evidence_readiness(
    organization_id_value, binding_row.category_id, as_of_value
  );
  if before_value ->> 'evidence_hash' <> expected_evidence_hash_value then
    raise exception using
      errcode = '40001', message = 'research_category_evidence_changed';
  end if;

  with candidate_sources as (
    select source.*,
      case
        when lower(coalesce(source.metadata ->> 'platform', '')) in (
          'youtube', 'instagram', 'marketplace', 'web', 'first_party', 'other'
        ) then lower(source.metadata ->> 'platform')
        when source.source_url ~* '^https://([^/]+[.])?(youtube[.]com|youtu[.]be)/'
          then 'youtube'
        when source.source_url ~* '^https://([^/]+[.])?instagram[.]com/'
          then 'instagram'
        when source.source_type = 'marketplace_page' then 'marketplace'
        when source.source_type in ('user_input', 'product_photo') then 'first_party'
        when source.source_url is not null then 'web'
        else 'other'
      end as platform_value,
      case
        when lower(coalesce(source.metadata ->> 'provider_key', ''))
          ~ '^[a-z][a-z0-9_.-]{1,79}$'
          then lower(source.metadata ->> 'provider_key')
        when source.metadata -> 'provider_citation_verified' = 'true'::jsonb
          then 'openai_web_search'
        else 'user_supplied'
      end as provider_key_value
    from content_factory.product_research_sources source
    where source.organization_id = organization_id_value
      and source.run_id = run_id_value
      and source.product_id = product_id_value
    order by source.created_at, source.id
    limit 100
  ), inserted as (
    insert into content_factory.research_category_source_ledger (
      organization_id, market_category_id, product_id, binding_id, run_id,
      source_id, source_type, title, source_url, provider_key, platform,
      trust_level, source_identity_key, source_content_hash,
      fetched_at, published_at,
      registered_by, lineage_hash
    )
    select
      organization_id_value, binding_row.category_id, product_id_value,
      binding_row.id, run_id_value, source.id, source.source_type,
      source.title, source.source_url, source.provider_key_value,
      source.platform_value, source.trust_level,
      content_factory_private.research_source_identity_key(
        source.source_url, source.content_hash
      ), source.content_hash,
      source.fetched_at, source.published_at, user_id,
      content_factory_private.json_hash(jsonb_build_object(
        'version', 'research-category-source-lineage-v1',
        'organization_id', organization_id_value,
        'market_category_id', binding_row.category_id,
        'product_id', product_id_value,
        'binding_id', binding_row.id,
        'run_id', run_id_value,
        'source_id', source.id,
        'source_type', source.source_type,
        'source_url', source.source_url,
        'provider_key', source.provider_key_value,
        'platform', source.platform_value,
        'trust_level', source.trust_level,
        'source_content_hash', source.content_hash,
        'fetched_at', source.fetched_at,
        'published_at', source.published_at
      ))
    from candidate_sources source
    on conflict do nothing
    returning id
  )
  select count(*)::integer into registered_count_value from inserted;

  readiness_value := content_factory_private.research_category_evidence_readiness(
    organization_id_value, binding_row.category_id, as_of_value
  );

  select snapshot.* into snapshot_row
  from content_factory.research_category_readiness_snapshots snapshot
  where snapshot.organization_id = organization_id_value
    and snapshot.market_category_id = binding_row.category_id
    and snapshot.evidence_hash = readiness_value ->> 'evidence_hash';
  if snapshot_row.id is null then
    insert into content_factory.research_category_readiness_snapshots (
      organization_id, market_category_id, product_id, binding_id, run_id,
      definition_version, score, dimensions, evidence_hash, request_hash,
      snapshot_hash, captured_by, capture_kind, idempotency_key
    ) values (
      organization_id_value, binding_row.category_id, product_id_value,
      binding_row.id, run_id_value, 'category-evidence-readiness-v1',
      (readiness_value ->> 'score')::integer,
      readiness_value -> 'dimensions', readiness_value ->> 'evidence_hash',
      content_factory_private.json_hash(request_payload),
      content_factory_private.json_hash(jsonb_build_object(
        'version', 'category-evidence-readiness-snapshot-v1',
        'organization_id', organization_id_value,
        'market_category_id', binding_row.category_id,
        'product_id', product_id_value,
        'binding_id', binding_row.id,
        'run_id', run_id_value,
        'evidence_hash', readiness_value ->> 'evidence_hash',
        'score', (readiness_value ->> 'score')::integer,
        'dimensions', readiness_value -> 'dimensions'
      )),
      user_id, 'creator_explicit', idempotency_key_value
    ) returning * into snapshot_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'metric_kind', 'category_evidence_readiness_not_model_iq',
    'source_ledger_rows_registered', registered_count_value,
    'snapshot', jsonb_build_object(
      'snapshot_id', snapshot_row.id,
      'score', snapshot_row.score,
      'dimensions', snapshot_row.dimensions,
      'evidence_hash', snapshot_row.evidence_hash,
      'snapshot_hash', snapshot_row.snapshot_hash,
      'captured_at', snapshot_row.captured_at
    ),
    'external_call_started', false
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_category_readiness_captured',
    'research_market_category',
    binding_row.category_id::text,
    jsonb_build_object(
      'score', snapshot_row.score,
      'evidence_hash', snapshot_row.evidence_hash,
      'source_ledger_rows_registered', registered_count_value,
      'metric_is_model_iq', false
    ),
    'research-category-readiness:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_capture_research_category_readiness',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.system_record_research_source_analysis(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  source_ledger_id_value uuid;
  expected_head_event_id_value uuid;
  expected_head_hash_value text;
  parser_key_value text;
  parser_version_value text;
  analysis_value jsonb;
  idempotency_key_value text;
  request_hash_value text;
  current_head content_factory.research_source_analysis_events%rowtype;
  replay content_factory.research_source_analysis_events%rowtype;
  event_row content_factory.research_source_analysis_events%rowtype;
  event_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'source_ledger_id', 'expected_head_event_id',
    'expected_head_hash', 'parser_key', 'parser_version', 'analysis',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_source_analysis_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  source_ledger_id_value := content_factory_private.require_uuid(
    p_payload, 'source_ledger_id'
  );
  parser_key_value := lower(content_factory_private.require_text(
    p_payload, 'parser_key', 2, 80
  ));
  parser_version_value := content_factory_private.require_text(
    p_payload, 'parser_version', 1, 120
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  analysis_value := p_payload -> 'analysis';
  if not coalesce(
    content_factory_private.research_source_analysis_is_valid(analysis_value),
    false
  ) then
    raise exception using
      errcode = '22023', message = 'research_source_analysis_invalid';
  end if;
  if parser_key_value !~ '^[a-z][a-z0-9_.-]{1,79}$' then
    raise exception using
      errcode = '22023', message = 'research_source_parser_key_invalid';
  end if;
  if (p_payload -> 'expected_head_event_id') is not null
     and jsonb_typeof(p_payload -> 'expected_head_event_id') <> 'null' then
    expected_head_event_id_value := content_factory_private.require_uuid(
      p_payload, 'expected_head_event_id'
    );
  end if;
  expected_head_hash_value := nullif(
    btrim(coalesce(p_payload ->> 'expected_head_hash', '')), ''
  );
  if (expected_head_event_id_value is null)
       <> (expected_head_hash_value is null)
     or (expected_head_hash_value is not null
       and expected_head_hash_value !~ '^[0-9a-f]{64}$') then
    raise exception using
      errcode = '22023', message = 'research_source_analysis_expected_head_invalid';
  end if;
  request_hash_value := content_factory_private.json_hash(
    p_payload - 'idempotency_key'
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-source-analysis:' || source_ledger_id_value::text)
  );
  select event.* into replay
  from content_factory.research_source_analysis_events event
  where event.organization_id = organization_id_value
    and event.idempotency_key = idempotency_key_value;
  if replay.id is not null then
    if replay.request_hash <> request_hash_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return jsonb_build_object(
      'ok', true, 'replayed', true,
      'event_id', replay.id, 'event_hash', replay.event_hash,
      'analysis_version', replay.analysis_version
    );
  end if;
  if not exists (
    select 1
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = organization_id_value
      and ledger.id = source_ledger_id_value
  ) then
    raise exception using
      errcode = '22023', message = 'research_source_ledger_not_found';
  end if;
  select event.* into current_head
  from content_factory.research_source_analysis_events event
  where event.organization_id = organization_id_value
    and event.source_ledger_id = source_ledger_id_value
  order by event.analysis_version desc, event.id desc
  limit 1;
  if current_head.id is null then
    if expected_head_event_id_value is not null then
      raise exception using
        errcode = '40001', message = 'research_source_analysis_head_stale';
    end if;
  elsif expected_head_event_id_value is distinct from current_head.id
     or expected_head_hash_value is distinct from current_head.event_hash then
    raise exception using
      errcode = '40001', message = 'research_source_analysis_head_stale';
  elsif current_head.origin = 'human_correction' then
    raise exception using
      errcode = '55000', message = 'research_source_analysis_human_head_protected';
  end if;

  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-source-analysis-event-v1',
    'organization_id', organization_id_value,
    'source_ledger_id', source_ledger_id_value,
    'analysis_version', coalesce(current_head.analysis_version, 0) + 1,
    'parent_event_id', current_head.id,
    'expected_parent_hash', current_head.event_hash,
    'origin', 'system_parser',
    'parser_key', parser_key_value,
    'parser_version', parser_version_value,
    'analysis', analysis_value
  ));
  insert into content_factory.research_source_analysis_events (
    organization_id, source_ledger_id, analysis_version, parent_event_id,
    expected_parent_hash, origin, actor_id, parser_key, parser_version,
    analysis, correction_reason, request_hash, event_hash, idempotency_key
  ) values (
    organization_id_value, source_ledger_id_value,
    coalesce(current_head.analysis_version, 0) + 1, current_head.id,
    current_head.event_hash, 'system_parser', null, parser_key_value,
    parser_version_value, analysis_value, null, request_hash_value,
    event_hash_value, idempotency_key_value
  ) returning * into event_row;
  return jsonb_build_object(
    'ok', true, 'replayed', false,
    'event_id', event_row.id, 'event_hash', event_row.event_hash,
    'analysis_version', event_row.analysis_version,
    'external_call_started', false
  );
end;
$$;

create or replace function public.creator_correct_research_source_analysis(
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
  source_ledger_id_value uuid;
  expected_head_event_id_value uuid;
  expected_head_hash_value text;
  correction_reason_value text;
  analysis_value jsonb;
  idempotency_key_value text;
  request_payload jsonb;
  replay_result jsonb;
  current_head content_factory.research_source_analysis_events%rowtype;
  event_row content_factory.research_source_analysis_events%rowtype;
  event_hash_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'source_ledger_id', 'expected_head_event_id',
    'expected_head_hash', 'analysis', 'correction_reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_source_correction_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  source_ledger_id_value := content_factory_private.require_uuid(
    p_payload, 'source_ledger_id'
  );
  expected_head_event_id_value := content_factory_private.require_uuid(
    p_payload, 'expected_head_event_id'
  );
  expected_head_hash_value := content_factory_private.require_text(
    p_payload, 'expected_head_hash', 64, 64
  );
  if expected_head_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'expected_head_hash_invalid';
  end if;
  correction_reason_value := content_factory_private.require_text(
    p_payload, 'correction_reason', 3, 1000
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  analysis_value := p_payload -> 'analysis';
  if not coalesce(
    content_factory_private.research_source_analysis_is_valid(analysis_value),
    false
  ) then
    raise exception using
      errcode = '22023', message = 'research_source_analysis_invalid';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  if not exists (
    select 1
    from content_factory.research_category_source_ledger ledger
    join content_factory.memberships membership
      on membership.organization_id = ledger.organization_id
     and membership.profile_id = user_id
     and membership.status = 'active'
    where ledger.organization_id = organization_id_value
      and ledger.id = source_ledger_id_value
  ) then
    raise exception using
      errcode = '22023', message = 'research_source_ledger_not_found';
  end if;
  request_payload := p_payload - 'idempotency_key';
  replay_result := content_factory_private.begin_command(
    organization_id_value,
    'creator_correct_research_source_analysis',
    idempotency_key_value,
    request_payload
  );
  if replay_result is not null then
    return replay_result;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-source-analysis:' || source_ledger_id_value::text)
  );
  select event.* into current_head
  from content_factory.research_source_analysis_events event
  where event.organization_id = organization_id_value
    and event.source_ledger_id = source_ledger_id_value
  order by event.analysis_version desc, event.id desc
  limit 1;
  if current_head.id is null
     or current_head.id <> expected_head_event_id_value
     or current_head.event_hash <> expected_head_hash_value then
    raise exception using
      errcode = '40001', message = 'research_source_analysis_head_stale';
  end if;
  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-source-analysis-event-v1',
    'organization_id', organization_id_value,
    'source_ledger_id', source_ledger_id_value,
    'analysis_version', current_head.analysis_version + 1,
    'parent_event_id', current_head.id,
    'expected_parent_hash', current_head.event_hash,
    'origin', 'human_correction',
    'actor_id', user_id,
    'analysis', analysis_value,
    'correction_reason', correction_reason_value
  ));
  insert into content_factory.research_source_analysis_events (
    organization_id, source_ledger_id, analysis_version, parent_event_id,
    expected_parent_hash, origin, actor_id, parser_key, parser_version,
    analysis, correction_reason, request_hash, event_hash, idempotency_key
  ) values (
    organization_id_value, source_ledger_id_value,
    current_head.analysis_version + 1, current_head.id,
    current_head.event_hash, 'human_correction', user_id,
    'human_correction', 'v1', analysis_value, correction_reason_value,
    content_factory_private.json_hash(request_payload), event_hash_value,
    idempotency_key_value
  ) returning * into event_row;
  result_value := jsonb_build_object(
    'ok', true,
    'event_id', event_row.id,
    'event_hash', event_row.event_hash,
    'analysis_version', event_row.analysis_version,
    'origin', event_row.origin,
    'external_call_started', false
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_source_analysis_corrected',
    'research_category_source',
    source_ledger_id_value::text,
    jsonb_build_object(
      'event_id', event_row.id,
      'analysis_version', event_row.analysis_version,
      'event_hash', event_row.event_hash
    ),
    'research-source-correction:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_correct_research_source_analysis',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_configure_research_source_collection_policy(
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
  run_id_value uuid;
  product_id_value uuid;
  platform_value text;
  provider_key_value text;
  status_value text;
  automatic_collection_ack_value boolean;
  terms_version_value text;
  terms_ack_value boolean;
  quota_ack_value boolean;
  no_retry_ack_value boolean;
  cadence_hours_value integer;
  max_records_value integer;
  monthly_hard_budget_units_value integer;
  legal_review_reference_value text;
  reason_value text;
  expected_policy_id_value uuid;
  expected_policy_hash_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay_result jsonb;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  current_policy content_factory.research_source_collection_policies%rowtype;
  policy_row content_factory.research_source_collection_policies%rowtype;
  policy_hash_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'platform', 'provider_key', 'status',
    'automatic_collection_ack', 'terms_version', 'terms_ack', 'quota_ack',
    'no_retry_ack', 'cadence_hours', 'max_records',
    'monthly_hard_budget_units', 'legal_review_reference', 'reason',
    'expected_policy_id', 'expected_policy_hash', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_collection_policy_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 20
  ));
  provider_key_value := lower(content_factory_private.require_text(
    p_payload, 'provider_key', 2, 80
  ));
  status_value := lower(content_factory_private.require_text(
    p_payload, 'status', 2, 20
  ));
  terms_version_value := content_factory_private.require_text(
    p_payload, 'terms_version', 3, 80
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if platform_value not in ('youtube', 'instagram')
     or status_value not in ('paused', 'enabled')
     or provider_key_value !~ '^[a-z][a-z0-9_.-]{1,79}$'
     or jsonb_typeof(p_payload -> 'automatic_collection_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'terms_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'quota_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'no_retry_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'cadence_hours') <> 'number'
     or jsonb_typeof(p_payload -> 'max_records') <> 'number'
     or jsonb_typeof(p_payload -> 'monthly_hard_budget_units') <> 'number'
     or coalesce(p_payload ->> 'cadence_hours', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'max_records', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'monthly_hard_budget_units', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_collection_policy_invalid';
  end if;
  automatic_collection_ack_value :=
    (p_payload ->> 'automatic_collection_ack')::boolean;
  terms_ack_value := (p_payload ->> 'terms_ack')::boolean;
  quota_ack_value := (p_payload ->> 'quota_ack')::boolean;
  no_retry_ack_value := (p_payload ->> 'no_retry_ack')::boolean;
  begin
    cadence_hours_value := (p_payload ->> 'cadence_hours')::integer;
    max_records_value := (p_payload ->> 'max_records')::integer;
    monthly_hard_budget_units_value :=
      (p_payload ->> 'monthly_hard_budget_units')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'research_collection_policy_invalid';
  end;
  if cadence_hours_value not between 24 and 720
     or max_records_value not between 1 and 25
     or monthly_hard_budget_units_value not between 0 and 100 then
    raise exception using
      errcode = '22023', message = 'research_collection_policy_invalid';
  end if;
  legal_review_reference_value := nullif(
    btrim(coalesce(p_payload ->> 'legal_review_reference', '')), ''
  );
  if legal_review_reference_value is not null
     and length(legal_review_reference_value) not between 3 and 160 then
    raise exception using
      errcode = '22023', message = 'legal_review_reference_invalid';
  end if;
  if status_value = 'enabled' and platform_value = 'instagram' then
    raise exception using
      errcode = '55000',
      message = 'research_instagram_provider_legal_choice_required';
  end if;
  if status_value = 'enabled' and (
       provider_key_value <> 'youtube_data_api_v3'
       or not automatic_collection_ack_value
       or terms_version_value <> 'youtube-developer-policies-2026-08-03-v1'
       or not terms_ack_value or not quota_ack_value or not no_retry_ack_value
       or monthly_hard_budget_units_value < 2
       or legal_review_reference_value is null
     ) then
    raise exception using
      errcode = '55000', message = 'research_youtube_automatic_policy_ack_required';
  end if;
  if (p_payload -> 'expected_policy_id') is not null
     and jsonb_typeof(p_payload -> 'expected_policy_id') <> 'null' then
    expected_policy_id_value := content_factory_private.require_uuid(
      p_payload, 'expected_policy_id'
    );
  end if;
  expected_policy_hash_value := nullif(
    btrim(coalesce(p_payload ->> 'expected_policy_hash', '')), ''
  );
  if (expected_policy_id_value is null) <> (expected_policy_hash_value is null)
     or (expected_policy_hash_value is not null
       and expected_policy_hash_value !~ '^[0-9a-f]{64}$') then
    raise exception using
      errcode = '22023', message = 'research_collection_expected_policy_invalid';
  end if;

  select run.product_id into product_id_value
  from content_factory.product_research_runs run
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
    organization_id_value,
    false,
    array['owner', 'admin']
  );
  request_payload := p_payload - 'idempotency_key';
  replay_result := content_factory_private.begin_command(
    organization_id_value,
    'creator_configure_research_source_collection_policy',
    idempotency_key_value,
    request_payload
  );
  if replay_result is not null then
    return replay_result;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-collection-policy:' || product_id_value::text
      || ':' || platform_value)
  );
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_required';
  end if;
  select policy.* into current_policy
  from content_factory.research_source_collection_policies policy
  where policy.organization_id = organization_id_value
    and policy.product_id = product_id_value
    and policy.platform = platform_value
  order by policy.policy_version desc, policy.id desc
  limit 1;
  if current_policy.id is null then
    if expected_policy_id_value is not null then
      raise exception using
        errcode = '40001', message = 'research_collection_policy_head_stale';
    end if;
  elsif current_policy.id is distinct from expected_policy_id_value
     or current_policy.policy_hash is distinct from expected_policy_hash_value then
    raise exception using
      errcode = '40001', message = 'research_collection_policy_head_stale';
  end if;

  policy_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-source-collection-policy-v1',
    'organization_id', organization_id_value,
    'product_id', product_id_value,
    'run_id', run_id_value,
    'binding_id', binding_row.id,
    'market_category_id', binding_row.category_id,
    'platform', platform_value,
    'provider_key', provider_key_value,
    'policy_version', coalesce(current_policy.policy_version, 0) + 1,
    'previous_policy_id', current_policy.id,
    'status', status_value,
    'automatic_collection_ack', automatic_collection_ack_value,
    'terms_version', terms_version_value,
    'terms_ack', terms_ack_value,
    'quota_ack', quota_ack_value,
    'no_retry_ack', no_retry_ack_value,
    'cadence_hours', cadence_hours_value,
    'max_records', max_records_value,
    'monthly_hard_budget_units', monthly_hard_budget_units_value,
    'legal_review_reference', legal_review_reference_value,
    'reason', reason_value
  ));
  insert into content_factory.research_source_collection_policies (
    organization_id, product_id, run_id, binding_id, market_category_id,
    platform, provider_key, policy_version, previous_policy_id, status,
    automatic_collection_ack, terms_version, terms_ack, quota_ack,
    no_retry_ack, cadence_hours, max_records,
    monthly_hard_budget_units, legal_review_reference, reason, created_by,
    request_hash, policy_hash, idempotency_key
  ) values (
    organization_id_value, product_id_value, run_id_value, binding_row.id,
    binding_row.category_id, platform_value, provider_key_value,
    coalesce(current_policy.policy_version, 0) + 1, current_policy.id,
    status_value, automatic_collection_ack_value, terms_version_value,
    terms_ack_value, quota_ack_value, no_retry_ack_value, cadence_hours_value,
    max_records_value, monthly_hard_budget_units_value,
    legal_review_reference_value, reason_value, user_id,
    content_factory_private.json_hash(request_payload), policy_hash_value,
    idempotency_key_value
  ) returning * into policy_row;
  result_value := jsonb_build_object(
    'ok', true,
    'policy', jsonb_build_object(
      'policy_id', policy_row.id,
      'policy_hash', policy_row.policy_hash,
      'policy_version', policy_row.policy_version,
      'platform', policy_row.platform,
      'provider_key', policy_row.provider_key,
      'status', policy_row.status,
      'automatic_collection_ack', policy_row.automatic_collection_ack,
      'terms_version', policy_row.terms_version,
      'terms_ack', policy_row.terms_ack,
      'quota_ack', policy_row.quota_ack,
      'no_retry_ack', policy_row.no_retry_ack,
      'cadence_hours', policy_row.cadence_hours,
      'max_records', policy_row.max_records,
      'monthly_hard_budget_units', policy_row.monthly_hard_budget_units
    ),
    'capability', jsonb_build_object(
      'automatic_enqueue_supported', (
        policy_row.status = 'enabled'
        and policy_row.platform = 'youtube'
      ),
      'external_call_started', false,
      'queued_ingestion_is_claimed_by_internal_worker', true,
      'instagram_enabled', false
    )
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_source_collection_policy_configured',
    'research_source_collection_policy',
    policy_row.id::text,
    jsonb_build_object(
      'platform', platform_value,
      'provider_key', provider_key_value,
      'status', status_value,
      'policy_hash', policy_hash_value,
      'external_call_started', false
    ),
    'research-collection-policy:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_configure_research_source_collection_policy',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.system_propose_due_research_source_collection(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer;
  selected_count_value integer := 0;
  created_count_value integer := 0;
  blocked_count_value integer := 0;
  candidate record;
  policy_row content_factory.research_source_collection_policies%rowtype;
  scheduled_for_value timestamptz;
  category_name_value text;
  blocked_reason_value text;
  month_start_value timestamptz;
  monthly_reserved_units_value integer := 0;
  ingestion_id_value uuid;
  ingestion_request_hash_value text;
  ingestion_idempotency_key_value text;
  intent_request_hash_value text;
  intent_hash_value text;
  intent_idempotency_key_value text;
  ingestions_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['limit']::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'limit') <> 'number'
     or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_collection_scheduler_payload_invalid';
  end if;
  begin
    limit_value := (p_payload ->> 'limit')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'research_collection_scheduler_limit_invalid';
  end;
  if limit_value not between 1 and 25 then
    raise exception using
      errcode = '22023', message = 'research_collection_scheduler_limit_invalid';
  end if;

  for candidate in
    with current_policies as (
      select distinct on (
        policy.organization_id, policy.product_id, policy.platform
      ) policy.*
      from content_factory.research_source_collection_policies policy
      order by policy.organization_id, policy.product_id, policy.platform,
        policy.policy_version desc, policy.id desc
    ), due_policies as (
      select policy.*,
        coalesce((
          select max(intent.scheduled_for)
            + make_interval(hours => policy.cadence_hours)
          from content_factory.research_source_collection_intents intent
          where intent.organization_id = policy.organization_id
            and intent.policy_id = policy.id
        ), policy.created_at) as due_at
      from current_policies policy
      where policy.status = 'enabled'
        and policy.platform = 'youtube'
        and policy.provider_key = 'youtube_data_api_v3'
        and policy.automatic_collection_ack
        and policy.terms_ack and policy.quota_ack and policy.no_retry_ack
    )
    select due_policy.*
    from due_policies due_policy
    where due_policy.due_at <= clock_timestamp()
    order by due_policy.organization_id, due_policy.market_category_id,
      due_policy.product_id, due_policy.id
    limit limit_value
  loop
    selected_count_value := selected_count_value + 1;
    perform pg_advisory_xact_lock(
      hashtext(candidate.organization_id::text),
      hashtext('research-source-monthly-budget:'
        || candidate.market_category_id::text)
    );

    select policy.* into policy_row
    from content_factory.research_source_collection_policies policy
    where policy.organization_id = candidate.organization_id
      and policy.product_id = candidate.product_id
      and policy.platform = candidate.platform
    order by policy.policy_version desc, policy.id desc
    limit 1;
    if policy_row.id is distinct from candidate.id
       or policy_row.status <> 'enabled' then
      continue;
    end if;
    select coalesce(
      max(intent.scheduled_for)
        + make_interval(hours => policy_row.cadence_hours),
      policy_row.created_at
    ) into scheduled_for_value
    from content_factory.research_source_collection_intents intent
    where intent.organization_id = policy_row.organization_id
      and intent.policy_id = policy_row.id;
    if scheduled_for_value > clock_timestamp()
       or exists (
         select 1
         from content_factory.research_source_collection_intents existing
         where existing.organization_id = policy_row.organization_id
           and existing.policy_id = policy_row.id
           and existing.scheduled_for = scheduled_for_value
       ) then
      continue;
    end if;

    blocked_reason_value := null;
    select category.canonical_name into category_name_value
    from content_factory.research_market_categories category
    where category.organization_id = policy_row.organization_id
      and category.id = policy_row.market_category_id
      and category.status = 'active';
    if category_name_value is null then
      blocked_reason_value := 'category_inactive';
      category_name_value := 'blocked category evidence';
    elsif policy_row.terms_version
          <> 'youtube-developer-policies-2026-08-03-v1'
       or not policy_row.automatic_collection_ack
       or not policy_row.terms_ack
       or not policy_row.quota_ack
       or not policy_row.no_retry_ack then
      blocked_reason_value := 'policy_ack_invalid';
    elsif not exists (
      select 1
      from content_factory.organizations organization
      join content_factory.memberships membership
        on membership.organization_id = organization.id
       and membership.profile_id = policy_row.created_by
       and membership.status = 'active'
       and membership.role in ('owner', 'admin')
      join content_factory.profiles profile
        on profile.id = membership.profile_id
       and profile.status = 'active'
      where organization.id = policy_row.organization_id
        and organization.status = 'active'
    ) then
      blocked_reason_value := 'policy_creator_inactive';
    elsif not exists (
      select 1
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id = policy_row.organization_id
        and binding.product_id = policy_row.product_id
        and binding.id = policy_row.binding_id
        and binding.category_id = policy_row.market_category_id
        and not exists (
          select 1
          from content_factory.research_product_market_category_bindings newer
          where newer.organization_id = binding.organization_id
            and newer.product_id = binding.product_id
            and newer.binding_version > binding.binding_version
        )
    ) then
      blocked_reason_value := 'category_binding_stale';
    elsif not exists (
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
      blocked_reason_value := 'provider_contract_closed';
    elsif not content_factory_private.research_youtube_retention_ready() then
      blocked_reason_value := 'retention_control_unavailable';
    elsif not content_factory_private.research_youtube_global_gate(
      'category_refresh'
    ) then
      blocked_reason_value := 'global_rollout_gate_closed';
    elsif not content_factory_private.research_youtube_refresh_gate(
      policy_row.organization_id
    ) then
      blocked_reason_value := 'organization_rollout_gate_closed';
    end if;

    month_start_value := date_trunc('month', clock_timestamp());
    select coalesce(sum(ingestion.max_quota_units), 0)::integer
    into monthly_reserved_units_value
    from content_factory.research_youtube_ingestion_runs ingestion
    where ingestion.organization_id = policy_row.organization_id
      and ingestion.market_category_id = policy_row.market_category_id
      and ingestion.requested_at >= month_start_value
      and ingestion.requested_at < month_start_value + interval '1 month';
    if blocked_reason_value is null
       and monthly_reserved_units_value + 2
         > policy_row.monthly_hard_budget_units then
      blocked_reason_value := 'monthly_hard_budget_exhausted';
    end if;

    intent_request_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-source-collection-intent-request-v1',
        'organization_id', policy_row.organization_id,
        'policy_id', policy_row.id,
        'policy_hash', policy_row.policy_hash,
        'scheduled_for', scheduled_for_value
      )
    );
    intent_idempotency_key_value :=
      'auto-source-intent-' || left(intent_request_hash_value, 64);

    if blocked_reason_value is not null then
      intent_hash_value := content_factory_private.json_hash(jsonb_build_object(
        'version', 'research-source-collection-intent-v1',
        'organization_id', policy_row.organization_id,
        'policy_id', policy_row.id,
        'policy_hash', policy_row.policy_hash,
        'scheduled_for', scheduled_for_value,
        'status', 'blocked',
        'blocked_reason', blocked_reason_value,
        'query_text', category_name_value,
        'max_records', policy_row.max_records,
        'monthly_reserved_units', monthly_reserved_units_value
      ));
      begin
        insert into content_factory.research_source_collection_intents (
          organization_id, policy_id, policy_hash, product_id, run_id,
          binding_id, market_category_id, platform, provider_key,
          ingestion_id, status, capability, blocked_reason, query_text,
          max_records, planned_quota_units, monthly_hard_budget_units,
          monthly_reserved_units, scheduled_for,
          automatic_enqueue_supported, external_call_started,
          no_retry, no_fallback, request_hash, intent_hash, idempotency_key
        ) values (
          policy_row.organization_id, policy_row.id, policy_row.policy_hash,
          policy_row.product_id, policy_row.run_id, policy_row.binding_id,
          policy_row.market_category_id, policy_row.platform,
          policy_row.provider_key, null, 'blocked',
          'automatic_collection_unavailable', blocked_reason_value,
          category_name_value, policy_row.max_records, 0,
          policy_row.monthly_hard_budget_units, monthly_reserved_units_value,
          scheduled_for_value, false, false, true, true,
          intent_request_hash_value, intent_hash_value,
          intent_idempotency_key_value
        );
        blocked_count_value := blocked_count_value + 1;
      exception when unique_violation then
        null;
      end;
      continue;
    end if;

    ingestion_id_value := extensions.gen_random_uuid();
    ingestion_request_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'research-youtube-auto-category-refresh-v1',
        'organization_id', policy_row.organization_id,
        'policy_id', policy_row.id,
        'policy_hash', policy_row.policy_hash,
        'scheduled_for', scheduled_for_value,
        'run_id', policy_row.run_id,
        'product_id', policy_row.product_id,
        'binding_id', policy_row.binding_id,
        'market_category_id', policy_row.market_category_id,
        'query_text', category_name_value,
        'published_after', scheduled_for_value - interval '90 days',
        'max_results', policy_row.max_records,
        'terms_version', policy_row.terms_version
      )
    );
    ingestion_idempotency_key_value :=
      'auto-youtube-' || left(ingestion_request_hash_value, 64);
    intent_hash_value := content_factory_private.json_hash(jsonb_build_object(
      'version', 'research-source-collection-intent-v1',
      'organization_id', policy_row.organization_id,
      'policy_id', policy_row.id,
      'policy_hash', policy_row.policy_hash,
      'scheduled_for', scheduled_for_value,
      'status', 'queued',
      'ingestion_id', ingestion_id_value,
      'query_text', category_name_value,
      'max_records', policy_row.max_records,
      'planned_quota_units', 2,
      'monthly_reserved_units', monthly_reserved_units_value + 2
    ));
    begin
      insert into content_factory.research_youtube_ingestion_runs (
        id, organization_id, run_id, product_id, binding_id,
        market_category_id, requested_by, mode, status, provider_key,
        adapter_version, query_text, query_hash, region_code,
        relevance_language, published_after, max_results,
        max_http_requests, max_quota_units, request_hash,
        idempotency_key, terms_version, no_retry
      ) values (
        ingestion_id_value, policy_row.organization_id, policy_row.run_id,
        policy_row.product_id, policy_row.binding_id,
        policy_row.market_category_id, policy_row.created_by,
        'category_refresh', 'queued', 'youtube_data_api_v3',
        'youtube-data-api-v3-public-metadata-v1', category_name_value,
        content_factory_private.json_hash(jsonb_build_object(
          'query_text', category_name_value
        )), null, null, scheduled_for_value - interval '90 days',
        policy_row.max_records, 2, 2, ingestion_request_hash_value,
        ingestion_idempotency_key_value, policy_row.terms_version, true
      );
      insert into content_factory.research_source_collection_intents (
        organization_id, policy_id, policy_hash, product_id, run_id,
        binding_id, market_category_id, platform, provider_key,
        ingestion_id, status, capability, blocked_reason, query_text,
        max_records, planned_quota_units, monthly_hard_budget_units,
        monthly_reserved_units, scheduled_for,
        automatic_enqueue_supported, external_call_started,
        no_retry, no_fallback, request_hash, intent_hash, idempotency_key
      ) values (
        policy_row.organization_id, policy_row.id, policy_row.policy_hash,
        policy_row.product_id, policy_row.run_id, policy_row.binding_id,
        policy_row.market_category_id, policy_row.platform,
        policy_row.provider_key, ingestion_id_value, 'queued',
        'automatic_youtube_enqueue', null, category_name_value,
        policy_row.max_records, 2, policy_row.monthly_hard_budget_units,
        monthly_reserved_units_value + 2, scheduled_for_value,
        true, false, true, true, intent_request_hash_value,
        intent_hash_value, intent_idempotency_key_value
      );
      created_count_value := created_count_value + 1;
      ingestions_value := ingestions_value || jsonb_build_array(
        jsonb_build_object(
          'ingestion_id', ingestion_id_value,
          'organization_id', policy_row.organization_id,
          'requested_by', policy_row.created_by
        )
      );
    exception when unique_violation then
      null;
    end;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'selected', selected_count_value,
    'created', created_count_value,
    'blocked', blocked_count_value,
    'due', selected_count_value,
    'ingestions', ingestions_value,
    'external_call_started', false,
    'automatic_retry_started', false
  );
end;
$$;

create or replace function content_factory_private.research_automatic_youtube_dispatch_allowed(
  ingestion_id_value uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.research_source_collection_intents intent
    join content_factory.research_source_collection_policies policy
      on policy.organization_id = intent.organization_id
     and policy.id = intent.policy_id
     and policy.policy_hash = intent.policy_hash
    join content_factory.research_youtube_ingestion_runs ingestion
      on ingestion.organization_id = intent.organization_id
     and ingestion.id = intent.ingestion_id
    join content_factory.organizations organization
      on organization.id = policy.organization_id
     and organization.status = 'active'
    join content_factory.memberships membership
      on membership.organization_id = policy.organization_id
     and membership.profile_id = policy.created_by
     and membership.status = 'active'
     and membership.role in ('owner', 'admin')
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where ingestion.id = ingestion_id_value
      and intent.status = 'queued'
      and intent.capability = 'automatic_youtube_enqueue'
      and intent.automatic_enqueue_supported
      and intent.external_call_started = false
      and intent.no_retry and intent.no_fallback
      and ingestion.mode = 'category_refresh'
      and ingestion.provider_key = 'youtube_data_api_v3'
      and ingestion.no_retry
      and policy.status = 'enabled'
      and policy.platform = 'youtube'
      and policy.provider_key = 'youtube_data_api_v3'
      and policy.automatic_collection_ack
      and policy.terms_version = 'youtube-developer-policies-2026-08-03-v1'
      and policy.terms_ack and policy.quota_ack and policy.no_retry_ack
      and not exists (
        select 1
        from content_factory.research_source_collection_policies newer_policy
        where newer_policy.organization_id = policy.organization_id
          and newer_policy.product_id = policy.product_id
          and newer_policy.platform = policy.platform
          and newer_policy.policy_version > policy.policy_version
      )
      and exists (
        select 1
        from content_factory.research_product_market_category_bindings binding
        where binding.organization_id = policy.organization_id
          and binding.product_id = policy.product_id
          and binding.id = policy.binding_id
          and binding.category_id = policy.market_category_id
          and not exists (
            select 1
            from content_factory.research_product_market_category_bindings newer
            where newer.organization_id = binding.organization_id
              and newer.product_id = binding.product_id
              and newer.binding_version > binding.binding_version
          )
      )
      and exists (
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
      )
      and content_factory_private.research_youtube_retention_ready()
      and content_factory_private.research_youtube_global_gate(
        'category_refresh'
      )
      and content_factory_private.research_youtube_refresh_gate(
        policy.organization_id
      )
  )
$$;

create or replace function public.system_claim_due_research_youtube_collection(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer;
  expired_count_value integer := 0;
  proposed_value jsonb;
  selected_count_value integer := 0;
  claimed_count_value integer := 0;
  candidate record;
  claim_value jsonb;
  transition_time_value timestamptz;
  items_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['limit']::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'limit') <> 'number'
     or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'research_collection_claim_payload_invalid';
  end if;
  begin
    limit_value := (p_payload ->> 'limit')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'research_collection_claim_limit_invalid';
  end;
  if limit_value not between 1 and 6 then
    raise exception using
      errcode = '22023', message = 'research_collection_claim_limit_invalid';
  end if;

  with expired as (
    select ingestion.id
    from content_factory.research_source_collection_intents intent
    join content_factory.research_youtube_ingestion_runs ingestion
      on ingestion.organization_id = intent.organization_id
     and ingestion.id = intent.ingestion_id
    where intent.status = 'queued'
      and intent.capability = 'automatic_youtube_enqueue'
      and intent.automatic_enqueue_supported
      and ingestion.mode = 'category_refresh'
      and ingestion.status = 'processing'
      and ingestion.lease_expires_at <= clock_timestamp()
    order by ingestion.lease_expires_at, ingestion.id
    limit 100
  )
  select count(*)::integer into expired_count_value
  from expired
  where content_factory_private.expire_research_youtube_ingestion(expired.id);

  proposed_value := public.system_propose_due_research_source_collection(
    jsonb_build_object('limit', limit_value)
  );
  for candidate in
    select ingestion.id as ingestion_id,
      ingestion.organization_id, ingestion.product_id, ingestion.requested_by,
      ingestion.requested_at
    from content_factory.research_source_collection_intents intent
    join content_factory.research_youtube_ingestion_runs ingestion
      on ingestion.organization_id = intent.organization_id
     and ingestion.id = intent.ingestion_id
    where intent.status = 'queued'
      and intent.capability = 'automatic_youtube_enqueue'
      and intent.automatic_enqueue_supported
      and ingestion.mode = 'category_refresh'
      and ingestion.status = 'queued'
    order by ingestion.requested_at, ingestion.id
    for update of ingestion skip locked
    limit limit_value
  loop
    selected_count_value := selected_count_value + 1;
    perform pg_advisory_xact_lock(
      hashtext(candidate.organization_id::text),
      hashtext('research-collection-policy:' || candidate.product_id::text
        || ':youtube')
    );
    if not content_factory_private.research_automatic_youtube_dispatch_allowed(
      candidate.ingestion_id
    ) then
      transition_time_value := clock_timestamp();
      update content_factory.research_youtube_ingestion_runs ingestion
      set status = 'failed',
          claimed_at = transition_time_value,
          lease_expires_at = transition_time_value + interval '5 minutes',
          completed_at = transition_time_value,
          completion_hash = content_factory_private.json_hash(
            jsonb_build_object(
              'version', 'research-youtube-terminal-v1',
              'ingestion_id', ingestion.id,
              'status', 'failed',
              'error_code', 'rollout_gate_closed',
              'error_message',
                'Automatic collection policy or gate closed; no retry attempted.',
              'completed_at', transition_time_value
            )
          ),
          error_code = 'rollout_gate_closed',
          error_message =
            'Automatic collection policy or gate closed; no retry attempted.'
      where ingestion.id = candidate.ingestion_id
        and ingestion.status = 'queued';
      continue;
    end if;
    claim_value := content_factory_private.claim_research_youtube_ingestion(
      candidate.ingestion_id
    );
    if coalesce((claim_value ->> 'claimed')::boolean, false) then
      claimed_count_value := claimed_count_value + 1;
      items_value := items_value || jsonb_build_array(
        jsonb_build_object(
          'ingestion_id', claim_value -> 'ingestion' ->> 'id',
          'organization_id', candidate.organization_id,
          'requested_by', candidate.requested_by,
          'status', claim_value -> 'ingestion' ->> 'status',
          'mode', claim_value -> 'ingestion' ->> 'mode',
          'provider_key', claim_value -> 'ingestion' ->> 'provider_key',
          'max_http_requests',
            (claim_value -> 'ingestion' ->> 'max_http_requests')::integer,
          'max_quota_units',
            (claim_value -> 'ingestion' ->> 'max_quota_units')::integer
        )
      );
    end if;
  end loop;
  return jsonb_build_object(
    'ok', true,
    'selected', selected_count_value,
    'claimed', claimed_count_value,
    'expired', expired_count_value,
    'items', items_value,
    'external_call_started', false,
    'automatic_retry_started', false
  );
end;
$$;

create or replace function public.system_read_automatic_research_youtube_ingestion(
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
  ingestion_row content_factory.research_youtube_ingestion_runs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['ingestion_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_automatic_youtube_read_payload_invalid';
  end if;
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  select ingestion.* into ingestion_row
  from content_factory.research_source_collection_intents intent
  join content_factory.research_youtube_ingestion_runs ingestion
    on ingestion.organization_id = intent.organization_id
   and ingestion.id = intent.ingestion_id
  where intent.ingestion_id = ingestion_id_value
    and intent.status = 'queued'
    and intent.capability = 'automatic_youtube_enqueue'
    and intent.automatic_enqueue_supported
    and ingestion.mode = 'category_refresh';
  if ingestion_row.id is null then
    raise exception using
      errcode = '42501', message = 'research_automatic_youtube_not_authorized';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(ingestion_row.organization_id::text),
    hashtext('research-collection-policy:' || ingestion_row.product_id::text
      || ':youtube')
  );
  if not content_factory_private.research_automatic_youtube_dispatch_allowed(
    ingestion_id_value
  ) then
    raise exception using
      errcode = '42501', message = 'research_automatic_youtube_policy_closed';
  end if;
  if ingestion_row.status <> 'processing' then
    raise exception using
      errcode = '55000', message = 'research_automatic_youtube_not_processing';
  end if;
  if ingestion_row.lease_expires_at <= clock_timestamp() then
    raise exception using
      errcode = '55000', message = 'research_automatic_youtube_lease_expired';
  end if;
  return jsonb_build_object(
    'ok', true,
    'automatic_dispatch_authorized', true,
    'claimed', false,
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

create or replace function public.system_begin_automatic_research_youtube_transport(
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
  organization_id_value uuid;
  product_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'ingestion_id', 'request_ordinal', 'request_kind', 'quota_bucket',
    'quota_units', 'request_hash'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_automatic_youtube_transport_payload_invalid';
  end if;
  ingestion_id_value := content_factory_private.require_uuid(
    p_payload, 'ingestion_id'
  );
  select ingestion.organization_id, ingestion.product_id
  into organization_id_value, product_id_value
  from content_factory.research_youtube_ingestion_runs ingestion
  where ingestion.id = ingestion_id_value;
  if organization_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_ingestion_not_found';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-collection-policy:' || product_id_value::text
      || ':youtube')
  );
  if not content_factory_private.research_automatic_youtube_dispatch_allowed(
    ingestion_id_value
  ) then
    raise exception using
      errcode = '42501', message = 'research_automatic_youtube_policy_closed';
  end if;
  return public.system_begin_research_youtube_transport(p_payload);
end;
$$;

create or replace function
content_factory_private.bootstrap_persisted_research_source_analyses(
  organization_id_value uuid,
  run_id_value uuid
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_row content_factory.product_research_runs%rowtype;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  source_row record;
  evidence_value jsonb;
  competitor_cited_value boolean;
  trend_cited_value boolean;
  category_cited_value boolean;
  cited_elsewhere_value boolean;
  classification_value text;
  relevance_score_value integer;
  confidence_value text;
  structural_signal_keys_value jsonb;
  limitations_value jsonb;
  analysis_value jsonb;
  parsed_count_value integer := 0;
begin
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value
    and run.status = 'completed';
  if run_row.id is null then
    raise exception using
      errcode = '55000', message = 'completed_research_run_required';
  end if;
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  join content_factory.research_market_categories category
    on category.organization_id = binding.organization_id
   and category.id = binding.category_id
   and category.status = 'active'
  where binding.organization_id = organization_id_value
    and binding.product_id = run_row.product_id
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_required';
  end if;

  -- The AI draft was schema-validated before completion.  The run summary is
  -- an equivalent persisted result fallback for legacy completions that did
  -- not create a draft.  Only citation IDs and allowlisted signal keys are
  -- interpreted below; model/provider prose is never copied to learning data.
  select draft.brief into evidence_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.origin = 'ai'
  order by draft.version desc, draft.id desc
  limit 1;
  evidence_value := coalesce(evidence_value, run_row.summary, '{}'::jsonb);
  if jsonb_typeof(evidence_value) <> 'object' then
    evidence_value := '{}'::jsonb;
  end if;

  for source_row in
    select source.id as source_id, source.source_type, source.trust_level,
      source.metadata ->> 'model_source_id' as model_source_id,
      source.metadata ->> 'original_source_type' as original_source_type,
      mapping.id as source_ledger_id
    from (
      select bounded_source.*
      from content_factory.product_research_sources bounded_source
      where bounded_source.organization_id = organization_id_value
        and bounded_source.run_id = run_id_value
        and jsonb_typeof(
          bounded_source.metadata -> 'model_source_id'
        ) = 'string'
        and bounded_source.metadata ->> 'model_source_id'
          ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
      order by bounded_source.created_at, bounded_source.id
      limit 24
    ) source
    join lateral (
      select ledger.*
      from content_factory.research_category_source_ledger ledger
      where ledger.organization_id = organization_id_value
        and ledger.market_category_id = binding_row.category_id
        and (
          ledger.source_content_hash = source.content_hash
          or ledger.source_identity_key =
            content_factory_private.research_source_identity_key(
              source.source_url, source.content_hash
            )
        )
      order by (ledger.source_content_hash = source.content_hash) desc,
        (
          ledger.source_identity_key =
            content_factory_private.research_source_identity_key(
              source.source_url, source.content_hash
            )
        ) desc, ledger.registered_at desc, ledger.id desc
      limit 1
    ) mapping on true
  loop
    perform pg_advisory_xact_lock(
      hashtext(organization_id_value::text),
      hashtext('research-source-analysis:' || source_row.source_ledger_id::text)
    );
    -- Any richer system result or human correction is authoritative.  This
    -- fallback only establishes a first editable head when none exists.
    if exists (
      select 1
      from content_factory.research_source_analysis_events event
      where event.organization_id = organization_id_value
        and event.source_ledger_id = source_row.source_ledger_id
    ) then
      continue;
    end if;

    competitor_cited_value := coalesce(jsonb_path_exists(
      evidence_value,
      'strict $.competitor_analysis.competitors[*].source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false) or coalesce(jsonb_path_exists(
      evidence_value,
      'strict $.competitor_analysis.saturated_patterns[*].source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false) or coalesce(jsonb_path_exists(
      evidence_value,
      'strict $.competitor_analysis.content_gaps[*].source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false);
    trend_cited_value := coalesce(jsonb_path_exists(
      evidence_value,
      'strict $.trend_analysis.signals[*].source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false);
    category_cited_value := coalesce(jsonb_path_exists(
      evidence_value,
      'strict $.category_analysis.source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false);
    cited_elsewhere_value := coalesce(jsonb_path_exists(
      evidence_value,
      'lax $.**.source_ids[*] ? (@ == $source_id)',
      jsonb_build_object('source_id', source_row.model_source_id), true
    ), false);

    select coalesce(
      jsonb_agg(signal.signal_key order by signal.signal_key),
      '[]'::jsonb
    ) into structural_signal_keys_value
    from (
      select distinct btrim(item.value ->> 'signal_key') as signal_key
      from jsonb_array_elements(case
        when jsonb_typeof(
          evidence_value #> '{trend_analysis,signals}'
        ) = 'array' then evidence_value #> '{trend_analysis,signals}'
        else '[]'::jsonb
      end) item(value)
      join content_factory.research_structural_trend_signal_types catalog
        on catalog.signal_key = btrim(item.value ->> 'signal_key')
       and catalog.status = 'active'
      where jsonb_typeof(item.value -> 'source_ids') = 'array'
        and exists (
          select 1
          from jsonb_array_elements_text(item.value -> 'source_ids') ref(value)
          where ref.value = source_row.model_source_id
        )
    ) signal;

    -- Exact validated citation roles drive classification.  Competitor wins
    -- over a simultaneous trend role; broad source types and arbitrary legacy
    -- metadata classifications never manufacture competitor/trend evidence.
    classification_value := case
      when competitor_cited_value then 'competitor'
      when trend_cited_value then 'trend_signal'
      when category_cited_value
        or source_row.source_type in (
          'user_input', 'product_photo', 'marketplace_page'
        )
        or source_row.original_source_type in (
          'input_photo', 'official', 'marketplace', 'product_page'
        )
        or source_row.trust_level in ('first_party', 'official')
        then 'reference'
      when cited_elsewhere_value
        and (
          source_row.original_source_type in ('review', 'editorial', 'social')
          or source_row.source_type in ('review', 'social_video')
        ) then 'adjacent'
      else 'unknown'
    end;
    relevance_score_value := case classification_value
      when 'competitor' then 75
      when 'trend_signal' then 70
      when 'reference' then 60
      when 'adjacent' then 50
      when 'unknown' then 25
      else 0
    end;
    confidence_value := case
      when competitor_cited_value or trend_cited_value
        or category_cited_value or cited_elsewhere_value then 'medium'
      else 'low'
    end;
    limitations_value := jsonb_build_array(
      'Deterministic interpretation uses citation roles from a persisted validated research result.',
      'No provider-authored prose, title, extracted fact or raw media text is stored in this event.'
    );
    if competitor_cited_value and trend_cited_value then
      limitations_value := limitations_value || jsonb_build_array(
        'The source has competitor and structural-trend citation roles; competitor takes precedence.'
      );
    end if;
    analysis_value := jsonb_build_object(
      'schema_version', 'research-source-interpretation-v1',
      'classification', classification_value,
      'relevance_score', relevance_score_value,
      'confidence', confidence_value,
      'summary', case classification_value
        when 'competitor' then
          'Persisted evidence has a validated competitor citation role in the latest research result.'
        when 'trend_signal' then
          'Persisted evidence has a validated structural-trend citation role in the latest research result.'
        when 'reference' then
          'Persisted evidence has a validated category or first-party reference role in the latest research result.'
        when 'adjacent' then
          'Persisted evidence is cited outside category, competitor and structural-trend evidence roles.'
        else
          'Persisted evidence has no validated category, competitor or structural-trend citation role.'
      end,
      'structural_signal_keys', structural_signal_keys_value,
      'limitations', limitations_value
    );
    perform public.system_record_research_source_analysis(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'source_ledger_id', source_row.source_ledger_id,
        'expected_head_event_id', null,
        'expected_head_hash', null,
        'parser_key', 'persisted_source_fallback',
        'parser_version', '1.0.0',
        'analysis', analysis_value,
        'idempotency_key',
          'category-fallback:' || source_row.source_ledger_id::text
      )
    );
    parsed_count_value := parsed_count_value + 1;
  end loop;
  return jsonb_build_object(
    'ok', true,
    'parsed', parsed_count_value,
    'item_limit', 24,
    'external_call_started', false
  );
end;
$$;

create or replace function public.system_register_research_category_sources(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  registered_count_value integer := 0;
  items_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_category_source_register_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-category-source-register:' || run_id_value::text)
  );
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value
    and run.status = 'completed';
  if run_row.id is null then
    raise exception using
      errcode = '55000', message = 'completed_research_run_required';
  end if;
  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  join content_factory.research_market_categories category
    on category.organization_id = binding.organization_id
   and category.id = binding.category_id
   and category.status = 'active'
  where binding.organization_id = organization_id_value
    and binding.product_id = run_row.product_id
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if binding_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_required';
  end if;
  with candidate_sources as (
    select source.*,
      case
        when lower(coalesce(source.metadata ->> 'platform', '')) in (
          'youtube', 'instagram', 'marketplace', 'web', 'first_party', 'other'
        ) then lower(source.metadata ->> 'platform')
        when source.source_url ~* '^https://([^/]+[.])?(youtube[.]com|youtu[.]be)/'
          then 'youtube'
        when source.source_url ~* '^https://([^/]+[.])?instagram[.]com/'
          then 'instagram'
        when source.source_type = 'marketplace_page' then 'marketplace'
        when source.source_type in ('user_input', 'product_photo') then 'first_party'
        when source.source_url is not null then 'web'
        else 'other'
      end as platform_value,
      case
        when lower(coalesce(source.metadata ->> 'provider_key', ''))
          ~ '^[a-z][a-z0-9_.-]{1,79}$'
          then lower(source.metadata ->> 'provider_key')
        when source.metadata -> 'provider_citation_verified' = 'true'::jsonb
          then 'openai_web_search'
        else 'user_supplied'
      end as provider_key_value
    from content_factory.product_research_sources source
    where source.organization_id = organization_id_value
      and source.run_id = run_id_value
      and source.product_id = run_row.product_id
    order by source.created_at, source.id
    limit 100
  ), inserted as (
    insert into content_factory.research_category_source_ledger (
      organization_id, market_category_id, product_id, binding_id, run_id,
      source_id, source_type, title, source_url, provider_key, platform,
      trust_level, source_identity_key, source_content_hash,
      fetched_at, published_at, registered_by, lineage_hash
    )
    select
      organization_id_value, binding_row.category_id, run_row.product_id,
      binding_row.id, run_id_value, source.id, source.source_type,
      source.title, source.source_url, source.provider_key_value,
      source.platform_value, source.trust_level,
      content_factory_private.research_source_identity_key(
        source.source_url, source.content_hash
      ), source.content_hash, source.fetched_at, source.published_at,
      run_row.created_by,
      content_factory_private.json_hash(jsonb_build_object(
        'version', 'research-category-source-lineage-v1',
        'organization_id', organization_id_value,
        'market_category_id', binding_row.category_id,
        'product_id', run_row.product_id,
        'binding_id', binding_row.id,
        'run_id', run_id_value,
        'source_id', source.id,
        'source_type', source.source_type,
        'source_url', source.source_url,
        'provider_key', source.provider_key_value,
        'platform', source.platform_value,
        'trust_level', source.trust_level,
        'source_content_hash', source.content_hash,
        'fetched_at', source.fetched_at,
        'published_at', source.published_at
      ))
    from candidate_sources source
    on conflict do nothing
    returning id
  )
  select count(*)::integer into registered_count_value from inserted;

  perform content_factory_private.bootstrap_persisted_research_source_analyses(
    organization_id_value, run_id_value
  );

  select coalesce(jsonb_agg(jsonb_build_object(
    'source_ledger_id', mapping.id,
    'source_id', source.id,
    'model_source_id', case
      when jsonb_typeof(source.metadata -> 'model_source_id') = 'string'
       and source.metadata ->> 'model_source_id'
         ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$'
        then source.metadata ->> 'model_source_id'
      else null
    end,
    'source_type', source.source_type,
    'current_head_event_id', head.id,
    'current_head_hash', head.event_hash
  ) order by source.created_at, source.id), '[]'::jsonb)
  into items_value
  from (
    select bounded_source.*
    from content_factory.product_research_sources bounded_source
    where bounded_source.organization_id = organization_id_value
      and bounded_source.run_id = run_id_value
    order by bounded_source.created_at, bounded_source.id
    limit 100
  ) source
  join lateral (
    select ledger.*
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = source.organization_id
      and ledger.market_category_id = binding_row.category_id
      and (
        ledger.source_identity_key =
          content_factory_private.research_source_identity_key(
            source.source_url, source.content_hash
          )
        or ledger.source_content_hash = source.content_hash
      )
    order by (ledger.source_content_hash = source.content_hash) desc,
    (
      ledger.source_identity_key =
        content_factory_private.research_source_identity_key(
          source.source_url, source.content_hash
        )
    ) desc, ledger.registered_at desc, ledger.id desc
    limit 1
  ) mapping on true
  left join lateral (
    select event.id, event.event_hash
    from content_factory.research_source_analysis_events event
    where event.organization_id = mapping.organization_id
      and event.source_ledger_id = mapping.id
    order by event.analysis_version desc, event.id desc
    limit 1
  ) head on true;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-category-source-register-v1',
    'registered', registered_count_value,
    'items', items_value,
    'item_limit', 100,
    'external_call_started', false
  );
end;
$$;

-- Keep product-research completion and durable category-source registration in
-- one transaction.  The original v2 completion implementation is preserved as
-- a private delegate so its validation, idempotency hash, and exact response
-- contract remain unchanged.  If registration fails, completion rolls back as
-- well; a lost-response replay safely executes the idempotent delegate and the
-- deduplicating registration again.
alter function public.system_complete_product_research(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_complete_product_research(jsonb)
  rename to complete_product_research_v2_base;

create or replace function public.system_complete_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  completion_value jsonb;
  run_id_value uuid;
  organization_id_value uuid;
  product_id_value uuid;
begin
  completion_value :=
    content_factory_private.complete_product_research_v2_base(p_payload);
  if completion_value ->> 'status' = 'completed'
     and btrim(coalesce(p_payload ->> 'status', '')) = 'completed' then
    begin
      run_id_value := (completion_value ->> 'run_id')::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '55000', message = 'research_completion_response_invalid';
    end;
    select run.organization_id, run.product_id
    into organization_id_value, product_id_value
    from content_factory.product_research_runs run
    where run.id = run_id_value
      and run.status = 'completed';
    if organization_id_value is null then
      raise exception using
        errcode = '55000', message = 'completed_research_run_required';
    end if;
    -- A first-time category is intentionally unresolved at completion.  Its
    -- binding path below performs registration atomically after confirmation.
    if exists (
      select 1
      from content_factory.research_product_market_category_bindings binding
      join content_factory.research_market_categories category
        on category.organization_id = binding.organization_id
       and category.id = binding.category_id
       and category.status = 'active'
      where binding.organization_id = organization_id_value
        and binding.product_id = product_id_value
    ) then
      perform public.system_register_research_category_sources(
        jsonb_build_object(
          'organization_id', organization_id_value,
          'run_id', run_id_value
        )
      );
    end if;
  end if;
  return completion_value;
end;
$$;

-- Category confirmation is the guaranteed local lifecycle edge for a new
-- market category.  Preserve the original command/idempotency implementation
-- privately, then register and bootstrap editable source interpretations in
-- the same transaction before returning its exact response.
alter function public.creator_resolve_research_market_category(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_resolve_research_market_category(jsonb)
  rename to resolve_research_market_category_v1_base;

create or replace function public.creator_resolve_research_market_category(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  resolution_value jsonb;
  organization_id_value uuid;
  run_id_value uuid;
begin
  resolution_value :=
    content_factory_private.resolve_research_market_category_v1_base(p_payload);
  if resolution_value -> 'ok' = 'true'::jsonb then
    organization_id_value := content_factory_private.require_uuid(
      p_payload, 'organization_id'
    );
    run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
    perform public.system_register_research_category_sources(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'run_id', run_id_value
      )
    );
  end if;
  return resolution_value;
end;
$$;

revoke all on function
  public.creator_research_category_learning_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_capture_research_category_readiness(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_correct_research_source_analysis(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_configure_research_source_collection_policy(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_record_research_source_analysis(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_propose_due_research_source_collection(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_claim_due_research_youtube_collection(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_read_automatic_research_youtube_ingestion(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_begin_automatic_research_youtube_transport(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_register_research_category_sources(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_complete_product_research(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_resolve_research_market_category(jsonb)
  from public, anon, authenticated, service_role;

grant execute on function
  public.creator_research_category_learning_status(jsonb) to authenticated;
grant execute on function
  public.creator_capture_research_category_readiness(jsonb) to authenticated;
grant execute on function
  public.creator_correct_research_source_analysis(jsonb) to authenticated;
grant execute on function
  public.creator_configure_research_source_collection_policy(jsonb)
  to authenticated;
grant execute on function
  public.system_record_research_source_analysis(jsonb) to service_role;
grant execute on function
  public.system_propose_due_research_source_collection(jsonb) to service_role;
grant execute on function
  public.system_claim_due_research_youtube_collection(jsonb) to service_role;
grant execute on function
  public.system_read_automatic_research_youtube_ingestion(jsonb)
  to service_role;
grant execute on function
  public.system_begin_automatic_research_youtube_transport(jsonb)
  to service_role;
grant execute on function
  public.system_register_research_category_sources(jsonb) to service_role;
grant execute on function
  public.system_complete_product_research(jsonb) to service_role;
grant execute on function
  public.creator_resolve_research_market_category(jsonb) to authenticated;

revoke all on function
  content_factory_private.research_analysis_has_forbidden_keys(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_source_analysis_is_valid(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_source_identity_key(text, text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_automatic_youtube_dispatch_allowed(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_research_category_learning_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_readiness_dimension(
    text, text, integer, integer, integer, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_category_evidence_readiness(
    uuid, uuid, timestamptz
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.complete_product_research_v2_base(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.resolve_research_market_category_v1_base(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.bootstrap_persisted_research_source_analyses(
    uuid, uuid
  ) from public, anon, authenticated, service_role;

commit;
