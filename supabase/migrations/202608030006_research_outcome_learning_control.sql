begin;

-- Outcome learning is an advisory, provider-free control plane.  It does not
-- replace or gate creator_generation_learning_policy yet, and it never writes
-- generation, provider, spend, placement, publication, or metric records.

create unique index if not exists generation_creative_signals_org_id_uq
  on content_factory.generation_creative_signals (organization_id, id);
create unique index if not exists content_review_decisions_org_review_id_uq
  on content_factory.content_review_decisions (organization_id, review_id, id);
create unique index if not exists metric_snapshots_org_placement_id_uq
  on content_factory.metric_snapshots (organization_id, placement_id, id);

create table if not exists content_factory.research_outcome_lineage_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    market_category_id uuid not null,
    category_binding_id uuid not null,
    research_run_id uuid not null,
    research_completion_hash text not null
      check (research_completion_hash ~ '^[0-9a-f]{64}$'),
    creative_brief_draft_id uuid not null,
    draft_content_hash text not null
      check (draft_content_hash ~ '^[0-9a-f]{64}$'),
    scenario_stage text not null default 'scenarios'
      check (scenario_stage = 'scenarios'),
    scenario_artifact_id uuid not null,
    scenario_artifact_hash text not null
      check (scenario_artifact_hash ~ '^[0-9a-f]{64}$'),
    scenario_dependency_hash text not null
      check (scenario_dependency_hash ~ '^[0-9a-f]{64}$'),
    scenario_position smallint not null check (scenario_position between 1 and 3),
    scenario_hash text not null check (scenario_hash ~ '^[0-9a-f]{64}$'),
    generation_job_id uuid not null,
    creative_signal_id uuid not null,
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    media_object_id uuid not null,
    media_sha256 text not null check (media_sha256 ~ '^[0-9a-f]{64}$'),
    review_id uuid not null,
    review_completion_hash text not null
      check (review_completion_hash ~ '^[0-9a-f]{64}$'),
    review_decision_id uuid not null,
    placement_id uuid not null,
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    creative_angle text not null check (creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    metric_snapshot_id uuid not null,
    metric_source text not null check (metric_source in (
      'manual', 'csv', 'official_api'
    )),
    metric_observed_at timestamptz not null,
    placement_published_at timestamptz not null,
    views bigint not null check (views >= 100),
    clicks bigint not null check (clicks between 0 and views),
    orders bigint not null check (orders between 0 and views),
    revenue_minor bigint not null check (revenue_minor >= 0),
    metric_is_correction boolean not null,
    structural_payload jsonb not null check (
      jsonb_typeof(structural_payload) = 'object'
      and structural_payload - array[
        'schema_version', 'creative_angle', 'platform', 'model',
        'scenario_position'
      ]::text[] = '{}'::jsonb
      and structural_payload ->> 'schema_version' =
        'research-outcome-structural-v1'
    ),
    effectiveness_evidence jsonb not null check (
      jsonb_typeof(effectiveness_evidence) = 'object'
      and effectiveness_evidence - array[
        'views', 'clicks', 'orders', 'revenue_minor', 'ctr', 'order_rate',
        'revenue_per_1000_views', 'metric_source', 'metric_observed_at',
        'placement_published_at', 'maturity_hours'
      ]::text[] = '{}'::jsonb
    ),
    guard_evidence jsonb not null check (
      jsonb_typeof(guard_evidence) = 'object'
      and guard_evidence - array[
        'qa_approved', 'media_watched_confirmed', 'review_blockers_count',
        'review_compliance_status', 'review_ruleset_version',
        'first_party_metric', 'metric_is_correction', 'raw_fields_excluded'
      ]::text[] = '{}'::jsonb
      and guard_evidence -> 'qa_approved' = 'true'::jsonb
      and guard_evidence -> 'media_watched_confirmed' = 'true'::jsonb
      and guard_evidence -> 'first_party_metric' = 'true'::jsonb
      and guard_evidence -> 'raw_fields_excluded' = 'true'::jsonb
    ),
    metric_hash text not null check (metric_hash ~ '^[0-9a-f]{64}$'),
    lineage_hash text not null check (lineage_hash ~ '^[0-9a-f]{64}$'),
    captured_by uuid not null,
    captured_at timestamptz not null default now(),
    constraint research_outcome_lineage_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_lineage_org_hash_uq
      unique (organization_id, lineage_hash),
    constraint research_outcome_lineage_org_placement_metric_uq
      unique (organization_id, placement_id, metric_snapshot_id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (
      organization_id, product_id, category_binding_id, market_category_id
    ) references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
    foreign key (organization_id, research_run_id, creative_brief_draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    foreign key (
      organization_id, research_run_id, creative_brief_draft_id,
      scenario_stage, scenario_artifact_id
    ) references content_factory.research_stage_draft_bindings(
      organization_id, run_id, draft_id, stage, artifact_id
    ),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, creative_signal_id)
      references content_factory.generation_creative_signals(organization_id, id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, review_id, review_decision_id)
      references content_factory.content_review_decisions(
        organization_id, review_id, id
      ),
    foreign key (organization_id, placement_id)
      references content_factory.placements(organization_id, id),
    foreign key (organization_id, placement_id, metric_snapshot_id)
      references content_factory.metric_snapshots(
        organization_id, placement_id, id
      ),
    foreign key (organization_id, captured_by)
      references content_factory.memberships(organization_id, profile_id),
    check (metric_observed_at >= placement_published_at + interval '72 hours')
);

create index if not exists research_outcome_lineage_scope_idx
  on content_factory.research_outcome_lineage_snapshots (
    organization_id, market_category_id, platform, model,
    metric_observed_at desc, id desc
  );
create index if not exists research_outcome_lineage_placement_timeline_idx
  on content_factory.research_outcome_lineage_snapshots (
    organization_id, placement_id, metric_observed_at desc, captured_at desc, id desc
  );

create table if not exists content_factory.research_outcome_learning_candidates (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    market_category_id uuid not null,
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    candidate_kind text not null default 'creative_angle_preference'
      check (candidate_kind = 'creative_angle_preference'),
    candidate_version integer not null check (candidate_version between 1 and 100000),
    candidate_payload jsonb not null check (
      jsonb_typeof(candidate_payload) = 'object'
      and candidate_payload - array[
        'schema_version', 'candidate_kind', 'scope',
        'preferred_creative_angle', 'avoid_creative_angle', 'ruleset_version'
      ]::text[] = '{}'::jsonb
      and candidate_payload ->> 'schema_version' =
        'research-outcome-learning-v1'
      and candidate_payload ->> 'candidate_kind' =
        'creative_angle_preference'
    ),
    effectiveness_evidence jsonb not null check (
      jsonb_typeof(effectiveness_evidence) = 'object'
      and effectiveness_evidence - array[
        'eligible_outcome_count', 'eligible_angle_count',
        'minimum_outcomes_per_angle', 'minimum_views_per_outcome',
        'minimum_maturity_hours', 'maximum_outcomes_considered',
        'overlapping_product_count',
        'preferred', 'comparator',
        'absolute_deltas', 'views_are_not_a_rank_signal'
      ]::text[] = '{}'::jsonb
      and effectiveness_evidence -> 'views_are_not_a_rank_signal' = 'true'::jsonb
    ),
    guard_evidence jsonb not null check (
      jsonb_typeof(guard_evidence) = 'object'
      and guard_evidence - array[
        'qa_approved_outcome_count', 'first_party_metric_outcome_count',
        'distinct_product_count', 'market_category_exact',
        'tenant_scope_exact', 'raw_competitor_content_excluded',
        'raw_prompt_caption_url_excluded', 'automatic_activation',
        'advisory_only', 'generation_consumption'
      ]::text[] = '{}'::jsonb
      and guard_evidence -> 'market_category_exact' = 'true'::jsonb
      and guard_evidence -> 'tenant_scope_exact' = 'true'::jsonb
      and guard_evidence -> 'raw_competitor_content_excluded' = 'true'::jsonb
      and guard_evidence -> 'raw_prompt_caption_url_excluded' = 'true'::jsonb
      and guard_evidence -> 'automatic_activation' = 'false'::jsonb
      and guard_evidence -> 'advisory_only' = 'true'::jsonb
      and guard_evidence ->> 'generation_consumption' = 'not_wired'
    ),
    evidence_hash text not null check (evidence_hash ~ '^[0-9a-f]{64}$'),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    constraint research_outcome_candidates_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_candidates_org_hash_uq
      unique (organization_id, candidate_hash),
    constraint research_outcome_candidates_scope_version_uq unique (
      organization_id, market_category_id, platform, model,
      candidate_kind, candidate_version
    ),
    foreign key (organization_id, market_category_id)
      references content_factory.research_market_categories(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists research_outcome_candidates_scope_idx
  on content_factory.research_outcome_learning_candidates (
    organization_id, market_category_id, platform, model,
    candidate_version desc, id desc
  );

create table if not exists content_factory.research_outcome_learning_candidate_evidence (
    organization_id uuid not null,
    candidate_id uuid not null,
    lineage_snapshot_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 10000),
    created_at timestamptz not null default now(),
    primary key (organization_id, candidate_id, lineage_snapshot_id),
    unique (organization_id, candidate_id, ordinal),
    foreign key (organization_id, candidate_id)
      references content_factory.research_outcome_learning_candidates(
        organization_id, id
      ),
    foreign key (organization_id, lineage_snapshot_id)
      references content_factory.research_outcome_lineage_snapshots(
        organization_id, id
      )
);

create index if not exists research_outcome_candidate_evidence_lineage_idx
  on content_factory.research_outcome_learning_candidate_evidence (
    organization_id, lineage_snapshot_id, candidate_id
  );

create table if not exists content_factory.research_outcome_learning_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    candidate_id uuid not null,
    action text not null check (action in (
      'activate', 'reject', 'quarantine', 'deactivate', 'revert'
    )),
    candidate_version integer not null check (candidate_version between 1 and 100000),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    expected_scope_version integer not null
      check (expected_scope_version between 0 and 100000),
    rollback_memory_version_id uuid,
    reason text not null check (length(btrim(reason)) between 3 and 500),
    confirmed_by uuid not null,
    confirmation boolean not null check (confirmation),
    decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    decided_at timestamptz not null default now(),
    constraint research_outcome_decisions_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_decisions_org_hash_uq
      unique (organization_id, decision_hash),
    constraint research_outcome_decisions_org_key_uq
      unique (organization_id, idempotency_key),
    foreign key (organization_id, candidate_id)
      references content_factory.research_outcome_learning_candidates(
        organization_id, id
      ),
    foreign key (organization_id, confirmed_by)
      references content_factory.memberships(organization_id, profile_id),
    check ((action = 'revert') = (rollback_memory_version_id is not null))
);

create table if not exists content_factory.research_outcome_learning_memory_versions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    market_category_id uuid not null,
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    candidate_kind text not null default 'creative_angle_preference'
      check (candidate_kind = 'creative_angle_preference'),
    memory_version integer not null check (memory_version between 1 and 100000),
    previous_memory_version_id uuid,
    state text not null check (state in ('active', 'inactive')),
    action text not null check (action in ('activate', 'deactivate', 'revert')),
    candidate_id uuid,
    rollback_target_memory_version_id uuid,
    decision_id uuid not null,
    activated_by uuid not null,
    created_at timestamptz not null default now(),
    constraint research_outcome_memory_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_memory_scope_version_uq unique (
      organization_id, market_category_id, platform, model,
      candidate_kind, memory_version
    ),
    constraint research_outcome_memory_org_decision_uq
      unique (organization_id, decision_id),
    foreign key (organization_id, market_category_id)
      references content_factory.research_market_categories(organization_id, id),
    foreign key (organization_id, candidate_id)
      references content_factory.research_outcome_learning_candidates(
        organization_id, id
      ),
    foreign key (organization_id, previous_memory_version_id)
      references content_factory.research_outcome_learning_memory_versions(
        organization_id, id
      ),
    foreign key (organization_id, rollback_target_memory_version_id)
      references content_factory.research_outcome_learning_memory_versions(
        organization_id, id
      ),
    foreign key (organization_id, decision_id)
      references content_factory.research_outcome_learning_decisions(
        organization_id, id
      ),
    foreign key (organization_id, activated_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (memory_version = 1 and previous_memory_version_id is null)
      or (memory_version > 1 and previous_memory_version_id is not null)
    ),
    check (
      (state = 'active' and action in ('activate', 'revert') and candidate_id is not null)
      or (state = 'inactive' and action = 'deactivate' and candidate_id is null)
    ),
    check (
      (action = 'activate' and rollback_target_memory_version_id is null)
      or (action in ('deactivate', 'revert')
          and rollback_target_memory_version_id is not null)
    )
);

