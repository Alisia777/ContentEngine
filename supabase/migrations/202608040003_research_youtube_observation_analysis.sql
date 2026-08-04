begin;

-- Retention-bound social observation analysis.
--
-- This migration closes the local gap between an already-authorized YouTube
-- collection and category learning.  It never starts a provider call, never
-- copies YouTube observations into durable source lineage and never promotes a
-- parser proposal to competitor or trend truth.  A single-attempt local job
-- creates an editable, append-only hypothesis tied to the exact retained
-- observation version.

create or replace function content_factory_private.research_youtube_observation_analysis_is_valid(
  value jsonb
)
returns boolean
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  signals_value jsonb;
  limitation_value jsonb;
begin
  if jsonb_typeof(value) <> 'object'
     or value - array[
       'schema_version', 'classification', 'review_priority', 'confidence',
       'recommendation', 'signals', 'summary', 'limitations'
     ]::text[] <> '{}'::jsonb
     or not value ?& array[
       'schema_version', 'classification', 'review_priority', 'confidence',
       'recommendation', 'signals', 'summary', 'limitations'
     ]::text[]
     or value ->> 'schema_version'
       <> 'research-youtube-observation-analysis-v1'
     or value ->> 'classification' not in (
       'potential_competitor', 'adjacent', 'unknown'
     )
     or jsonb_typeof(value -> 'review_priority') <> 'number'
     or coalesce(value ->> 'review_priority', '') !~ '^[0-9]{1,3}$'
     or (value ->> 'review_priority')::integer not between 0 and 100
     or value ->> 'confidence' not in ('low', 'medium')
     or value ->> 'recommendation' not in (
       'review_candidate', 'needs_more_evidence'
     )
     or jsonb_typeof(value -> 'signals') <> 'object'
     or jsonb_typeof(value -> 'summary') <> 'string'
     or length(btrim(value ->> 'summary')) not between 20 and 1200
     or jsonb_typeof(value -> 'limitations') <> 'array'
     or jsonb_array_length(value -> 'limitations') not between 1 and 8
     or length(value::text) > 16384
     or content_factory_private.research_analysis_has_forbidden_keys(value) then
    return false;
  end if;

  signals_value := value -> 'signals';
  if signals_value - array[
       'search_position', 'query_token_overlap_count', 'query_token_count',
       'published_age_days', 'same_channel_observation_count',
       'counters_present'
     ]::text[] <> '{}'::jsonb
     or not signals_value ?& array[
       'search_position', 'query_token_overlap_count', 'query_token_count',
       'published_age_days', 'same_channel_observation_count',
       'counters_present'
     ]::text[]
     or coalesce(signals_value ->> 'search_position', '') !~ '^[0-9]{1,2}$'
     or jsonb_typeof(signals_value -> 'search_position') <> 'number'
     or (signals_value ->> 'search_position')::integer not between 1 and 25
     or coalesce(signals_value ->> 'query_token_overlap_count', '')
       !~ '^[0-9]{1,3}$'
     or jsonb_typeof(signals_value -> 'query_token_overlap_count') <> 'number'
     or coalesce(signals_value ->> 'query_token_count', '') !~ '^[0-9]{1,3}$'
     or jsonb_typeof(signals_value -> 'query_token_count') <> 'number'
     or (signals_value ->> 'query_token_overlap_count')::integer
       > (signals_value ->> 'query_token_count')::integer
     or coalesce(signals_value ->> 'published_age_days', '')
       !~ '^[0-9]{1,7}$'
     or jsonb_typeof(signals_value -> 'published_age_days') <> 'number'
     or coalesce(signals_value ->> 'same_channel_observation_count', '')
       !~ '^[0-9]{1,7}$'
     or jsonb_typeof(signals_value -> 'same_channel_observation_count')
       <> 'number'
     or (signals_value ->> 'same_channel_observation_count')::integer < 1
     or jsonb_typeof(signals_value -> 'counters_present') <> 'boolean' then
    return false;
  end if;

  for limitation_value in
    select item.value from jsonb_array_elements(value -> 'limitations') item
  loop
    if jsonb_typeof(limitation_value) <> 'string'
       or length(btrim(limitation_value #>> '{}')) not between 3 and 500 then
      return false;
    end if;
  end loop;
  return true;
exception when invalid_text_representation or numeric_value_out_of_range then
  return false;
end;
$$;

alter table content_factory.research_youtube_video_observations
  add constraint research_youtube_observation_exact_version_uq
  unique (organization_id, id, observation_hash, retention_expires_at);

-- Retrieval/display through the official API and creation of derived
-- competitor/trend hypotheses are separate capabilities. YouTube permits the
-- latter only for an audited analytics use case that accepted the applicable
-- amendment. The fail-closed decision below is append-only and operator-owned.
create table content_factory.research_youtube_derived_analysis_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  provider_key text not null check (provider_key = 'youtube_data_api_v3'),
  adapter_version text not null check (
    adapter_version = 'youtube-data-api-v3-public-metadata-v1'
  ),
  decision text not null check (
    decision in ('approval_required', 'approved', 'emergency_paused')
  ),
  terms_version text not null check (
    terms_version = 'youtube-derived-metrics-policy-2026-06-01-v1'
  ),
  terms_review_ack boolean not null,
  analytics_amendment_ack boolean not null,
  approval_reference text check (
    approval_reference is null
    or length(btrim(approval_reference)) between 3 and 160
  ),
  reason text not null check (length(btrim(reason)) between 3 and 500),
  decided_at timestamptz not null default now(),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  unique (idempotency_key),
  unique (decision_hash),
  check (
    decision <> 'approved'
    or (
      terms_review_ack and analytics_amendment_ack
      and approval_reference is not null
    )
  )
);

insert into content_factory.research_youtube_derived_analysis_decisions (
  provider_key, adapter_version, decision, terms_version, terms_review_ack,
  analytics_amendment_ack, approval_reference, reason, idempotency_key,
  decision_hash
) values (
  'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
  'approval_required', 'youtube-derived-metrics-policy-2026-06-01-v1',
  false, false, null,
  'Initial fail-closed state pending audited analytics amendment approval',
  'youtube-derived-analysis-approval-required-20260804',
  content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-derived-analysis-decision-v1',
    'decision', 'approval_required',
    'terms_version', 'youtube-derived-metrics-policy-2026-06-01-v1',
    'terms_review_ack', false,
    'analytics_amendment_ack', false,
    'approval_reference', null,
    'reason',
      'Initial fail-closed state pending audited analytics amendment approval',
    'idempotency_key',
      'youtube-derived-analysis-approval-required-20260804'
  ))
);

alter table content_factory.research_youtube_derived_analysis_decisions
  enable row level security;
revoke all on table
  content_factory.research_youtube_derived_analysis_decisions
  from public, anon, authenticated, service_role;
create trigger research_youtube_derived_analysis_decision_immutable
before update or delete
on content_factory.research_youtube_derived_analysis_decisions
for each row execute function
  content_factory_private.reject_research_youtube_mutation();

create or replace function
  content_factory_private.research_youtube_derived_analysis_approved()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((
    select decision.decision = 'approved'
      and decision.terms_review_ack
      and decision.analytics_amendment_ack
      and decision.approval_reference is not null
    from content_factory.research_youtube_derived_analysis_decisions decision
    order by decision.decided_at desc, decision.id desc
    limit 1
  ), false);
$$;

