begin;

-- The browser generation flow and the Python creative-learning core used to
-- be separate paths.  Keep only bounded, structural creative signals here:
-- exact historical wording and claims are deliberately never persisted as
-- reusable learning.
create table if not exists content_factory.generation_creative_signals (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_job_id uuid not null,
    product_id uuid not null,
    platform text not null
      check (platform in (
        'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
      )),
    model text not null
      check (model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')),
    creative_angle text not null
      check (creative_angle in (
        'product_focus', 'trust_builder', 'demonstration', 'comparison',
        'objection_handling', 'curiosity_gap'
      )),
    hook_patterns jsonb not null default '[]'::jsonb check (
      jsonb_typeof(hook_patterns) = 'array'
      and jsonb_array_length(hook_patterns) <= 8
      and length(hook_patterns::text) <= 512
    ),
    source text not null
      check (source in (
        'baseline', 'approved_research', 'performance_learning'
      )),
    compiler_version text not null
      check (compiler_version ~ '^[a-z0-9][a-z0-9._-]{2,63}$'),
    applied_policy_hash text check (
      applied_policy_hash is null
      or applied_policy_hash ~ '^[0-9a-f]{64}$'
    ),
    creative_brief_draft_id uuid,
    scenario_position smallint check (
      scenario_position is null or scenario_position between 1 and 3
    ),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, creative_brief_draft_id)
      references content_factory.creative_brief_drafts(organization_id, id),
    check (
      (
        source = 'approved_research'
        and creative_brief_draft_id is not null
        and scenario_position is not null
        and applied_policy_hash is null
      )
      or (
        source = 'performance_learning'
        and creative_brief_draft_id is null
        and scenario_position is null
        and applied_policy_hash is not null
      )
      or (
        source = 'baseline'
        and creative_brief_draft_id is null
        and scenario_position is null
        and applied_policy_hash is null
      )
    ),
    unique (organization_id, generation_job_id)
);

create index if not exists generation_creative_signals_learning_idx
  on content_factory.generation_creative_signals
  (organization_id, product_id, platform, creative_angle, created_at desc);

alter table content_factory.generation_creative_signals enable row level security;
revoke all on content_factory.generation_creative_signals
  from public, anon, authenticated;
grant all on content_factory.generation_creative_signals to service_role;

create or replace function
  content_factory_private.guard_generation_creative_signal_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_creative_signal_append_only';
end;
$$;

drop trigger if exists generation_creative_signal_append_only
  on content_factory.generation_creative_signals;
create trigger generation_creative_signal_append_only
before update or delete on content_factory.generation_creative_signals
for each row execute function
  content_factory_private.guard_generation_creative_signal_append_only();

revoke all on function
  content_factory_private.guard_generation_creative_signal_append_only()
  from public, anon, authenticated, service_role;

