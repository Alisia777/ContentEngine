begin;

-- An approved generation handoff is an immutable, server-owned snapshot.
-- Editing, recomputing and reverting always append a new version; approval
-- and head changes are separate append-only ledgers.  None of the control
-- RPCs below can start a provider request or authorize spend.
create table content_factory.generation_spec_versions (
    version_id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null check (spec_version between 1 and 100000),
    previous_version_id uuid,
    product_id uuid not null,
    primary_media_id uuid not null,
    media_ids uuid[] not null check (cardinality(media_ids) between 1 and 5),
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    duration_seconds integer not null check (duration_seconds between 0 and 15),
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    format text not null check (format in ('9:16', '16:9', '1:1')),
    audio boolean not null,
    exact_scope jsonb not null check (
      jsonb_typeof(exact_scope) = 'object'
      and exact_scope - array[
        'primary_media_id', 'media_ids', 'platform', 'model',
        'duration_seconds', 'product_category', 'format', 'audio'
      ]::text[] = '{}'::jsonb
      and exact_scope ?& array[
        'primary_media_id', 'media_ids', 'platform', 'model',
        'duration_seconds', 'product_category', 'format', 'audio'
      ]::text[]
    ),
    editable_intent text not null check (
      length(btrim(editable_intent)) between 1 and 1200
    ),
    compiled_prompt text not null check (length(compiled_prompt) between 1 and 20000),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    research_provenance jsonb,
    research_snapshot_hash text check (
      research_snapshot_hash is null or research_snapshot_hash ~ '^[0-9a-f]{64}$'
    ),
    performance_policy_provenance jsonb,
    repair_provenance jsonb,
    outcome_selection_id uuid,
    outcome_selection_hash text check (
      outcome_selection_hash is null or outcome_selection_hash ~ '^[0-9a-f]{64}$'
    ),
    canonical_learning_context jsonb not null check (
      jsonb_typeof(canonical_learning_context) = 'object'
      and length(canonical_learning_context::text) <= 4096
    ),
    canonical_repair_context jsonb check (
      canonical_repair_context is null
      or (
        jsonb_typeof(canonical_repair_context) = 'object'
        and length(canonical_repair_context::text) <= 4096
      )
    ),
    final_policy jsonb not null check (
      jsonb_typeof(final_policy) = 'object'
      and length(final_policy::text) <= 65536
    ),
    final_policy_hash text not null check (final_policy_hash ~ '^[0-9a-f]{64}$'),
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    reason text not null check (length(btrim(reason)) between 3 and 500),
    created_by uuid not null,
    created_at timestamptz not null default clock_timestamp(),
    constraint generation_spec_versions_org_version_id_uq
      unique (organization_id, version_id),
    constraint generation_spec_versions_org_spec_version_id_uq
      unique (organization_id, spec_id, version_id),
    constraint generation_spec_versions_org_spec_version_uq
      unique (organization_id, spec_id, spec_version),
    constraint generation_spec_versions_org_spec_hash_uq
      unique (organization_id, spec_id, spec_hash),
    constraint generation_spec_versions_exact_identity_uq
      unique (organization_id, spec_id, spec_version, spec_hash),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, primary_media_id, product_id)
      references content_factory.media_objects(organization_id, id, product_id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, outcome_selection_id)
      references content_factory.research_outcome_generation_selections(
        organization_id, id
      ),
    foreign key (organization_id, spec_id, previous_version_id)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, version_id
      ),
    check ((spec_version = 1) = (previous_version_id is null)),
    check ((outcome_selection_id is null) = (outcome_selection_hash is null)),
    check (media_ids[1] = primary_media_id),
    check (exact_scope = jsonb_build_object(
      'primary_media_id', primary_media_id,
      'media_ids', to_jsonb(media_ids),
      'platform', platform,
      'model', model,
      'duration_seconds', duration_seconds,
      'product_category', product_category,
      'format', format,
      'audio', audio
    )),
    check (
      (model = 'gen4_turbo'
       and duration_seconds in (2, 5, 8, 10) and not audio)
      or (model = 'seedance2_fast'
       and duration_seconds in (4, 8, 12, 15) and audio)
      or (model = 'seedream5_lite' and duration_seconds = 0 and not audio)
    )
);

create or replace function content_factory_private.uuid_array_is_unique(
  values_value uuid[]
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select cardinality(values_value) = (
    select count(distinct item.value)
    from unnest(values_value) item(value)
  );
$$;

alter table content_factory.generation_spec_versions
  add constraint generation_spec_versions_media_ids_unique_check
  check (content_factory_private.uuid_array_is_unique(media_ids));

revoke all on function content_factory_private.uuid_array_is_unique(uuid[])
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.raw_text_sha256(
  value_value text
)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select encode(
    extensions.digest(convert_to(value_value, 'UTF8'), 'sha256'),
    'hex'
  );
$$;

revoke all on function content_factory_private.raw_text_sha256(text)
  from public, anon, authenticated, service_role;

-- Reproduce the installed approved-research signal compiler without reading
-- mutable UI state. This is intentionally the same bounded structural
-- inference used by the paid-start signal writer; raw research copy is never
-- returned or persisted in a generation specification.
create or replace function
  content_factory_private.generation_spec_research_structure(
    brief_value jsonb,
    scenario_position_value integer
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  scenario_value jsonb;
  hook_value text;
  research_text text;
  patterns_value jsonb := '[]'::jsonb;
  angle_value text;
begin
  if jsonb_typeof(brief_value) is distinct from 'object'
     or coalesce(scenario_position_value not between 1 and 3, true) then
    return null;
  end if;
  scenario_value := brief_value #> array[
    'scenarios', (scenario_position_value - 1)::text
  ];
  if jsonb_typeof(scenario_value) <> 'object' then
    return null;
  end if;
  hook_value := btrim(coalesce(scenario_value ->> 'hook', ''));
  research_text := lower(concat_ws(
    ' ', hook_value, scenario_value -> 'shot_list',
    brief_value #>> '{task_blueprint,mandatory_shots}'
  ));
  if position('?' in hook_value) > 0 then
    patterns_value := patterns_value || '"question_led"'::jsonb;
  end if;
  if research_text ~* '(why|почему|зачем)' then
    patterns_value := patterns_value || '"why_explanation"'::jsonb;
  end if;
  if research_text ~* '(before|до покупки|перед покупкой)' then
    patterns_value := patterns_value || '"before_buying"'::jsonb;
  end if;
  if research_text ~*
       '(compare|versus|(^|[^a-z])vs([^a-z]|$)|сравн|дешев)' then
    patterns_value := patterns_value || '"comparison"'::jsonb;
  end if;
  if research_text ~* '(watch|show|see|смотр|покаж)' then
    patterns_value := patterns_value || '"demonstration"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(i|my|я|мой|моя|мне)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"first_person"'::jsonb;
  end if;
  if research_text ~ '[0-9]'
     or research_text ~*
       '(^|[^[:alnum:]_])(one|один|одна|три|three)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"numbered"'::jsonb;
  end if;
  if length(hook_value) between 1 and 72 then
    patterns_value := patterns_value || '"concise"'::jsonb;
  end if;
  angle_value := case
    when patterns_value @> '["comparison"]'::jsonb then 'comparison'
    when patterns_value @> '["before_buying"]'::jsonb
      or patterns_value @> '["why_explanation"]'::jsonb
      then 'objection_handling'
    when patterns_value @> '["demonstration"]'::jsonb then 'demonstration'
    when patterns_value @> '["question_led"]'::jsonb then 'curiosity_gap'
    when research_text ~* '(честн|довер|спокойн|реальн|trust)'
      then 'trust_builder'
    else 'product_focus'
  end;
  return jsonb_build_object(
    'creative_angle', angle_value,
    'hook_patterns', patterns_value,
    'compiler_version', 'safe-brief-v7'
  );
end;
$$;

revoke all on function
  content_factory_private.generation_spec_research_structure(jsonb, integer)
  from public, anon, authenticated, service_role;

create index generation_spec_versions_scope_idx
  on content_factory.generation_spec_versions (
    organization_id, product_id, product_category, platform, model,
    created_at desc, version_id desc
  );

create table content_factory.generation_spec_approval_events (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null,
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    action text not null check (action in ('approve', 'reject')),
    confirmation boolean not null check (confirmation),
    reason text not null check (length(btrim(reason)) between 3 and 500),
    actor_id uuid not null,
    event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    created_at timestamptz not null default clock_timestamp(),
    constraint generation_spec_approval_events_org_id_uq
      unique (organization_id, id),
    constraint generation_spec_approval_events_org_hash_uq
      unique (organization_id, event_hash),
    constraint generation_spec_approval_events_org_key_uq
      unique (organization_id, idempotency_key),
    foreign key (organization_id, spec_id, spec_version, spec_hash)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, spec_version, spec_hash
      ),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id)
);

create table content_factory.generation_spec_head_events (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    spec_id uuid not null,
    event_sequence integer not null check (event_sequence between 1 and 200000),
    action text not null check (action in (
      'prepare', 'patch', 'approve', 'reject', 'revert', 'recompute'
    )),
    state text not null check (state in ('draft', 'approved', 'rejected')),
    spec_version integer not null,
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    prior_event_id uuid,
    approval_event_id uuid,
    reason text not null check (length(btrim(reason)) between 3 and 500),
    actor_id uuid not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default clock_timestamp(),
    constraint generation_spec_head_events_org_id_uq
      unique (organization_id, id),
    constraint generation_spec_head_events_org_sequence_uq
      unique (organization_id, spec_id, event_sequence),
    constraint generation_spec_head_events_org_hash_uq
      unique (organization_id, event_hash),
    foreign key (organization_id, spec_id, spec_version, spec_hash)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, spec_version, spec_hash
      ),
    foreign key (organization_id, prior_event_id)
      references content_factory.generation_spec_head_events(organization_id, id),
    foreign key (organization_id, approval_event_id)
      references content_factory.generation_spec_approval_events(organization_id, id),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id),
    check ((action in ('approve', 'reject')) = (approval_event_id is not null)),
    check ((event_sequence = 1) = (prior_event_id is null)),
    check (
      (action = 'approve' and state = 'approved')
      or (action = 'reject' and state = 'rejected')
      or (action not in ('approve', 'reject') and state = 'draft')
    )
);

create index generation_spec_head_events_timeline_idx
  on content_factory.generation_spec_head_events (
    organization_id, spec_id, event_sequence desc
  );

create table content_factory.generation_job_spec_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_job_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null,
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    final_policy_hash text not null check (final_policy_hash ~ '^[0-9a-f]{64}$'),
    outcome_selection_id uuid,
    outcome_selection_hash text check (
      outcome_selection_hash is null or outcome_selection_hash ~ '^[0-9a-f]{64}$'
    ),
    context_hash text not null check (context_hash ~ '^[0-9a-f]{64}$'),
    start_request_hash text not null check (
      start_request_hash ~ '^[0-9a-f]{64}$'
    ),
    start_result jsonb not null check (
      jsonb_typeof(start_result) = 'object'
      and length(start_result::text) <= 131072
    ),
    claim_snapshot jsonb not null check (
      jsonb_typeof(claim_snapshot) = 'object'
      and length(claim_snapshot::text) <= 131072
    ),
    claim_snapshot_hash text not null check (
      claim_snapshot_hash ~ '^[0-9a-f]{64}$'
    ),
    bound_by uuid not null,
    bound_at timestamptz not null default clock_timestamp(),
    constraint generation_job_spec_bindings_org_id_uq
      unique (organization_id, id),
    constraint generation_job_spec_bindings_org_job_uq
      unique (organization_id, generation_job_id),
    constraint generation_job_spec_bindings_org_spec_uq
      unique (organization_id, spec_id, spec_version),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, spec_id, spec_version, spec_hash)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, spec_version, spec_hash
      ),
    foreign key (organization_id, outcome_selection_id)
      references content_factory.research_outcome_generation_selections(
        organization_id, id
      ),
    foreign key (organization_id, bound_by)
      references content_factory.memberships(organization_id, profile_id),
    check ((outcome_selection_id is null) = (outcome_selection_hash is null)),
    check (
      claim_snapshot ? 'snapshot_hash'
      and claim_snapshot ->> 'snapshot_hash' = claim_snapshot_hash
      and claim_snapshot_hash = content_factory_private.json_hash(
        claim_snapshot - 'snapshot_hash'
      )
    )
);

alter table content_factory.generation_spec_versions enable row level security;
alter table content_factory.generation_spec_approval_events enable row level security;
alter table content_factory.generation_spec_head_events enable row level security;
alter table content_factory.generation_job_spec_bindings enable row level security;

revoke all on content_factory.generation_spec_versions
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_spec_approval_events
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_spec_head_events
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_job_spec_bindings
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_generation_spec_mutation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000', message = 'generation_spec_ledger_append_only';
end;
$$;

create trigger generation_spec_versions_append_only
before update or delete on content_factory.generation_spec_versions
for each row execute function
  content_factory_private.reject_generation_spec_mutation();
create trigger generation_spec_approval_events_append_only
before update or delete on content_factory.generation_spec_approval_events
for each row execute function
  content_factory_private.reject_generation_spec_mutation();
create trigger generation_spec_head_events_append_only
before update or delete on content_factory.generation_spec_head_events
for each row execute function
  content_factory_private.reject_generation_spec_mutation();
create trigger generation_job_spec_bindings_append_only
before update or delete on content_factory.generation_job_spec_bindings
for each row execute function
  content_factory_private.reject_generation_spec_mutation();

revoke all on function
  content_factory_private.reject_generation_spec_mutation()
  from public, anon, authenticated, service_role;

alter table content_factory.generation_jobs
  add column generation_spec_id uuid,
  add column generation_spec_version integer,
  add column generation_spec_hash text;

alter table content_factory.generation_jobs
  add constraint generation_jobs_spec_identity_shape_check check (
    (generation_spec_id is null
      and generation_spec_version is null
      and generation_spec_hash is null)
    or
    (generation_spec_id is not null
      and generation_spec_version between 1 and 100000
      and generation_spec_hash ~ '^[0-9a-f]{64}$')
  ),
  add constraint generation_jobs_spec_identity_fk foreign key (
    organization_id, generation_spec_id, generation_spec_version,
    generation_spec_hash
  ) references content_factory.generation_spec_versions(
    organization_id, spec_id, spec_version, spec_hash
  );