alter table content_factory.research_outcome_learning_decisions
  add constraint research_outcome_decisions_rollback_memory_fk
  foreign key (organization_id, rollback_memory_version_id)
  references content_factory.research_outcome_learning_memory_versions(
    organization_id, id
  );

create index if not exists research_outcome_memory_scope_idx
  on content_factory.research_outcome_learning_memory_versions (
    organization_id, market_category_id, platform, model,
    memory_version desc, id desc
  );

alter table content_factory.research_outcome_lineage_snapshots enable row level security;
alter table content_factory.research_outcome_learning_candidates enable row level security;
alter table content_factory.research_outcome_learning_candidate_evidence enable row level security;
alter table content_factory.research_outcome_learning_decisions enable row level security;
alter table content_factory.research_outcome_learning_memory_versions enable row level security;

revoke all on content_factory.research_outcome_lineage_snapshots
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_outcome_learning_candidates
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_outcome_learning_candidate_evidence
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_outcome_learning_decisions
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_outcome_learning_memory_versions
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_outcome_learning_mutation()
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

drop trigger if exists research_outcome_lineage_append_only
  on content_factory.research_outcome_lineage_snapshots;
create trigger research_outcome_lineage_append_only
before update or delete on content_factory.research_outcome_lineage_snapshots
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();
drop trigger if exists research_outcome_candidate_append_only
  on content_factory.research_outcome_learning_candidates;
create trigger research_outcome_candidate_append_only
before update or delete on content_factory.research_outcome_learning_candidates
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();
drop trigger if exists research_outcome_candidate_evidence_append_only
  on content_factory.research_outcome_learning_candidate_evidence;
create trigger research_outcome_candidate_evidence_append_only
before update or delete on content_factory.research_outcome_learning_candidate_evidence
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();
drop trigger if exists research_outcome_decision_append_only
  on content_factory.research_outcome_learning_decisions;
create trigger research_outcome_decision_append_only
before update or delete on content_factory.research_outcome_learning_decisions
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();
drop trigger if exists research_outcome_memory_append_only
  on content_factory.research_outcome_learning_memory_versions;
create trigger research_outcome_memory_append_only
before update or delete on content_factory.research_outcome_learning_memory_versions
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();

create or replace function content_factory_private.research_outcome_candidate_document(
  organization_id_value uuid,
  candidate_id_value uuid
)
returns jsonb
language sql
stable
set search_path = ''
as $$
  select jsonb_build_object(
    'candidate_id', candidate.id,
    'candidate_version', candidate.candidate_version,
    'candidate_hash', candidate.candidate_hash,
    'candidate_kind', candidate.candidate_kind,
    'scope', candidate.candidate_payload -> 'scope',
    'candidate_payload', candidate.candidate_payload,
    'effectiveness_evidence', candidate.effectiveness_evidence,
    'guard_evidence', candidate.guard_evidence,
    'status', case
      when current_memory.state = 'active'
       and current_memory.candidate_id = candidate.id then 'active'
      when latest_decision.action = 'reject' then 'rejected'
      when latest_decision.action = 'quarantine' then 'quarantined'
      when latest_decision.action = 'deactivate' then 'deactivated'
      when latest_decision.action in ('activate', 'revert') then 'superseded'
      when candidate.candidate_version < latest_candidate.candidate_version
        then 'superseded'
      else 'pending'
    end,
    'created_at', candidate.created_at,
    'advisory_only', true,
    'generation_consumption', 'not_wired'
  )
  from content_factory.research_outcome_learning_candidates candidate
  left join lateral (
    select decision.action
    from content_factory.research_outcome_learning_decisions decision
    where decision.organization_id = candidate.organization_id
      and decision.candidate_id = candidate.id
    order by decision.decided_at desc, decision.id desc
    limit 1
  ) latest_decision on true
  left join lateral (
    select max(scope_candidate.candidate_version) as candidate_version
    from content_factory.research_outcome_learning_candidates scope_candidate
    where scope_candidate.organization_id = candidate.organization_id
      and scope_candidate.market_category_id = candidate.market_category_id
      and scope_candidate.platform = candidate.platform
      and scope_candidate.model = candidate.model
      and scope_candidate.candidate_kind = candidate.candidate_kind
  ) latest_candidate on true
  left join lateral (
    select memory.state, memory.candidate_id
    from content_factory.research_outcome_learning_memory_versions memory
    where memory.organization_id = candidate.organization_id
      and memory.market_category_id = candidate.market_category_id
      and memory.platform = candidate.platform
      and memory.model = candidate.model
      and memory.candidate_kind = candidate.candidate_kind
    order by memory.memory_version desc, memory.id desc
    limit 1
  ) current_memory on true
  where candidate.organization_id = $1
    and candidate.id = $2