create table content_factory.research_youtube_observation_analysis_jobs (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  ingestion_id uuid not null,
  parser_key text not null check (
    parser_key = 'youtube_observation_deterministic'
  ),
  parser_version text not null check (parser_version = '1.0.0'),
  status text not null check (
    status in (
      'approval_required', 'queued', 'processing', 'completed', 'failed'
    )
  ),
  input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
  attempt_count integer not null default 0 check (attempt_count between 0 and 1),
  no_retry boolean not null default true check (no_retry),
  external_call_started boolean not null default false check (
    not external_call_started
  ),
  parsed_count integer not null default 0 check (parsed_count between 0 and 25),
  claimed_at timestamptz,
  completed_at timestamptz,
  error_code text check (
    error_code is null or error_code in (
      'analysis_input_changed', 'analysis_evidence_expired',
      'analysis_parser_failed'
    )
  ),
  error_message text check (
    error_message is null or length(btrim(error_message)) between 1 and 1000
  ),
  retention_expires_at timestamptz not null,
  job_hash text not null check (job_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, ingestion_id, parser_version),
  unique (organization_id, job_hash),
  foreign key (organization_id, ingestion_id)
    references content_factory.research_youtube_ingestion_runs(
      organization_id, id
    ),
  check (retention_expires_at > created_at),
  check (
    (status in ('approval_required', 'queued')
      and attempt_count = 0 and claimed_at is null
      and completed_at is null and parsed_count = 0
      and error_code is null and error_message is null)
    or (status = 'processing' and attempt_count = 1 and claimed_at is not null
      and completed_at is null and error_code is null and error_message is null)
    or (status = 'completed' and attempt_count = 1 and claimed_at is not null
      and completed_at is not null and error_code is null
      and error_message is null)
    or (status = 'failed' and attempt_count = 1 and claimed_at is not null
      and completed_at is not null and parsed_count = 0
      and error_code is not null and error_message is not null)
  )
);

create table content_factory.research_youtube_observation_analysis_events (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  observation_id uuid not null,
  observation_hash text not null check (observation_hash ~ '^[0-9a-f]{64}$'),
  analysis_version integer not null check (analysis_version between 1 and 100000),
  parent_event_id uuid,
  expected_parent_hash text check (
    expected_parent_hash is null or expected_parent_hash ~ '^[0-9a-f]{64}$'
  ),
  origin text not null check (origin in ('system_parser', 'human_correction')),
  actor_id uuid,
  parser_key text not null check (parser_key ~ '^[a-z][a-z0-9_.-]{1,79}$'),
  parser_version text not null check (
    length(btrim(parser_version)) between 1 and 120
  ),
  analysis jsonb not null check (
    content_factory_private.research_youtube_observation_analysis_is_valid(
      analysis
    )
  ),
  correction_reason text check (
    correction_reason is null
    or length(btrim(correction_reason)) between 3 and 1000
  ),
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  retention_expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, observation_id, id),
  unique (organization_id, observation_id, observation_hash, analysis_version),
  unique (organization_id, event_hash),
  unique (organization_id, idempotency_key),
  foreign key (
    organization_id, observation_id, observation_hash, retention_expires_at
  ) references content_factory.research_youtube_video_observations(
    organization_id, id, observation_hash, retention_expires_at
  ) on delete cascade,
  foreign key (organization_id, observation_id, parent_event_id)
    references content_factory.research_youtube_observation_analysis_events(
      organization_id, observation_id, id
    ),
  foreign key (organization_id, actor_id)
    references content_factory.memberships(organization_id, profile_id),
  check (retention_expires_at > created_at),
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

create index research_youtube_analysis_jobs_due_idx
  on content_factory.research_youtube_observation_analysis_jobs
  (status, created_at, id);
create index research_youtube_analysis_jobs_retention_idx
  on content_factory.research_youtube_observation_analysis_jobs
  (retention_expires_at, id);
create index research_youtube_analysis_events_head_idx
  on content_factory.research_youtube_observation_analysis_events
  (organization_id, observation_id, analysis_version desc, id desc);
create index research_youtube_analysis_events_retention_idx
  on content_factory.research_youtube_observation_analysis_events
  (retention_expires_at, id);

alter table content_factory.research_youtube_observation_analysis_jobs
  enable row level security;
alter table content_factory.research_youtube_observation_analysis_events
  enable row level security;
revoke all on table content_factory.research_youtube_observation_analysis_jobs
  from public, anon, authenticated, service_role;
revoke all on table content_factory.research_youtube_observation_analysis_events
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_youtube_analysis_event_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE'
     and current_setting('content_factory.youtube_retention_purge', true) = 'on' then
    return old;
  end if;
  raise exception using
    errcode = '55000',
    message = 'research_youtube_observation_analysis_events_append_only';
end;
$$;

create trigger reject_research_youtube_analysis_event_mutation
before update or delete
on content_factory.research_youtube_observation_analysis_events
for each row execute function
  content_factory_private.reject_research_youtube_analysis_event_mutation();

create or replace function content_factory_private.research_youtube_analysis_input_hash(
  ingestion_id_value uuid
)
returns text
language sql
stable
set search_path = ''
as $$
  select content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-observation-analysis-input-v1',
    'ingestion_id', ingestion_id_value,
    'observation_hashes', coalesce(jsonb_agg(
      observation.observation_hash
      order by observation.search_position, observation.id
    ), '[]'::jsonb)
  ))
  from content_factory.research_youtube_video_observations observation
  where observation.ingestion_id = ingestion_id_value;
$$;

create or replace function content_factory_private.enqueue_research_youtube_observation_analysis()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  input_hash_value text;
  retention_expires_at_value timestamptz;
  job_hash_value text;
begin
  if old.status = new.status or new.status <> 'completed' then
    return new;
  end if;
  -- Serialize enqueue with approval changes so a completed ingestion cannot be
  -- stranded in approval_required immediately after the gate becomes approved.
  perform pg_advisory_xact_lock(
    hashtext('research-youtube-derived-analysis'), 0
  );
  select
    content_factory_private.research_youtube_analysis_input_hash(new.id),
    max(observation.retention_expires_at)
  into input_hash_value, retention_expires_at_value
  from content_factory.research_youtube_video_observations observation
  where observation.organization_id = new.organization_id
    and observation.ingestion_id = new.id;
  if retention_expires_at_value is null then
    return new;
  end if;
  job_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-observation-analysis-job-v1',
    'organization_id', new.organization_id,
    'ingestion_id', new.id,
    'parser_key', 'youtube_observation_deterministic',
    'parser_version', '1.0.0',
    'input_hash', input_hash_value,
    'retention_expires_at', retention_expires_at_value
  ));
  insert into content_factory.research_youtube_observation_analysis_jobs (
    organization_id, ingestion_id, parser_key, parser_version, status,
    input_hash, retention_expires_at, job_hash
  ) values (
    new.organization_id, new.id, 'youtube_observation_deterministic',
    '1.0.0', case
      when content_factory_private.research_youtube_derived_analysis_approved()
        then 'queued'
      else 'approval_required'
    end, input_hash_value, retention_expires_at_value,
    job_hash_value
  ) on conflict (organization_id, ingestion_id, parser_version) do nothing;
  return new;
end;
$$;

create trigger enqueue_research_youtube_observation_analysis
after update of status on content_factory.research_youtube_ingestion_runs
for each row execute function
  content_factory_private.enqueue_research_youtube_observation_analysis();