create or replace function
  content_factory_private.validate_generation_spec_outcome_live(
    organization_id_value uuid,
    primary_media_id_value uuid,
    platform_value text,
    model_value text,
    product_category_value text,
    selection_id_value uuid,
    performance_provenance_value jsonb,
    learning_context_value jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  advisory_value jsonb;
begin
  select selection.* into selection_row
  from content_factory.research_outcome_generation_selections selection
  where selection.organization_id = organization_id_value
    and selection.id = selection_id_value
  for share;
  if selection_row.id is null or selection_row.expires_at <= clock_timestamp()
     or performance_provenance_value is null
     or learning_context_value ->> 'source' <> 'performance_learning' then
    raise exception using
      errcode = '55000', message = 'generation_spec_outcome_selection_stale';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-market-product:' || selection_row.product_id::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext(
      'research-outcome-learning:' ||
      selection_row.market_category_id::text || ':' ||
      selection_row.platform || ':' || selection_row.model
    )
  );
  advisory_value := content_factory_private.research_outcome_generation_advisory(
    organization_id_value, primary_media_id_value, platform_value,
    model_value, product_category_value
  );
  if advisory_value ->> 'product_id' is distinct from selection_row.product_id::text
     or advisory_value #>> '{scope,market_category_id}'
          is distinct from selection_row.market_category_id::text
     or advisory_value #>> '{scope,category_binding_id}'
          is distinct from selection_row.category_binding_id::text
     or advisory_value #>> '{scope,category_binding_version}'
          is distinct from selection_row.category_binding_version::text
     or advisory_value #>> '{memory,memory_version_id}'
          is distinct from selection_row.memory_version_id::text
     or advisory_value #>> '{memory,memory_version}'
          is distinct from selection_row.memory_version::text
     or advisory_value #>> '{memory,candidate_id}'
          is distinct from selection_row.candidate_id::text
     or advisory_value #>> '{candidate,candidate_id}'
          is distinct from selection_row.candidate_id::text
     or advisory_value #>> '{candidate,candidate_version}'
          is distinct from selection_row.candidate_version::text
     or advisory_value #>> '{candidate,candidate_hash}'
          is distinct from selection_row.candidate_hash
     or advisory_value #>> '{base_policy,policy_hash}'
          is distinct from selection_row.base_policy_hash
     or advisory_value #>> '{base_policy,version}'
          is distinct from selection_row.base_policy_version
     or advisory_value #>> '{base_policy,selection_mode}'
          is distinct from selection_row.base_selection_mode
     or advisory_value #>> '{base_policy,preferred_angle}'
          is distinct from selection_row.base_preferred_angle
     or performance_provenance_value ->> 'policy_hash'
          is distinct from selection_row.base_policy_hash
     or performance_provenance_value ->> 'policy_version'
          is distinct from selection_row.base_policy_version
     or learning_context_value ->> 'creative_angle'
          is distinct from selection_row.base_preferred_angle
     or (
       selection_row.selection_action = 'control'
       and advisory_value #> '{permissions,control_allowed}' <> 'true'::jsonb
     )
     or (
       selection_row.selection_action = 'apply'
       and advisory_value #> '{permissions,apply_allowed}' <> 'true'::jsonb
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_outcome_selection_stale';
  end if;
  return advisory_value;
end;
$$;

revoke all on function
  content_factory_private.validate_generation_spec_outcome_live(
    uuid, uuid, text, text, text, uuid, jsonb, jsonb
  ) from public, anon, authenticated, service_role;

create or replace function content_factory_private.create_generation_spec_version(
  organization_id_value uuid,
  spec_id_value uuid,
  previous_version_id_value uuid,
  exact_scope_value jsonb,
  editable_intent_value text,
  proposed_prompt_value text,
  learning_context_value jsonb,
  repair_context_value jsonb,
  research_provenance_value jsonb,
  performance_policy_provenance_value jsonb,
  repair_provenance_value jsonb,
  outcome_selection_id_value uuid,
  reason_value text,
  actor_id_value uuid
)
returns content_factory.generation_spec_versions
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result_row content_factory.generation_spec_versions%rowtype;
  previous_row content_factory.generation_spec_versions%rowtype;
  primary_media_id_value uuid;
  media_ids_value uuid[];
  media_count integer;
  verified_media_count integer;
  product_id_value uuid;
  platform_value text;
  model_value text;
  duration_value integer;
  product_category_value text;
  format_value text;
  audio_value boolean;
  normalized_scope jsonb;
  normalized_learning_context jsonb;
  prompt_value text;
  source_value text;
  policy_value jsonb;
  policy_hash_value text;
  policy_version_value text;
  draft_row content_factory.creative_brief_drafts%rowtype;
  research_structure_value jsonb;
  research_snapshot_hash_value text;
  repair_policy jsonb;
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  outcome_selection_hash_value text;
  final_policy_without_hash jsonb;
  final_policy_value jsonb;
  final_policy_hash_value text;
  spec_hash_value text;
  next_version integer;
begin
  if jsonb_typeof(exact_scope_value) <> 'object'
     or exact_scope_value - array[
       'primary_media_id', 'media_ids', 'platform', 'model',
       'duration_seconds', 'product_category', 'format', 'audio'
     ]::text[] <> '{}'::jsonb
     or not exact_scope_value ?& array[
       'primary_media_id', 'media_ids', 'platform', 'model',
       'duration_seconds', 'product_category', 'format', 'audio'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;
  begin
    primary_media_id_value := (exact_scope_value ->> 'primary_media_id')::uuid;
    if jsonb_typeof(exact_scope_value -> 'media_ids') <> 'array'
       or jsonb_array_length(exact_scope_value -> 'media_ids') not between 1 and 5
       or jsonb_typeof(exact_scope_value -> 'duration_seconds') <> 'number'
       or exact_scope_value ->> 'duration_seconds' !~ '^[0-9]+$'
       or jsonb_typeof(exact_scope_value -> 'audio') <> 'boolean' then
      raise invalid_text_representation;
    end if;
    select array_agg(item.value::uuid order by item.ordinality)
      into media_ids_value
    from jsonb_array_elements_text(exact_scope_value -> 'media_ids')
      with ordinality item(value, ordinality);
    duration_value := (exact_scope_value ->> 'duration_seconds')::integer;
    audio_value := (exact_scope_value ->> 'audio')::boolean;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end;
  media_count := cardinality(media_ids_value);
  if media_ids_value[1] is distinct from primary_media_id_value
     or media_count <> (
       select count(distinct media_id)
       from unnest(media_ids_value) selected(media_id)
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;
  platform_value := lower(btrim(coalesce(exact_scope_value ->> 'platform', '')));
  model_value := lower(btrim(coalesce(exact_scope_value ->> 'model', '')));
  product_category_value := lower(btrim(coalesce(
    exact_scope_value ->> 'product_category', ''
  )));
  format_value := btrim(coalesce(exact_scope_value ->> 'format', ''));
  if platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or product_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     )
     or format_value not in ('9:16', '16:9', '1:1')
     or not (
       (model_value = 'gen4_turbo'
        and duration_value in (2, 5, 8, 10) and not audio_value)
       or (model_value = 'seedance2_fast'
        and duration_value in (4, 8, 12, 15) and audio_value
        and format_value = '9:16')
       or (model_value = 'seedream5_lite'
        and duration_value = 0 and not audio_value
        and format_value = '1:1')
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;

  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.id = primary_media_id_value
    and media.status = 'ready'
    and coalesce(media.metadata ->> 'kind', '') in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed' = 'true'::jsonb;
  if product_id_value is null then
    raise exception using
      errcode = '42501', message = 'generation_spec_primary_media_invalid';
  end if;
  select count(*)::integer into verified_media_count
  from unnest(media_ids_value) selected(media_id)
  join content_factory.media_objects media
    on media.organization_id = organization_id_value
   and media.id = selected.media_id
   and media.product_id = product_id_value
   and media.status = 'ready'
   and coalesce(media.metadata ->> 'kind', '') in ('product_photo', 'packshot')
   and media.metadata -> 'rights_confirmed' = 'true'::jsonb;
  if verified_media_count <> media_count then
    raise exception using
      errcode = '42501', message = 'generation_spec_reference_bundle_invalid';
  end if;

  editable_intent_value := btrim(coalesce(editable_intent_value, ''));
  if length(editable_intent_value) not between 1 and 1200 then
    raise exception using
      errcode = '22023', message = 'generation_spec_editable_intent_invalid';
  end if;
  prompt_value := btrim(coalesce(proposed_prompt_value, ''));
  if length(prompt_value) < 1
     or length(prompt_value) > (case model_value
       when 'gen4_turbo' then 1000 else 1200 end) then
    raise exception using
      errcode = '22023', message = 'generation_spec_prompt_invalid';
  end if;

  if jsonb_typeof(learning_context_value) <> 'object'
     or learning_context_value - array[
       'creative_angle', 'hook_patterns', 'source', 'compiler_version',
       'applied_policy_hash', 'creative_brief_draft_id',
       'scenario_position', 'product_category'
     ]::text[] <> '{}'::jsonb
     or not learning_context_value ?& array[
       'creative_angle', 'hook_patterns', 'source',
       'compiler_version', 'product_category'
     ]::text[]
     or jsonb_typeof(learning_context_value -> 'hook_patterns') <> 'array'
     or jsonb_array_length(learning_context_value -> 'hook_patterns') > 8
     or length((learning_context_value -> 'hook_patterns')::text) > 512
     or learning_context_value ->> 'creative_angle' not in (
       'product_focus', 'trust_builder', 'demonstration', 'comparison',
       'objection_handling', 'curiosity_gap'
     )
     or learning_context_value ->> 'compiler_version' <> 'safe-brief-v7'
     or lower(btrim(coalesce(
       learning_context_value ->> 'product_category', ''
     ))) <> product_category_value then
    raise exception using
      errcode = '22023', message = 'generation_spec_learning_context_invalid';
  end if;
  source_value := learning_context_value ->> 'source';
  if source_value not in (
       'baseline', 'approved_research', 'performance_learning'
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_learning_context_invalid';
  end if;
  normalized_learning_context := learning_context_value;

  if research_provenance_value is not null then
    if jsonb_typeof(research_provenance_value) <> 'object'
       or research_provenance_value - array[
         'research_id', 'creative_brief_draft_id', 'scenario_position'
       ]::text[] <> '{}'::jsonb
       or not research_provenance_value ?& array[
         'research_id', 'creative_brief_draft_id', 'scenario_position'
       ]::text[] then
      raise exception using
        errcode = '22023', message = 'generation_spec_research_provenance_invalid';
    end if;
    begin
      select draft.* into draft_row
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = organization_id_value
        and draft.run_id = (research_provenance_value ->> 'research_id')::uuid
        and draft.id = (
          research_provenance_value ->> 'creative_brief_draft_id'
        )::uuid
        and draft.product_id = product_id_value
        and draft.status = 'approved';
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023', message = 'generation_spec_research_provenance_invalid';
    end;
    if draft_row.id is null
       or jsonb_typeof(research_provenance_value -> 'scenario_position')
            <> 'number'
       or research_provenance_value ->> 'scenario_position' !~ '^[1-3]$' then
      raise exception using
        errcode = '55000', message = 'generation_spec_research_provenance_stale';
    end if;
    research_snapshot_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'research_id', draft_row.run_id,
        'creative_brief_draft_id', draft_row.id,
        'creative_brief_content_hash', draft_row.content_hash,
        'scenario_position',
          (research_provenance_value ->> 'scenario_position')::integer
      )
    );
  end if;
  if source_value = 'approved_research' and (
       draft_row.id is null
       or performance_policy_provenance_value is not null
       or learning_context_value ->> 'creative_brief_draft_id'
            is distinct from draft_row.id::text
       or learning_context_value ->> 'scenario_position'
            is distinct from research_provenance_value ->> 'scenario_position'
       or learning_context_value ? 'applied_policy_hash'
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_research_learning_mismatch';
  end if;
  if source_value = 'approved_research' then
    research_structure_value :=
      content_factory_private.generation_spec_research_structure(
        draft_row.brief,
        (research_provenance_value ->> 'scenario_position')::integer
      );
    if research_structure_value is null
       or learning_context_value ->> 'creative_angle' is distinct from
            research_structure_value ->> 'creative_angle'
       or learning_context_value -> 'hook_patterns' is distinct from
            research_structure_value -> 'hook_patterns'
       or learning_context_value ->> 'compiler_version' is distinct from
            research_structure_value ->> 'compiler_version' then
      raise exception using
        errcode = '55000', message = 'generation_spec_research_learning_mismatch';
    end if;
  end if;

  if performance_policy_provenance_value is not null then
    if jsonb_typeof(performance_policy_provenance_value) <> 'object'
       or performance_policy_provenance_value - array[
         'policy_hash', 'policy_version'
       ]::text[] <> '{}'::jsonb
       or not performance_policy_provenance_value ?& array[
         'policy_hash', 'policy_version'
       ]::text[]
       or coalesce(performance_policy_provenance_value ->> 'policy_hash', '')
            !~ '^[0-9a-f]{64}$'
       or length(btrim(coalesce(
         performance_policy_provenance_value ->> 'policy_version', ''
       ))) not between 3 and 80 then
      raise exception using
        errcode = '22023', message = 'generation_spec_performance_provenance_invalid';
    end if;
    policy_value := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'media_id', primary_media_id_value,
        'platform', platform_value,
        'model', model_value,
        'product_category', product_category_value
      )
    );
    policy_hash_value := policy_value ->> 'policy_hash';
    policy_version_value := policy_value ->> 'version';
    if policy_hash_value is distinct from
         performance_policy_provenance_value ->> 'policy_hash'
       or policy_version_value is distinct from
         performance_policy_provenance_value ->> 'policy_version' then
      raise exception using
        errcode = '55000', message = 'generation_spec_performance_policy_stale';
    end if;
  else
    policy_value := jsonb_build_object(
      'version', 'generation-spec-baseline-v1',
      'generation_allowed', true,
      'product_category', product_category_value,
      'platform', platform_value,
      'model', model_value,
      'reason_codes', jsonb_build_array('explicit_human_spec_baseline')
    );
  end if;
  if source_value = 'performance_learning' and (
       performance_policy_provenance_value is null
       or learning_context_value ->> 'applied_policy_hash'
            is distinct from policy_hash_value
       or policy_value -> 'generation_allowed' is distinct from 'true'::jsonb
       or learning_context_value ->> 'creative_angle'
            is distinct from policy_value ->> 'preferred_angle'
       or learning_context_value -> 'hook_patterns'
            is distinct from coalesce(
              policy_value -> 'preferred_hook_patterns', '[]'::jsonb
            )
       or learning_context_value ? 'creative_brief_draft_id'
       or learning_context_value ? 'scenario_position'
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_performance_learning_mismatch';
  end if;
  if source_value = 'baseline' and (
       research_provenance_value is not null
       or performance_policy_provenance_value is not null
       or
       learning_context_value ? 'applied_policy_hash'
       or learning_context_value ? 'creative_brief_draft_id'
       or learning_context_value ? 'scenario_position'
       or learning_context_value ->> 'creative_angle' <> 'product_focus'
       or learning_context_value -> 'hook_patterns' <> '[]'::jsonb
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_baseline_learning_invalid';
  end if;

  if (repair_context_value is null) <> (repair_provenance_value is null) then
    raise exception using
      errcode = '22023', message = 'generation_spec_repair_provenance_invalid';
  end if;
  if repair_context_value is not null then
    if jsonb_typeof(repair_provenance_value) <> 'object'
       or repair_provenance_value - array[
         'source_review_id', 'source_generation_job_id', 'policy_hash'
       ]::text[] <> '{}'::jsonb
       or not repair_provenance_value ?& array[
         'source_review_id', 'source_generation_job_id', 'policy_hash'
       ]::text[]
       or jsonb_typeof(repair_context_value) <> 'object'
       or repair_context_value - array[
         'source_review_id', 'source_generation_job_id', 'guard_codes',
         'policy_hash', 'compiler_version'
       ]::text[] <> '{}'::jsonb
       or not repair_context_value ?& array[
         'source_review_id', 'source_generation_job_id', 'guard_codes',
         'policy_hash', 'compiler_version'
       ]::text[]
       or repair_context_value ->> 'compiler_version' <> 'review-repair-v1'
       or jsonb_typeof(repair_context_value -> 'guard_codes') <> 'array'
       or jsonb_array_length(repair_context_value -> 'guard_codes')
            not between 1 and 3
       or exists (
         select 1
         from jsonb_array_elements_text(
           repair_context_value -> 'guard_codes'
         ) guard(code)
         where guard.code not in (
           'product_fidelity', 'technical_stability', 'hook_clarity',
           'visual_quality', 'trust', 'platform_fit',
           'audio_quality', 'speech_fidelity'
         )
       )
       or (
         select count(*)
         from jsonb_array_elements_text(
           repair_context_value -> 'guard_codes'
         ) guard(code)
       ) <> (
         select count(distinct guard.code)
         from jsonb_array_elements_text(
           repair_context_value -> 'guard_codes'
         ) guard(code)
       )
       or coalesce(repair_context_value ->> 'policy_hash', '')
            !~ '^[0-9a-f]{64}$'
       or repair_provenance_value ->> 'source_review_id'
            is distinct from repair_context_value ->> 'source_review_id'
       or repair_provenance_value ->> 'source_generation_job_id'
            is distinct from repair_context_value ->> 'source_generation_job_id'
       or repair_provenance_value ->> 'policy_hash'
            is distinct from repair_context_value ->> 'policy_hash' then
      raise exception using
        errcode = '22023', message = 'generation_spec_repair_provenance_invalid';
    end if;
    repair_policy := public.creator_generation_repair_policy(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'review_id', repair_context_value ->> 'source_review_id'
      )
    );
    if repair_policy -> 'applied' is distinct from 'true'::jsonb
       or repair_policy ->> 'policy_hash'
            is distinct from repair_context_value ->> 'policy_hash'
       or repair_policy ->> 'source_generation_job_id'
            is distinct from repair_context_value ->> 'source_generation_job_id'
       or repair_policy -> 'guard_codes'
            is distinct from repair_context_value -> 'guard_codes'
       or repair_policy ->> 'input_media_id'
            is distinct from primary_media_id_value::text
       or repair_policy ->> 'model' is distinct from model_value
       or repair_policy ->> 'platform' is distinct from platform_value then
      raise exception using
        errcode = '55000', message = 'generation_spec_repair_policy_stale';
    end if;
  end if;

  if outcome_selection_id_value is not null then
    select selection.* into selection_row
    from content_factory.research_outcome_generation_selections selection
    where selection.organization_id = organization_id_value
      and selection.id = outcome_selection_id_value
    for share;
    if selection_row.id is null
       or selection_row.input_media_id <> primary_media_id_value
       or selection_row.product_id <> product_id_value
       or selection_row.product_category <> product_category_value
       or selection_row.platform <> platform_value
       or selection_row.model <> model_value
       or selection_row.expires_at <= clock_timestamp() then
      raise exception using
        errcode = '55000', message = 'generation_spec_outcome_selection_stale';
    end if;
    perform content_factory_private.validate_generation_spec_outcome_live(
      organization_id_value, primary_media_id_value, platform_value,
      model_value, product_category_value, outcome_selection_id_value,
      performance_policy_provenance_value, normalized_learning_context
    );
    outcome_selection_hash_value := selection_row.selection_hash;
  end if;

  normalized_scope := jsonb_build_object(
    'primary_media_id', primary_media_id_value,
    'media_ids', to_jsonb(media_ids_value),
    'platform', platform_value,
    'model', model_value,
    'duration_seconds', duration_value,
    'product_category', product_category_value,
    'format', format_value,
    'audio', audio_value
  );
  final_policy_without_hash := jsonb_build_object(
    'schema_version', 'generation-spec-effective-policy-v1',
    'learning_policy', policy_value,
    'research_snapshot_hash', research_snapshot_hash_value,
    'performance_policy_provenance', performance_policy_provenance_value,
    'repair_policy_hash', case when repair_policy is null then null
      else repair_policy -> 'policy_hash' end,
    'outcome_selection', case when selection_row.id is null then null
      else jsonb_build_object(
        'selection_id', selection_row.id,
        'selection_hash', selection_row.selection_hash,
        'selection_action', selection_row.selection_action,
        'expires_at', selection_row.expires_at
      ) end,
    'generation_allowed',
      coalesce((policy_value ->> 'generation_allowed')::boolean, true)
      and coalesce(selection_row.selection_action <> 'apply', true),
    'automatic_approval', false,
    'automatic_spend', false,
    'automatic_generation', false
  );
  final_policy_hash_value :=
    content_factory_private.json_hash(final_policy_without_hash);
  final_policy_value := final_policy_without_hash || jsonb_build_object(
    'final_policy_hash', final_policy_hash_value
  );

  if spec_id_value is null then
    spec_id_value := extensions.gen_random_uuid();
  end if;
  select * into previous_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.version_id = previous_version_id_value;
  if previous_version_id_value is not null and previous_row.version_id is null then
    raise exception using
      errcode = '55000', message = 'generation_spec_previous_version_invalid';
  end if;
  select coalesce(max(version.spec_version), 0) + 1 into next_version
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value;
  if (next_version = 1) <> (previous_version_id_value is null) then
    raise exception using
      errcode = '55000', message = 'generation_spec_version_sequence_invalid';
  end if;
  spec_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'generation-spec-v1',
    'spec_id', spec_id_value,
    'spec_version', next_version,
    'previous_spec_hash', previous_row.spec_hash,
    'product_id', product_id_value,
    'exact_scope', normalized_scope,
    'editable_intent', editable_intent_value,
    'compiled_prompt', prompt_value,
    'prompt_hash', content_factory_private.raw_text_sha256(prompt_value),
    'learning_context', normalized_learning_context,
    'repair_context', repair_context_value,
    'research_provenance', research_provenance_value,
    'research_snapshot_hash', research_snapshot_hash_value,
    'performance_policy_provenance', performance_policy_provenance_value,
    'repair_provenance', repair_provenance_value,
    'outcome_selection_id', outcome_selection_id_value,
    'outcome_selection_hash', outcome_selection_hash_value,
    'final_policy_hash', final_policy_hash_value
  ));

  insert into content_factory.generation_spec_versions (
    organization_id, spec_id, spec_version, previous_version_id,
    product_id, primary_media_id, media_ids, platform, model,
    duration_seconds, product_category, format, audio, exact_scope,
    editable_intent, compiled_prompt, prompt_hash,
    research_provenance, research_snapshot_hash,
    performance_policy_provenance, repair_provenance,
    outcome_selection_id, outcome_selection_hash,
    canonical_learning_context, canonical_repair_context,
    final_policy, final_policy_hash,
    spec_hash, reason, created_by
  ) values (
    organization_id_value, spec_id_value, next_version,
    previous_version_id_value, product_id_value, primary_media_id_value,
    media_ids_value, platform_value, model_value, duration_value,
    product_category_value, format_value, audio_value, normalized_scope,
    editable_intent_value, prompt_value,
    content_factory_private.raw_text_sha256(prompt_value),
    research_provenance_value, research_snapshot_hash_value,
    performance_policy_provenance_value, repair_provenance_value,
    outcome_selection_id_value, outcome_selection_hash_value,
    normalized_learning_context, repair_context_value,
    final_policy_value, final_policy_hash_value,
    spec_hash_value, reason_value, actor_id_value
  ) returning * into result_row;
  return result_row;