$$;

-- Single source of truth for the exact currently eligible outcome per
-- placement.  Refresh snapshots these rows; activation anti-joins the same
-- rows against captured lineage so a new mature placement or a newer valid
-- metric/correction can never be hidden behind a previously reviewed
-- candidate. Invalid and non-latest metric rows are excluded before the
-- distinct-per-placement selection.
create or replace function
  content_factory_private.research_current_eligible_outcomes(
    organization_id_value uuid,
    market_category_id_value uuid,
    platform_value text,
    model_value text
  )
returns table (
  organization_id uuid,
  product_id uuid,
  market_category_id uuid,
  category_binding_id uuid,
  research_run_id uuid,
  research_completion_hash text,
  creative_brief_draft_id uuid,
  draft_content_hash text,
  scenario_artifact_id uuid,
  scenario_artifact_hash text,
  scenario_dependency_hash text,
  scenario_position smallint,
  scenario_hash text,
  generation_job_id uuid,
  creative_signal_id uuid,
  prompt_hash text,
  media_object_id uuid,
  media_sha256 text,
  review_id uuid,
  review_completion_hash text,
  review_decision_id uuid,
  placement_id uuid,
  platform text,
  model text,
  creative_angle text,
  metric_snapshot_id uuid,
  metric_source text,
  metric_observed_at timestamptz,
  placement_published_at timestamptz,
  views bigint,
  clicks bigint,
  orders bigint,
  revenue_minor bigint,
  metric_is_correction boolean,
  blockers_count integer,
  compliance_status text,
  ruleset_version text
)
language sql
stable
security definer
set search_path = ''
as $$
  select distinct on (placement.id)
    signal.organization_id,
    signal.product_id,
    category_binding.category_id as market_category_id,
    category_binding.id as category_binding_id,
    draft.run_id as research_run_id,
    research_run.completion_hash as research_completion_hash,
    draft.id as creative_brief_draft_id,
    draft.content_hash as draft_content_hash,
    scenario_binding.artifact_id as scenario_artifact_id,
    scenario_artifact.content_hash as scenario_artifact_hash,
    scenario_binding.dependency_hash as scenario_dependency_hash,
    signal.scenario_position,
    content_factory_private.json_hash(
      draft.brief -> 'scenarios' -> (signal.scenario_position - 1)
    ) as scenario_hash,
    job.id as generation_job_id,
    signal.id as creative_signal_id,
    signal.prompt_hash,
    media.id as media_object_id,
    media.sha256 as media_sha256,
    qa.review_id,
    qa.review_completion_hash,
    qa.review_decision_id,
    placement.id as placement_id,
    signal.platform,
    signal.model,
    signal.creative_angle,
    metric.id as metric_snapshot_id,
    metric.source as metric_source,
    metric.observed_at as metric_observed_at,
    placement.published_at as placement_published_at,
    metric.views,
    metric.clicks,
    metric.orders,
    metric.revenue_minor,
    metric.is_correction as metric_is_correction,
    qa.blockers_count,
    qa.compliance_status,
    qa.ruleset_version
  from content_factory.generation_creative_signals signal
  join content_factory.generation_jobs job
    on job.organization_id = signal.organization_id
   and job.id = signal.generation_job_id
   and job.product_id = signal.product_id
   and job.status = 'succeeded'
   and job.output ->> 'output_media_id' is not null
  join content_factory.creative_brief_drafts draft
    on draft.organization_id = signal.organization_id
   and draft.id = signal.creative_brief_draft_id
   and draft.product_id = signal.product_id
   and draft.status = 'approved'
   and draft.approved_at <= job.created_at
   and jsonb_typeof(draft.brief -> 'scenarios') = 'array'
   and jsonb_array_length(draft.brief -> 'scenarios') >= signal.scenario_position
  join content_factory.product_research_runs research_run
    on research_run.organization_id = draft.organization_id
   and research_run.id = draft.run_id
   and research_run.product_id = draft.product_id
   and research_run.status = 'completed'
   and research_run.completion_hash is not null
  join content_factory.research_stage_draft_bindings scenario_binding
    on scenario_binding.organization_id = draft.organization_id
   and scenario_binding.run_id = draft.run_id
   and scenario_binding.draft_id = draft.id
   and scenario_binding.stage = 'scenarios'
  join content_factory.research_stage_artifacts scenario_artifact
    on scenario_artifact.organization_id = scenario_binding.organization_id
   and scenario_artifact.run_id = scenario_binding.run_id
   and scenario_artifact.stage = scenario_binding.stage
   and scenario_artifact.id = scenario_binding.artifact_id
  join content_factory.research_stage_decisions scenario_approval
    on scenario_approval.organization_id = scenario_binding.organization_id
   and scenario_approval.run_id = scenario_binding.run_id
   and scenario_approval.draft_id = scenario_binding.draft_id
   and scenario_approval.stage = scenario_binding.stage
   and scenario_approval.artifact_id = scenario_binding.artifact_id
   and scenario_approval.decision = 'approved'
   and scenario_approval.created_at <= job.created_at
  join lateral (
    select binding.id, binding.category_id
    from content_factory.research_product_market_category_bindings binding
    where binding.organization_id = signal.organization_id
      and binding.product_id = signal.product_id
      and binding.confirmed_at <= job.created_at
    order by binding.binding_version desc, binding.id desc
    limit 1
  ) category_binding
    on category_binding.category_id = market_category_id_value
  join content_factory.media_objects media
    on media.organization_id = job.organization_id
   and media.id::text = job.output ->> 'output_media_id'
   and media.product_id = job.product_id
   and media.status = 'ready'
   and media.metadata ->> 'kind' in ('generated_video', 'generated_image')
  join content_factory.placements placement
    on placement.organization_id = job.organization_id
   and placement.generation_job_id = job.id
   and placement.product_id = job.product_id
   and placement.platform = signal.platform
   and placement.status = 'published'
   and placement.published_at is not null
   and placement.published_at <= now() - interval '72 hours'
   and placement.metadata ->> 'source_media_id' = media.id::text
   and placement.metadata ->> 'media_sha256' = media.sha256
  join lateral (
    select
      review.id as review_id,
      review.completion_hash as review_completion_hash,
      decision.id as review_decision_id,
      coalesce((review.result ->> 'blockers_count')::integer, 0)
        as blockers_count,
      coalesce(review.result ->> 'compliance_status', 'pass')
        as compliance_status,
      review.ruleset_version
    from content_factory.content_review_runs review
    join content_factory.content_review_decisions decision
      on decision.organization_id = review.organization_id
     and decision.review_id = review.id
     and decision.decision = 'approved'
     and decision.media_watched_confirmed
     and decision.review_completion_hash = review.completion_hash
     and decision.media_sha256_snapshot = review.media_sha256_snapshot
    where review.organization_id = media.organization_id
      and review.id::text = placement.metadata ->> 'content_review_id'
      and decision.id::text =
        placement.metadata ->> 'content_review_decision_id'
      and review.media_object_id = media.id
      and review.media_sha256_snapshot = media.sha256
      and review.status = 'completed'
      and review.completion_hash is not null
      and coalesce((review.result ->> 'blockers_count')::integer, 0) = 0
      and coalesce(review.result ->> 'compliance_status', 'pass') <> 'block'
    order by review.finished_at desc, review.id desc
    limit 1
  ) qa on true
  join lateral (
    select metric_row.*
    from content_factory.metric_snapshots metric_row
    where metric_row.organization_id = placement.organization_id
      and metric_row.placement_id = placement.id
      and metric_row.observed_at >= placement.published_at + interval '72 hours'
      and metric_row.observed_at <= now()
      and metric_row.views >= 100
      and metric_row.clicks <= metric_row.views
      and metric_row.orders <= metric_row.views
    order by metric_row.observed_at desc, metric_row.created_at desc,
             metric_row.id desc
    limit 1
  ) metric on true
  where signal.organization_id = organization_id_value
    and signal.source = 'approved_research'
    and signal.creative_brief_draft_id is not null
    and signal.scenario_position is not null
    and signal.platform = platform_value
    and signal.model = model_value
  order by placement.id, metric.observed_at desc, metric.created_at desc,
           metric.id desc
$$;