-- Backfill only still-retained completed ingestions.  It creates local work;
-- it does not contact YouTube and does not retry the original ingestion.
insert into content_factory.research_youtube_observation_analysis_jobs (
  organization_id, ingestion_id, parser_key, parser_version, status,
  input_hash, retention_expires_at, job_hash
)
select ingestion.organization_id, ingestion.id,
  'youtube_observation_deterministic', '1.0.0', case
    when content_factory_private.research_youtube_derived_analysis_approved()
      then 'queued'
    else 'approval_required'
  end,
  prepared.input_hash, prepared.retention_expires_at,
  content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-observation-analysis-job-v1',
    'organization_id', ingestion.organization_id,
    'ingestion_id', ingestion.id,
    'parser_key', 'youtube_observation_deterministic',
    'parser_version', '1.0.0',
    'input_hash', prepared.input_hash,
    'retention_expires_at', prepared.retention_expires_at
  ))
from content_factory.research_youtube_ingestion_runs ingestion
join lateral (
  select content_factory_private.research_youtube_analysis_input_hash(
      ingestion.id
    ) as input_hash,
    max(observation.retention_expires_at) as retention_expires_at
  from content_factory.research_youtube_video_observations observation
  where observation.organization_id = ingestion.organization_id
    and observation.ingestion_id = ingestion.id
) prepared on prepared.retention_expires_at > clock_timestamp()
where ingestion.status = 'completed'
on conflict (organization_id, ingestion_id, parser_version) do nothing;

create or replace function content_factory_private.research_youtube_observation_analysis_payload(
  observation_id_value uuid
)
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  observation_row content_factory.research_youtube_video_observations%rowtype;
  query_text_value text;
  query_token_count_value integer := 0;
  query_token_overlap_count_value integer := 0;
  published_age_days_value integer := 0;
  same_channel_observation_count_value integer := 1;
  counters_present_value boolean := false;
  priority_value integer := 0;
  classification_value text := 'unknown';
  confidence_value text := 'low';
  recommendation_value text := 'needs_more_evidence';
  summary_value text;
begin
  select observation.* into observation_row
  from content_factory.research_youtube_video_observations observation
  where observation.id = observation_id_value;
  if observation_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_observation_not_found';
  end if;
  select ingestion.query_text into query_text_value
  from content_factory.research_youtube_ingestion_runs ingestion
  where ingestion.organization_id = observation_row.organization_id
    and ingestion.id = observation_row.ingestion_id;

  with query_tokens as (
    select distinct token.value
    from regexp_split_to_table(
      lower(query_text_value), '[^[:alnum:]_]+'
    ) token(value)
    where length(token.value) >= 3
    order by token.value
    limit 50
  ), title_tokens as (
    select distinct token.value
    from regexp_split_to_table(
      lower(observation_row.title), '[^[:alnum:]_]+'
    ) token(value)
    where length(token.value) >= 3
  )
  select
    (select count(*)::integer from query_tokens),
    (select count(*)::integer
       from query_tokens query_token
       join title_tokens title_token using (value))
  into query_token_count_value, query_token_overlap_count_value;

  published_age_days_value := greatest(0, floor(extract(epoch from (
    observation_row.observed_at - observation_row.published_at
  )) / 86400)::integer);
  select greatest(1, count(distinct candidate.video_id)::integer)
  into same_channel_observation_count_value
  from content_factory.research_youtube_video_observations candidate
  where candidate.organization_id = observation_row.organization_id
    and candidate.ingestion_id = observation_row.ingestion_id
    and candidate.channel_id = observation_row.channel_id;
  counters_present_value := observation_row.view_count is not null
    or observation_row.like_count is not null
    or observation_row.comment_count is not null;

  priority_value := least(100,
    case when query_token_count_value > 0 then floor(
      40.0 * query_token_overlap_count_value / query_token_count_value
    )::integer else 0 end
    + greatest(0, 20 - ((observation_row.search_position - 1) * 2))
    + case
        when published_age_days_value <= 30 then 15
        when published_age_days_value <= 90 then 8
        else 0
      end
    + case when same_channel_observation_count_value >= 2 then 15 else 0 end
    + case when counters_present_value then 10 else 0 end
  );

  if query_token_overlap_count_value > 0
     and same_channel_observation_count_value >= 2 then
    classification_value := 'potential_competitor';
    recommendation_value := 'review_candidate';
    if counters_present_value then
      confidence_value := 'medium';
    end if;
    summary_value := format(
      'Детерминированный парсер предлагает проверить канал как возможного конкурента: совпало токенов запроса %s из %s, канал представлен %s видео в этом bounded-сборе.',
      query_token_overlap_count_value, query_token_count_value,
      same_channel_observation_count_value
    );
  elsif query_token_overlap_count_value > 0 then
    classification_value := 'adjacent';
    summary_value := format(
      'Детерминированный парсер нашёл смежное наблюдение: совпало токенов запроса %s из %s, но одного видео недостаточно для гипотезы о конкуренте.',
      query_token_overlap_count_value, query_token_count_value
    );
  else
    summary_value := format(
      'Детерминированный парсер не нашёл достаточного совпадения с запросом категории: проверено %s нормализованных токенов; требуется дополнительное доказательство.',
      query_token_count_value
    );
  end if;

  return jsonb_build_object(
    'schema_version', 'research-youtube-observation-analysis-v1',
    'classification', classification_value,
    'review_priority', priority_value,
    'confidence', confidence_value,
    'recommendation', recommendation_value,
    'signals', jsonb_build_object(
      'search_position', observation_row.search_position,
      'query_token_overlap_count', query_token_overlap_count_value,
      'query_token_count', query_token_count_value,
      'published_age_days', published_age_days_value,
      'same_channel_observation_count', same_channel_observation_count_value,
      'counters_present', counters_present_value
    ),
    'summary', summary_value,
    'limitations', jsonb_build_array(
      'Гипотеза основана только на official public metadata, token overlap, позиции, свежести и повторяемости канала.',
      'Она не подтверждает конкурента или тренд и не содержит captions, transcript либо raw provider payload.',
      'Подтверждение или исключение кандидата остаётся отдельным человеческим решением.'
    )
  );
end;
$$;