end;
$$;

revoke all on function content_factory_private.create_generation_spec_version(
  uuid, uuid, uuid, jsonb, text, text, jsonb, jsonb,
  jsonb, jsonb, jsonb, uuid, text, uuid
) from public, anon, authenticated, service_role;

create or replace function content_factory_private.generation_spec_document(
  organization_id_value uuid,
  spec_id_value uuid
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  head_row content_factory.generation_spec_head_events%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  approved_at_value timestamptz;
  result_value jsonb;
begin
  select event.* into head_row
  from content_factory.generation_spec_head_events event
  where event.organization_id = organization_id_value
    and event.spec_id = spec_id_value
  order by event.event_sequence desc
  limit 1;
  if head_row.id is null then
    raise exception using
      errcode = '22023', message = 'generation_spec_not_found';
  end if;
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = head_row.spec_version
    and version.spec_hash = head_row.spec_hash;
  if spec_row.version_id is null then
    raise exception using
      errcode = '55000', message = 'generation_spec_head_invalid';
  end if;
  if head_row.state = 'approved' then
    approved_at_value := head_row.created_at;
  end if;
  result_value := jsonb_build_object(
    'spec_id', spec_row.spec_id,
    'spec_version', spec_row.spec_version,
    'spec_hash', spec_row.spec_hash,
    'status', head_row.state,
    'exact_scope', spec_row.exact_scope,
    'editable_intent', spec_row.editable_intent,
    'compiled_prompt', spec_row.compiled_prompt,
    'prompt_hash', spec_row.prompt_hash,
    'research_provenance', spec_row.research_provenance,
    'performance_policy_provenance',
      spec_row.performance_policy_provenance,
    'repair_provenance', spec_row.repair_provenance,
    'outcome_selection_id', spec_row.outcome_selection_id,
    'created_at', spec_row.created_at,
    'updated_at', head_row.created_at
  );
  if approved_at_value is not null then
    result_value := result_value || jsonb_build_object(
      'approved_at', approved_at_value
    );
  end if;
  return result_value;
end;
$$;

create or replace function content_factory_private.generation_spec_history(
  organization_id_value uuid,
  spec_id_value uuid
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with current_head as (
    select event.*
    from content_factory.generation_spec_head_events event
    where event.organization_id = organization_id_value
      and event.spec_id = spec_id_value
    order by event.event_sequence desc
    limit 1
  ), bounded_versions as (
    select version.*,
      case when version.spec_version = head.spec_version
        then head.state else 'superseded' end as document_status,
      coalesce((
        select max(event.created_at)
        from content_factory.generation_spec_head_events event
        where event.organization_id = version.organization_id
          and event.spec_id = version.spec_id
          and event.spec_version = version.spec_version
      ), version.created_at) as document_updated_at,
      head.created_at as current_approved_at
    from content_factory.generation_spec_versions version
    cross join current_head head
    where version.organization_id = organization_id_value
      and version.spec_id = spec_id_value
    order by version.spec_version desc
    limit 20
  )
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'spec_id', version.spec_id,
      'spec_version', version.spec_version,
      'spec_hash', version.spec_hash,
      'status', version.document_status,
      'exact_scope', version.exact_scope,
      'editable_intent', version.editable_intent,
      'compiled_prompt', version.compiled_prompt,
      'prompt_hash', version.prompt_hash,
      'research_provenance', version.research_provenance,
      'performance_policy_provenance',
        version.performance_policy_provenance,
      'repair_provenance', version.repair_provenance,
      'outcome_selection_id', version.outcome_selection_id,
      'created_at', version.created_at,
      'updated_at', version.document_updated_at
    ) || case when version.document_status = 'approved'
      then jsonb_build_object('approved_at', version.current_approved_at)
      else '{}'::jsonb end
    order by version.spec_version desc
  ), '[]'::jsonb)
  from bounded_versions version;
$$;

