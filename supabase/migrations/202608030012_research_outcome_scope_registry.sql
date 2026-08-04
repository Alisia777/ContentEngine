begin;

-- Read-only discovery for exact outcome-learning scopes.  A scope is visible
-- only when it is grounded in an approved scenarios ledger with an exact
-- market-category decision, or when that exact tuple already exists in an
-- outcome-learning ledger for a category in this product's binding history.
-- The function never creates candidate, memory, generation, provider,
-- publication, metric, command-receipt, or event rows.
create or replace function public.creator_research_outcome_learning_scopes(
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
  limit_value integer := 30;
  numeric_value numeric;
  discovered_count integer := 0;
  returned_count integer := 0;
  approved_recommended_count integer := 0;
  first_scope_key text;
  approved_recommended_scope_key text;
  suggested_scope_key_value text;
  truncated_value boolean := false;
  scopes_value jsonb := '[]'::jsonb;
  guidance_status text;
  guidance_next_step text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_outcome_scope_registry_payload_invalid';
  end if;

  -- Do not call current_profile_id(): that legacy helper upserts profiles and
  -- would make a discovery RPC observably mutating. membership_role performs
  -- the required auth/profile/membership checks without writes.
  if auth.uid() is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number' then
      raise exception using
        errcode = '22023', message = 'research_outcome_scope_registry_limit_invalid';
    end if;
    begin
      numeric_value := (p_payload ->> 'limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'research_outcome_scope_registry_limit_invalid';
    end;
    if numeric_value <> trunc(numeric_value)
       or numeric_value not between 1 and 50 then
      raise exception using
        errcode = '22023', message = 'research_outcome_scope_registry_limit_invalid';
    end if;
    limit_value := numeric_value::integer;
  end if;

  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;

  with
  current_binding as (
    select binding.category_id
    from content_factory.research_product_market_category_bindings binding
    where binding.organization_id = organization_id_value
      and binding.product_id = product_id_value
    order by binding.binding_version desc, binding.id desc
    limit 1
  ),
  product_categories as (
    select distinct binding.category_id
    from content_factory.research_product_market_category_bindings binding
    where binding.organization_id = organization_id_value
      and binding.product_id = product_id_value
  ),
  approved_scenario_sources as (
    select distinct
      category_binding.category_id as market_category_id,
      scenario.value ->> 'platform' as platform,
      case scenario.value ->> 'recommended_generation_mode'
        when 'real_gen4' then 'gen4_turbo'
        when 'real_seedance' then 'seedance2_fast'
        when 'real_photo' then 'seedream5_lite'
      end as model,
      true as from_approved_scenario,
      scenario.ordinality::smallint as scenario_position,
      scenario.ordinality = case
        when draft.brief #>> '{creative_potential,recommended_scenario_position}'
          ~ '^[1-3]$'
          then (
            draft.brief #>> '{creative_potential,recommended_scenario_position}'
          )::integer
        else null
      end as approved_recommended,
      false as from_lineage,
      false as from_candidate,
      false as from_memory,
      greatest(draft.approved_at, category_binding.confirmed_at)
        as latest_activity_at,
      null::text as current_memory_state,
      null::integer as current_memory_version
    from content_factory.creative_brief_drafts draft
    join content_factory.product_research_runs research_run
      on research_run.organization_id = draft.organization_id
     and research_run.id = draft.run_id
     and research_run.product_id = draft.product_id
     and research_run.status = 'completed'
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
    join content_factory.research_product_market_category_bindings category_binding
      on category_binding.organization_id = draft.organization_id
     and category_binding.product_id = draft.product_id
     and category_binding.candidate_hash = content_factory_private.json_hash(
       draft.brief -> 'category_analysis'
     )
    cross join lateral jsonb_array_elements(
      case
        when jsonb_typeof(scenario_artifact.payload -> 'scenarios') = 'array'
          then scenario_artifact.payload -> 'scenarios'
        else '[]'::jsonb
      end
    ) with ordinality as scenario(value, ordinality)
    where draft.organization_id = organization_id_value
      and draft.run_id = run_id_value
      and draft.product_id = product_id_value
      and draft.status = 'approved'
      and draft.approved_at is not null
      and jsonb_typeof(draft.brief -> 'category_analysis') = 'object'
      and jsonb_typeof(scenario.value) = 'object'
      and scenario.ordinality between 1 and 3
      -- Exact, case-sensitive allowlists intentionally reject normalization.
      and scenario.value ->> 'platform' in (
        'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
      )
      -- No fallback to legacy generation_mode is permitted.
      and scenario.value ->> 'recommended_generation_mode' in (
        'real_gen4', 'real_seedance', 'real_photo'
      )
  ),
  lineage_sources as (
    select
      lineage.market_category_id,
      lineage.platform,
      lineage.model,
      false as from_approved_scenario,
      null::smallint as scenario_position,
      false as approved_recommended,
      true as from_lineage,
      false as from_candidate,
      false as from_memory,
      max(lineage.captured_at) as latest_activity_at,
      null::text as current_memory_state,
      null::integer as current_memory_version
    from content_factory.research_outcome_lineage_snapshots lineage
    join product_categories product_category
      on product_category.category_id = lineage.market_category_id
    where lineage.organization_id = organization_id_value
    group by lineage.market_category_id, lineage.platform, lineage.model
  ),
  candidate_sources as (
    select
      candidate.market_category_id,
      candidate.platform,
      candidate.model,
      false as from_approved_scenario,
      null::smallint as scenario_position,
      false as approved_recommended,
      false as from_lineage,
      true as from_candidate,
      false as from_memory,
      max(candidate.created_at) as latest_activity_at,
      null::text as current_memory_state,
      null::integer as current_memory_version
    from content_factory.research_outcome_learning_candidates candidate
    join product_categories product_category
      on product_category.category_id = candidate.market_category_id
    where candidate.organization_id = organization_id_value
      and candidate.candidate_kind = 'creative_angle_preference'
    group by candidate.market_category_id, candidate.platform, candidate.model
  ),
  latest_memory_sources as (
    select distinct on (
      memory.market_category_id, memory.platform, memory.model
    )
      memory.market_category_id,
      memory.platform,
      memory.model,
      false as from_approved_scenario,
      null::smallint as scenario_position,
      false as approved_recommended,
      false as from_lineage,
      false as from_candidate,
      true as from_memory,
      memory.created_at as latest_activity_at,
      memory.state as current_memory_state,
      memory.memory_version as current_memory_version
    from content_factory.research_outcome_learning_memory_versions memory
    join product_categories product_category
      on product_category.category_id = memory.market_category_id
    where memory.organization_id = organization_id_value
      and memory.candidate_kind = 'creative_angle_preference'
    order by memory.market_category_id, memory.platform, memory.model,
             memory.memory_version desc, memory.id desc
  ),
  source_rows as (
    select * from approved_scenario_sources
    union all
    select * from lineage_sources
    union all
    select * from candidate_sources
    union all
    select * from latest_memory_sources
  ),
  aggregated_scopes as (
    select
      source.market_category_id,
      source.platform,
      source.model,
      bool_or(source.from_approved_scenario) as from_approved_scenario,
      coalesce(
        array_agg(
          distinct source.scenario_position order by source.scenario_position
        ) filter (
          where source.from_approved_scenario
            and source.scenario_position is not null
        ),
        '{}'::smallint[]
      ) as approved_scenario_positions,
      coalesce(
        bool_or(source.approved_recommended), false
      ) as approved_recommended,
      bool_or(source.from_lineage) as from_lineage,
      bool_or(source.from_candidate) as from_candidate,
      bool_or(source.from_memory) as from_memory,
      max(source.latest_activity_at) as latest_activity_at,
      max(source.current_memory_state) filter (
        where source.from_memory
      ) as current_memory_state,
      max(source.current_memory_version) filter (
        where source.from_memory
      ) as current_memory_version
    from source_rows source
    group by source.market_category_id, source.platform, source.model
  ),
  exact_scopes as (
    select
      aggregated.*,
      category.canonical_name,
      category.status as category_status,
      exists (
        select 1
        from current_binding
        where current_binding.category_id = aggregated.market_category_id
      ) as current_product_category,
      aggregated.market_category_id::text || ':' ||
        aggregated.platform || ':' || aggregated.model as scope_key
    from aggregated_scopes aggregated
    join content_factory.research_market_categories category
      on category.organization_id = organization_id_value
     and category.id = aggregated.market_category_id
  ),
  limited_scopes as (
    select
      exact.*,
      row_number() over (
        order by
          exact.current_product_category desc,
          exact.approved_recommended desc,
          (exact.current_memory_state = 'active') desc nulls last,
          exact.from_approved_scenario desc,
          exact.latest_activity_at desc nulls last,
          exact.market_category_id,
          exact.platform,
          exact.model
      ) as ordinal
    from exact_scopes exact
    order by
      exact.current_product_category desc,
      exact.approved_recommended desc,
      (exact.current_memory_state = 'active') desc nulls last,
      exact.from_approved_scenario desc,
      exact.latest_activity_at desc nulls last,
      exact.market_category_id,
      exact.platform,
      exact.model
    limit limit_value + 1
  )
  select
    count(*)::integer,
    count(*) filter (
      where limited.approved_recommended
        and limited.ordinal <= limit_value
    )::integer,
    max(limited.scope_key) filter (where limited.ordinal = 1),
    max(limited.scope_key) filter (
      where limited.approved_recommended
        and limited.ordinal <= limit_value
    ),
    coalesce(jsonb_agg(jsonb_build_object(
      'scope_key', limited.scope_key,
      'scope', jsonb_build_object(
        'market_category_id', limited.market_category_id,
        'platform', limited.platform,
        'model', limited.model
      ),
      'market_category', jsonb_build_object(
        'market_category_id', limited.market_category_id,
        'canonical_name', limited.canonical_name,
        'status', limited.category_status
      ),
      'sources', jsonb_build_object(
        'approved_scenario', limited.from_approved_scenario,
        'lineage', limited.from_lineage,
        'candidate', limited.from_candidate,
        'memory', limited.from_memory
      ),
      'approved_scenario_positions',
        to_jsonb(limited.approved_scenario_positions),
      'approved_recommended', limited.approved_recommended,
      'current_product_category', limited.current_product_category,
      'current_memory_state', limited.current_memory_state,
      'current_memory_version', limited.current_memory_version,
      'latest_activity_at', limited.latest_activity_at
    ) order by limited.ordinal) filter (
      where limited.ordinal <= limit_value
    ), '[]'::jsonb)
  into
    discovered_count,
    approved_recommended_count,
    first_scope_key,
    approved_recommended_scope_key,
    scopes_value
  from limited_scopes limited;

  truncated_value := discovered_count > limit_value;
  returned_count := least(discovered_count, limit_value);
  suggested_scope_key_value := case
    when truncated_value then null
    when returned_count = 1 then first_scope_key
    when approved_recommended_count = 1 then approved_recommended_scope_key
    else null
  end;
  guidance_status := case
    when returned_count = 0 then 'no_exact_scopes'
    when truncated_value then 'scope_list_truncated'
    when returned_count = 1 then 'single_exact_scope'
    else 'scope_selection_required'
  end;
  guidance_next_step := case guidance_status
    when 'no_exact_scopes' then
      'approve_scenario_and_confirm_exact_market_category'
    when 'scope_list_truncated' then 'choose_from_bounded_exact_scopes'
    when 'single_exact_scope' then 'open_unique_exact_scope'
    else 'choose_exact_scope'
  end;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-scope-registry-v1',
    'run_id', run_id_value,
    'product_id', product_id_value,
    'limit', limit_value,
    'returned_scope_count', returned_count,
    'truncated', truncated_value,
    'suggested_scope_key', suggested_scope_key_value,
    'scopes', scopes_value,
    'guidance', jsonb_build_object(
      'status', guidance_status,
      'recommended_next_step', guidance_next_step,
      'selection_required', returned_count > 1 or truncated_value,
      'automatic_selection', false,
      'read_only', true,
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
end;
$$;

revoke all on function public.creator_research_outcome_learning_scopes(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_outcome_learning_scopes(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