create or replace function
  public.system_decide_research_youtube_derived_analysis(
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
  analytics_amendment_ack_value boolean;
  approval_reference_value text;
  reason_value text;
  idempotency_key_value text;
  decision_hash_value text;
  decided_at_value timestamptz;
  decision_row content_factory.research_youtube_derived_analysis_decisions%rowtype;
  current_decision_row
    content_factory.research_youtube_derived_analysis_decisions%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'decision', 'terms_version', 'terms_review_ack',
       'analytics_amendment_ack', 'approval_reference', 'reason',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'decision', 'terms_version', 'terms_review_ack',
       'analytics_amendment_ack', 'approval_reference', 'reason',
       'idempotency_key'
     ]::text[]
     or jsonb_typeof(p_payload -> 'terms_review_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'analytics_amendment_ack') <> 'boolean'
     or jsonb_typeof(p_payload -> 'approval_reference')
       not in ('null', 'string') then
    raise exception using
      errcode = '22023',
      message = 'research_youtube_derived_analysis_decision_payload_invalid';
  end if;
  decision_value := btrim(coalesce(p_payload ->> 'decision', ''));
  terms_version_value := btrim(coalesce(p_payload ->> 'terms_version', ''));
  terms_review_ack_value := (p_payload ->> 'terms_review_ack')::boolean;
  analytics_amendment_ack_value :=
    (p_payload ->> 'analytics_amendment_ack')::boolean;
  approval_reference_value := nullif(
    btrim(coalesce(p_payload ->> 'approval_reference', '')), ''
  );
  reason_value := btrim(coalesce(p_payload ->> 'reason', ''));
  idempotency_key_value := btrim(
    coalesce(p_payload ->> 'idempotency_key', '')
  );
  if decision_value not in (
       'approval_required', 'approved', 'emergency_paused'
     )
     or terms_version_value
       <> 'youtube-derived-metrics-policy-2026-06-01-v1'
     or length(reason_value) not between 3 and 500
     or length(idempotency_key_value) not between 8 and 180
     or (approval_reference_value is not null
       and length(approval_reference_value) not between 3 and 160)
     or (decision_value = 'approved' and (
       not terms_review_ack_value
       or not analytics_amendment_ack_value
       or approval_reference_value is null
     ))
     or (decision_value <> 'approved' and (
       terms_review_ack_value
       or analytics_amendment_ack_value
       or approval_reference_value is not null
     )) then
    raise exception using
      errcode = '55000',
      message = 'research_youtube_derived_analysis_approval_required';
  end if;
  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-derived-analysis-decision-v1',
    'decision', decision_value,
    'terms_version', terms_version_value,
    'terms_review_ack', terms_review_ack_value,
    'analytics_amendment_ack', analytics_amendment_ack_value,
    'approval_reference', approval_reference_value,
    'reason', reason_value,
    'idempotency_key', idempotency_key_value
  ));

  perform pg_advisory_xact_lock(
    hashtext('research-youtube-derived-analysis'), 0
  );
  select decision.* into decision_row
  from content_factory.research_youtube_derived_analysis_decisions decision
  where decision.idempotency_key = idempotency_key_value;
  if decision_row.id is not null then
    if decision_row.decision_hash <> decision_hash_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
  else
    -- The timestamp is assigned only after the global lock is held, so the
    -- append order and canonical head order cannot disagree under contention.
    decided_at_value := clock_timestamp();
    insert into content_factory.research_youtube_derived_analysis_decisions (
      provider_key, adapter_version, decision, terms_version,
      terms_review_ack, analytics_amendment_ack, approval_reference, reason,
      decided_at, idempotency_key, decision_hash
    ) values (
      'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
      decision_value, terms_version_value, terms_review_ack_value,
      analytics_amendment_ack_value, approval_reference_value, reason_value,
      decided_at_value, idempotency_key_value, decision_hash_value
    ) returning * into decision_row;
  end if;

  select decision.* into current_decision_row
  from content_factory.research_youtube_derived_analysis_decisions decision
  order by decision.decided_at desc, decision.id desc
  limit 1;

  -- An idempotent replay returns its original receipt, but side effects always
  -- reconcile from the latest canonical gate decision.
  if current_decision_row.decision = 'approved' then
    update content_factory.research_youtube_observation_analysis_jobs job
    set status = 'queued'
    where job.status = 'approval_required'
      and job.attempt_count = 0
      and job.retention_expires_at > clock_timestamp();
  else
    update content_factory.research_youtube_observation_analysis_jobs job
    set status = 'approval_required'
    where job.status = 'queued' and job.attempt_count = 0;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-youtube-derived-analysis-approval-v1',
    'decision', decision_row.decision,
    'decision_id', decision_row.id,
    'approval_reference', decision_row.approval_reference,
    'decided_at', decision_row.decided_at,
    'external_call_started', false,
    'automatic_retry_started', false
  );
end;
$$;

create or replace function public.system_process_due_research_youtube_observation_analysis(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer := 6;
  job_row content_factory.research_youtube_observation_analysis_jobs%rowtype;
  observation_row content_factory.research_youtube_video_observations%rowtype;
  analysis_value jsonb;
  request_hash_value text;
  event_hash_value text;
  current_input_hash_value text;
  parsed_count_value integer;
  selected_count_value integer := 0;
  completed_count_value integer := 0;
  failed_count_value integer := 0;
  items_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_analysis_process_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'research_youtube_analysis_process_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
    if limit_value not between 1 and 6 then
      raise exception using
        errcode = '22023', message = 'research_youtube_analysis_process_limit_invalid';
    end if;
  end if;

  perform pg_advisory_xact_lock(
    hashtext('research-youtube-derived-analysis'), 0
  );
  if not content_factory_private.research_youtube_derived_analysis_approved()
  then
    update content_factory.research_youtube_observation_analysis_jobs job
    set status = 'approval_required'
    where job.status = 'queued' and job.attempt_count = 0;
    return jsonb_build_object(
      'ok', true,
      'selected', 0,
      'completed', 0,
      'failed', 0,
      'items', '[]'::jsonb,
      'external_call_started', false,
      'provider_attempt_count', 0,
      'cost_minor', 0,
      'automatic_retry_started', false
    );
  end if;

  for job_row in
    select job.*
    from content_factory.research_youtube_observation_analysis_jobs job
    where job.status = 'queued'
    order by job.created_at, job.id
    limit limit_value
    for update skip locked
  loop
    selected_count_value := selected_count_value + 1;
    update content_factory.research_youtube_observation_analysis_jobs job
    set status = 'processing', attempt_count = 1,
        claimed_at = clock_timestamp()
    where job.id = job_row.id
    returning * into job_row;
    begin
      if job_row.retention_expires_at <= clock_timestamp() then
        raise exception using
          errcode = '55000', message = 'analysis_evidence_expired';
      end if;
      current_input_hash_value :=
        content_factory_private.research_youtube_analysis_input_hash(
          job_row.ingestion_id
        );
      if current_input_hash_value <> job_row.input_hash then
        raise exception using
          errcode = '55000', message = 'analysis_input_changed';
      end if;
      parsed_count_value := 0;
      for observation_row in
        select observation.*
        from content_factory.research_youtube_video_observations observation
        where observation.organization_id = job_row.organization_id
          and observation.ingestion_id = job_row.ingestion_id
          and observation.retention_expires_at > clock_timestamp()
        order by observation.search_position, observation.id
      loop
        perform pg_advisory_xact_lock(
          hashtext(observation_row.organization_id::text),
          hashtext('research-youtube-observation-analysis:'
            || observation_row.id::text)
        );
        if exists (
          select 1
          from content_factory.research_youtube_observation_analysis_events event
          where event.organization_id = observation_row.organization_id
            and event.observation_id = observation_row.id
        ) then
          parsed_count_value := parsed_count_value + 1;
          continue;
        end if;
        analysis_value :=
          content_factory_private.research_youtube_observation_analysis_payload(
            observation_row.id
          );
        if not coalesce(
          content_factory_private.research_youtube_observation_analysis_is_valid(
            analysis_value
          ), false
        ) then
          raise exception using
            errcode = '22023', message = 'analysis_parser_failed';
        end if;
        request_hash_value := content_factory_private.json_hash(
          jsonb_build_object(
            'version', 'research-youtube-observation-analysis-request-v1',
            'job_id', job_row.id,
            'input_hash', job_row.input_hash,
            'observation_id', observation_row.id,
            'observation_hash', observation_row.observation_hash
          )
        );
        event_hash_value := content_factory_private.json_hash(
          jsonb_build_object(
            'version', 'research-youtube-observation-analysis-event-v1',
            'organization_id', observation_row.organization_id,
            'observation_id', observation_row.id,
            'observation_hash', observation_row.observation_hash,
            'analysis_version', 1,
            'origin', 'system_parser',
            'parser_key', job_row.parser_key,
            'parser_version', job_row.parser_version,
            'analysis', analysis_value,
            'retention_expires_at', observation_row.retention_expires_at
          )
        );
        insert into content_factory.research_youtube_observation_analysis_events (
          organization_id, observation_id, observation_hash, analysis_version,
          parent_event_id, expected_parent_hash, origin, actor_id, parser_key,
          parser_version, analysis, correction_reason, request_hash, event_hash,
          idempotency_key, retention_expires_at
        ) values (
          observation_row.organization_id, observation_row.id,
          observation_row.observation_hash, 1, null, null, 'system_parser',
          null, job_row.parser_key, job_row.parser_version, analysis_value, null,
          request_hash_value, event_hash_value,
          'youtube-analysis:' || observation_row.id::text || ':1.0.0',
          observation_row.retention_expires_at
        ) on conflict (organization_id, idempotency_key) do nothing;
        parsed_count_value := parsed_count_value + 1;
      end loop;
      update content_factory.research_youtube_observation_analysis_jobs job
      set status = 'completed', completed_at = clock_timestamp(),
          parsed_count = parsed_count_value
      where job.id = job_row.id;
      completed_count_value := completed_count_value + 1;
      items_value := items_value || jsonb_build_array(jsonb_build_object(
        'job_id', job_row.id,
        'ingestion_id', job_row.ingestion_id,
        'status', 'completed',
        'parsed_count', parsed_count_value
      ));
    exception when others then
      update content_factory.research_youtube_observation_analysis_jobs job
      set status = 'failed', completed_at = clock_timestamp(), parsed_count = 0,
          error_code = case sqlerrm
            when 'analysis_input_changed' then 'analysis_input_changed'
            when 'analysis_evidence_expired' then 'analysis_evidence_expired'
            else 'analysis_parser_failed'
          end,
          error_message = left(sqlerrm, 1000)
      where job.id = job_row.id;
      failed_count_value := failed_count_value + 1;
      items_value := items_value || jsonb_build_array(jsonb_build_object(
        'job_id', job_row.id,
        'ingestion_id', job_row.ingestion_id,
        'status', 'failed',
        'error_code', case sqlerrm
          when 'analysis_input_changed' then 'analysis_input_changed'
          when 'analysis_evidence_expired' then 'analysis_evidence_expired'
          else 'analysis_parser_failed'
        end
      ));
    end;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'selected', selected_count_value,
    'completed', completed_count_value,
    'failed', failed_count_value,
    'items', items_value,
    'external_call_started', false,
    'provider_attempt_count', 0,
    'cost_minor', 0,
    'automatic_retry_started', false
  );