create or replace function content_factory_private.generation_spec_next_action(
  state_value text
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select case state_value
    when 'approved' then jsonb_build_object(
      'code', 'confirm_spend_for_approved_spec',
      'action', 'confirm_spend',
      'label', 'Подтвердить платную генерацию',
      'reason', 'Текущая неизменяемая версия явно одобрена человеком.',
      'requires_confirmation', true,
      'provider_action', false,
      'spend_action', false
    )
    when 'rejected' then jsonb_build_object(
      'code', 'patch_rejected_generation_spec',
      'action', 'patch',
      'label', 'Исправить спецификацию',
      'reason', 'Отклонённую версию нельзя передать платному провайдеру.',
      'requires_confirmation', true,
      'provider_action', false,
      'spend_action', false
    )
    else jsonb_build_object(
      'code', 'review_and_approve_generation_spec',
      'action', 'approve',
      'label', 'Проверить и одобрить',
      'reason', 'До расхода человек должен одобрить точную текущую версию.',
      'requires_confirmation', true,
      'provider_action', false,
      'spend_action', false
    )
  end;
$$;

create or replace function content_factory_private.generation_spec_envelope(
  organization_id_value uuid,
  spec_id_value uuid
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  document_value jsonb;
begin
  document_value := content_factory_private.generation_spec_document(
    organization_id_value, spec_id_value
  );
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-control-v1',
    'generation_spec', document_value,
    'history', content_factory_private.generation_spec_history(
      organization_id_value, spec_id_value
    ),
    'recommended_next_action',
      content_factory_private.generation_spec_next_action(
        document_value ->> 'status'
      ),
    'automatic_approval', false,
    'automatic_spend', false,
    'automatic_generation', false
  );
end;
$$;

create or replace function content_factory_private.assert_generation_spec_current(
  organization_id_value uuid,
  spec_id_value uuid,
  spec_version_value integer,
  spec_hash_value text,
  approval_required boolean default true,
  dynamic_revalidation boolean default true
)
returns content_factory.generation_spec_versions
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  head_row content_factory.generation_spec_head_events%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  policy_value jsonb;
  repair_policy jsonb;
  current_research_snapshot_hash text;
  research_structure_value jsonb;
  verified_media_count integer;
begin
  select event.* into head_row
  from content_factory.generation_spec_head_events event
  where event.organization_id = organization_id_value
    and event.spec_id = spec_id_value
  order by event.event_sequence desc
  limit 1
  for share;
  if head_row.id is null
     or head_row.spec_version <> spec_version_value
     or head_row.spec_hash <> spec_hash_value then
    raise exception using
      errcode = '55000', message = 'generation_spec_stale';
  end if;
  if approval_required and head_row.state <> 'approved' then
    raise exception using
      errcode = '42501', message = 'generation_spec_approval_required';
  end if;
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;
  if spec_row.version_id is null
     or spec_row.prompt_hash <>
       content_factory_private.raw_text_sha256(spec_row.compiled_prompt) then
    raise exception using
      errcode = '55000', message = 'generation_spec_stale';
  end if;

  select count(*)::integer into verified_media_count
  from unnest(spec_row.media_ids) selected(media_id)
  join content_factory.media_objects media
    on media.organization_id = organization_id_value
   and media.id = selected.media_id
   and media.product_id = spec_row.product_id
   and media.status = 'ready'
   and coalesce(media.metadata ->> 'kind', '') in ('product_photo', 'packshot')
   and media.metadata -> 'rights_confirmed' = 'true'::jsonb;
  if verified_media_count <> cardinality(spec_row.media_ids) then
    raise exception using
      errcode = '55000', message = 'generation_spec_media_stale';
  end if;

  if spec_row.research_provenance is not null then
    select draft.* into draft_row
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id_value
      and draft.run_id = (
        spec_row.research_provenance ->> 'research_id'
      )::uuid
      and draft.id = (
        spec_row.research_provenance ->> 'creative_brief_draft_id'
      )::uuid
      and draft.product_id = spec_row.product_id
      and draft.status = 'approved';
    if draft_row.id is null then
      raise exception using
        errcode = '55000', message = 'generation_spec_research_provenance_stale';
    end if;
    current_research_snapshot_hash := content_factory_private.json_hash(
      jsonb_build_object(
        'research_id', draft_row.run_id,
        'creative_brief_draft_id', draft_row.id,
        'creative_brief_content_hash', draft_row.content_hash,
        'scenario_position',
          (spec_row.research_provenance ->> 'scenario_position')::integer
      )
    );
    if current_research_snapshot_hash <> spec_row.research_snapshot_hash then
      raise exception using
        errcode = '55000', message = 'generation_spec_research_provenance_stale';
    end if;
  end if;

  if spec_row.canonical_learning_context ->> 'compiler_version' <>
       'safe-brief-v7' then
    raise exception using
      errcode = '55000', message = 'generation_spec_learning_context_stale';
  end if;
  if spec_row.canonical_learning_context ->> 'source' = 'baseline' then
    if spec_row.research_provenance is not null
       or spec_row.performance_policy_provenance is not null
       or spec_row.canonical_learning_context ->> 'creative_angle' <>
            'product_focus'
       or spec_row.canonical_learning_context -> 'hook_patterns' <>
            '[]'::jsonb then
      raise exception using
        errcode = '55000', message = 'generation_spec_learning_context_stale';
    end if;
  elsif spec_row.canonical_learning_context ->> 'source' =
          'approved_research' then
    if spec_row.research_provenance is null
       or spec_row.performance_policy_provenance is not null then
      raise exception using
        errcode = '55000', message = 'generation_spec_learning_context_stale';
    end if;
    research_structure_value :=
      content_factory_private.generation_spec_research_structure(
        draft_row.brief,
        (spec_row.research_provenance ->> 'scenario_position')::integer
      );
    if research_structure_value is null
       or spec_row.canonical_learning_context ->> 'creative_brief_draft_id'
            is distinct from draft_row.id::text
       or spec_row.canonical_learning_context ->> 'scenario_position'
            is distinct from
              spec_row.research_provenance ->> 'scenario_position'
       or spec_row.canonical_learning_context ->> 'creative_angle'
            is distinct from research_structure_value ->> 'creative_angle'
       or spec_row.canonical_learning_context -> 'hook_patterns'
            is distinct from research_structure_value -> 'hook_patterns' then
      raise exception using
        errcode = '55000', message = 'generation_spec_learning_context_stale';
    end if;
  elsif spec_row.canonical_learning_context ->> 'source' =
          'performance_learning' then
    if spec_row.performance_policy_provenance is null
       or spec_row.canonical_learning_context ->> 'applied_policy_hash'
            is distinct from
              spec_row.performance_policy_provenance ->> 'policy_hash' then
      raise exception using
        errcode = '55000', message = 'generation_spec_learning_context_stale';
    end if;
  else
    raise exception using
      errcode = '55000', message = 'generation_spec_learning_context_stale';
  end if;

  if dynamic_revalidation
     and spec_row.performance_policy_provenance is not null then
    policy_value := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'media_id', spec_row.primary_media_id,
        'platform', spec_row.platform,
        'model', spec_row.model,
        'product_category', spec_row.product_category
      )
    );
    if policy_value ->> 'policy_hash' is distinct from
         spec_row.performance_policy_provenance ->> 'policy_hash'
       or policy_value ->> 'version' is distinct from
         spec_row.performance_policy_provenance ->> 'policy_version'
       or policy_value -> 'generation_allowed' = 'false'::jsonb then
      raise exception using
        errcode = '55000', message = 'generation_spec_performance_policy_stale';
    end if;
  end if;

  if dynamic_revalidation and spec_row.canonical_repair_context is not null then
    repair_policy := public.creator_generation_repair_policy(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'review_id', spec_row.canonical_repair_context ->> 'source_review_id'
      )
    );
    if repair_policy -> 'applied' is distinct from 'true'::jsonb
       or repair_policy ->> 'policy_hash' is distinct from
         spec_row.canonical_repair_context ->> 'policy_hash' then
      raise exception using
        errcode = '55000', message = 'generation_spec_repair_policy_stale';
    end if;
  end if;

  if spec_row.outcome_selection_id is not null then
    select selection.* into selection_row
    from content_factory.research_outcome_generation_selections selection
    where selection.organization_id = organization_id_value
      and selection.id = spec_row.outcome_selection_id;
    if selection_row.id is null
       or selection_row.selection_hash <> spec_row.outcome_selection_hash
       or selection_row.expires_at <= clock_timestamp() then
      raise exception using
        errcode = '55000', message = 'generation_spec_outcome_selection_stale';
    end if;
    if dynamic_revalidation then
      perform content_factory_private.validate_generation_spec_outcome_live(
        organization_id_value, spec_row.primary_media_id,
        spec_row.platform, spec_row.model, spec_row.product_category,
        spec_row.outcome_selection_id,
        spec_row.performance_policy_provenance,
        spec_row.canonical_learning_context
      );
    end if;
    -- Applying a learned structural override requires the full live evidence
    -- revalidator at the consumption boundary.  Until that proof exists,
    -- fail closed while control/baseline specs remain usable.
    if selection_row.selection_action = 'apply' then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_outcome_apply_revalidation_required';
    end if;
  end if;
  if spec_row.final_policy -> 'generation_allowed' <> 'true'::jsonb then
    raise exception using
      errcode = '55000', message = 'generation_spec_policy_blocked';
  end if;
  return spec_row;
end;
$$;

revoke all on function content_factory_private.generation_spec_document(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.generation_spec_history(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.generation_spec_next_action(text)
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.generation_spec_envelope(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.assert_generation_spec_current(
  uuid, uuid, integer, text, boolean, boolean
) from public, anon, authenticated, service_role;

create or replace function public.creator_prepare_generation_spec(
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
  idempotency_key_value text;
  reason_value text;
  request_payload jsonb;
  replay jsonb;
  spec_id_value uuid := extensions.gen_random_uuid();
  outcome_selection_id_value uuid;
  spec_row content_factory.generation_spec_versions%rowtype;
  head_event_id_value uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'idempotency_key', 'exact_scope',
       'editable_intent', 'proposed_prompt', 'learning_context',
       'repair_context', 'research_provenance',
       'performance_policy_provenance', 'repair_provenance',
       'outcome_selection_id', 'confirmation', 'reason'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'idempotency_key', 'exact_scope',
       'editable_intent', 'proposed_prompt', 'learning_context',
       'repair_context', 'research_provenance',
       'performance_policy_provenance', 'repair_provenance',
       'confirmation', 'reason'
     ]::text[]
     or jsonb_typeof(p_payload -> 'editable_intent') <> 'string'
     or jsonb_typeof(p_payload -> 'proposed_prompt') <> 'string'
     or jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' <> 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'generation_spec_prepare_payload_invalid';
  end if;
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  if p_payload ? 'outcome_selection_id'
     and p_payload -> 'outcome_selection_id' <> 'null'::jsonb then
    outcome_selection_id_value := content_factory_private.require_uuid(
      p_payload, 'outcome_selection_id'
    );
  end if;
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id_value, 'creator_prepare_generation_spec',
    idempotency_key_value, request_payload
  );
  if replay is not null then
    return replay;
  end if;

  spec_row := content_factory_private.create_generation_spec_version(
    organization_id_value,
    spec_id_value,
    null,
    p_payload -> 'exact_scope',
    p_payload ->> 'editable_intent',
    p_payload ->> 'proposed_prompt',
    p_payload -> 'learning_context',
    nullif(p_payload -> 'repair_context', 'null'::jsonb),
    nullif(p_payload -> 'research_provenance', 'null'::jsonb),
    nullif(p_payload -> 'performance_policy_provenance', 'null'::jsonb),
    nullif(p_payload -> 'repair_provenance', 'null'::jsonb),
    outcome_selection_id_value,
    reason_value,
    actor_id_value
  );

  insert into content_factory.generation_spec_head_events (
    organization_id, spec_id, event_sequence, action, state,
    spec_version, spec_hash, prior_event_id, approval_event_id,
    reason, actor_id, request_hash, event_hash
  ) values (
    organization_id_value, spec_row.spec_id, 1, 'prepare', 'draft',
    spec_row.spec_version, spec_row.spec_hash, null, null,
    reason_value, actor_id_value,
    content_factory_private.json_hash(request_payload),
    content_factory_private.json_hash(jsonb_build_object(
      'schema_version', 'generation-spec-head-event-v1',
      'organization_id', organization_id_value,
      'spec_id', spec_row.spec_id,
      'event_sequence', 1,
      'action', 'prepare',
      'state', 'draft',
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash,
      'reason', reason_value,
      'actor_id', actor_id_value,
      'request_hash', content_factory_private.json_hash(request_payload)
    ))
  ) returning id into head_event_id_value;

  result_value := content_factory_private.generation_spec_envelope(
    organization_id_value, spec_row.spec_id
  );
  return content_factory_private.finish_command(
    organization_id_value, actor_id_value,
    'creator_prepare_generation_spec', idempotency_key_value,
    request_payload, result_value
  );
end;
$$;

create or replace function public.creator_generation_spec_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  document_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_status_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, false,
    array['owner', 'admin', 'producer', 'operator', 'reviewer']
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or p_payload ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_status_payload_invalid';
  end;
  spec_hash_value := lower(content_factory_private.require_text(
    p_payload, 'spec_hash', 64, 64
  ));
  document_value := content_factory_private.generation_spec_document(
    organization_id_value, spec_id_value
  );
  if document_value -> 'spec_version' is distinct from
       to_jsonb(spec_version_value)
     or document_value ->> 'spec_hash' is distinct from spec_hash_value then
    raise exception using
      errcode = '55000', message = 'generation_spec_stale';
  end if;
  if document_value ->> 'status' = 'approved' then
    perform content_factory_private.assert_generation_spec_current(
      organization_id_value, spec_id_value, spec_version_value,
      spec_hash_value, false, true
    );
  end if;
  return content_factory_private.generation_spec_envelope(
    organization_id_value, spec_id_value
  );
end;
$$;

create or replace function public.creator_control_generation_spec(
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
  spec_id_value uuid;
  expected_version_value integer;
  expected_hash_value text;
  action_value text;
  reason_value text;
  idempotency_key_value text;
  request_payload jsonb;
  request_hash_value text;
  replay jsonb;
  current_head content_factory.generation_spec_head_events%rowtype;
  current_spec content_factory.generation_spec_versions%rowtype;
  target_spec content_factory.generation_spec_versions%rowtype;
  new_spec content_factory.generation_spec_versions%rowtype;
  approval_event_id_value uuid;
  new_event_id_value uuid;
  new_state_value text;
  next_sequence_value integer;
  patch_value jsonb;
  exact_scope_value jsonb;
  editable_intent_value text;
  proposed_prompt_value text;
  learning_context_value jsonb;
  repair_context_value jsonb;
  research_provenance_value jsonb;
  performance_policy_provenance_value jsonb;
  repair_provenance_value jsonb;
  outcome_selection_id_value uuid;
  target_version_value integer;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'spec_id', 'expected_spec_version',
       'expected_spec_hash', 'action', 'confirmation', 'reason',
       'idempotency_key', 'patch', 'target_spec_version'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'spec_id', 'expected_spec_version',
       'expected_spec_hash', 'action', 'confirmation', 'reason',
       'idempotency_key'
     ]::text[]
     or jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' <> 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_payload_invalid';
  end if;
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'expected_spec_version') <> 'number'
       or p_payload ->> 'expected_spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    expected_version_value := (p_payload ->> 'expected_spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_version_invalid';
  end;
  expected_hash_value := lower(content_factory_private.require_text(
    p_payload, 'expected_spec_hash', 64, 64
  ));
  action_value := lower(content_factory_private.require_text(
    p_payload, 'action', 5, 12
  ));
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if expected_hash_value !~ '^[0-9a-f]{64}$'
     or action_value not in (
       'patch', 'approve', 'reject', 'revert', 'recompute'
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_payload_invalid';
  end if;
  if action_value = 'patch' then
    patch_value := p_payload -> 'patch';
    if jsonb_typeof(patch_value) <> 'object'
       or patch_value = '{}'::jsonb
       or patch_value - array[
         'exact_scope', 'editable_intent', 'proposed_prompt',
         'learning_context', 'repair_context', 'research_provenance',
         'performance_policy_provenance', 'repair_provenance',
         'outcome_selection_id'
       ]::text[] <> '{}'::jsonb
       or p_payload ? 'target_spec_version' then
      raise exception using
        errcode = '22023', message = 'generation_spec_patch_invalid';
    end if;
  elsif action_value = 'revert' then
    if p_payload ? 'patch'
       or jsonb_typeof(p_payload -> 'target_spec_version') <> 'number'
       or p_payload ->> 'target_spec_version' !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'generation_spec_revert_invalid';
    end if;
    target_version_value := (p_payload ->> 'target_spec_version')::integer;
  elsif p_payload ? 'patch' or p_payload ? 'target_spec_version' then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_payload_invalid';
  end if;

  request_payload := p_payload - 'idempotency_key';
  request_hash_value := content_factory_private.json_hash(request_payload);
  replay := content_factory_private.begin_command(
    organization_id_value, 'creator_control_generation_spec',
    idempotency_key_value, request_payload
  );
  if replay is not null then
    return replay;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-spec:' || spec_id_value::text)
  );
  select event.* into current_head
  from content_factory.generation_spec_head_events event
  where event.organization_id = organization_id_value
    and event.spec_id = spec_id_value
  order by event.event_sequence desc
  limit 1
  for update;
  if current_head.id is null then
    raise exception using
      errcode = '22023', message = 'generation_spec_not_found';
  end if;
  if current_head.spec_version <> expected_version_value
     or current_head.spec_hash <> expected_hash_value then
    raise exception using
      errcode = '55000', message = 'generation_spec_stale';
  end if;
  select version.* into current_spec
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = current_head.spec_version
    and version.spec_hash = current_head.spec_hash;
  if current_spec.version_id is null then
    raise exception using
      errcode = '55000', message = 'generation_spec_head_invalid';
  end if;
  next_sequence_value := current_head.event_sequence + 1;

  if action_value in ('approve', 'reject') then
    if action_value = 'approve' and current_head.state <> 'draft' then
      raise exception using
        errcode = '55000', message = 'generation_spec_approval_state_invalid';
    end if;
    if action_value = 'approve' then
      perform content_factory_private.assert_generation_spec_current(
        organization_id_value, spec_id_value,
        current_spec.spec_version, current_spec.spec_hash,
        false, true
      );
    end if;
    insert into content_factory.generation_spec_approval_events (
      organization_id, spec_id, spec_version, spec_hash, action,
      confirmation, reason, actor_id, event_hash, idempotency_key
    ) values (
      organization_id_value, spec_id_value, current_spec.spec_version,
      current_spec.spec_hash, action_value, true, reason_value,
      actor_id_value,
      content_factory_private.json_hash(jsonb_build_object(
        'schema_version', 'generation-spec-approval-event-v1',
        'organization_id', organization_id_value,
        'spec_id', spec_id_value,
        'spec_version', current_spec.spec_version,
        'spec_hash', current_spec.spec_hash,
        'action', action_value,
        'confirmation', true,
        'reason', reason_value,
        'actor_id', actor_id_value,
        'request_hash', request_hash_value
      )),
      idempotency_key_value
    ) returning id into approval_event_id_value;
    new_spec := current_spec;
    new_state_value := case action_value
      when 'approve' then 'approved' else 'rejected' end;
  else
    if action_value = 'revert' then
      select version.* into target_spec
      from content_factory.generation_spec_versions version
      where version.organization_id = organization_id_value
        and version.spec_id = spec_id_value
        and version.spec_version = target_version_value;
      if target_spec.version_id is null
         or target_spec.spec_version >= current_spec.spec_version then
        raise exception using
          errcode = '55000', message = 'generation_spec_revert_target_invalid';
      end if;
      exact_scope_value := target_spec.exact_scope;
      editable_intent_value := target_spec.editable_intent;
      proposed_prompt_value := target_spec.compiled_prompt;
      learning_context_value := target_spec.canonical_learning_context;
      repair_context_value := target_spec.canonical_repair_context;
      research_provenance_value := target_spec.research_provenance;
      performance_policy_provenance_value :=
        target_spec.performance_policy_provenance;
      repair_provenance_value := target_spec.repair_provenance;
      outcome_selection_id_value := target_spec.outcome_selection_id;
    else
      exact_scope_value := case when action_value = 'patch'
        and patch_value ? 'exact_scope' then patch_value -> 'exact_scope'
        else current_spec.exact_scope end;
      editable_intent_value := case when action_value = 'patch'
        and patch_value ? 'editable_intent'
        then patch_value ->> 'editable_intent'
        else current_spec.editable_intent end;
      proposed_prompt_value := case when action_value = 'patch'
        and patch_value ? 'proposed_prompt'
        then patch_value ->> 'proposed_prompt'
        else current_spec.compiled_prompt end;
      learning_context_value := case when action_value = 'patch'
        and patch_value ? 'learning_context'
        then patch_value -> 'learning_context'
        else current_spec.canonical_learning_context end;
      repair_context_value := case when action_value = 'patch'
        and patch_value ? 'repair_context'
        then nullif(patch_value -> 'repair_context', 'null'::jsonb)
        else current_spec.canonical_repair_context end;
      research_provenance_value := case when action_value = 'patch'
        and patch_value ? 'research_provenance'
        then nullif(patch_value -> 'research_provenance', 'null'::jsonb)
        else current_spec.research_provenance end;
      performance_policy_provenance_value := case when action_value = 'patch'
        and patch_value ? 'performance_policy_provenance'
        then nullif(
          patch_value -> 'performance_policy_provenance', 'null'::jsonb
        ) else current_spec.performance_policy_provenance end;
      repair_provenance_value := case when action_value = 'patch'
        and patch_value ? 'repair_provenance'
        then nullif(patch_value -> 'repair_provenance', 'null'::jsonb)
        else current_spec.repair_provenance end;
      if action_value = 'patch' and patch_value ? 'outcome_selection_id' then
        if patch_value -> 'outcome_selection_id' = 'null'::jsonb then
          outcome_selection_id_value := null;
        else
          begin
            outcome_selection_id_value :=
              (patch_value ->> 'outcome_selection_id')::uuid;
          exception when invalid_text_representation then
            raise exception using
              errcode = '22023', message = 'generation_spec_patch_invalid';
          end;
        end if;
      else
        outcome_selection_id_value := current_spec.outcome_selection_id;
      end if;
    end if;
    new_spec := content_factory_private.create_generation_spec_version(
      organization_id_value, spec_id_value, current_spec.version_id,
      exact_scope_value, editable_intent_value, proposed_prompt_value,
      learning_context_value, repair_context_value,
      research_provenance_value, performance_policy_provenance_value,
      repair_provenance_value, outcome_selection_id_value,
      reason_value, actor_id_value
    );
    new_state_value := 'draft';
  end if;

  insert into content_factory.generation_spec_head_events (
    organization_id, spec_id, event_sequence, action, state,
    spec_version, spec_hash, prior_event_id, approval_event_id,
    reason, actor_id, request_hash, event_hash
  ) values (
    organization_id_value, spec_id_value, next_sequence_value,
    action_value, new_state_value, new_spec.spec_version,
    new_spec.spec_hash, current_head.id, approval_event_id_value,
    reason_value, actor_id_value, request_hash_value,
    content_factory_private.json_hash(jsonb_build_object(
      'schema_version', 'generation-spec-head-event-v1',
      'organization_id', organization_id_value,
      'spec_id', spec_id_value,
      'event_sequence', next_sequence_value,
      'action', action_value,
      'state', new_state_value,
      'spec_version', new_spec.spec_version,
      'spec_hash', new_spec.spec_hash,
      'prior_event_id', current_head.id,
      'approval_event_id', approval_event_id_value,
      'reason', reason_value,
      'actor_id', actor_id_value,
      'request_hash', request_hash_value
    ))
  ) returning id into new_event_id_value;

  result_value := content_factory_private.generation_spec_envelope(
    organization_id_value, spec_id_value
  );
  return content_factory_private.finish_command(
    organization_id_value, actor_id_value,
    'creator_control_generation_spec', idempotency_key_value,
    request_payload, result_value
  );
end;
$$;

create or replace function public.creator_generation_spec_effective_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  outcome_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_effective_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or p_payload ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_effective_payload_invalid';
  end;
  spec_hash_value := lower(content_factory_private.require_text(
    p_payload, 'spec_hash', 64, 64
  ));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'generation_spec_effective_payload_invalid';
  end if;
  spec_row := content_factory_private.assert_generation_spec_current(
    organization_id_value, spec_id_value, spec_version_value,
    spec_hash_value, true, true
  );
  if spec_row.outcome_selection_id is not null then
    select selection.* into selection_row
    from content_factory.research_outcome_generation_selections selection
    where selection.organization_id = organization_id_value
      and selection.id = spec_row.outcome_selection_id;
    outcome_value := jsonb_build_object(
      'selection_id', selection_row.id,
      'selection_hash', selection_row.selection_hash,
      'selection_action', selection_row.selection_action,
      'expires_at', selection_row.expires_at
    );
  end if;
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-effective-policy-v1',
    'generation_spec_context', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash
    ),
    'status', 'approved_current',
    'exact_scope', spec_row.exact_scope,
    'compiled_prompt', spec_row.compiled_prompt,
    'prompt_hash', spec_row.prompt_hash,
    'learning_context', spec_row.canonical_learning_context,
    'repair_context', spec_row.canonical_repair_context,
    'final_policy_hash', spec_row.final_policy_hash,
    'outcome_selection', outcome_value,
    'automatic_approval', false,
    'automatic_spend', false,
    'automatic_generation', false
  );