-- Resolve a conservative product-level policy from approved, published
-- generations with mature cumulative metrics.  A policy needs at least two
-- competing angles, at least three observations for each, and a stable
-- relative separation.  This mirrors the rank-based Python policy without
-- allowing raw hook copy or unsupported claims into a future prompt.
create or replace function public.creator_generation_learning_policy(
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
  actor_role text;
  team_scope boolean;
  media_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  platform_value text;
  model_value text;
  platform_evidence_count integer := 0;
  use_platform_scope boolean := false;
  evidence_count integer := 0;
  eligible_angle_count integer := 0;
  preferred_angle_value text;
  preferred_angle_score numeric;
  preferred_angle_count integer := 0;
  second_angle_score numeric;
  avoid_angle_value text;
  avoid_angle_score numeric;
  confidence_value text := 'none';
  applied_value boolean := false;
  hook_patterns_value jsonb := '[]'::jsonb;
  source_ids_value jsonb := '[]'::jsonb;
  benchmark_value jsonb := '{}'::jsonb;
  reason_codes_value jsonb := '[]'::jsonb;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'media_id', 'platform', 'model'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_learning_policy_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);
  media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  platform_value := lower(btrim(coalesce(p_payload ->> 'platform', '')));
  model_value := lower(btrim(coalesce(p_payload ->> 'model', '')));
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) or model_value not in (
    'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_learning_policy_scope_invalid';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb
    and (team_scope or media.owner_id = user_id);
  if media_row.id is null or media_row.product_id is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  select count(*)::integer into platform_evidence_count
  from content_factory.generation_creative_signals signal
  join content_factory.generation_jobs job
    on job.organization_id = signal.organization_id
   and job.id = signal.generation_job_id
   and job.product_id = signal.product_id
   and job.status = 'succeeded'
  join content_factory.placements placement
    on placement.organization_id = signal.organization_id
   and placement.generation_job_id = signal.generation_job_id
   and placement.status = 'published'
   and placement.platform = signal.platform
  join lateral (
    select metric.*
    from content_factory.metric_snapshots metric
    where metric.organization_id = placement.organization_id
      and metric.placement_id = placement.id
    order by metric.observed_at desc, metric.created_at desc
    limit 1
  ) metric on true
  where signal.organization_id = organization_id
    and signal.product_id = media_row.product_id
    and signal.platform = platform_value
    and metric.views >= 100
    and metric.clicks <= metric.views
    and metric.orders <= metric.views
    and exists (
      select 1
      from content_factory.content_review_runs review
      join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
       and decision.decision = 'approved'
       and decision.media_watched_confirmed
      where review.organization_id = job.organization_id
        and review.media_object_id::text = job.output ->> 'output_media_id'
        and review.status = 'completed'
        and review.completion_hash = decision.review_completion_hash
        and review.media_sha256_snapshot =
          decision.media_sha256_snapshot
    );
  use_platform_scope := platform_evidence_count >= 6;

  with observations as (
    select
      signal.generation_job_id,
      signal.creative_angle,
      signal.hook_patterns,
      metric.views,
      metric.clicks,
      metric.orders,
      metric.revenue_minor,
      metric.clicks::numeric / metric.views::numeric as ctr,
      metric.orders::numeric / metric.views::numeric as order_rate
    from content_factory.generation_creative_signals signal
    join content_factory.generation_jobs job
      on job.organization_id = signal.organization_id
     and job.id = signal.generation_job_id
     and job.product_id = signal.product_id
     and job.status = 'succeeded'
    join content_factory.placements placement
      on placement.organization_id = signal.organization_id
     and placement.generation_job_id = signal.generation_job_id
     and placement.status = 'published'
     and placement.platform = signal.platform
    join lateral (
      select metric.*
      from content_factory.metric_snapshots metric
      where metric.organization_id = placement.organization_id
        and metric.placement_id = placement.id
      order by metric.observed_at desc, metric.created_at desc
      limit 1
    ) metric on true
    where signal.organization_id = organization_id
      and signal.product_id = media_row.product_id
      and (not use_platform_scope or signal.platform = platform_value)
      and metric.views >= 100
      and metric.clicks <= metric.views
      and metric.orders <= metric.views
      and exists (
        select 1
        from content_factory.content_review_runs review
        join content_factory.content_review_decisions decision
          on decision.organization_id = review.organization_id
         and decision.review_id = review.id
         and decision.decision = 'approved'
         and decision.media_watched_confirmed
        where review.organization_id = job.organization_id
          and review.media_object_id::text =
            job.output ->> 'output_media_id'
          and review.status = 'completed'
          and review.completion_hash = decision.review_completion_hash
          and review.media_sha256_snapshot =
            decision.media_sha256_snapshot
      )
  ),
  eligible_angles as (
    select creative_angle
    from observations
    group by creative_angle
    having count(*) >= 3
  ),
  eligible_observations as (
    select observation.*
    from observations observation
    join eligible_angles using (creative_angle)
  ),
  ranked as (
    select
      observation.*,
      (
        percent_rank() over (order by observation.ctr) +
        percent_rank() over (order by observation.order_rate)
      ) / 2.0 as relative_score
    from eligible_observations observation
  ),
  angle_scores as (
    select
      creative_angle,
      count(*)::integer as observation_count,
      avg(relative_score) as score,
      row_number() over (
        order by avg(relative_score) desc, creative_angle
      ) as best_rank,
      row_number() over (
        order by avg(relative_score), creative_angle
      ) as worst_rank
    from ranked
    group by creative_angle
  ),
  summary as (
    select
      (select count(*)::integer from eligible_observations) as evidence_count,
      (select count(*)::integer from eligible_angles) as angle_count,
      max(creative_angle) filter (where best_rank = 1) as preferred_angle,
      max(score) filter (where best_rank = 1) as preferred_score,
      max(observation_count) filter (where best_rank = 1) as preferred_count,
      max(score) filter (where best_rank = 2) as second_score,
      max(creative_angle) filter (where worst_rank = 1) as avoid_angle,
      max(score) filter (where worst_rank = 1) as avoid_score
    from angle_scores
  )
  select
    summary.evidence_count,
    summary.angle_count,
    summary.preferred_angle,
    summary.preferred_score,
    summary.preferred_count,
    summary.second_score,
    summary.avoid_angle,
    summary.avoid_score
  into
    evidence_count,
    eligible_angle_count,
    preferred_angle_value,
    preferred_angle_score,
    preferred_angle_count,
    second_angle_score,
    avoid_angle_value,
    avoid_angle_score
  from summary;

  evidence_count := coalesce(evidence_count, 0);
  eligible_angle_count := coalesce(eligible_angle_count, 0);
  if evidence_count >= 12 and eligible_angle_count >= 2 then
    confidence_value := 'high';
  elsif evidence_count >= 6 and eligible_angle_count >= 2 then
    confidence_value := 'medium';
  elsif evidence_count > 0 then
    confidence_value := 'low';
  end if;
  applied_value :=
    confidence_value in ('medium', 'high')
    and preferred_angle_score >= 0.60
    and preferred_angle_score - coalesce(second_angle_score, 1) >= 0.10;
  if not applied_value then
    preferred_angle_value := null;
    avoid_angle_value := null;
  elsif avoid_angle_score > 0.40
     or preferred_angle_score - avoid_angle_score < 0.20 then
    avoid_angle_value := null;
  end if;

  if applied_value then
    with qualified as (
      select
        signal.generation_job_id,
        signal.hook_patterns,
        metric.views,
        metric.clicks,
        metric.orders,
        metric.clicks::numeric / metric.views::numeric as ctr,
        metric.orders::numeric / metric.views::numeric as order_rate
      from content_factory.generation_creative_signals signal
      join content_factory.generation_jobs job
        on job.organization_id = signal.organization_id
       and job.id = signal.generation_job_id
       and job.status = 'succeeded'
      join content_factory.placements placement
        on placement.organization_id = signal.organization_id
       and placement.generation_job_id = signal.generation_job_id
       and placement.status = 'published'
       and placement.platform = signal.platform
      join lateral (
        select metric.*
        from content_factory.metric_snapshots metric
        where metric.organization_id = placement.organization_id
          and metric.placement_id = placement.id
        order by metric.observed_at desc, metric.created_at desc
        limit 1
      ) metric on true
      where signal.organization_id = organization_id
        and signal.product_id = media_row.product_id
        and signal.creative_angle = preferred_angle_value
        and (not use_platform_scope or signal.platform = platform_value)
        and metric.views >= 100
        and metric.clicks <= metric.views
        and metric.orders <= metric.views
        and exists (
          select 1
          from content_factory.content_review_runs review
          join content_factory.content_review_decisions decision
            on decision.organization_id = review.organization_id
           and decision.review_id = review.id
           and decision.decision = 'approved'
           and decision.media_watched_confirmed
          where review.organization_id = job.organization_id
            and review.media_object_id::text =
              job.output ->> 'output_media_id'
            and review.status = 'completed'
            and review.completion_hash = decision.review_completion_hash
            and review.media_sha256_snapshot =
              decision.media_sha256_snapshot
        )
    ),
    pattern_counts as (
      select pattern.value as pattern, count(*)::integer as uses
      from qualified
      cross join lateral jsonb_array_elements_text(
        qualified.hook_patterns
      ) pattern(value)
      group by pattern.value
      order by uses desc, pattern.value
      limit 4
    )
    select
      coalesce(
        (select jsonb_agg(pattern order by uses desc, pattern)
         from pattern_counts),
        '[]'::jsonb
      ),
      coalesce(
        (select jsonb_agg(generation_job_id order by generation_job_id)
         from qualified),
        '[]'::jsonb
      ),
      coalesce(
        (select jsonb_build_object(
          'median_ctr', percentile_cont(0.5) within group (order by ctr),
          'median_order_rate',
            percentile_cont(0.5) within group (order by order_rate),
          'minimum_views_per_observation', 100
        ) from qualified),
        '{}'::jsonb
      )
    into hook_patterns_value, source_ids_value, benchmark_value;
  end if;

  reason_codes_value := case
    when applied_value and use_platform_scope then
      '["stable_relative_performance_signal","platform_specific_evidence"]'::jsonb
    when applied_value then
      '["stable_relative_performance_signal","cross_platform_fallback"]'::jsonb
    when evidence_count = 0 then
      '["no_qualified_performance_evidence"]'::jsonb
    when eligible_angle_count < 2 then
      '["insufficient_angle_comparison"]'::jsonb
    else
      '["no_stable_angle_separation"]'::jsonb
  end;

  policy_without_hash := jsonb_build_object(
    'version', 'generation-learning-v1',
    'applied', applied_value,
    'confidence', confidence_value,
    'evidence_count', evidence_count,
    'target_platform', platform_value,
    'scope', case
      when use_platform_scope then 'product_platform'
      else 'product_cross_platform'
    end,
    'preferred_angle', preferred_angle_value,
    'avoid_angle', avoid_angle_value,
    'preferred_hook_patterns', hook_patterns_value,
    'reason_codes', reason_codes_value,
    'benchmark', benchmark_value,
    'source_job_ids', source_ids_value,
    'safety', jsonb_build_object(
      'claims_are_never_learned', true,
      'product_identity_is_immutable', true,
      'rights_are_immutable', true,
      'format_and_spend_are_immutable', true
    )
  );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);
  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value,
    'requested_model', model_value
  );
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