end;
$$;

create or replace function public.creator_correct_research_youtube_observation_analysis(
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
  observation_id_value uuid;
  observation_hash_value text;
  expected_head_event_id_value uuid;
  expected_head_hash_value text;
  correction_reason_value text;
  analysis_value jsonb;
  idempotency_key_value text;
  request_payload jsonb;
  replay_result jsonb;
  observation_row content_factory.research_youtube_video_observations%rowtype;
  current_head content_factory.research_youtube_observation_analysis_events%rowtype;
  event_row content_factory.research_youtube_observation_analysis_events%rowtype;
  event_hash_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'observation_id', 'observation_hash',
    'expected_head_event_id', 'expected_head_hash', 'analysis',
    'correction_reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_youtube_analysis_correction_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  observation_id_value := content_factory_private.require_uuid(
    p_payload, 'observation_id'
  );
  observation_hash_value := content_factory_private.require_text(
    p_payload, 'observation_hash', 64, 64
  );
  expected_head_event_id_value := content_factory_private.require_uuid(
    p_payload, 'expected_head_event_id'
  );
  expected_head_hash_value := content_factory_private.require_text(
    p_payload, 'expected_head_hash', 64, 64
  );
  correction_reason_value := content_factory_private.require_text(
    p_payload, 'correction_reason', 3, 1000
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  analysis_value := p_payload -> 'analysis';
  if observation_hash_value !~ '^[0-9a-f]{64}$'
     or expected_head_hash_value !~ '^[0-9a-f]{64}$'
     or not coalesce(
       content_factory_private.research_youtube_observation_analysis_is_valid(
         analysis_value
       ), false
     ) then
    raise exception using
      errcode = '22023', message = 'research_youtube_observation_analysis_invalid';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  -- Approval changes, parser writes and corrections share one lock. Once this
  -- check succeeds the gate cannot be paused before the correction commits.
  perform pg_advisory_xact_lock(
    hashtext('research-youtube-derived-analysis'), 0
  );
  if not content_factory_private.research_youtube_derived_analysis_approved()
  then
    raise exception using
      errcode = '55000',
      message = 'research_youtube_derived_analysis_approval_required';
  end if;
  select observation.* into observation_row
  from content_factory.research_youtube_video_observations observation
  join content_factory.memberships membership
    on membership.organization_id = observation.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where observation.organization_id = organization_id_value
    and observation.id = observation_id_value
    and observation.observation_hash = observation_hash_value
    and observation.retention_expires_at > clock_timestamp();
  if observation_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_youtube_observation_not_found';
  end if;

  request_payload := p_payload - 'idempotency_key';
  replay_result := content_factory_private.begin_command(
    organization_id_value,
    'creator_correct_research_youtube_observation_analysis',
    idempotency_key_value,
    request_payload
  );
  if replay_result is not null then
    return replay_result;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-youtube-observation-analysis:'
      || observation_id_value::text)
  );
  select event.* into current_head
  from content_factory.research_youtube_observation_analysis_events event
  where event.organization_id = organization_id_value
    and event.observation_id = observation_id_value
    and event.observation_hash = observation_hash_value
    and event.retention_expires_at > clock_timestamp()
  order by event.analysis_version desc, event.id desc
  limit 1;
  if current_head.id is null
     or current_head.id <> expected_head_event_id_value
     or current_head.event_hash <> expected_head_hash_value then
    raise exception using
      errcode = '40001', message = 'research_youtube_observation_analysis_head_stale';
  end if;

  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-youtube-observation-analysis-event-v1',
    'organization_id', organization_id_value,
    'observation_id', observation_id_value,
    'observation_hash', observation_hash_value,
    'analysis_version', current_head.analysis_version + 1,
    'parent_event_id', current_head.id,
    'expected_parent_hash', current_head.event_hash,
    'origin', 'human_correction',
    'actor_id', user_id,
    'analysis', analysis_value,
    'correction_reason', correction_reason_value,
    'retention_expires_at', observation_row.retention_expires_at
  ));
  insert into content_factory.research_youtube_observation_analysis_events (
    organization_id, observation_id, observation_hash, analysis_version,
    parent_event_id, expected_parent_hash, origin, actor_id, parser_key,
    parser_version, analysis, correction_reason, request_hash, event_hash,
    idempotency_key, retention_expires_at
  ) values (
    organization_id_value, observation_id_value, observation_hash_value,
    current_head.analysis_version + 1, current_head.id,
    current_head.event_hash, 'human_correction', user_id,
    'human_correction', 'v1', analysis_value, correction_reason_value,
    content_factory_private.json_hash(request_payload), event_hash_value,
    idempotency_key_value, observation_row.retention_expires_at
  ) returning * into event_row;
  result_value := jsonb_build_object(
    'ok', true,
    'event_id', event_row.id,
    'event_hash', event_row.event_hash,
    'analysis_version', event_row.analysis_version,
    'origin', event_row.origin,
    'retention_expires_at', event_row.retention_expires_at,
    'external_call_started', false,
    'provider_attempt_count', 0,
    'automatic_retry_started', false
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'research_youtube_observation_analysis_corrected',
    'research_youtube_observation',
    observation_id_value::text,
    jsonb_build_object(
      'event_id', event_row.id,
      'analysis_version', event_row.analysis_version,
      'event_hash', event_row.event_hash,
      'candidate_decision_changed', false
    ),
    'research-youtube-analysis-correction:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_correct_research_youtube_observation_analysis',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

-- Readiness v3 gives analysis credit only to an actual parser head.  The
-- proposal still cannot create competitor or trend credit.  A human correction
-- validates that analysis only; a confirmed competitor remains the separate
-- candidate decision already counted by v2.
alter function content_factory_private.research_category_evidence_readiness(
  uuid, uuid, timestamptz
) rename to research_category_evidence_readiness_v2_base;

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
  base_value jsonb;
  dimensions_value jsonb;
  social_analysis_count_value integer := 0;
  social_human_count_value integer := 0;
  current_analysis_count_value integer := 0;
  current_human_count_value integer := 0;
  social_event_hashes_value jsonb := '[]'::jsonb;
  score_value integer := 0;
begin
  base_value :=
    content_factory_private.research_category_evidence_readiness_v2_base(
      organization_id_value, market_category_id_value, as_of_value
    );

  with latest_observations as (
    select distinct on (observation.video_id) observation.*
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = organization_id_value
      and observation.market_category_id = market_category_id_value
      and observation.observed_at <= as_of_value
      and observation.retention_expires_at > as_of_value
    order by observation.video_id, observation.observed_at desc,
      observation.observation_hash desc, observation.id desc
  ), observed as (
    select observation.*,
      decision.decision,
      head.origin as analysis_origin,
      head.event_hash as analysis_event_hash
    from latest_observations observation
    left join lateral (
      select candidate.decision
      from content_factory.research_youtube_candidate_decisions candidate
      where candidate.organization_id = observation.organization_id
        and candidate.observation_id = observation.id
        and candidate.decided_at <= as_of_value
        and candidate.retention_expires_at > as_of_value
      order by candidate.decided_at desc, candidate.decision_hash desc,
        candidate.id desc
      limit 1
    ) decision on true
    left join lateral (
      select event.origin, event.event_hash
      from content_factory.research_youtube_observation_analysis_events event
      where event.organization_id = observation.organization_id
        and event.observation_id = observation.id
        and event.observation_hash = observation.observation_hash
        and event.created_at <= as_of_value
        and event.retention_expires_at > as_of_value
      order by event.analysis_version desc, event.id desc
      limit 1
    ) head on true
  )
  select
    count(*) filter (
      where observed.analysis_event_hash is not null
        and observed.decision is distinct from 'exclude_candidate'
    )::integer,
    count(*) filter (
      where observed.analysis_event_hash is not null
        and observed.analysis_origin = 'human_correction'
        and observed.decision is null
    )::integer,
    coalesce(jsonb_agg(observed.analysis_event_hash
      order by observed.analysis_event_hash) filter (
        where observed.analysis_event_hash is not null
      ), '[]'::jsonb)
  into social_analysis_count_value, social_human_count_value,
       social_event_hashes_value
  from observed;

  select (dimension ->> 'current')::integer
  into current_analysis_count_value
  from jsonb_array_elements(base_value -> 'dimensions') dimension
  where dimension ->> 'key' = 'analysis_coverage';
  select (dimension ->> 'current')::integer
  into current_human_count_value
  from jsonb_array_elements(base_value -> 'dimensions') dimension
  where dimension ->> 'key' = 'human_validation';

  select jsonb_agg(
    case dimension ->> 'key'
      when 'analysis_coverage' then
        content_factory_private.research_readiness_dimension(
          'analysis_coverage', 'Structured / normalized source coverage', 15,
          coalesce(current_analysis_count_value, 0)
            + social_analysis_count_value,
          8, 'analyze_unreviewed_sources'
        )
      when 'human_validation' then
        content_factory_private.research_readiness_dimension(
          'human_validation', 'Human-validated evidence', 15,
          coalesce(current_human_count_value, 0) + social_human_count_value,
          4, 'review_and_correct_source_analysis'
        )
      else dimension
    end order by ordinal
  )
  into dimensions_value
  from jsonb_array_elements(base_value -> 'dimensions')
    with ordinality item(dimension, ordinal);

  select coalesce(sum((dimension ->> 'weighted_points')::integer), 0)::integer
  into score_value
  from jsonb_array_elements(dimensions_value) dimension;

  return jsonb_build_object(
    'metric_kind', base_value ->> 'metric_kind',
    'definition_version', 'category-evidence-readiness-v3',
    'score', score_value,
    'dimensions', dimensions_value,
    'weights_total', 100,
    'evidence_hash', content_factory_private.json_hash(jsonb_build_object(
      'definition_version', 'category-evidence-readiness-v3',
      'base_evidence_hash', base_value ->> 'evidence_hash',
      'current_retained_youtube_analysis_event_hashes',
        social_event_hashes_value,
      'dimensions', dimensions_value
    )),
    'as_of', as_of_value,
    'limits', (base_value -> 'limits') || jsonb_build_object(
      'meaning',
        'Coverage of durable evidence plus retention-bound YouTube metadata; deterministic parser heads add analysis coverage, while only human decisions add semantic credit'
    )
  );
end;
$$;

alter table content_factory.research_category_readiness_snapshots
  drop constraint research_category_readiness_snapshots_definition_version_check;
alter table content_factory.research_category_readiness_snapshots
  add constraint research_category_readiness_snapshots_definition_version_check
  check (definition_version in (
    'category-evidence-readiness-v1', 'category-evidence-readiness-v2',
    'category-evidence-readiness-v3'
  ));

create or replace function content_factory_private.normalize_research_readiness_snapshot_v2()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.definition_version := 'category-evidence-readiness-v3';
  new.snapshot_hash := content_factory_private.json_hash(jsonb_build_object(
    'version', 'category-evidence-readiness-snapshot-v3',
    'organization_id', new.organization_id,
    'market_category_id', new.market_category_id,
    'product_id', new.product_id,
    'binding_id', new.binding_id,
    'run_id', new.run_id,
    'evidence_hash', new.evidence_hash,
    'score', new.score,
    'dimensions', new.dimensions
  ));
  return new;
end;
$$;

alter function public.creator_research_category_learning_status(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_research_category_learning_status(jsonb)
  rename to creator_research_category_learning_status_pre_social_v2;
revoke all on function
  content_factory_private.creator_research_category_learning_status_pre_social_v2(jsonb)
  from public, anon, authenticated, service_role;

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
  base_value jsonb;
  items_value jsonb := '[]'::jsonb;
  as_of_value timestamptz;
  derived_decision_row
    content_factory.research_youtube_derived_analysis_decisions%rowtype;
begin
  -- Readers share the approval/analysis lock; gate, parser, correction and
  -- retention writers take it exclusively. This pins the enriched status to
  -- the same evidence instant used by the readiness calculation below.
  perform pg_advisory_xact_lock_shared(
    hashtext('research-youtube-derived-analysis'), 0
  );
  base_value :=
    content_factory_private.creator_research_category_learning_status_pre_social_v2(
      p_payload
    );
  as_of_value := (base_value #>> '{metric,readiness,as_of}')::timestamptz;

  select decision.* into derived_decision_row
  from content_factory.research_youtube_derived_analysis_decisions decision
  where decision.decided_at <= as_of_value
  order by decision.decided_at desc, decision.id desc
  limit 1;

  select coalesce(jsonb_agg(
    item.value || jsonb_build_object(
      'current_analysis', (
        select jsonb_build_object(
          'event_id', event.id,
          'analysis_version', event.analysis_version,
          'origin', event.origin,
          'parser_key', event.parser_key,
          'parser_version', event.parser_version,
          'analysis', event.analysis,
          'correction_reason', event.correction_reason,
          'event_hash', event.event_hash,
          'created_at', event.created_at,
          'retention_expires_at', event.retention_expires_at
        )
        from content_factory.research_youtube_observation_analysis_events event
        where event.organization_id = (base_value ->> 'organization_id')::uuid
          and event.observation_id = (item.value ->> 'observation_id')::uuid
          and event.observation_hash = item.value ->> 'observation_hash'
          and event.created_at <= as_of_value
          and event.retention_expires_at > as_of_value
        order by event.analysis_version desc, event.id desc
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
          'created_at', history.created_at,
          'retention_expires_at', history.retention_expires_at
        ) order by history.analysis_version desc), '[]'::jsonb)
        from (
          select event.*
          from content_factory.research_youtube_observation_analysis_events event
          where event.organization_id = (base_value ->> 'organization_id')::uuid
            and event.observation_id = (item.value ->> 'observation_id')::uuid
            and event.observation_hash = item.value ->> 'observation_hash'
            and event.created_at <= as_of_value
            and event.retention_expires_at > as_of_value
          order by event.analysis_version desc, event.id desc
          limit 10
        ) history
      ),
      'analysis_job', (
        select jsonb_build_object(
          'job_id', job.id,
          'status', job.status,
          'attempt_count', job.attempt_count,
          'no_retry', job.no_retry,
          'external_call_started', job.external_call_started,
          'parsed_count', job.parsed_count,
          'error_code', job.error_code,
          'input_hash', job.input_hash,
          'job_hash', job.job_hash,
          'created_at', job.created_at,
          'completed_at', job.completed_at
        )
        from content_factory.research_youtube_observation_analysis_jobs job
        where job.organization_id = (base_value ->> 'organization_id')::uuid
          and job.ingestion_id = (item.value ->> 'ingestion_id')::uuid
          and job.created_at <= as_of_value
          and job.retention_expires_at > as_of_value
        order by job.created_at desc, job.id desc
        limit 1
      ),
      'can_correct_analysis',
        coalesce(derived_decision_row.decision = 'approved', false) and exists (
        select 1
        from content_factory.research_youtube_observation_analysis_events event
        where event.organization_id = (base_value ->> 'organization_id')::uuid
          and event.observation_id = (item.value ->> 'observation_id')::uuid
          and event.observation_hash = item.value ->> 'observation_hash'
          and event.created_at <= as_of_value
          and event.retention_expires_at > as_of_value
      )
    ) order by item.ordinal
  ), '[]'::jsonb)
  into items_value
  from jsonb_array_elements(base_value #> '{retained_youtube_evidence,items}')
    with ordinality item(value, ordinal);

  return jsonb_set(
    jsonb_set(
      jsonb_set(base_value, '{version}',
        to_jsonb('research-category-learning-readiness-v2'::text)),
      '{retained_youtube_evidence}',
      (base_value -> 'retained_youtube_evidence') || jsonb_build_object(
        'items', items_value,
        'analysis_contract', 'research-youtube-observation-analysis-v1',
        'analysis_history_limit_per_observation', 10,
        'analysis_corrected_by',
          'creator_correct_research_youtube_observation_analysis',
        'analysis_external_call_started', false,
        'analysis_automatic_retry_allowed', false
      )
    ),
    '{provider_strategy}',
    jsonb_build_object(
      'version', 'social-observation-adapter-v1',
      'recommended_production_order', jsonb_build_array(
        'youtube_data_api_v3', 'instagram_meta_graph'
      ),
      'youtube_retrieval_capability',
        'official_api_controlled_rollout',
      'youtube_derived_analysis_state', derived_decision_row.decision,
      'youtube_derived_analysis_policy',
        'youtube-derived-metrics-policy-2026-06-01-v1',
      'youtube_derived_analysis_approval_ref',
        derived_decision_row.approval_reference,
      'instagram_activation_gate',
        'oauth_app_review_permissions_and_legal_approval_required',
      'instagram_known_professional_lookup',
        'supported_after_approval',
      'instagram_hashtag_discovery',
        'limited_after_approval',
      'instagram_arbitrary_account_discovery',
        'unsupported_coverage_gap',
      'disabled_by_policy', jsonb_build_array(
        'apify_scraper', 'bright_data_scraper', 'oxylabs_youtube_scraper',
        'dataforseo_youtube_scraper'
      ),
      'recommendation',
        'Use official APIs first; keep YouTube derived analysis approval-gated and expose unsupported coverage instead of silently scraping.'
    )
  );
end;
$$;

alter table content_factory.research_youtube_retention_receipts
  add column analysis_event_deleted_count integer not null default 0
    check (analysis_event_deleted_count >= 0),
  add column analysis_job_deleted_count integer not null default 0
    check (analysis_job_deleted_count >= 0),
  add column analysis_overdue_remaining_count integer not null default 0
    check (analysis_overdue_remaining_count >= 0),
  add column analysis_accounted boolean not null default false;

create or replace function
  content_factory_private.finalize_research_youtube_retention_receipt()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op <> 'UPDATE'
     or coalesce(
       current_setting('content_factory.youtube_retention_purge', true), ''
     ) <> 'on'
     or old.analysis_accounted
     or not new.analysis_accounted
     or row(
       new.id, new.purged_at, new.cutoff_at,
       new.observation_deleted_count,
       new.candidate_decision_deleted_count,
       new.transport_receipt_deleted_count,
       new.transport_attempt_deleted_count,
       new.successful
     ) is distinct from row(
       old.id, old.purged_at, old.cutoff_at,
       old.observation_deleted_count,
       old.candidate_decision_deleted_count,
       old.transport_receipt_deleted_count,
       old.transport_attempt_deleted_count,
       old.successful
     )
     or new.overdue_remaining_count
       <> old.overdue_remaining_count
          + new.analysis_overdue_remaining_count then
    raise exception using
      errcode = '55000',
      message = 'research_youtube_retention_receipts_append_only';
  end if;
  return new;
end;
$$;

drop trigger if exists research_youtube_retention_receipt_immutable
  on content_factory.research_youtube_retention_receipts;
create trigger research_youtube_retention_receipt_immutable
before update or delete on content_factory.research_youtube_retention_receipts
for each row execute function
  content_factory_private.finalize_research_youtube_retention_receipt();

alter function content_factory_private.research_youtube_retention_ready()
  rename to research_youtube_retention_ready_pre_analysis_v1;

create or replace function content_factory_private.research_youtube_retention_ready()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    content_factory_private.research_youtube_retention_ready_pre_analysis_v1()
    and coalesce((
      select receipt.analysis_accounted
      from content_factory.research_youtube_retention_receipts receipt
      order by receipt.purged_at desc, receipt.id desc
      limit 1
    ), false)
    and not exists (
      select 1
      from content_factory.research_youtube_observation_analysis_jobs job
      where job.retention_expires_at <= clock_timestamp()
    )
    and not exists (
      select 1
      from content_factory.research_youtube_observation_analysis_events event
      where event.retention_expires_at <= clock_timestamp()
    );
$$;

alter function public.system_purge_expired_youtube_api_data(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_purge_expired_youtube_api_data(jsonb)
  rename to system_purge_expired_youtube_api_data_pre_analysis_v1;
revoke all on function
  content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(jsonb)
  from public, anon, authenticated, service_role;

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
  cutoff_value timestamptz;
  event_before_value integer := 0;
  event_after_value integer := 0;
  event_deleted_count_value integer := 0;
  job_deleted_count_value integer := 0;
  overdue_analysis_count_value integer := 0;
  base_value jsonb;
  combined_receipt_hash_value text;
  combined_overdue_count_value integer := 0;
  receipt_row content_factory.research_youtube_retention_receipts%rowtype;
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
  -- One exclusive analysis lock prevents parser/correction/enqueue writes while
  -- total event deltas are measured. The dedicated purge lock prevents two
  -- retention receipts from accounting for the same cascade.
  perform pg_advisory_xact_lock(
    hashtext('research-youtube-derived-analysis'), 0
  );
  perform pg_advisory_xact_lock(
    hashtext('research-youtube-retention-purge'), 0
  );
  perform set_config('content_factory.youtube_retention_purge', 'on', true);
  select count(*)::integer into event_before_value
  from content_factory.research_youtube_observation_analysis_events;

  -- The legacy purge owns the canonical cutoff and may cascade observation
  -- deletions into analysis events. Reuse its exact returned cutoff everywhere
  -- in the v2 accounting boundary.
  base_value :=
    content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(
      p_payload
    );
  cutoff_value := (base_value ->> 'cutoff_at')::timestamptz;

  with due as (
    select job.id
    from content_factory.research_youtube_observation_analysis_jobs job
    where job.retention_expires_at <= cutoff_value
    order by job.retention_expires_at, job.id
    limit limit_value
    for update skip locked
  ), deleted as (
    delete from content_factory.research_youtube_observation_analysis_jobs job
    using due
    where job.id = due.id
    returning job.id
  )
  select count(*)::integer into job_deleted_count_value from deleted;

  select count(*)::integer into event_after_value
  from content_factory.research_youtube_observation_analysis_events;
  event_deleted_count_value := greatest(
    0, event_before_value - event_after_value
  );
  select
    (select count(*)
       from content_factory.research_youtube_observation_analysis_jobs job
      where job.retention_expires_at <= cutoff_value)
    + (select count(*)
       from content_factory.research_youtube_observation_analysis_events event
      where event.retention_expires_at <= cutoff_value)
  into overdue_analysis_count_value;

  select receipt.* into receipt_row
  from content_factory.research_youtube_retention_receipts receipt
  where receipt.id = (base_value ->> 'receipt_id')::uuid
    and not receipt.analysis_accounted
  for update;
  if receipt_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_youtube_retention_receipt_finalize_failed';
  end if;
  combined_overdue_count_value :=
    receipt_row.overdue_remaining_count + overdue_analysis_count_value;
  combined_receipt_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-youtube-retention-receipt-v2',
      'cutoff_at', receipt_row.cutoff_at,
      'observation_deleted_count', receipt_row.observation_deleted_count,
      'candidate_decision_deleted_count',
        receipt_row.candidate_decision_deleted_count,
      'transport_receipt_deleted_count',
        receipt_row.transport_receipt_deleted_count,
      'transport_attempt_deleted_count',
        receipt_row.transport_attempt_deleted_count,
      'analysis_event_deleted_count', event_deleted_count_value,
      'analysis_job_deleted_count', job_deleted_count_value,
      'analysis_overdue_remaining_count', overdue_analysis_count_value,
      'overdue_remaining_count', combined_overdue_count_value,
      'successful', true,
      'analysis_accounted', true
    )
  );
  update content_factory.research_youtube_retention_receipts receipt
  set analysis_event_deleted_count = event_deleted_count_value,
      analysis_job_deleted_count = job_deleted_count_value,
      analysis_overdue_remaining_count = overdue_analysis_count_value,
      analysis_accounted = true,
      overdue_remaining_count = combined_overdue_count_value,
      receipt_hash = combined_receipt_hash_value
  where receipt.id = receipt_row.id
  returning * into receipt_row;

  return base_value || jsonb_build_object(
    'version', 'research-youtube-retention-v2',
    'analysis_event_deleted_count', event_deleted_count_value,
    'analysis_job_deleted_count', job_deleted_count_value,
    'analysis_overdue_remaining_count', overdue_analysis_count_value,
    'analysis_accounted', true,
    'receipt_hash', combined_receipt_hash_value,
    'overdue_remaining_count', combined_overdue_count_value
  );