end;
$$;

create or replace function
  content_factory_private.bind_generation_spec_to_paid_job()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  spec_id_text text;
  spec_version_text text;
  spec_hash_text text;
  spec_id_value uuid;
  spec_version_value integer;
  spec_row content_factory.generation_spec_versions%rowtype;
begin
  if tg_op = 'UPDATE' then
    if new.generation_spec_id is distinct from old.generation_spec_id
       or new.generation_spec_version is distinct from old.generation_spec_version
       or new.generation_spec_hash is distinct from old.generation_spec_hash then
      raise exception using
        errcode = '55000', message = 'generation_spec_job_identity_immutable';
    end if;
    return new;
  end if;
  if new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  spec_id_text := btrim(coalesce(current_setting(
    'content_factory.generation_spec_id', true
  ), ''));
  spec_version_text := btrim(coalesce(current_setting(
    'content_factory.generation_spec_version', true
  ), ''));
  spec_hash_text := lower(btrim(coalesce(current_setting(
    'content_factory.generation_spec_hash', true
  ), '')));
  if spec_id_text = '' or spec_version_text = '' or spec_hash_text = '' then
    raise exception using
      errcode = '42501', message = 'generation_spec_approval_required';
  end if;
  begin
    spec_id_value := spec_id_text::uuid;
    spec_version_value := spec_version_text::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_context_invalid';
  end;
  if spec_hash_text !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'generation_spec_context_invalid';
  end if;
  spec_row := content_factory_private.assert_generation_spec_current(
    new.organization_id, spec_id_value, spec_version_value,
    spec_hash_text, true, true
  );
  if new.product_id <> spec_row.product_id
     or new.input ->> 'input_media_id'
          is distinct from spec_row.primary_media_id::text
     or new.input ->> 'model' is distinct from spec_row.model
     or new.input ->> 'platform' is distinct from spec_row.platform
     or new.input -> 'duration_seconds'
          is distinct from to_jsonb(spec_row.duration_seconds)
     or new.input ->> 'format' is distinct from spec_row.format
     or coalesce(new.input -> 'audio', 'false'::jsonb)
          is distinct from to_jsonb(spec_row.audio)
     or btrim(coalesce(new.input ->> 'prompt_text', ''))
          is distinct from spec_row.compiled_prompt
     or lower(btrim(coalesce(current_setting(
       'content_factory.generation_product_category', true
     ), ''))) is distinct from spec_row.product_category then
    raise exception using
      errcode = '55000', message = 'generation_spec_job_binding_invalid';
  end if;
  new.generation_spec_id := spec_row.spec_id;
  new.generation_spec_version := spec_row.spec_version;
  new.generation_spec_hash := spec_row.spec_hash;
  new.input := new.input || jsonb_build_object(
    'generation_spec_context', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash
    )
  );
  return new;
end;
$$;

drop trigger if exists a_generation_spec_binding_guard
  on content_factory.generation_jobs;
create trigger a_generation_spec_binding_guard
before insert or update of
  generation_spec_id, generation_spec_version, generation_spec_hash
on content_factory.generation_jobs
for each row execute function
  content_factory_private.bind_generation_spec_to_paid_job();