create or replace function public.creator_refresh_research_outcome_learning(
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
  organization_id uuid;
  market_category_id_value uuid;
  platform_value text;
  model_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  captured_count integer := 0;
  eligible_outcome_count integer := 0;
  eligible_angle_count integer := 0;
  distinct_product_count integer := 0;
  preferred_angle_value text;
  preferred_count integer := 0;
  preferred_product_count integer := 0;
  preferred_views bigint := 0;
  preferred_clicks bigint := 0;
  preferred_orders bigint := 0;
  preferred_revenue bigint := 0;
  preferred_ctr numeric := 0;
  preferred_order_rate numeric := 0;
  preferred_score numeric := 0;
  comparator_angle_value text;
  comparator_count integer := 0;
  comparator_product_count integer := 0;
  comparator_views bigint := 0;
  comparator_clicks bigint := 0;
  comparator_orders bigint := 0;
  comparator_revenue bigint := 0;
  comparator_ctr numeric := 0;
  comparator_order_rate numeric := 0;
  comparator_score numeric := 0;
  overlapping_product_count integer := 0;
  qualifies boolean := false;
  evidence_set jsonb := '[]'::jsonb;
  evidence_hash_value text;
  candidate_payload_value jsonb;
  effectiveness_value jsonb;
  guard_value jsonb;
  candidate_hash_value text;
  candidate_version_value integer;
  candidate_id_value uuid;
  candidate_created boolean := false;
  candidate_document jsonb;
  guidance_status text;
  guidance_next_step text;
  guidance_reasons jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'market_category_id', 'platform', 'model',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_outcome_refresh_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  market_category_id_value := content_factory_private.require_uuid(
    p_payload, 'market_category_id'
  );
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  model_value := lower(content_factory_private.require_text(
    p_payload, 'model', 2, 80
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) or model_value not in (
    'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
  ) then
    raise exception using
      errcode = '22023', message = 'research_outcome_scope_invalid';
  end if;
  perform content_factory_private.membership_role(
    organization_id, false, array['owner', 'admin', 'producer']
  );
  if not exists (
    select 1
    from content_factory.research_market_categories category
    where category.organization_id = organization_id
      and category.id = market_category_id_value
  ) then
    raise exception using
      errcode = '22023', message = 'research_market_category_not_found';
  end if;

  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_refresh_research_outcome_learning',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'research-outcome-learning:' || market_category_id_value::text || ':' ||
      platform_value || ':' || model_value
    )
  );

  with eligible as (
    select *
    from content_factory_private.research_current_eligible_outcomes(
      organization_id,
      market_category_id_value,
      platform_value,
      model_value
    )
  ), inserted as (
    insert into content_factory.research_outcome_lineage_snapshots (
      organization_id, product_id, market_category_id, category_binding_id,
      research_run_id, research_completion_hash, creative_brief_draft_id,
      draft_content_hash, scenario_artifact_id, scenario_artifact_hash,
      scenario_dependency_hash, scenario_position, scenario_hash,
      generation_job_id, creative_signal_id, prompt_hash, media_object_id,
      media_sha256, review_id, review_completion_hash, review_decision_id,
      placement_id, platform, model, creative_angle, metric_snapshot_id,
      metric_source, metric_observed_at, placement_published_at, views,
      clicks, orders, revenue_minor, metric_is_correction,
      structural_payload, effectiveness_evidence, guard_evidence,
      metric_hash, lineage_hash, captured_by
    )
    select
      eligible.organization_id,
      eligible.product_id,
      eligible.market_category_id,
      eligible.category_binding_id,
      eligible.research_run_id,
      eligible.research_completion_hash,
      eligible.creative_brief_draft_id,
      eligible.draft_content_hash,
      eligible.scenario_artifact_id,
      eligible.scenario_artifact_hash,
      eligible.scenario_dependency_hash,
      eligible.scenario_position,
      eligible.scenario_hash,
      eligible.generation_job_id,
      eligible.creative_signal_id,
      eligible.prompt_hash,
      eligible.media_object_id,
      eligible.media_sha256,
      eligible.review_id,
      eligible.review_completion_hash,
      eligible.review_decision_id,
      eligible.placement_id,
      eligible.platform,
      eligible.model,
      eligible.creative_angle,
      eligible.metric_snapshot_id,
      eligible.metric_source,
      eligible.metric_observed_at,
      eligible.placement_published_at,
      eligible.views,
      eligible.clicks,
      eligible.orders,
      eligible.revenue_minor,
      eligible.metric_is_correction,
      jsonb_build_object(
        'schema_version', 'research-outcome-structural-v1',
        'creative_angle', eligible.creative_angle,
        'platform', eligible.platform,
        'model', eligible.model,
        'scenario_position', eligible.scenario_position
      ),
      jsonb_build_object(
        'views', eligible.views,
        'clicks', eligible.clicks,
        'orders', eligible.orders,
        'revenue_minor', eligible.revenue_minor,
        'ctr', round(eligible.clicks::numeric / eligible.views::numeric, 8),
        'order_rate', round(eligible.orders::numeric / eligible.views::numeric, 8),
        'revenue_per_1000_views',
          round(eligible.revenue_minor::numeric * 1000 / eligible.views::numeric, 4),
        'metric_source', eligible.metric_source,
        'metric_observed_at', eligible.metric_observed_at,
        'placement_published_at', eligible.placement_published_at,
        'maturity_hours', floor(extract(epoch from (
          eligible.metric_observed_at - eligible.placement_published_at
        )) / 3600)::integer
      ),
      jsonb_build_object(
        'qa_approved', true,
        'media_watched_confirmed', true,
        'review_blockers_count', eligible.blockers_count,
        'review_compliance_status', eligible.compliance_status,
        'review_ruleset_version', eligible.ruleset_version,
        'first_party_metric', true,
        'metric_is_correction', eligible.metric_is_correction,
        'raw_fields_excluded', true
      ),
      content_factory_private.json_hash(jsonb_build_object(
        'metric_snapshot_id', eligible.metric_snapshot_id,
        'request_hash', (
          select metric.request_hash
          from content_factory.metric_snapshots metric
          where metric.id = eligible.metric_snapshot_id
        ),
        'observed_at', eligible.metric_observed_at,
        'views', eligible.views,
        'clicks', eligible.clicks,
        'orders', eligible.orders,
        'revenue_minor', eligible.revenue_minor,
        'is_correction', eligible.metric_is_correction
      )),
      content_factory_private.json_hash(jsonb_build_object(
        'category_binding_id', eligible.category_binding_id,
        'research_run_id', eligible.research_run_id,
        'draft_id', eligible.creative_brief_draft_id,
        'draft_content_hash', eligible.draft_content_hash,
        'scenario_artifact_id', eligible.scenario_artifact_id,
        'scenario_artifact_hash', eligible.scenario_artifact_hash,
        'scenario_position', eligible.scenario_position,
        'scenario_hash', eligible.scenario_hash,
        'generation_job_id', eligible.generation_job_id,
        'creative_signal_id', eligible.creative_signal_id,
        'prompt_hash', eligible.prompt_hash,
        'media_object_id', eligible.media_object_id,
        'media_sha256', eligible.media_sha256,
        'review_id', eligible.review_id,
        'review_completion_hash', eligible.review_completion_hash,
        'review_decision_id', eligible.review_decision_id,
        'placement_id', eligible.placement_id,
        'metric_snapshot_id', eligible.metric_snapshot_id
      )),
      user_id
    from eligible
    on conflict (organization_id, placement_id, metric_snapshot_id) do nothing
    returning id
  )
  select count(*)::integer into captured_count from inserted;

  with latest as (
    select lineage.*,
      row_number() over (
        partition by lineage.organization_id, lineage.placement_id
        order by lineage.metric_observed_at desc, lineage.captured_at desc,
                 lineage.id desc
      ) as placement_rank
    from content_factory.research_outcome_lineage_snapshots lineage
    where lineage.organization_id = organization_id
      and lineage.market_category_id = market_category_id_value
      and lineage.platform = platform_value
      and lineage.model = model_value
  ), current_outcomes as (
    select *
    from latest
    where placement_rank = 1
    order by metric_observed_at desc, captured_at desc, id desc
    limit 10000
  ), angle_stats as (
    select
      creative_angle,
      count(*)::integer as outcome_count,
      count(distinct product_id)::integer as product_count,
      sum(views)::bigint as total_views,
      sum(clicks)::bigint as total_clicks,
      sum(orders)::bigint as total_orders,
      sum(revenue_minor)::bigint as total_revenue,
      avg(clicks::numeric / views::numeric) as mean_ctr,
      avg(orders::numeric / views::numeric) as mean_order_rate
    from current_outcomes
    group by creative_angle
    having count(*) >= 3
       and count(distinct product_id) >= 2
  ), ranked as (
    select angle_stats.*,
      (
        percent_rank() over (order by mean_ctr) +
        percent_rank() over (order by mean_order_rate)
      ) / 2.0 as relative_score
    from angle_stats
  ), ordered as (
    select ranked.*,
      row_number() over (
        order by relative_score desc, mean_order_rate desc,
                 mean_ctr desc, creative_angle
      ) as preference_rank
    from ranked
  ), summary as (
    select
      (
        select count(*)::integer
        from current_outcomes outcome
        join angle_stats using (creative_angle)
      ) as outcome_count,
      (select count(*)::integer from angle_stats) as angle_count,
      (
        select count(distinct outcome.product_id)::integer
        from current_outcomes outcome
        join angle_stats using (creative_angle)
      ) as product_count,
      max(creative_angle) filter (where preference_rank = 1) as preferred_angle,
      max(outcome_count) filter (where preference_rank = 1) as preferred_count,
      max(product_count) filter (where preference_rank = 1)
        as preferred_product_count,
      max(total_views) filter (where preference_rank = 1) as preferred_views,
      max(total_clicks) filter (where preference_rank = 1) as preferred_clicks,
      max(total_orders) filter (where preference_rank = 1) as preferred_orders,
      max(total_revenue) filter (where preference_rank = 1) as preferred_revenue,
      max(mean_ctr) filter (where preference_rank = 1) as preferred_ctr,
      max(mean_order_rate) filter (where preference_rank = 1)
        as preferred_order_rate,
      max(relative_score) filter (where preference_rank = 1) as preferred_score,
      max(creative_angle) filter (where preference_rank = 2) as comparator_angle,
      max(outcome_count) filter (where preference_rank = 2) as comparator_count,
      max(product_count) filter (where preference_rank = 2)
        as comparator_product_count,
      max(total_views) filter (where preference_rank = 2) as comparator_views,
      max(total_clicks) filter (where preference_rank = 2) as comparator_clicks,
      max(total_orders) filter (where preference_rank = 2) as comparator_orders,
      max(total_revenue) filter (where preference_rank = 2) as comparator_revenue,
      max(mean_ctr) filter (where preference_rank = 2) as comparator_ctr,
      max(mean_order_rate) filter (where preference_rank = 2)
        as comparator_order_rate,
      max(relative_score) filter (where preference_rank = 2) as comparator_score
    from ordered
  )
  select
    coalesce(outcome_count, 0), coalesce(angle_count, 0),
    coalesce(product_count, 0), preferred_angle,
    coalesce(preferred_count, 0), coalesce(preferred_product_count, 0),
    coalesce(preferred_views, 0),
    coalesce(preferred_clicks, 0), coalesce(preferred_orders, 0),
    coalesce(preferred_revenue, 0), coalesce(preferred_ctr, 0),
    coalesce(preferred_order_rate, 0), coalesce(preferred_score, 0),
    comparator_angle, coalesce(comparator_count, 0),
    coalesce(comparator_product_count, 0),
    coalesce(comparator_views, 0), coalesce(comparator_clicks, 0),
    coalesce(comparator_orders, 0), coalesce(comparator_revenue, 0),
    coalesce(comparator_ctr, 0), coalesce(comparator_order_rate, 0),
    coalesce(comparator_score, 0)
  into
    eligible_outcome_count, eligible_angle_count, distinct_product_count,
    preferred_angle_value, preferred_count, preferred_product_count,
    preferred_views,
    preferred_clicks, preferred_orders, preferred_revenue, preferred_ctr,
    preferred_order_rate, preferred_score, comparator_angle_value,
    comparator_count, comparator_product_count, comparator_views,
    comparator_clicks, comparator_orders,
    comparator_revenue, comparator_ctr, comparator_order_rate, comparator_score
  from summary;

  if preferred_angle_value is not null
     and comparator_angle_value is not null then
    with latest as (
      select lineage.*,
        row_number() over (
          partition by lineage.organization_id, lineage.placement_id
          order by lineage.metric_observed_at desc, lineage.captured_at desc,
                   lineage.id desc
        ) as placement_rank
      from content_factory.research_outcome_lineage_snapshots lineage
      where lineage.organization_id = organization_id
        and lineage.market_category_id = market_category_id_value
        and lineage.platform = platform_value
        and lineage.model = model_value
    ), current_outcomes as (
      select *
      from latest
      where placement_rank = 1
      order by metric_observed_at desc, captured_at desc, id desc
      limit 10000
    )
    select count(*)::integer into overlapping_product_count
    from (
      select outcome.product_id
      from current_outcomes outcome
      where outcome.creative_angle in (
        preferred_angle_value, comparator_angle_value
      )
      group by outcome.product_id
      having count(distinct outcome.creative_angle) = 2
    ) overlap;
  end if;

  qualifies :=
    eligible_outcome_count >= 6
    and eligible_angle_count >= 2
    and distinct_product_count >= 2
    and preferred_product_count >= 2
    and comparator_product_count >= 2
    and overlapping_product_count >= 2
    and preferred_angle_value is not null
    and comparator_angle_value is not null
    and preferred_score >= 0.75
    and preferred_score - comparator_score >= 0.25
    and preferred_clicks + preferred_orders > 0
    and (
      preferred_ctr - comparator_ctr >= 0.001
      or preferred_order_rate - comparator_order_rate >= 0.0005
    );

  if qualifies then
    with latest as (
      select lineage.*,
        row_number() over (
          partition by lineage.organization_id, lineage.placement_id
          order by lineage.metric_observed_at desc, lineage.captured_at desc,
                   lineage.id desc
        ) as placement_rank
      from content_factory.research_outcome_lineage_snapshots lineage
      where lineage.organization_id = organization_id
        and lineage.market_category_id = market_category_id_value
        and lineage.platform = platform_value
        and lineage.model = model_value
    ), current_outcomes as (
      select *
      from latest
      where placement_rank = 1
      order by metric_observed_at desc, captured_at desc, id desc
      limit 10000
    )
    select coalesce(jsonb_agg(jsonb_build_object(
      'lineage_snapshot_id', latest.id,
      'metric_hash', latest.metric_hash
    ) order by latest.id), '[]'::jsonb)
    into evidence_set
    from current_outcomes latest;

    evidence_hash_value := content_factory_private.json_hash(evidence_set);
    candidate_payload_value := jsonb_build_object(
      'schema_version', 'research-outcome-learning-v1',
      'candidate_kind', 'creative_angle_preference',
      'scope', jsonb_build_object(
        'market_category_id', market_category_id_value,
        'platform', platform_value,
        'model', model_value
      ),
      'preferred_creative_angle', preferred_angle_value,
      'avoid_creative_angle', null,
      'ruleset_version', 'research-outcome-effectiveness-v1'
    );
    effectiveness_value := jsonb_build_object(
      'eligible_outcome_count', eligible_outcome_count,
      'eligible_angle_count', eligible_angle_count,
      'minimum_outcomes_per_angle', 3,
      'minimum_views_per_outcome', 100,
      'minimum_maturity_hours', 72,
      'maximum_outcomes_considered', 10000,
      'overlapping_product_count', overlapping_product_count,
      'preferred', jsonb_build_object(
        'creative_angle', preferred_angle_value,
        'outcome_count', preferred_count,
        'product_count', preferred_product_count,
        'total_views', preferred_views,
        'total_clicks', preferred_clicks,
        'total_orders', preferred_orders,
        'total_revenue_minor', preferred_revenue,
        'mean_ctr', round(preferred_ctr, 8),
        'mean_order_rate', round(preferred_order_rate, 8),
        'relative_score', round(preferred_score, 6)
      ),
      'comparator', jsonb_build_object(
        'creative_angle', comparator_angle_value,
        'outcome_count', comparator_count,
        'product_count', comparator_product_count,
        'total_views', comparator_views,
        'total_clicks', comparator_clicks,
        'total_orders', comparator_orders,
        'total_revenue_minor', comparator_revenue,
        'mean_ctr', round(comparator_ctr, 8),
        'mean_order_rate', round(comparator_order_rate, 8),
        'relative_score', round(comparator_score, 6)
      ),
      'absolute_deltas', jsonb_build_object(
        'mean_ctr', round(preferred_ctr - comparator_ctr, 8),
        'mean_order_rate',
          round(preferred_order_rate - comparator_order_rate, 8)
      ),
      'views_are_not_a_rank_signal', true
    );
    guard_value := jsonb_build_object(
      'qa_approved_outcome_count', eligible_outcome_count,
      'first_party_metric_outcome_count', eligible_outcome_count,
      'distinct_product_count', distinct_product_count,
      'market_category_exact', true,
      'tenant_scope_exact', true,
      'raw_competitor_content_excluded', true,
      'raw_prompt_caption_url_excluded', true,
      'automatic_activation', false,
      'advisory_only', true,
      'generation_consumption', 'not_wired'
    );
    candidate_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'candidate_payload', candidate_payload_value,
        'effectiveness_evidence', effectiveness_value,
        'guard_evidence', guard_value,
        'evidence_hash', evidence_hash_value
      )
    );

    select candidate.id into candidate_id_value
    from content_factory.research_outcome_learning_candidates candidate
    where candidate.organization_id = organization_id
      and candidate.candidate_hash = candidate_hash_value;
    if candidate_id_value is null then
      select coalesce(max(candidate.candidate_version), 0) + 1
        into candidate_version_value
      from content_factory.research_outcome_learning_candidates candidate
      where candidate.organization_id = organization_id
        and candidate.market_category_id = market_category_id_value
        and candidate.platform = platform_value
        and candidate.model = model_value
        and candidate.candidate_kind = 'creative_angle_preference';

      insert into content_factory.research_outcome_learning_candidates (
        organization_id, market_category_id, platform, model,
        candidate_kind, candidate_version, candidate_payload,
        effectiveness_evidence, guard_evidence, evidence_hash,
        candidate_hash, created_by
      ) values (
        organization_id, market_category_id_value, platform_value, model_value,
        'creative_angle_preference', candidate_version_value,
        candidate_payload_value, effectiveness_value, guard_value,
        evidence_hash_value, candidate_hash_value, user_id
      ) returning id into candidate_id_value;

      insert into content_factory.research_outcome_learning_candidate_evidence (
        organization_id, candidate_id, lineage_snapshot_id, ordinal
      )
      select
        organization_id,
        candidate_id_value,
        (item.value ->> 'lineage_snapshot_id')::uuid,
        item.ordinality::integer
      from jsonb_array_elements(evidence_set) with ordinality
        as item(value, ordinality);
      candidate_created := true;
    end if;
    candidate_document :=
      content_factory_private.research_outcome_candidate_document(
        organization_id, candidate_id_value
      );
  end if;

  if eligible_outcome_count = 0 then
    guidance_status := 'no_eligible_outcomes';
    guidance_next_step := 'collect_qa_approved_mature_first_party_metrics';
    guidance_reasons := jsonb_build_array('no_exact_eligible_lineage');
  elsif not qualifies then
    guidance_status := 'insufficient_comparable_evidence';
    guidance_next_step := 'gather_more_comparable_outcomes';
    guidance_reasons := case
      when eligible_angle_count < 2 then
        jsonb_build_array('two_structural_angles_required')
      when distinct_product_count < 2 then
        jsonb_build_array('two_independent_products_required')
      when preferred_product_count < 2
        or comparator_product_count < 2
        or overlapping_product_count < 2 then
        jsonb_build_array('same_products_control_required')
      when preferred_clicks + preferred_orders = 0 then
        jsonb_build_array('views_only_evidence_rejected')
      else jsonb_build_array('effectiveness_separation_not_stable')
    end;
  elsif candidate_document ->> 'status' = 'pending' then
    guidance_status := 'candidate_requires_decision';
    guidance_next_step := 'review_activate_reject_or_quarantine';
    guidance_reasons := jsonb_build_array(
      'bounded_effectiveness_signal', 'explicit_activation_required'
    );
  else
    guidance_status := case candidate_document ->> 'status'
      when 'active' then 'advisory_memory_active'
      when 'deactivated' then 'advisory_memory_inactive'
      else 'candidate_already_decided'
    end;
    guidance_next_step := case candidate_document ->> 'status'
      when 'active' then 'monitor_effectiveness_and_keep_rollback_ready'
      when 'deactivated' then 'wait_for_new_candidate'
      else 'wait_for_new_evidence_version'
    end;
    guidance_reasons := jsonb_build_array(
      'same_candidate_hash_already_decided',
      candidate_document ->> 'status'
    );
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-learning-control-v1',
    'scope', jsonb_build_object(
      'market_category_id', market_category_id_value,
      'platform', platform_value,
      'model', model_value
    ),
    'captured_outcome_count', captured_count,
    'eligible_outcome_count', eligible_outcome_count,
    'candidate_created', candidate_created,
    'candidate', candidate_document,
    'guidance', jsonb_build_object(
      'status', guidance_status,
      'recommended_next_step', guidance_next_step,
      'reason_codes', guidance_reasons,
      'automatic_activation', false,
      'advisory_only', true,
      'generation_consumption', 'not_wired',
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_refresh_research_outcome_learning',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_decide_research_outcome_learning(
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
  organization_id uuid;
  candidate_id_value uuid;
  action_value text;
  candidate_version_value integer;
  candidate_hash_value text;
  expected_scope_version_value integer;
  rollback_memory_version_id_value uuid;
  reason_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  candidate_row content_factory.research_outcome_learning_candidates%rowtype;
  latest_candidate_version integer;
  current_memory content_factory.research_outcome_learning_memory_versions%rowtype;
  rollback_memory content_factory.research_outcome_learning_memory_versions%rowtype;
  existing_action text;
  decision_id_value uuid;
  memory_row content_factory.research_outcome_learning_memory_versions%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'candidate_id', 'action', 'candidate_version',
    'candidate_hash', 'expected_scope_version', 'rollback_memory_version_id',
    'reason', 'confirmation', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_outcome_decision_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  candidate_id_value := content_factory_private.require_uuid(
    p_payload, 'candidate_id'
  );
  action_value := content_factory_private.require_text(
    p_payload, 'action', 6, 20
  );
  if action_value not in (
    'activate', 'reject', 'quarantine', 'deactivate', 'revert'
  ) then
    raise exception using
      errcode = '22023', message = 'research_outcome_decision_action_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' <> 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_outcome_decision_confirmation_required';
  end if;
  begin
    candidate_version_value := (p_payload ->> 'candidate_version')::integer;
    expected_scope_version_value :=
      (p_payload ->> 'expected_scope_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'research_outcome_decision_version_invalid';
  end;
  if candidate_version_value is null
     or expected_scope_version_value is null
     or candidate_version_value not between 1 and 100000
     or expected_scope_version_value not between 0 and 100000 then
    raise exception using
      errcode = '22023', message = 'research_outcome_decision_version_invalid';
  end if;
  candidate_hash_value := content_factory_private.require_text(
    p_payload, 'candidate_hash', 64, 64
  );
  if candidate_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'candidate_hash_invalid';
  end if;
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if action_value = 'revert' then
    rollback_memory_version_id_value := content_factory_private.require_uuid(
      p_payload, 'rollback_memory_version_id'
    );
  elsif p_payload ? 'rollback_memory_version_id' then
    raise exception using
      errcode = '22023', message = 'research_outcome_rollback_target_unexpected';
  end if;

  perform content_factory_private.membership_role(
    organization_id, false, array['owner', 'admin', 'producer']
  );
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_research_outcome_learning',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  select candidate.* into candidate_row
  from content_factory.research_outcome_learning_candidates candidate
  where candidate.organization_id = organization_id
    and candidate.id = candidate_id_value;
  if candidate_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_outcome_candidate_not_found';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'research-outcome-learning:' || candidate_row.market_category_id::text ||
      ':' || candidate_row.platform || ':' || candidate_row.model
    )
  );
  select candidate.* into candidate_row
  from content_factory.research_outcome_learning_candidates candidate
  where candidate.organization_id = organization_id
    and candidate.id = candidate_id_value
  for share;
  if candidate_row.candidate_version <> candidate_version_value
     or candidate_row.candidate_hash <> candidate_hash_value then
    raise exception using
      errcode = '55000', message = 'research_outcome_candidate_stale';
  end if;

  select coalesce(max(candidate.candidate_version), 0)
    into latest_candidate_version
  from content_factory.research_outcome_learning_candidates candidate
  where candidate.organization_id = organization_id
    and candidate.market_category_id = candidate_row.market_category_id
    and candidate.platform = candidate_row.platform
    and candidate.model = candidate_row.model
    and candidate.candidate_kind = candidate_row.candidate_kind;
  if action_value = 'activate'
     and latest_candidate_version <> candidate_row.candidate_version then
    raise exception using
      errcode = '55000', message = 'research_outcome_candidate_superseded';
  end if;
  -- The candidate/lineage evidence guard below is intentionally bounded to
  -- the latest 10k captured outcomes.  This separate live-source anti-join
  -- closes the window before refresh: the same exact selector used by refresh
  -- must already have a lineage row in this precise tenant/category/scope.
  if action_value = 'activate' and exists (
    select 1
    from content_factory_private.research_current_eligible_outcomes(
      organization_id,
      candidate_row.market_category_id,
      candidate_row.platform,
      candidate_row.model
    ) current_source
    where not exists (
      select 1
      from content_factory.research_outcome_lineage_snapshots lineage
      where lineage.organization_id = current_source.organization_id
        and lineage.market_category_id = current_source.market_category_id
        and lineage.platform = current_source.platform
        and lineage.model = current_source.model
        and lineage.product_id = current_source.product_id
        and lineage.category_binding_id = current_source.category_binding_id
        and lineage.generation_job_id = current_source.generation_job_id
        and lineage.creative_signal_id = current_source.creative_signal_id
        and lineage.placement_id = current_source.placement_id
        and lineage.metric_snapshot_id = current_source.metric_snapshot_id
    )
  ) then
    raise exception using
      errcode = '55000', message = 'research_outcome_refresh_required';
  end if;
  if action_value = 'activate' and exists (
    with latest as (
      select lineage.id,
        row_number() over (
          partition by lineage.organization_id, lineage.placement_id
          order by lineage.metric_observed_at desc, lineage.captured_at desc,
                   lineage.id desc
        ) as placement_rank,
        lineage.metric_observed_at,
        lineage.captured_at
      from content_factory.research_outcome_lineage_snapshots lineage
      where lineage.organization_id = organization_id
        and lineage.market_category_id = candidate_row.market_category_id
        and lineage.platform = candidate_row.platform
        and lineage.model = candidate_row.model
    ), current_outcomes as (
      select latest.id
      from latest
      where latest.placement_rank = 1
      order by latest.metric_observed_at desc, latest.captured_at desc,
               latest.id desc
      limit 10000
    ), candidate_evidence as (
      select evidence.lineage_snapshot_id as id
      from content_factory.research_outcome_learning_candidate_evidence evidence
      where evidence.organization_id = organization_id
        and evidence.candidate_id = candidate_row.id
    ), evidence_difference as (
      (select current_outcomes.id from current_outcomes
       except
       select candidate_evidence.id from candidate_evidence)
      union all
      (select candidate_evidence.id from candidate_evidence
       except
       select current_outcomes.id from current_outcomes)
    )
    select 1 from evidence_difference
  ) then
    raise exception using
      errcode = '55000', message = 'research_outcome_candidate_stale';
  end if;

  select memory.* into current_memory
  from content_factory.research_outcome_learning_memory_versions memory
  where memory.organization_id = organization_id
    and memory.market_category_id = candidate_row.market_category_id
    and memory.platform = candidate_row.platform
    and memory.model = candidate_row.model
    and memory.candidate_kind = candidate_row.candidate_kind
  order by memory.memory_version desc, memory.id desc
  limit 1
  for share;
  if coalesce(current_memory.memory_version, 0)
       <> expected_scope_version_value then
    raise exception using
      errcode = '55000', message = 'research_outcome_scope_version_stale';
  end if;

  select decision.action into existing_action
  from content_factory.research_outcome_learning_decisions decision
  where decision.organization_id = organization_id
    and decision.candidate_id = candidate_row.id
  order by decision.decided_at desc, decision.id desc
  limit 1;

  if action_value in ('activate', 'reject', 'quarantine')
     and existing_action is not null then
    raise exception using
      errcode = '55000', message = 'research_outcome_candidate_already_decided';
  end if;
  if action_value = 'deactivate' and (
    current_memory.id is null
    or current_memory.state <> 'active'
    or current_memory.candidate_id <> candidate_row.id
  ) then
    raise exception using
      errcode = '55000', message = 'research_outcome_active_memory_mismatch';
  end if;
  if action_value = 'revert' then
    select memory.* into rollback_memory
    from content_factory.research_outcome_learning_memory_versions memory
    where memory.organization_id = organization_id
      and memory.id = rollback_memory_version_id_value
      and memory.market_category_id = candidate_row.market_category_id
      and memory.platform = candidate_row.platform
      and memory.model = candidate_row.model
      and memory.candidate_kind = candidate_row.candidate_kind
      and memory.state = 'active'
      and memory.candidate_id = candidate_row.id;
    if rollback_memory.id is null
       or current_memory.id is null
       or rollback_memory.memory_version >= current_memory.memory_version
       or (
         current_memory.state = 'active'
         and current_memory.candidate_id = rollback_memory.candidate_id
       ) then
      raise exception using
        errcode = '55000', message = 'research_outcome_rollback_target_invalid';
    end if;
  end if;

  insert into content_factory.research_outcome_learning_decisions (
    organization_id, candidate_id, action, candidate_version,
    candidate_hash, expected_scope_version, rollback_memory_version_id,
    reason, confirmed_by, confirmation, decision_hash, idempotency_key
  ) values (
    organization_id,
    candidate_row.id,
    action_value,
    candidate_row.candidate_version,
    candidate_row.candidate_hash,
    expected_scope_version_value,
    rollback_memory_version_id_value,
    reason_value,
    user_id,
    true,
    content_factory_private.json_hash(jsonb_build_object(
      'candidate_id', candidate_row.id,
      'action', action_value,
      'candidate_version', candidate_row.candidate_version,
      'candidate_hash', candidate_row.candidate_hash,
      'expected_scope_version', expected_scope_version_value,
      'rollback_memory_version_id', rollback_memory_version_id_value,
      'reason', reason_value,
      'confirmed_by', user_id
    )),
    idempotency_key_value
  ) returning id into decision_id_value;

  if action_value in ('activate', 'deactivate', 'revert') then
    insert into content_factory.research_outcome_learning_memory_versions (
      organization_id, market_category_id, platform, model, candidate_kind,
      memory_version, previous_memory_version_id, state, action,
      candidate_id, rollback_target_memory_version_id, decision_id,
      activated_by
    ) values (
      organization_id,
      candidate_row.market_category_id,
      candidate_row.platform,
      candidate_row.model,
      candidate_row.candidate_kind,
      coalesce(current_memory.memory_version, 0) + 1,
      current_memory.id,
      case when action_value = 'deactivate' then 'inactive' else 'active' end,
      action_value,
      case when action_value = 'deactivate' then null else candidate_row.id end,
      case
        when action_value = 'deactivate' then current_memory.id
        when action_value = 'revert' then rollback_memory.id
        else null
      end,
      decision_id_value,
      user_id
    ) returning * into memory_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-learning-control-v1',
    'action', action_value,
    'decision', jsonb_build_object(
      'decision_id', decision_id_value,
      'candidate_id', candidate_row.id,
      'candidate_version', candidate_row.candidate_version,
      'candidate_hash', candidate_row.candidate_hash,
      'expected_scope_version', expected_scope_version_value,
      'rollback_memory_version_id', rollback_memory_version_id_value,
      'confirmed_by', user_id
    ),
    'memory', case when memory_row.id is null then null else jsonb_build_object(
      'memory_version_id', memory_row.id,
      'memory_version', memory_row.memory_version,
      'state', memory_row.state,
      'candidate_id', memory_row.candidate_id,
      'previous_memory_version_id', memory_row.previous_memory_version_id,
      'rollback_target_memory_version_id',
        memory_row.rollback_target_memory_version_id,
      'advisory_only', true,
      'generation_consumption', 'not_wired'
    ) end,
    'guidance', jsonb_build_object(
      'status', case action_value
        when 'activate' then 'advisory_memory_active'
        when 'reject' then 'candidate_rejected'
        when 'quarantine' then 'candidate_quarantined'
        when 'deactivate' then 'advisory_memory_inactive'
        else 'prior_advisory_memory_restored'
      end,
      'recommended_next_step', case action_value
        when 'activate' then 'monitor_effectiveness_and_keep_rollback_ready'
        when 'reject' then 'review_next_pending_candidate'
        when 'quarantine' then 'collect_additional_evidence_before_reconsideration'
        when 'deactivate' then 'review_rollback_target_or_wait_for_new_candidate'
        when 'revert' then 'monitor_restored_memory_and_keep_rollback_ready'
        else 'review_decision_state'
      end,
      'automatic_activation', false,
      'advisory_only', true,
      'generation_consumption', 'not_wired',
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_research_outcome_learning',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_research_outcome_learning_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  market_category_id_value uuid;
  platform_value text;
  model_value text;
  actor_role text;
  category_value jsonb;
  captured_current_outcome_count integer := 0;
  candidates_value jsonb := '[]'::jsonb;
  current_memory content_factory.research_outcome_learning_memory_versions%rowtype;
  current_memory_value jsonb;
  rollback_memory content_factory.research_outcome_learning_memory_versions%rowtype;
  rollback_value jsonb;
  decision_history_value jsonb := '[]'::jsonb;
  pending_count integer := 0;
  guidance_status text;
  guidance_next_step text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'market_category_id', 'platform', 'model'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_outcome_status_payload_invalid';
  end if;
  perform content_factory_private.current_profile_id();
  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  market_category_id_value := content_factory_private.require_uuid(
    p_payload, 'market_category_id'
  );
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  model_value := lower(content_factory_private.require_text(
    p_payload, 'model', 2, 80
  ));
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) or model_value not in (
    'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
  ) then
    raise exception using
      errcode = '22023', message = 'research_outcome_scope_invalid';
  end if;
  actor_role := content_factory_private.membership_role(
    organization_id, false, array['owner', 'admin', 'producer', 'reviewer']
  );
  select jsonb_build_object(
    'market_category_id', category.id,
    'canonical_name', category.canonical_name,
    'status', category.status
  ) into category_value
  from content_factory.research_market_categories category
  where category.organization_id = organization_id
    and category.id = market_category_id_value;
  if category_value is null then
    raise exception using
      errcode = '22023', message = 'research_market_category_not_found';
  end if;

  select count(*)::integer into captured_current_outcome_count
  from (
    select distinct on (lineage.placement_id) lineage.id
    from content_factory.research_outcome_lineage_snapshots lineage
    where lineage.organization_id = organization_id
      and lineage.market_category_id = market_category_id_value
      and lineage.platform = platform_value
      and lineage.model = model_value
    order by lineage.placement_id, lineage.metric_observed_at desc,
             lineage.captured_at desc, lineage.id desc
    limit 10000
  ) current_outcomes;

  select memory.* into current_memory
  from content_factory.research_outcome_learning_memory_versions memory
  where memory.organization_id = organization_id
    and memory.market_category_id = market_category_id_value
    and memory.platform = platform_value
    and memory.model = model_value
    and memory.candidate_kind = 'creative_angle_preference'
  order by memory.memory_version desc, memory.id desc
  limit 1;
  if current_memory.id is not null then
    current_memory_value := jsonb_build_object(
      'memory_version_id', current_memory.id,
      'memory_version', current_memory.memory_version,
      'state', current_memory.state,
      'action', current_memory.action,
      'candidate_id', current_memory.candidate_id,
      'candidate', case when current_memory.candidate_id is null then null else
        content_factory_private.research_outcome_candidate_document(
          organization_id, current_memory.candidate_id
        ) end,
      'previous_memory_version_id', current_memory.previous_memory_version_id,
      'rollback_target_memory_version_id',
        current_memory.rollback_target_memory_version_id,
      'created_at', current_memory.created_at,
      'advisory_only', true,
      'generation_consumption', 'not_wired'
    );
  end if;

  if current_memory.action = 'deactivate'
     and current_memory.rollback_target_memory_version_id is not null then
    select memory.* into rollback_memory
    from content_factory.research_outcome_learning_memory_versions memory
    where memory.organization_id = organization_id
      and memory.id = current_memory.rollback_target_memory_version_id;
  elsif current_memory.id is not null then
    select memory.* into rollback_memory
    from content_factory.research_outcome_learning_memory_versions memory
    where memory.organization_id = organization_id
      and memory.market_category_id = market_category_id_value
      and memory.platform = platform_value
      and memory.model = model_value
      and memory.candidate_kind = 'creative_angle_preference'
      and memory.memory_version < current_memory.memory_version
      and memory.state = 'active'
      and memory.candidate_id is distinct from current_memory.candidate_id
    order by memory.memory_version desc, memory.id desc
    limit 1;
  end if;
  if rollback_memory.id is not null then
    rollback_value := jsonb_build_object(
      'memory_version_id', rollback_memory.id,
      'memory_version', rollback_memory.memory_version,
      'candidate_id', rollback_memory.candidate_id,
      'candidate_hash', (
        select candidate.candidate_hash
        from content_factory.research_outcome_learning_candidates candidate
        where candidate.organization_id = organization_id
          and candidate.id = rollback_memory.candidate_id
      ),
      'candidate_version', (
        select candidate.candidate_version
        from content_factory.research_outcome_learning_candidates candidate
        where candidate.organization_id = organization_id
          and candidate.id = rollback_memory.candidate_id
      ),
      'candidate', content_factory_private.research_outcome_candidate_document(
        organization_id, rollback_memory.candidate_id
      )
    );
  end if;

  select coalesce(jsonb_agg(
    content_factory_private.research_outcome_candidate_document(
      organization_id, candidate.id
    ) order by candidate.candidate_version desc, candidate.id desc
  ), '[]'::jsonb)
  into candidates_value
  from (
    select bounded.*
    from content_factory.research_outcome_learning_candidates bounded
    where bounded.organization_id = organization_id
      and bounded.market_category_id = market_category_id_value
      and bounded.platform = platform_value
      and bounded.model = model_value
      and bounded.candidate_kind = 'creative_angle_preference'
    order by bounded.candidate_version desc, bounded.id desc
    limit 20
  ) candidate;

  select count(*)::integer into pending_count
  from jsonb_array_elements(candidates_value) candidate(value)
  where candidate.value ->> 'status' = 'pending';

  select coalesce(jsonb_agg(jsonb_build_object(
    'action', decision.action,
    'candidate_id', decision.candidate_id,
    'candidate_version', decision.candidate_version,
    'candidate_hash', decision.candidate_hash,
    'expected_scope_version', decision.expected_scope_version,
    'rollback_memory_version_id', decision.rollback_memory_version_id,
    'reason', decision.reason,
    'decided_at', decision.decided_at
  ) order by decision.decided_at desc, decision.id desc), '[]'::jsonb)
  into decision_history_value
  from (
    select bounded.*
    from content_factory.research_outcome_learning_decisions bounded
    join content_factory.research_outcome_learning_candidates candidate
      on candidate.organization_id = bounded.organization_id
     and candidate.id = bounded.candidate_id
    where bounded.organization_id = organization_id
      and candidate.market_category_id = market_category_id_value
      and candidate.platform = platform_value
      and candidate.model = model_value
      and candidate.candidate_kind = 'creative_angle_preference'
    order by bounded.decided_at desc, bounded.id desc
    limit 20
  ) decision;
  if captured_current_outcome_count = 0 then
    guidance_status := 'no_eligible_outcomes';
    guidance_next_step := 'collect_qa_approved_mature_first_party_metrics';
  elsif pending_count > 0 then
    guidance_status := 'candidate_requires_decision';
    guidance_next_step := 'review_activate_reject_or_quarantine';
  elsif current_memory.state = 'active' then
    guidance_status := 'advisory_memory_active';
    guidance_next_step := 'monitor_effectiveness_and_keep_rollback_ready';
  elsif current_memory.state = 'inactive' then
    guidance_status := 'advisory_memory_inactive';
    guidance_next_step := case when rollback_value is null
      then 'wait_for_new_candidate' else 'review_rollback_target' end;
  else
    guidance_status := 'outcomes_need_comparison';
    guidance_next_step := 'refresh_bounded_learning_candidates';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-learning-control-v1',
    'can_decide', actor_role in ('owner', 'admin', 'producer'),
    'can_refresh', actor_role in ('owner', 'admin', 'producer'),
    'market_category', category_value,
    'scope', jsonb_build_object(
      'market_category_id', market_category_id_value,
      'platform', platform_value,
      'model', model_value
    ),
    'captured_current_outcome_count', captured_current_outcome_count,
    'candidates', candidates_value,
    'current_memory', current_memory_value,
    'rollback_target', rollback_value,
    'decision_history', decision_history_value,
    'guidance', jsonb_build_object(
      'status', guidance_status,
      'recommended_next_step', guidance_next_step,
      'automatic_activation', false,
      'advisory_only', true,
      'generation_consumption', 'not_wired',
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private.reject_research_outcome_learning_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_outcome_candidate_document(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_current_eligible_outcomes(
    uuid, uuid, text, text
  )
  from public, anon, authenticated, service_role;

revoke all on function public.creator_refresh_research_outcome_learning(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_decide_research_outcome_learning(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_research_outcome_learning_status(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_refresh_research_outcome_learning(jsonb)
  to authenticated;
grant execute on function public.creator_decide_research_outcome_learning(jsonb)
  to authenticated;
grant execute on function public.creator_research_outcome_learning_status(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