end;
$$;

revoke all on function
  content_factory_private.research_youtube_observation_analysis_is_valid(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_derived_analysis_approved()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_analysis_input_hash(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_observation_analysis_payload(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.enqueue_research_youtube_observation_analysis()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_research_youtube_analysis_event_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.finalize_research_youtube_retention_receipt()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_category_evidence_readiness_v2_base(
    uuid, uuid, timestamptz
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_category_evidence_readiness(
    uuid, uuid, timestamptz
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_retention_ready_pre_analysis_v1()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_youtube_retention_ready()
  from public, anon, authenticated, service_role;

revoke all on function
  public.system_decide_research_youtube_derived_analysis(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.system_process_due_research_youtube_observation_analysis(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_correct_research_youtube_observation_analysis(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_research_category_learning_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_purge_expired_youtube_api_data(jsonb)
  from public, anon, authenticated, service_role;

grant execute on function
  public.system_decide_research_youtube_derived_analysis(jsonb)
  to service_role;
grant execute on function
  public.system_process_due_research_youtube_observation_analysis(jsonb)
  to service_role;
grant execute on function
  public.creator_correct_research_youtube_observation_analysis(jsonb)
  to authenticated;
grant execute on function
  public.creator_research_category_learning_status(jsonb)
  to authenticated;
grant execute on function public.system_purge_expired_youtube_api_data(jsonb)
  to service_role;

comment on table content_factory.research_youtube_observation_analysis_jobs is
  'Single-attempt local parser work. It starts no provider call, retry, fallback or generation.';
comment on table
  content_factory.research_youtube_derived_analysis_decisions is
  'Append-only operator gate separating official YouTube retrieval from amendment-approved derived analytics.';
comment on table content_factory.research_youtube_observation_analysis_events is
  'Append-only, editable parser hypotheses bound to exact retention-limited YouTube observations; never canonical competitor or trend truth.';
comment on function
  public.system_decide_research_youtube_derived_analysis(jsonb) is
  'Records the audited analytics-amendment approval gate; approval starts no provider call and only releases retained local work.';
comment on function
  public.system_process_due_research_youtube_observation_analysis(jsonb) is
  'Processes bounded deterministic local analysis work with zero HTTP calls, provider attempts, cost and automatic retries.';
comment on function
  public.creator_correct_research_youtube_observation_analysis(jsonb) is
  'Appends a human correction to an exact active observation-analysis head; candidate confirmation remains separate.';

select pg_notify('pgrst', 'reload schema');

commit;