-- A provider claim runs with the worker identity rather than the requesting
-- member's JWT.  Resolve the member only from the already-created exact paid
-- job, verify that membership is still active, temporarily install that
-- identity for the existing authoritative policy readers, and restore every
-- claim setting before returning.  Only hashes and bounded structural fields
-- are persisted; raw research/review content never enters this ledger.
create or replace function
  content_factory_private.generation_spec_live_claim_snapshot(
    organization_id_value uuid,
    generation_job_id_value uuid,
    spec_id_value uuid,
    spec_version_value integer,
    spec_hash_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  job_row content_factory.generation_jobs%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  signal_row content_factory.generation_creative_signals%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  selection_row
    content_factory.research_outcome_generation_selections%rowtype;
  prior_claim_sub text := current_setting(
    'request.jwt.claim.sub', true
  );
  prior_claim_role text := current_setting(
    'request.jwt.claim.role', true
  );
  prior_claims text := current_setting('request.jwt.claims', true);
  learning_policy_value jsonb;
  learning_policy_snapshot jsonb;
  expected_learning_policy jsonb;
  normalized_live_learning_policy jsonb;
  normalized_expected_learning_policy jsonb;
  live_exploration jsonb;
  expected_exploration jsonb;
  live_reason_codes jsonb;
  expected_reason_codes jsonb;
  live_category_evidence_count integer;
  expected_category_evidence_count integer;
  research_snapshot jsonb := null;
  creative_signal_snapshot jsonb;
  repair_policy_value jsonb;
  repair_policy_snapshot jsonb := null;
  outcome_advisory_value jsonb;
  outcome_snapshot jsonb := null;
  snapshot_without_hash jsonb;
begin
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.id = generation_job_id_value
    and job.generation_spec_id = spec_id_value
    and job.generation_spec_version = spec_version_value
    and job.generation_spec_hash = spec_hash_value
  for share;
  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend
     or job_row.requested_by is null then
    raise exception using
      errcode = '55000', message = 'generation_spec_provider_start_stale';
  end if;

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;
  if spec_row.version_id is null
     or spec_row.product_id <> job_row.product_id
     or not exists (
       select 1
       from content_factory.memberships membership
       join content_factory.organizations organization
         on organization.id = membership.organization_id
        and organization.status = 'active'
       join content_factory.profiles profile
         on profile.id = membership.profile_id
        and profile.status = 'active'
       join auth.users auth_user
         on auth_user.id = membership.profile_id
        and auth_user.email is not null
       where membership.organization_id = organization_id_value
         and membership.profile_id = job_row.requested_by
         and membership.status = 'active'
         and membership.role in (
           'owner', 'admin', 'producer', 'operator'
         )
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_provider_start_stale';
  end if;

  select signal.* into signal_row
  from content_factory.generation_creative_signals signal
  where signal.organization_id = organization_id_value
    and signal.generation_job_id = job_row.id
    and signal.product_id = spec_row.product_id;
  if signal_row.id is null
     or signal_row.platform <> spec_row.platform
     or signal_row.model <> spec_row.model
     or signal_row.product_category is distinct from spec_row.product_category
     or signal_row.prompt_hash <>
          content_factory_private.json_hash(to_jsonb(spec_row.compiled_prompt))
     or signal_row.creative_angle is distinct from
          spec_row.canonical_learning_context ->> 'creative_angle'
     or signal_row.hook_patterns is distinct from
          spec_row.canonical_learning_context -> 'hook_patterns'
     or signal_row.source is distinct from
          spec_row.canonical_learning_context ->> 'source'
     or signal_row.compiler_version is distinct from
          spec_row.canonical_learning_context ->> 'compiler_version'
     or (
       signal_row.source = 'performance_learning'
       and (
         signal_row.applied_policy_hash is distinct from
           spec_row.performance_policy_provenance ->> 'policy_hash'
         or signal_row.creative_brief_draft_id is not null
         or signal_row.scenario_position is not null
       )
     )
     or (
       signal_row.source = 'approved_research'
       and (
         signal_row.applied_policy_hash is not null
         or signal_row.creative_brief_draft_id::text is distinct from
           spec_row.research_provenance ->> 'creative_brief_draft_id'
         or signal_row.scenario_position::text is distinct from
           spec_row.research_provenance ->> 'scenario_position'
       )
     )
     or (
       signal_row.source = 'baseline'
       and (
         signal_row.applied_policy_hash is not null
         or signal_row.creative_brief_draft_id is not null
         or signal_row.scenario_position is not null
       )
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_provider_start_stale';
  end if;
  creative_signal_snapshot := jsonb_build_object(
    'signal_id', signal_row.id,
    'prompt_hash', signal_row.prompt_hash,
    'creative_angle', signal_row.creative_angle,
    'hook_patterns', signal_row.hook_patterns,
    'source', signal_row.source,
    'compiler_version', signal_row.compiler_version,
    'applied_policy_hash', signal_row.applied_policy_hash,
    'creative_brief_draft_id', signal_row.creative_brief_draft_id,
    'scenario_position', signal_row.scenario_position,
    'product_category', signal_row.product_category
  );

  perform set_config(
    'request.jwt.claim.sub', job_row.requested_by::text, true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claims',
    jsonb_build_object(
      'sub', job_row.requested_by,
      'role', 'authenticated'
    )::text,
    true
  );

  begin
    learning_policy_value := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'media_id', spec_row.primary_media_id,
        'platform', spec_row.platform,
        'model', spec_row.model,
        'product_category', spec_row.product_category
      )
    );
    if jsonb_typeof(learning_policy_value) <> 'object'
       or coalesce(learning_policy_value ->> 'policy_hash', '')
            !~ '^[0-9a-f]{64}$'
       or learning_policy_value -> 'generation_allowed'
            is distinct from 'true'::jsonb
       or learning_policy_value ->> 'requested_model'
            is distinct from spec_row.model
       or learning_policy_value ->> 'product_category'
            is distinct from spec_row.product_category then
      raise exception using
        errcode = '55000', message = 'generation_spec_provider_start_stale';
    end if;
    expected_learning_policy := spec_row.final_policy -> 'learning_policy';
    if spec_row.performance_policy_provenance is not null then
      if jsonb_typeof(expected_learning_policy) <> 'object'
         or learning_policy_value -> 'applied' is distinct from 'true'::jsonb
         or coalesce(
              learning_policy_value ->> 'category_evidence_count', ''
            ) !~ '^[0-9]+$'
         or coalesce(
              expected_learning_policy ->> 'category_evidence_count', ''
            ) !~ '^[0-9]+$' then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      live_category_evidence_count := (
        learning_policy_value ->> 'category_evidence_count'
      )::integer;
      expected_category_evidence_count := (
        expected_learning_policy ->> 'category_evidence_count'
      )::integer;
      -- The one newly-created queued job contributes exactly one typed
      -- creative signal to this non-ranking cold-start counter.  No other
      -- learning-policy drift is permitted after human approval.
      if live_category_evidence_count <>
           expected_category_evidence_count + 1
         or learning_policy_value -> 'category_cold_start' is distinct from
              to_jsonb(live_category_evidence_count = 0)
         or expected_learning_policy -> 'category_cold_start'
              is distinct from
              to_jsonb(expected_category_evidence_count = 0) then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      select coalesce(
        jsonb_agg(item.value order by item.ordinality), '[]'::jsonb
      ) into live_reason_codes
      from jsonb_array_elements_text(coalesce(
        learning_policy_value -> 'reason_codes', '[]'::jsonb
      )) with ordinality item(value, ordinality)
      where item.value <> 'category_cold_start';
      select coalesce(
        jsonb_agg(item.value order by item.ordinality), '[]'::jsonb
      ) into expected_reason_codes
      from jsonb_array_elements_text(coalesce(
        expected_learning_policy -> 'reason_codes', '[]'::jsonb
      )) with ordinality item(value, ordinality)
      where item.value <> 'category_cold_start';
      normalized_live_learning_policy :=
        learning_policy_value - array[
          'policy_hash', 'category_evidence_count',
          'category_cold_start', 'reason_codes'
        ]::text[] || jsonb_build_object(
          'reason_codes', live_reason_codes
        );
      normalized_expected_learning_policy :=
        expected_learning_policy - array[
          'policy_hash', 'category_evidence_count',
          'category_cold_start', 'reason_codes'
        ]::text[] || jsonb_build_object(
          'reason_codes', expected_reason_codes
        );
      if expected_learning_policy ->> 'selection_mode' =
           'bounded_exploration' then
        live_exploration := learning_policy_value -> 'exploration';
        expected_exploration := expected_learning_policy -> 'exploration';
        if learning_policy_value ->> 'selection_mode' is distinct from
             'bounded_exploration'
           or jsonb_typeof(live_exploration) <> 'object'
           or jsonb_typeof(expected_exploration) <> 'object'
           or live_exploration - array[
                'candidate_count', 'selected_prior_use_count',
                'balancing_scope'
              ]::text[] <> '{}'::jsonb
           or expected_exploration - array[
                'candidate_count', 'selected_prior_use_count',
                'balancing_scope'
              ]::text[] <> '{}'::jsonb
           or live_exploration -> 'candidate_count' is distinct from
                '2'::jsonb
           or expected_exploration -> 'candidate_count' is distinct from
                '2'::jsonb
           or live_exploration ->> 'balancing_scope' is distinct from
                'product_platform_model'
           or expected_exploration ->> 'balancing_scope' is distinct from
                'product_platform_model'
           or coalesce(
                live_exploration ->> 'selected_prior_use_count', ''
              ) !~ '^[0-9]+$'
           or coalesce(
                expected_exploration ->> 'selected_prior_use_count', ''
              ) !~ '^[0-9]+$'
           or expected_learning_policy ->> 'preferred_angle'
                is distinct from signal_row.creative_angle
           or expected_learning_policy -> 'preferred_hook_patterns'
                is distinct from signal_row.hook_patterns
           or expected_learning_policy ->> 'selected_angle'
                is distinct from signal_row.creative_angle
           or expected_learning_policy -> 'selected_hook_patterns'
                is distinct from signal_row.hook_patterns
           or (
             (
               learning_policy_value ->> 'preferred_angle' =
                 'product_focus'
               and learning_policy_value -> 'preferred_hook_patterns' =
                 '[]'::jsonb
             ) or (
               learning_policy_value ->> 'preferred_angle' =
                 'demonstration'
               and learning_policy_value -> 'preferred_hook_patterns' =
                 '["demonstration"]'::jsonb
             )
           ) is not true
           or learning_policy_value ->> 'selected_angle' is distinct from
                learning_policy_value ->> 'preferred_angle'
           or learning_policy_value -> 'selected_hook_patterns'
                is distinct from
                  learning_policy_value -> 'preferred_hook_patterns' then
          raise exception using
            errcode = '55000',
            message = 'generation_spec_provider_start_stale';
        end if;
        -- The exact queued signal can advance only the two-candidate
        -- exploration cursor. Keep every gate, guard, safety field, reason,
        -- and bounded-exploration invariant in the equality comparison.
        normalized_live_learning_policy :=
          normalized_live_learning_policy - array[
            'preferred_angle', 'preferred_hook_patterns',
            'selected_angle', 'selected_hook_patterns', 'exploration'
          ]::text[] || jsonb_build_object(
            'exploration', live_exploration - 'selected_prior_use_count'
          );
        normalized_expected_learning_policy :=
          normalized_expected_learning_policy - array[
            'preferred_angle', 'preferred_hook_patterns',
            'selected_angle', 'selected_hook_patterns', 'exploration'
          ]::text[] || jsonb_build_object(
            'exploration', expected_exploration - 'selected_prior_use_count'
          );
      end if;
      if normalized_live_learning_policy is distinct from
           normalized_expected_learning_policy then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
    elsif jsonb_typeof(expected_learning_policy) <> 'object'
          or expected_learning_policy ->> 'version' <>
               'generation-spec-baseline-v1'
          or expected_learning_policy -> 'generation_allowed'
               is distinct from 'true'::jsonb then
      -- Baseline/research specs deliberately freeze a human-approved prompt
      -- instead of adopting the live structural policy. The full live policy
      -- is still snapshotted below and must remain byte-for-byte current at
      -- claim, while its generation gate is enforced above.
      raise exception using
        errcode = '55000', message = 'generation_spec_provider_start_stale';
    end if;
    learning_policy_snapshot := jsonb_build_object(
      'canonical_hash',
        content_factory_private.json_hash(learning_policy_value),
      'version', learning_policy_value ->> 'version',
      'policy_hash', learning_policy_value ->> 'policy_hash',
      'applied', learning_policy_value -> 'applied',
      'generation_allowed', learning_policy_value -> 'generation_allowed',
      'selection_mode', learning_policy_value ->> 'selection_mode',
      'preferred_angle', learning_policy_value ->> 'preferred_angle',
      'preferred_hook_patterns', coalesce(
        learning_policy_value -> 'preferred_hook_patterns', '[]'::jsonb
      ),
      'quality_guard_codes', coalesce(
        learning_policy_value -> 'quality_guard_codes', '[]'::jsonb
      ),
      'quality_guard_variants', coalesce(
        learning_policy_value -> 'quality_guard_variants', '{}'::jsonb
      ),
      'product_category', learning_policy_value ->> 'product_category',
      'category_evidence_count',
        learning_policy_value -> 'category_evidence_count'
    );

    if spec_row.research_provenance is not null then
      select draft.* into draft_row
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = organization_id_value
        and draft.run_id = (
          spec_row.research_provenance ->> 'research_id'
        )::uuid
        and draft.id = (
          spec_row.research_provenance ->> 'creative_brief_draft_id'
        )::uuid
        and draft.product_id = spec_row.product_id
      for share;
      research_snapshot := jsonb_build_object(
        'research_id', draft_row.run_id,
        'creative_brief_draft_id', draft_row.id,
        'creative_brief_content_hash', draft_row.content_hash,
        'scenario_position', (
          spec_row.research_provenance ->> 'scenario_position'
        )::integer
      );
      if draft_row.id is null
         or draft_row.status <> 'approved'
         or content_factory_private.json_hash(research_snapshot)
              <> spec_row.research_snapshot_hash then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      research_snapshot := research_snapshot || jsonb_build_object(
        'status', draft_row.status,
        'snapshot_hash', spec_row.research_snapshot_hash
      );
    end if;

    if spec_row.canonical_repair_context is not null then
      repair_policy_value := public.creator_generation_repair_policy(
        jsonb_build_object(
          'organization_id', organization_id_value,
          'review_id',
            spec_row.canonical_repair_context ->> 'source_review_id'
        )
      );
      if repair_policy_value -> 'applied' is distinct from 'true'::jsonb
         or repair_policy_value ->> 'policy_hash' is distinct from
              spec_row.canonical_repair_context ->> 'policy_hash'
         or repair_policy_value ->> 'source_generation_job_id'
              is distinct from spec_row.canonical_repair_context
                ->> 'source_generation_job_id'
         or repair_policy_value -> 'guard_codes' is distinct from
              spec_row.canonical_repair_context -> 'guard_codes'
         or repair_policy_value ->> 'input_media_id'
              is distinct from spec_row.primary_media_id::text
         or repair_policy_value ->> 'model' is distinct from spec_row.model
         or repair_policy_value ->> 'platform'
              is distinct from spec_row.platform then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      repair_policy_snapshot := jsonb_build_object(
        'canonical_hash',
          content_factory_private.json_hash(repair_policy_value),
        'version', repair_policy_value ->> 'version',
        'policy_hash', repair_policy_value ->> 'policy_hash',
        'source_review_id', repair_policy_value ->> 'source_review_id',
        'source_generation_job_id',
          repair_policy_value ->> 'source_generation_job_id',
        'guard_codes', repair_policy_value -> 'guard_codes'
      );
    end if;

    if spec_row.outcome_selection_id is not null then
      select selection.* into selection_row
      from content_factory.research_outcome_generation_selections selection
      where selection.organization_id = organization_id_value
        and selection.id = spec_row.outcome_selection_id
      for share;
      if selection_row.id is null
         or selection_row.selection_hash <>
              spec_row.outcome_selection_hash
         or selection_row.selection_action <> 'control'
         or selection_row.expires_at <= clock_timestamp()
         or selection_row.input_media_id <> spec_row.primary_media_id
         or selection_row.product_id <> spec_row.product_id
         or selection_row.product_category <> spec_row.product_category
         or selection_row.platform <> spec_row.platform
         or selection_row.model <> spec_row.model then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      perform pg_advisory_xact_lock(
        hashtext(organization_id_value::text),
        hashtext(
          'research-market-product:' || selection_row.product_id::text
        )
      );
      perform pg_advisory_xact_lock(
        hashtext(organization_id_value::text),
        hashtext(
          'research-outcome-learning:' ||
          selection_row.market_category_id::text || ':' ||
          selection_row.platform || ':' || selection_row.model
        )
      );
      outcome_advisory_value :=
        content_factory_private.research_outcome_generation_advisory(
          organization_id_value, spec_row.primary_media_id,
          spec_row.platform, spec_row.model, spec_row.product_category
        );
      if outcome_advisory_value ->> 'product_id'
           is distinct from selection_row.product_id::text
         or outcome_advisory_value #>> '{scope,market_category_id}'
           is distinct from selection_row.market_category_id::text
         or outcome_advisory_value #>> '{scope,category_binding_id}'
           is distinct from selection_row.category_binding_id::text
         or outcome_advisory_value #>> '{scope,category_binding_version}'
           is distinct from selection_row.category_binding_version::text
         or outcome_advisory_value #>> '{memory,memory_version_id}'
           is distinct from selection_row.memory_version_id::text
         or outcome_advisory_value #>> '{memory,memory_version}'
           is distinct from selection_row.memory_version::text
         or outcome_advisory_value #>> '{candidate,candidate_id}'
           is distinct from selection_row.candidate_id::text
         or outcome_advisory_value #>> '{candidate,candidate_version}'
           is distinct from selection_row.candidate_version::text
         or outcome_advisory_value #>> '{candidate,candidate_hash}'
           is distinct from selection_row.candidate_hash
         or outcome_advisory_value #>> '{base_policy,policy_hash}'
           is distinct from learning_policy_value ->> 'policy_hash'
         or outcome_advisory_value #>> '{base_policy,selection_mode}'
           is distinct from learning_policy_value ->> 'selection_mode'
         or outcome_advisory_value #>> '{base_policy,preferred_angle}'
           is distinct from learning_policy_value ->> 'preferred_angle'
         or outcome_advisory_value #> '{permissions,control_allowed}'
           is distinct from 'true'::jsonb then
        raise exception using
          errcode = '55000', message = 'generation_spec_provider_start_stale';
      end if;
      outcome_snapshot := jsonb_build_object(
        'selection_id', selection_row.id,
        'selection_hash', selection_row.selection_hash,
        'selection_action', selection_row.selection_action,
        'expires_at', selection_row.expires_at,
        'advisory_canonical_hash',
          content_factory_private.json_hash(outcome_advisory_value),
        'base_policy_hash',
          outcome_advisory_value #>> '{base_policy,policy_hash}',
        'control_allowed',
          outcome_advisory_value #> '{permissions,control_allowed}'
      );
    end if;
  exception when others then
    perform set_config(
      'request.jwt.claim.sub', coalesce(prior_claim_sub, ''), true
    );
    perform set_config(
      'request.jwt.claim.role', coalesce(prior_claim_role, ''), true
    );
    perform set_config(
      'request.jwt.claims', coalesce(nullif(prior_claims, ''), '{}'), true
    );
    raise;
  end;

  perform set_config(
    'request.jwt.claim.sub', coalesce(prior_claim_sub, ''), true
  );
  perform set_config(
    'request.jwt.claim.role', coalesce(prior_claim_role, ''), true
  );
  perform set_config(
    'request.jwt.claims', coalesce(nullif(prior_claims, ''), '{}'), true
  );

  snapshot_without_hash := jsonb_build_object(
    'version', 'generation-spec-claim-snapshot-v1',
    'organization_id', organization_id_value,
    'generation_job_id', job_row.id,
    'generation_spec_context', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash
    ),
    'requested_by', job_row.requested_by,
    'creative_signal', creative_signal_snapshot,
    'learning_policy', learning_policy_snapshot,
    'research', research_snapshot,
    'repair_policy', repair_policy_snapshot,
    'outcome_selection', outcome_snapshot
  );
  return snapshot_without_hash || jsonb_build_object(
    'snapshot_hash',
      content_factory_private.json_hash(snapshot_without_hash)
  );
end;
$$;