-- Preserve the audited paid-generation commands behind the public wrapper.
-- The wrapper removes the advisory learning context before the old strict
-- payload validators run, then records only a server-bound structural signal.
create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  command_payload jsonb;
  learning_context jsonb;
  organization_id uuid;
  campaign_id_value uuid;
  campaign_row content_factory.generation_campaigns%rowtype;
  result jsonb;
  job_id_value uuid;
  stored_campaign_id uuid;
  job_row content_factory.generation_jobs%rowtype;
  hook_patterns_value jsonb;
  learning_source_value text;
  server_policy jsonb;
  research_draft content_factory.creative_brief_drafts%rowtype;
  research_draft_id_value uuid;
  scenario_position_value integer;
  research_scenario jsonb;
  research_text text;
  research_hook text;
  computed_angle_value text;
  computed_patterns_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  learning_context := p_payload -> 'learning_context';
  command_payload := p_payload - 'learning_context';
  if learning_context is not null then
    if jsonb_typeof(learning_context) <> 'object'
       or learning_context - array[
         'creative_angle', 'hook_patterns', 'source',
         'compiler_version', 'applied_policy_hash',
         'creative_brief_draft_id', 'scenario_position'
       ]::text[] <> '{}'::jsonb
       or coalesce(learning_context ->> 'creative_angle', '') not in (
         'product_focus', 'trust_builder', 'demonstration', 'comparison',
         'objection_handling', 'curiosity_gap'
       )
       or coalesce(learning_context ->> 'source', '') not in (
         'baseline', 'approved_research', 'performance_learning'
       )
       or coalesce(learning_context ->> 'compiler_version', '')
          !~ '^[a-z0-9][a-z0-9._-]{2,63}$'
       or jsonb_typeof(
         coalesce(learning_context -> 'hook_patterns', '[]'::jsonb)
       ) <> 'array'
       or jsonb_array_length(
         coalesce(learning_context -> 'hook_patterns', '[]'::jsonb)
       ) > 8
       or exists (
         select 1
         from jsonb_array_elements(
           coalesce(learning_context -> 'hook_patterns', '[]'::jsonb)
         ) pattern(value)
         where jsonb_typeof(pattern.value) <> 'string'
       )
       or exists (
         select 1
         from jsonb_array_elements_text(
           coalesce(learning_context -> 'hook_patterns', '[]'::jsonb)
         ) pattern(value)
         where pattern.value not in (
           'question_led', 'why_explanation', 'before_buying',
           'comparison', 'demonstration', 'first_person',
           'numbered', 'concise'
         )
       )
       or (
         learning_context ? 'applied_policy_hash'
         and learning_context ->> 'applied_policy_hash' is not null
         and learning_context ->> 'applied_policy_hash'
           !~ '^[0-9a-f]{64}$'
       ) then
      raise exception using
        errcode = '22023',
        message = 'generation_learning_context_invalid';
    end if;
    hook_patterns_value :=
      coalesce(learning_context -> 'hook_patterns', '[]'::jsonb);
    learning_source_value := learning_context ->> 'source';
    if (
      select count(*) from jsonb_array_elements_text(hook_patterns_value)
    ) <> (
      select count(distinct pattern.value)
      from jsonb_array_elements_text(hook_patterns_value) pattern(value)
    ) then
      raise exception using
        errcode = '22023',
        message = 'generation_learning_context_invalid';
    end if;
    if learning_source_value = 'approved_research' then
      begin
        research_draft_id_value :=
          (learning_context ->> 'creative_brief_draft_id')::uuid;
        scenario_position_value :=
          (learning_context ->> 'scenario_position')::integer;
      exception when invalid_text_representation
        or numeric_value_out_of_range then
        raise exception using
          errcode = '22023',
          message = 'generation_learning_context_invalid';
      end;
      if research_draft_id_value is null
         or scenario_position_value not between 1 and 3
         or learning_context ? 'applied_policy_hash' then
        raise exception using
          errcode = '22023',
          message = 'generation_learning_context_invalid';
      end if;
    elsif learning_source_value = 'performance_learning' then
      if coalesce(learning_context ->> 'applied_policy_hash', '')
           !~ '^[0-9a-f]{64}$'
         or learning_context ? 'creative_brief_draft_id'
         or learning_context ? 'scenario_position' then
        raise exception using
          errcode = '22023',
          message = 'generation_learning_context_invalid';
      end if;
    elsif learning_source_value = 'baseline' then
      if learning_context ->> 'creative_angle' <> 'product_focus'
         or hook_patterns_value <> '[]'::jsonb
         or learning_context ? 'applied_policy_hash'
         or learning_context ? 'creative_brief_draft_id'
         or learning_context ? 'scenario_position' then
        raise exception using
          errcode = '22023',
          message = 'generation_learning_context_invalid';
      end if;
    end if;
  end if;

  if lower(btrim(coalesce(command_payload ->> 'platform', ''))) =
     'instagram' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_platform_not_supported';
  end if;
  organization_id :=
    content_factory_private.resolve_organization(command_payload);

  if learning_context is not null
     and learning_source_value = 'performance_learning' then
    server_policy := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id,
        'media_id', command_payload #>> '{media_ids,0}',
        'platform', command_payload ->> 'platform',
        'model', command_payload ->> 'model'
      )
    );
    if server_policy -> 'applied' is distinct from 'true'::jsonb
       or server_policy ->> 'policy_hash'
          is distinct from learning_context ->> 'applied_policy_hash'
       or server_policy ->> 'preferred_angle'
          is distinct from learning_context ->> 'creative_angle'
       or coalesce(
         server_policy -> 'preferred_hook_patterns',
         '[]'::jsonb
       ) is distinct from hook_patterns_value then
      raise exception using
        errcode = '55000',
        message = 'generation_learning_policy_stale';
    end if;
  end if;

  if command_payload ->> 'model' <> 'seedream5_lite' then
    result :=
      content_factory_private.creator_start_real_generation_campaign_v1(
        command_payload
      );
  else
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'operator']
    );
    if command_payload ? 'campaign_id' then
      campaign_id_value := content_factory_private.require_uuid(
        command_payload, 'campaign_id'
      );
    else
      select campaign.id into campaign_id_value
      from content_factory.generation_campaigns campaign
      where campaign.organization_id = organization_id
        and campaign.kind = 'default';
    end if;
    select campaign.* into campaign_row
    from content_factory.generation_campaigns campaign
    where campaign.organization_id = organization_id
      and campaign.id = campaign_id_value;
    if campaign_row.id is null then
      raise exception using
        errcode = '22023',
        message = 'paid_generation_campaign_required';
    end if;
    if campaign_row.status <> 'active' then
      raise exception using
        errcode = '42501',
        message = 'paid_generation_campaign_not_active';
    end if;
    perform set_config(
      'content_factory.generation_campaign_id',
      campaign_id_value::text,
      true
    );
    result :=
      content_factory_private.creator_start_seedream5_lite_photo(
        command_payload - 'campaign_id'
      );
    begin
      job_id_value := (result #>> '{job,id}')::uuid;
    exception when invalid_text_representation or null_value_not_allowed then
      raise exception using
        errcode = '55000',
        message = 'generation_campaign_binding_invalid';
    end;
    select job.campaign_id into stored_campaign_id
    from content_factory.generation_jobs job
    where job.organization_id = organization_id
      and job.id = job_id_value;
    if stored_campaign_id is distinct from campaign_id_value then
      raise exception using
        errcode = '23505',
        message = 'idempotency_key_conflict';
    end if;
    result := jsonb_set(
      result, '{job,campaign_id}',
      to_jsonb(campaign_id_value::text), true
    );
    result := jsonb_set(
      result, '{job,campaign_name}',
      to_jsonb(campaign_row.name), true
    );
    result := jsonb_set(
      result, '{batch,campaign_id}',
      to_jsonb(campaign_id_value::text), true
    );
  end if;

  if learning_context is not null then
    begin
      job_id_value := (result #>> '{job,id}')::uuid;
    exception when invalid_text_representation or null_value_not_allowed then
      raise exception using
        errcode = '55000',
        message = 'generation_learning_signal_binding_invalid';
    end;
    select job.* into job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id
      and job.id = job_id_value;
    if job_row.id is null
       or job_row.product_id is null
       or job_row.input ->> 'platform'
          is distinct from command_payload ->> 'platform'
       or job_row.input ->> 'model'
          is distinct from command_payload ->> 'model'
       or job_row.input ->> 'prompt_text'
          is distinct from command_payload ->> 'brief' then
      raise exception using
        errcode = '55000',
        message = 'generation_learning_signal_binding_invalid';
    end if;

    if learning_source_value = 'approved_research' then
      select draft.* into research_draft
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = organization_id
        and draft.id = research_draft_id_value
        and draft.product_id = job_row.product_id
        and draft.status = 'approved';
      research_scenario := research_draft.brief #> array[
        'scenarios',
        (scenario_position_value - 1)::text
      ];
      if research_draft.id is null
         or jsonb_typeof(research_scenario) <> 'object' then
        raise exception using
          errcode = '55000',
          message = 'generation_learning_research_provenance_invalid';
      end if;
      research_hook := btrim(coalesce(
        research_scenario ->> 'hook',
        ''
      ));
      research_text := lower(concat_ws(
        ' ',
        research_hook,
        research_scenario -> 'shot_list',
        research_draft.brief #>> '{task_blueprint,mandatory_shots}'
      ));
      computed_patterns_value := '[]'::jsonb;
      if position('?' in research_hook) > 0 then
        computed_patterns_value :=
          computed_patterns_value || '"question_led"'::jsonb;
      end if;
      if research_text ~* '(why|почему|зачем)' then
        computed_patterns_value :=
          computed_patterns_value || '"why_explanation"'::jsonb;
      end if;
      if research_text ~* '(before|до покупки|перед покупкой)' then
        computed_patterns_value :=
          computed_patterns_value || '"before_buying"'::jsonb;
      end if;
      if research_text ~* '(compare|versus|(^|[^a-z])vs([^a-z]|$)|сравн|дешев)' then
        computed_patterns_value :=
          computed_patterns_value || '"comparison"'::jsonb;
      end if;
      if research_text ~* '(watch|show|see|смотр|покаж)' then
        computed_patterns_value :=
          computed_patterns_value || '"demonstration"'::jsonb;
      end if;
      if research_text ~* '(^|[^[:alnum:]_])(i|my|я|мой|моя|мне)([^[:alnum:]_]|$)' then
        computed_patterns_value :=
          computed_patterns_value || '"first_person"'::jsonb;
      end if;
      if research_text ~ '[0-9]'
         or research_text ~* '(^|[^[:alnum:]_])(one|один|одна|три|three)([^[:alnum:]_]|$)' then
        computed_patterns_value :=
          computed_patterns_value || '"numbered"'::jsonb;
      end if;
      if length(research_hook) between 1 and 72 then
        computed_patterns_value :=
          computed_patterns_value || '"concise"'::jsonb;
      end if;
      computed_angle_value := case
        when computed_patterns_value @> '["comparison"]'::jsonb
          then 'comparison'
        when computed_patterns_value @> '["before_buying"]'::jsonb
          or computed_patterns_value @> '["why_explanation"]'::jsonb
          then 'objection_handling'
        when computed_patterns_value @> '["demonstration"]'::jsonb
          then 'demonstration'
        when computed_patterns_value @> '["question_led"]'::jsonb
          then 'curiosity_gap'
        when research_text ~* '(честн|довер|спокойн|реальн|trust)'
          then 'trust_builder'
        else 'product_focus'
      end;
      learning_context := jsonb_set(
        jsonb_set(
          learning_context,
          '{creative_angle}',
          to_jsonb(computed_angle_value),
          true
        ),
        '{hook_patterns}',
        computed_patterns_value,
        true
      );
      hook_patterns_value := computed_patterns_value;
    end if;

    insert into content_factory.generation_creative_signals (
      organization_id, generation_job_id, product_id, platform, model,
      creative_angle, hook_patterns, source, compiler_version,
      applied_policy_hash, creative_brief_draft_id, scenario_position,
      prompt_hash
    ) values (
      organization_id,
      job_row.id,
      job_row.product_id,
      job_row.input ->> 'platform',
      job_row.input ->> 'model',
      learning_context ->> 'creative_angle',
      hook_patterns_value,
      learning_context ->> 'source',
      learning_context ->> 'compiler_version',
      nullif(learning_context ->> 'applied_policy_hash', ''),
      research_draft_id_value,
      scenario_position_value,
      content_factory_private.json_hash(to_jsonb(
        job_row.input ->> 'prompt_text'
      ))
    )
    on conflict (organization_id, generation_job_id) do nothing;

    if not exists (
      select 1
      from content_factory.generation_creative_signals signal
      where signal.organization_id = organization_id
        and signal.generation_job_id = job_row.id
        and signal.product_id = job_row.product_id
        and signal.platform = job_row.input ->> 'platform'
        and signal.model = job_row.input ->> 'model'
        and signal.creative_angle =
          learning_context ->> 'creative_angle'
        and signal.hook_patterns = hook_patterns_value
        and signal.source = learning_context ->> 'source'
        and signal.compiler_version =
          learning_context ->> 'compiler_version'
        and signal.applied_policy_hash is not distinct from
          nullif(learning_context ->> 'applied_policy_hash', '')
        and signal.creative_brief_draft_id is not distinct from
          research_draft_id_value
        and signal.scenario_position is not distinct from
          scenario_position_value
        and signal.prompt_hash =
          content_factory_private.json_hash(to_jsonb(
            job_row.input ->> 'prompt_text'
          ))
    ) then
      raise exception using
        errcode = '23505',
        message = 'generation_learning_signal_conflict';
    end if;
    result := jsonb_set(
      result,
      '{job,learning_signal_recorded}',
      'true'::jsonb,
      true
    );
  end if;
  return result;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

commit;