revoke all on function
  content_factory_private.generation_spec_live_claim_snapshot(
    uuid, uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.guard_generation_spec_provider_start()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  spec_row content_factory.generation_spec_versions%rowtype;
  binding_row content_factory.generation_job_spec_bindings%rowtype;
  reference_ids_value jsonb;
  live_claim_snapshot jsonb;
  caught_state text;
  caught_message text;
begin
  if old.status <> 'queued' or new.status <> 'starting'
     or new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  -- Pre-migration/service-owned rows remain operable. Authenticated starts
  -- after this migration always carry the three-column identity.
  if new.generation_spec_id is null then
    return new;
  end if;
  begin
    perform pg_advisory_xact_lock(
      hashtext(new.organization_id::text),
      hashtext('generation-spec:' || new.generation_spec_id::text)
    );
    spec_row := content_factory_private.assert_generation_spec_current(
      new.organization_id, new.generation_spec_id,
      new.generation_spec_version, new.generation_spec_hash,
      true, false
    );
    select binding.* into binding_row
    from content_factory.generation_job_spec_bindings binding
    where binding.organization_id = new.organization_id
      and binding.generation_job_id = new.id
      and binding.spec_id = new.generation_spec_id
      and binding.spec_version = new.generation_spec_version
      and binding.spec_hash = new.generation_spec_hash;
    reference_ids_value := coalesce(
      new.input -> 'reference_media_ids',
      jsonb_build_array(new.input ->> 'input_media_id')
    );
    live_claim_snapshot :=
      content_factory_private.generation_spec_live_claim_snapshot(
        new.organization_id, new.id, new.generation_spec_id,
        new.generation_spec_version, new.generation_spec_hash
      );
    if binding_row.id is null
       or binding_row.bound_by <> new.requested_by
       or binding_row.prompt_hash <> spec_row.prompt_hash
       or binding_row.final_policy_hash <> spec_row.final_policy_hash
       or binding_row.outcome_selection_id
            is distinct from spec_row.outcome_selection_id
       or binding_row.outcome_selection_hash
            is distinct from spec_row.outcome_selection_hash
       or binding_row.claim_snapshot <> live_claim_snapshot
       or binding_row.claim_snapshot_hash <>
            live_claim_snapshot ->> 'snapshot_hash'
       or new.product_id <> spec_row.product_id
       or reference_ids_value is distinct from
            spec_row.exact_scope -> 'media_ids'
       or new.input ->> 'input_media_id'
            is distinct from spec_row.primary_media_id::text
       or new.input ->> 'product_category'
            is distinct from spec_row.product_category
       or new.input ->> 'model' is distinct from spec_row.model
       or new.input ->> 'platform' is distinct from spec_row.platform
       or new.input -> 'duration_seconds'
            is distinct from to_jsonb(spec_row.duration_seconds)
       or new.input ->> 'format' is distinct from spec_row.format
       or coalesce(new.input -> 'audio', 'false'::jsonb)
            is distinct from to_jsonb(spec_row.audio)
       or content_factory_private.raw_text_sha256(
         coalesce(new.input ->> 'prompt_text', '')
       ) <> spec_row.prompt_hash then
      raise exception using
        errcode = '55000', message = 'generation_spec_provider_start_stale';
    end if;
  exception when others then
    get stacked diagnostics
      caught_state = returned_sqlstate,
      caught_message = message_text;
    -- Only deterministic generation-spec validation failures are safe to
    -- classify as a definitive stale claim. Database, dependency, casting,
    -- authorization, and other unexpected failures must retain their original
    -- error so the worker retries and the reservation remains untouched.
    if (caught_state = '55000' and caught_message in (
         'generation_spec_provider_start_stale',
         'generation_spec_stale',
         'generation_spec_media_stale',
         'generation_spec_research_provenance_stale',
         'generation_spec_learning_context_stale',
         'generation_spec_performance_policy_stale',
         'generation_spec_repair_policy_stale',
         'generation_spec_outcome_selection_stale',
         'generation_spec_outcome_apply_revalidation_required',
         'generation_spec_policy_blocked'
       ))
       or (
         caught_state = '42501'
         and caught_message = 'generation_spec_approval_required'
       ) then
      raise exception using
        errcode = '55000', message = 'generation_spec_provider_start_stale';
    end if;
    raise;
  end;
  return new;
end;
$$;

drop trigger if exists b_generation_spec_provider_start_guard
  on content_factory.generation_jobs;
create trigger b_generation_spec_provider_start_guard
before update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_generation_spec_provider_start();

-- A stale claim is definitive before any provider task exists. A trigger
-- exception alone would roll back and leave both the queued job and its spend
-- reservation live, so consume that one exact exception here, terminalize the
-- complete job/batch/review-task aggregate, let the installed spend trigger
-- append its release, and return a non-retryable result instead of raising.
alter function public.system_update_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_update_real_generation(jsonb)
  rename to system_update_real_generation_pre_generation_spec_claim_v3;

revoke all on function
  content_factory_private
    .system_update_real_generation_pre_generation_spec_claim_v3(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_update_real_generation(
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
  job_id_value uuid;
  status_value text;
  caught_message text;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  binding_row content_factory.generation_job_spec_bindings%rowtype;
  task_count integer;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  status_value := lower(btrim(coalesce(p_payload ->> 'status', '')));
  if status_value <> 'starting' then
    return content_factory_private
      .system_update_real_generation_pre_generation_spec_claim_v3(p_payload);
  end if;
  if p_payload - array['job_id', 'status']::text[] <> '{}'::jsonb then
    return content_factory_private
      .system_update_real_generation_pre_generation_spec_claim_v3(p_payload);
  end if;
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
  for update;
  if job_row.id is null or job_row.generation_spec_id is null then
    return content_factory_private
      .system_update_real_generation_pre_generation_spec_claim_v3(p_payload);
  end if;

  if job_row.status = 'failed'
     and job_row.output ->> 'failure_code' =
       'generation_spec_provider_start_stale' then
    if not exists (
         select 1
         from content_factory.generation_batches batch
         where batch.organization_id = job_row.organization_id
           and batch.id = job_row.batch_id
           and batch.status = 'failed'
       )
       or (
         select count(*)
         from content_factory.creator_tasks task
         where task.organization_id = job_row.organization_id
           and task.generation_job_id = job_row.id
           and task.status = 'cancelled'
           and task.result ->> 'failure_code' =
             'generation_spec_provider_start_stale'
       ) <> 1
       or not exists (
         select 1
         from content_factory.generation_spend_ledger ledger
         where ledger.organization_id = job_row.organization_id
           and ledger.generation_job_id = job_row.id
           and ledger.event_type = 'released'
           and ledger.reserved_delta_minor = -job_row.estimated_cost_minor
           and ledger.committed_delta_minor = 0
       )
       or exists (
         select 1
         from content_factory.generation_storage_reservations reservation
         where reservation.organization_id = job_row.organization_id
           and reservation.generation_job_id = job_row.id
           and reservation.status = 'active'
       ) then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_claim_terminalization_failed';
    end if;
    return jsonb_build_object(
      'ok', false,
      'claimed', false,
      'terminal', true,
      'code', 'generation_spec_provider_start_stale',
      'retryable', false,
      'job', jsonb_build_object(
        'id', job_row.id,
        'batch_id', job_row.batch_id,
        'status', job_row.status,
        'provider', job_row.provider,
        'failure_code', job_row.output ->> 'failure_code',
        'updated_at', job_row.updated_at
      )
    );
  end if;
  if job_row.status <> 'queued' then
    return content_factory_private
      .system_update_real_generation_pre_generation_spec_claim_v3(p_payload);
  end if;

  perform pg_advisory_xact_lock(
    hashtext(job_row.organization_id::text),
    hashtext('generation-spec:' || job_row.generation_spec_id::text)
  );
  begin
    result_value := content_factory_private
      .system_update_real_generation_pre_generation_spec_claim_v3(p_payload);
    return result_value;
  exception when sqlstate '55000' then
    get stacked diagnostics caught_message = message_text;
    if caught_message <> 'generation_spec_provider_start_stale' then
      raise;
    end if;
  end;

  -- The failed claim subtransaction is gone. Re-read and lock every durable
  -- aggregate member before writing the terminal state.
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.id = job_id_value
  for update;
  select binding.* into binding_row
  from content_factory.generation_job_spec_bindings binding
  where binding.organization_id = job_row.organization_id
    and binding.generation_job_id = job_row.id
    and binding.spec_id = job_row.generation_spec_id
    and binding.spec_version = job_row.generation_spec_version
    and binding.spec_hash = job_row.generation_spec_hash;
  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id = job_row.organization_id
    and batch.id = job_row.batch_id
  for update;
  select count(*)::integer, (array_agg(task.id order by task.id))[1]
    into task_count, task_row.id
  from content_factory.creator_tasks task
  where task.organization_id = job_row.organization_id
    and task.generation_job_id = job_row.id;
  if task_count = 1 then
    select task.* into task_row
    from content_factory.creator_tasks task
    where task.organization_id = job_row.organization_id
      and task.id = task_row.id
    for update;
  end if;

  if job_row.status <> 'queued'
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or not job_row.allow_real_spend
     or job_row.actual_cost_minor <> 0
     or nullif(btrim(coalesce(
          job_row.output ->> 'provider_task_id', ''
        )), '') is not null
     or binding_row.id is null
     or binding_row.bound_by <> job_row.requested_by
     or batch_row.id is null
     or batch_row.status <> 'queued'
     or batch_row.organization_id <> job_row.organization_id
     or batch_row.product_id <> job_row.product_id
     or task_count <> 1
     or task_row.id::text is distinct from
          job_row.input ->> 'review_task_id'
     or task_row.status <> 'blocked'
     or task_row.product_id is distinct from job_row.product_id
     or task_row.assignee_id is distinct from job_row.assigned_to
     or task_row.created_by is distinct from job_row.requested_by
     or not exists (
       select 1
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id = job_row.organization_id
         and ledger.generation_job_id = job_row.id
         and ledger.event_type = 'reserved'
     )
     or exists (
       select 1
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id = job_row.organization_id
         and ledger.generation_job_id = job_row.id
         and ledger.event_type in (
           'settled', 'released', 'frozen', 'refunded'
         )
     )
     or exists (
       select 1
       from content_factory.generation_storage_reservations reservation
       where reservation.organization_id = job_row.organization_id
         and reservation.generation_job_id = job_row.id
     ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_provider_start_stale';
  end if;

  update content_factory.generation_jobs job
  set status = 'failed',
      actual_cost_minor = 0,
      output = (
        job.output - 'output_media_id' - 'output_object_name'
      ) || jsonb_build_object(
        'failure_code', 'generation_spec_provider_start_stale',
        'failed_at', clock_timestamp(),
        'actual_cost_minor', 0,
        'currency', 'USD'
      )
  where job.id = job_row.id
    and job.status = 'queued'
  returning * into job_row;
  if job_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_claim_terminalization_failed';
  end if;

  update content_factory.generation_batches batch
  set status = 'failed', total_created = 0
  where batch.organization_id = job_row.organization_id
    and batch.id = job_row.batch_id
    and batch.status = 'queued';
  if not found then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_claim_terminalization_failed';
  end if;

  update content_factory.creator_tasks task
  set status = 'cancelled',
      completed_at = coalesce(task.completed_at, clock_timestamp()),
      result = task.result || jsonb_build_object(
        'generation_status', 'failed',
        'failure_code', 'generation_spec_provider_start_stale',
        'review_required', false,
        'provider', job_row.provider,
        'model', job_row.input ->> 'model',
        'duration_seconds', job_row.input -> 'duration_seconds',
        'audio', coalesce(job_row.input -> 'audio', 'false'::jsonb),
        'estimated_cost_minor', job_row.estimated_cost_minor,
        'currency', 'USD'
      )
  where task.organization_id = job_row.organization_id
    and task.id = task_row.id
    and task.status = 'blocked';
  if not found or not exists (
    select 1
    from content_factory.generation_spend_ledger ledger
    where ledger.organization_id = job_row.organization_id
      and ledger.generation_job_id = job_row.id
      and ledger.event_type = 'released'
      and ledger.reserved_delta_minor = -job_row.estimated_cost_minor
      and ledger.committed_delta_minor = 0
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_claim_terminalization_failed';
  end if;

  perform content_factory_private.emit_event(
    job_row.organization_id,
    job_row.requested_by,
    'real_generation_failed',
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'status', job_row.status,
      'failure_code', 'generation_spec_provider_start_stale',
      'provider_action', false,
      'spend_released', true,
      'terminal', true
    ),
    'real-generation:' || job_row.id::text || ':failed',
    'system'
  );

  return jsonb_build_object(
    'ok', false,
    'claimed', false,
    'terminal', true,
    'code', 'generation_spec_provider_start_stale',
    'retryable', false,
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'status', job_row.status,
      'provider', job_row.provider,
      'failure_code', job_row.output ->> 'failure_code',
      'updated_at', job_row.updated_at
    )
  );
end;
$$;

revoke all on function public.system_update_real_generation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_update_real_generation(jsonb)
  to service_role;

-- Replace the deliberate foundation hard gate. Only a fully-bound control
-- selection is consumable here; learned "apply" remains fail-closed until a
-- service-safe live evidence revalidator is available at provider claim.
create or replace function
  content_factory_private.validate_research_outcome_generation_assignment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  binding_row content_factory.generation_job_spec_bindings%rowtype;
begin
  select selection.* into selection_row
  from content_factory.research_outcome_generation_selections selection
  where selection.organization_id = new.organization_id
    and selection.id = new.selection_id
  for share;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = new.generation_job_id
  for share;
  select binding.* into binding_row
  from content_factory.generation_job_spec_bindings binding
  where binding.organization_id = new.organization_id
    and binding.generation_job_id = new.generation_job_id
    and binding.outcome_selection_id = new.selection_id
    and binding.outcome_selection_hash = new.selection_hash;
  if selection_row.id is null or job_row.id is null or binding_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_assignment_binding_invalid';
  end if;
  if selection_row.selection_action = 'apply' then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_outcome_apply_revalidation_required';
  end if;
  if selection_row.selection_action <> 'control'
     or new.bound_at > selection_row.expires_at
     or job_row.created_at < selection_row.created_at
     or job_row.created_at > selection_row.expires_at
     or job_row.mode <> 'real'
     or not job_row.allow_real_spend
     or job_row.product_id <> selection_row.product_id
     or job_row.input ->> 'platform' <> selection_row.platform
     or job_row.input ->> 'model' <> selection_row.model
     or job_row.input ->> 'product_category' <> selection_row.product_category
     or new.product_id <> selection_row.product_id
     or new.market_category_id <> selection_row.market_category_id
     or new.category_binding_id <> selection_row.category_binding_id
     or new.category_binding_version <> selection_row.category_binding_version
     or new.platform <> selection_row.platform
     or new.model <> selection_row.model
     or new.product_category <> selection_row.product_category
     or new.memory_version_id <> selection_row.memory_version_id
     or new.memory_version <> selection_row.memory_version
     or new.candidate_id <> selection_row.candidate_id
     or new.candidate_version <> selection_row.candidate_version
     or new.candidate_hash <> selection_row.candidate_hash
     or new.assignment_action <> selection_row.selection_action
     or new.selected_creative_angle is distinct from
        selection_row.selected_creative_angle
     or new.selected_hook_patterns <> '[]'::jsonb
     or new.selection_hash <> selection_row.selection_hash
     or new.base_policy_hash <> selection_row.base_policy_hash
     or new.final_policy_hash <> binding_row.final_policy_hash
     or new.prompt_hash <> binding_row.prompt_hash
     or new.effectiveness_status <> 'unknown'
     or new.bound_by <> job_row.requested_by then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_assignment_invalid';
  end if;
  return new;
end;
$$;

alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_generation_spec_v15;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_generation_spec_v15(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
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
  context_value jsonb;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  result_value jsonb;
  job_id_value uuid;
  batch_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
  binding_row content_factory.generation_job_spec_bindings%rowtype;
  signal_row content_factory.generation_creative_signals%rowtype;
  repair_signal_row content_factory.generation_repair_signals%rowtype;
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  reference_ids_value jsonb;
  context_hash_value text;
  start_request_hash_value text;
  claim_snapshot_value jsonb;
  claim_snapshot_hash_value text;
  replay_batch_id_value uuid;
  replay_job_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  context_value := p_payload -> 'generation_spec_context';
  if jsonb_typeof(context_value) <> 'object'
     or context_value - array[
       'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not context_value ?& array[
       'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_context_invalid';
  end if;
  begin
    spec_id_value := (context_value ->> 'spec_id')::uuid;
    if jsonb_typeof(context_value -> 'spec_version') <> 'number'
       or context_value ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (context_value ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_context_invalid';
  end;
  spec_hash_value := lower(btrim(coalesce(context_value ->> 'spec_hash', '')));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'generation_spec_context_invalid';
  end if;
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  start_request_hash_value := content_factory_private.json_hash(
    p_payload - 'idempotency_key'
  );
  select batch.id, job.id
    into replay_batch_id_value, replay_job_id_value
  from content_factory.generation_batches batch
  join content_factory.generation_jobs job
    on job.organization_id = batch.organization_id
   and job.batch_id = batch.id
  where batch.organization_id = organization_id_value
    and batch.idempotency_key = btrim(coalesce(
      p_payload ->> 'idempotency_key', ''
    ))
    and job.requested_by = actor_id_value
  limit 1;
  if replay_job_id_value is not null then
    select binding.* into binding_row
    from content_factory.generation_job_spec_bindings binding
    where binding.organization_id = organization_id_value
      and binding.generation_job_id = replay_job_id_value;
    if binding_row.id is null
       or binding_row.spec_id <> spec_id_value
       or binding_row.spec_version <> spec_version_value
       or binding_row.spec_hash <> spec_hash_value
       or binding_row.start_request_hash <> start_request_hash_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return binding_row.start_result;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-spec:' || spec_id_value::text)
  );
  -- A concurrent exact retry can miss the uncommitted batch before waiting on
  -- the spec lock. Re-read after the lock and return the immutable binding
  -- before dynamic policy freshness can be changed by the first job's signal.
  replay_batch_id_value := null;
  replay_job_id_value := null;
  binding_row := null;
  select batch.id, job.id
    into replay_batch_id_value, replay_job_id_value
  from content_factory.generation_batches batch
  join content_factory.generation_jobs job
    on job.organization_id = batch.organization_id
   and job.batch_id = batch.id
  where batch.organization_id = organization_id_value
    and batch.idempotency_key = btrim(coalesce(
      p_payload ->> 'idempotency_key', ''
    ))
    and job.requested_by = actor_id_value
  limit 1;
  if replay_job_id_value is not null then
    select binding.* into binding_row
    from content_factory.generation_job_spec_bindings binding
    where binding.organization_id = organization_id_value
      and binding.generation_job_id = replay_job_id_value;
    if binding_row.id is null
       or binding_row.spec_id <> spec_id_value
       or binding_row.spec_version <> spec_version_value
       or binding_row.spec_hash <> spec_hash_value
       or binding_row.start_request_hash <> start_request_hash_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return binding_row.start_result;
  end if;
  spec_row := content_factory_private.assert_generation_spec_current(
    organization_id_value, spec_id_value, spec_version_value,
    spec_hash_value, true, true
  );

  if p_payload -> 'media_ids' is distinct from spec_row.exact_scope -> 'media_ids'
     or lower(btrim(coalesce(p_payload ->> 'platform', '')))
          is distinct from spec_row.platform
     or lower(btrim(coalesce(p_payload ->> 'model', '')))
          is distinct from spec_row.model
     or p_payload -> 'duration_seconds'
          is distinct from to_jsonb(spec_row.duration_seconds)
     or lower(btrim(coalesce(p_payload ->> 'product_category', '')))
          is distinct from spec_row.product_category
     or btrim(coalesce(p_payload ->> 'format', ''))
          is distinct from spec_row.format
     or coalesce(p_payload -> 'audio', 'false'::jsonb)
          is distinct from to_jsonb(spec_row.audio)
     or btrim(coalesce(p_payload ->> 'brief', ''))
          is distinct from spec_row.compiled_prompt
     or p_payload -> 'learning_context'
          is distinct from spec_row.canonical_learning_context
     or nullif(p_payload -> 'repair_context', 'null'::jsonb)
          is distinct from spec_row.canonical_repair_context then
    raise exception using
      errcode = '55000', message = 'generation_spec_request_mismatch';
  end if;

  perform set_config(
    'content_factory.generation_spec_id', spec_row.spec_id::text, true
  );
  perform set_config(
    'content_factory.generation_spec_version', spec_row.spec_version::text, true
  );
  perform set_config(
    'content_factory.generation_spec_hash', spec_row.spec_hash, true
  );
  result_value := content_factory_private
    .creator_start_real_generation_pre_generation_spec_v15(
      case
        when p_payload -> 'repair_context' = 'null'::jsonb then
          p_payload - array[
            'generation_spec_context', 'repair_context'
          ]::text[]
        else p_payload - 'generation_spec_context'
      end
    );
  begin
    job_id_value := (result_value #>> '{job,id}')::uuid;
    batch_id_value := (result_value #>> '{batch,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000', message = 'generation_spec_job_binding_invalid';
  end;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.id = job_id_value
    and job.batch_id = batch_id_value
    and job.requested_by = actor_id_value
  for update;
  reference_ids_value := coalesce(
    job_row.input -> 'reference_media_ids',
    jsonb_build_array(job_row.input ->> 'input_media_id')
  );
  if job_row.id is null
     or job_row.product_id <> spec_row.product_id
     or job_row.generation_spec_id <> spec_row.spec_id
     or job_row.generation_spec_version <> spec_row.spec_version
     or job_row.generation_spec_hash <> spec_row.spec_hash
     or reference_ids_value is distinct from spec_row.exact_scope -> 'media_ids'
     or job_row.input ->> 'product_category'
          is distinct from spec_row.product_category
     or job_row.input ->> 'model' is distinct from spec_row.model
     or job_row.input -> 'duration_seconds'
          is distinct from to_jsonb(spec_row.duration_seconds)
     or job_row.input ->> 'format' is distinct from spec_row.format
     or coalesce(job_row.input -> 'audio', 'false'::jsonb)
          is distinct from to_jsonb(spec_row.audio)
     or job_row.input ->> 'platform' is distinct from spec_row.platform
     or btrim(coalesce(job_row.input ->> 'prompt_text', ''))
          is distinct from spec_row.compiled_prompt then
    if job_row.id is not null and (
      job_row.generation_spec_id is distinct from spec_row.spec_id
      or job_row.generation_spec_version is distinct from spec_row.spec_version
      or job_row.generation_spec_hash is distinct from spec_row.spec_hash
    ) then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    raise exception using
      errcode = '55000', message = 'generation_spec_job_binding_invalid';
  end if;

  select signal.* into signal_row
  from content_factory.generation_creative_signals signal
  where signal.organization_id = organization_id_value
    and signal.generation_job_id = job_id_value;
  if signal_row.id is null
     or signal_row.prompt_hash <> content_factory_private.json_hash(
       to_jsonb(spec_row.compiled_prompt)
     )
     or signal_row.creative_angle is distinct from
          spec_row.canonical_learning_context ->> 'creative_angle'
     or signal_row.hook_patterns is distinct from
          spec_row.canonical_learning_context -> 'hook_patterns'
     or signal_row.source <>
          spec_row.canonical_learning_context ->> 'source'
     or signal_row.compiler_version is distinct from
          spec_row.canonical_learning_context ->> 'compiler_version'
     or signal_row.product_category is distinct from
          spec_row.product_category
     or (
       signal_row.source = 'performance_learning'
       and (
         signal_row.applied_policy_hash is distinct from
           spec_row.performance_policy_provenance ->> 'policy_hash'
         or signal_row.creative_brief_draft_id is not null
         or signal_row.scenario_position is not null
       )
     )
     or (
       signal_row.source = 'approved_research'
       and (
         signal_row.applied_policy_hash is not null
         or
         signal_row.creative_brief_draft_id::text is distinct from
           spec_row.research_provenance ->> 'creative_brief_draft_id'
         or signal_row.scenario_position::text is distinct from
           spec_row.research_provenance ->> 'scenario_position'
       )
     )
     or (
       signal_row.source = 'baseline'
       and (
         signal_row.applied_policy_hash is not null
         or signal_row.creative_brief_draft_id is not null
         or signal_row.scenario_position is not null
       )
     ) then
    raise exception using
      errcode = '55000', message = 'generation_spec_learning_binding_invalid';
  end if;
  if spec_row.canonical_repair_context is not null then
    select signal.* into repair_signal_row
    from content_factory.generation_repair_signals signal
    where signal.organization_id = organization_id_value
      and signal.generation_job_id = job_id_value;
    if repair_signal_row.id is null
       or repair_signal_row.source_review_id::text is distinct from
         spec_row.canonical_repair_context ->> 'source_review_id'
       or repair_signal_row.source_generation_job_id::text is distinct from
         spec_row.canonical_repair_context ->> 'source_generation_job_id'
       or repair_signal_row.policy_hash is distinct from
         spec_row.canonical_repair_context ->> 'policy_hash' then
      raise exception using
        errcode = '55000', message = 'generation_spec_repair_binding_invalid';
    end if;
  end if;

  claim_snapshot_value :=
    content_factory_private.generation_spec_live_claim_snapshot(
      organization_id_value, job_id_value, spec_row.spec_id,
      spec_row.spec_version, spec_row.spec_hash
    );
  claim_snapshot_hash_value := claim_snapshot_value ->> 'snapshot_hash';
  if claim_snapshot_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '55000', message = 'generation_spec_job_binding_invalid';
  end if;

  context_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'organization_id', organization_id_value,
    'generation_job_id', job_id_value,
    'spec_id', spec_row.spec_id,
    'spec_version', spec_row.spec_version,
    'spec_hash', spec_row.spec_hash,
    'prompt_hash', spec_row.prompt_hash,
    'final_policy_hash', spec_row.final_policy_hash,
    'outcome_selection_id', spec_row.outcome_selection_id,
    'outcome_selection_hash', spec_row.outcome_selection_hash,
    'claim_snapshot_hash', claim_snapshot_hash_value
  ));
  result_value := jsonb_set(
    result_value, '{job,generation_spec_context}', context_value, true
  );
  insert into content_factory.generation_job_spec_bindings (
    organization_id, generation_job_id, spec_id, spec_version, spec_hash,
    prompt_hash, final_policy_hash, outcome_selection_id,
    outcome_selection_hash, context_hash, start_request_hash,
    start_result, claim_snapshot, claim_snapshot_hash, bound_by
  ) values (
    organization_id_value, job_id_value, spec_row.spec_id,
    spec_row.spec_version, spec_row.spec_hash, spec_row.prompt_hash,
    spec_row.final_policy_hash, spec_row.outcome_selection_id,
    spec_row.outcome_selection_hash, context_hash_value,
    start_request_hash_value, result_value, claim_snapshot_value,
    claim_snapshot_hash_value, actor_id_value
  ) on conflict (organization_id, generation_job_id) do nothing;
  select binding.* into binding_row
  from content_factory.generation_job_spec_bindings binding
  where binding.organization_id = organization_id_value
    and binding.generation_job_id = job_id_value;
  if binding_row.id is null
     or binding_row.spec_id <> spec_row.spec_id
     or binding_row.spec_version <> spec_row.spec_version
     or binding_row.spec_hash <> spec_row.spec_hash
     or binding_row.prompt_hash <> spec_row.prompt_hash
     or binding_row.final_policy_hash <> spec_row.final_policy_hash
     or binding_row.context_hash <> context_hash_value
     or binding_row.start_request_hash <> start_request_hash_value
     or binding_row.claim_snapshot <> claim_snapshot_value
     or binding_row.claim_snapshot_hash <> claim_snapshot_hash_value
     or binding_row.start_result <> result_value then
    raise exception using
      errcode = '23505', message = 'idempotency_key_conflict';
  end if;

  if spec_row.outcome_selection_id is not null then
    select selection.* into selection_row
    from content_factory.research_outcome_generation_selections selection
    where selection.organization_id = organization_id_value
      and selection.id = spec_row.outcome_selection_id;
    insert into content_factory.research_outcome_generation_assignments (
      organization_id, selection_id, generation_job_id, product_id,
      market_category_id, category_binding_id, category_binding_version,
      platform, model, product_category, memory_version_id, memory_version,
      candidate_id, candidate_version, candidate_hash, assignment_action,
      selected_creative_angle, selected_hook_patterns, selection_hash,
      base_policy_hash, final_policy_hash, prompt_hash,
      effectiveness_status, bound_by
    ) values (
      organization_id_value, selection_row.id, job_id_value,
      selection_row.product_id, selection_row.market_category_id,
      selection_row.category_binding_id, selection_row.category_binding_version,
      selection_row.platform, selection_row.model,
      selection_row.product_category, selection_row.memory_version_id,
      selection_row.memory_version, selection_row.candidate_id,
      selection_row.candidate_version, selection_row.candidate_hash,
      selection_row.selection_action, selection_row.selected_creative_angle,
      selection_row.selected_hook_patterns, selection_row.selection_hash,
      selection_row.base_policy_hash, spec_row.final_policy_hash,
      spec_row.prompt_hash, 'unknown', actor_id_value
    ) on conflict (organization_id, generation_job_id) do nothing;
    if not exists (
      select 1
      from content_factory.research_outcome_generation_assignments assignment
      where assignment.organization_id = organization_id_value
        and assignment.generation_job_id = job_id_value
        and assignment.selection_id = selection_row.id
        and assignment.selection_hash = selection_row.selection_hash
        and assignment.final_policy_hash = spec_row.final_policy_hash
        and assignment.prompt_hash = spec_row.prompt_hash
    ) then
      raise exception using
        errcode = '55000', message = 'generation_spec_outcome_binding_invalid';
    end if;
  end if;

  update content_factory.generation_batches batch
  set input = batch.input || jsonb_build_object(
    'generation_spec_context', context_value
  )
  where batch.organization_id = organization_id_value
    and batch.id = batch_id_value;
  return result_value;
end;
$$;

revoke all on function public.creator_prepare_generation_spec(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_control_generation_spec(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_generation_spec_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_generation_spec_effective_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_prepare_generation_spec(jsonb)
  to authenticated;
grant execute on function public.creator_control_generation_spec(jsonb)
  to authenticated;
grant execute on function public.creator_generation_spec_status(jsonb)
  to authenticated;
grant execute on function public.creator_generation_spec_effective_policy(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.bind_generation_spec_to_paid_job()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_generation_spec_provider_start()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.validate_research_outcome_generation_assignment()
  from public, anon, authenticated, service_role;
revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

comment on function public.creator_prepare_generation_spec(jsonb) is
  'Creates a server-owned immutable draft only; never approves, spends, or generates.';
comment on function public.creator_control_generation_spec(jsonb) is
  'Appends patch/approve/reject/revert/recompute control events without provider action.';
comment on function public.creator_generation_spec_effective_policy(jsonb) is
  'Returns only an exact, current, explicitly approved paid-generation handoff.';

notify pgrst, 'reload schema';

commit;
