begin;

-- Reconnect the learning loop (owner priority 3).
--
-- 1. Restore the audited "generation-learning-v9-ai-teaching" overlay into
--    content_factory_private.creator_generation_learning_policy_pre_project_v47.
--    202608040016 replaced that private alias with a passthrough to the
--    pre-legacy v8 chain, so confirmed teach-card decisions in
--    content_factory.ai_effective_category_policies stopped steering
--    preferred/avoid creative angles.  The body below is the exact overlay
--    installed by 202608040002 for public.creator_generation_learning_policy.
--    Live chain after this migration: public wrapper (202608050002)
--    -> pre_advisory_v9 -> pre_historical_case_v1 -> call_project_scoped_v47
--    -> pre_project_v47 [teaching overlay restored] -> pre_ai_control_room_v8
--    -> unscoped_v7 -> rejection chain.  pre_advisory_v9's existing shadow
--    reason 'historical_case_advisory_shadowed_by_manual_teaching_policy'
--    becomes truthful again: manual teaching wins, historical advisory yields.
create or replace function
  content_factory_private.creator_generation_learning_policy_pre_project_v47(
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
  base_policy jsonb;
  organization_id uuid;
  category_value text;
  policy_row content_factory.ai_effective_category_policies%rowtype;
  generation_allowed_value boolean;
  base_preferred_angle_value text;
  preferred_angle_value text;
  avoid_angle_value text;
  preferred_angle_changed boolean := false;
  negative_fallback_applied boolean := false;
  preferred_hook_patterns_value jsonb;
  selected_hook_patterns_value jsonb;
  applied_value boolean;
  confidence_value text;
  reason_codes_value jsonb;
  safety_value jsonb;
  requested_model_value text;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  base_policy := content_factory_private
    .creator_generation_learning_policy_pre_ai_control_room_v8(p_payload);

  category_value := lower(btrim(coalesce(
    base_policy ->> 'product_category',
    p_payload ->> 'product_category',
    ''
  )));
  if category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    return base_policy;
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  select policy.*
  into policy_row
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = organization_id
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;

  if policy_row.id is null
     or (
       policy_row.preferred_creative_angle is null
       and policy_row.avoid_creative_angle is null
     ) then
    return base_policy;
  end if;

  generation_allowed_value :=
    base_policy -> 'generation_allowed' is distinct from 'false'::jsonb;
  base_preferred_angle_value :=
    nullif(base_policy ->> 'preferred_angle', '');
  preferred_angle_value := coalesce(
    policy_row.preferred_creative_angle,
    base_preferred_angle_value
  );
  avoid_angle_value := coalesce(
    policy_row.avoid_creative_angle,
    nullif(base_policy ->> 'avoid_angle', '')
  );
  if policy_row.avoid_creative_angle is not null
     and (
       preferred_angle_value is null
       or preferred_angle_value = policy_row.avoid_creative_angle
     ) then
    preferred_angle_value := case policy_row.avoid_creative_angle
      when 'product_focus' then 'trust_builder'
      else 'product_focus'
    end;
    negative_fallback_applied := true;
  end if;
  if avoid_angle_value is not distinct from preferred_angle_value then
    avoid_angle_value := null;
  end if;

  preferred_angle_changed :=
    preferred_angle_value is distinct from base_preferred_angle_value;
  preferred_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'preferred_hook_patterns') = 'array'
      then base_policy -> 'preferred_hook_patterns'
    else '[]'::jsonb
  end;
  selected_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'selected_hook_patterns') = 'array'
      then base_policy -> 'selected_hook_patterns'
    else preferred_hook_patterns_value
  end;

  applied_value := generation_allowed_value and (
    base_policy -> 'applied' = 'true'::jsonb
    or policy_row.preferred_creative_angle is not null
    or policy_row.avoid_creative_angle is not null
  );
  confidence_value := case
    when policy_row.preferred_creative_angle is not null
      or policy_row.avoid_creative_angle is not null then 'high'
    else coalesce(base_policy ->> 'confidence', 'none')
  end;
  reason_codes_value := case
    when jsonb_typeof(base_policy -> 'reason_codes') = 'array'
      then base_policy -> 'reason_codes'
    else '[]'::jsonb
  end || jsonb_build_array(
    case
      when not generation_allowed_value
        then 'ai_teaching_policy_available_but_generation_blocked'
      when policy_row.preferred_creative_angle is not null
        then 'ai_teaching_positive_angle_applied'
      when negative_fallback_applied
        then 'ai_teaching_negative_fallback_preferred'
      else 'ai_teaching_negative_angle_advisory'
    end,
    case
      when policy_row.avoid_creative_angle is not null
        then 'ai_teaching_negative_angle_applied'
      else 'ai_teaching_no_negative_angle'
    end,
    'ai_teaching_deterministic_selection'
  );
  safety_value := case
    when jsonb_typeof(base_policy -> 'safety') = 'object'
      then base_policy -> 'safety'
    else '{}'::jsonb
  end || jsonb_build_object(
    'ai_teaching_bounded_creative_angles_only', true,
    'raw_knowledge_and_notes_excluded', true,
    'exact_category_scope', true,
    'cross_category_learning_forbidden', true,
    'generation_allowed_preserved', true,
    'rejection_guards_preserved', true,
    'deterministic_negative_fallback', true,
    'hook_patterns_cleared_on_angle_change', true,
    'bounded_exploration_cursor_removed', true
  );

  requested_model_value := base_policy ->> 'requested_model';
  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model' - 'exploration')
    || jsonb_build_object(
      'version', 'generation-learning-v9-ai-teaching',
      'product_category', category_value,
      'applied', applied_value,
      'confidence', confidence_value,
      -- Human teaching is deterministic.  It must not inherit the mutable
      -- two-arm exploration cursor because the generation-spec provider guard
      -- gives that cursor a deliberately narrow product_focus/demonstration
      -- drift allowance.  "performance" is the installed non-exploration
      -- selection contract understood by the existing handoff and outcome
      -- consumers; the adjacent provenance identifies its human source.
      'selection_mode', 'performance',
      'selection_provenance', jsonb_build_object(
        'schema_version', 'ai-teaching-selection-provenance-v1',
        'source', 'human_teaching_card_policy',
        'deterministic', true,
        'product_category', category_value,
        'scope_version', policy_row.scope_version,
        'teaching_policy_hash', policy_row.policy_hash,
        -- A queued paid job is allowed to advance category_evidence_count by
        -- one before provider claim, which also changes the base policy hash.
        -- Keep only the stable installed base version in provenance so the
        -- live guard can apply its existing top-level drift normalization.
        'base_policy_version', base_policy ->> 'version'
      ),
      'preferred_angle', preferred_angle_value,
      'avoid_angle', avoid_angle_value,
      'preferred_hook_patterns', preferred_hook_patterns_value,
      'selected_angle', preferred_angle_value,
      'selected_hook_patterns', selected_hook_patterns_value,
      'reason_codes', reason_codes_value,
      'safety', safety_value,
      'ai_teaching_policy', jsonb_build_object(
        'version', 'ai-category-teaching-policy-v1',
        'scope_version', policy_row.scope_version,
        'policy_hash', policy_row.policy_hash,
        'preferred_creative_angle',
          policy_row.preferred_creative_angle,
        'avoid_creative_angle', policy_row.avoid_creative_angle,
        'negative_fallback_applied', negative_fallback_applied,
        'positive_decision_id', policy_row.positive_decision_id,
        'negative_decision_id', policy_row.negative_decision_id,
        'raw_notes_excluded', true
      )
    );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);

  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value,
    'requested_model', requested_model_value
  );
end;
$$;

revoke all on function
  content_factory_private.creator_generation_learning_policy_pre_project_v47(
    jsonb
  ) from public, anon, authenticated, service_role;

comment on function
  content_factory_private.creator_generation_learning_policy_pre_project_v47(
    jsonb
  ) is
  'Private project-scoped teaching overlay over the audited pre-legacy v8 policy chain; confirmed teach-card decisions steer bounded creative angles again while raw knowledge and notes stay excluded.';

-- 2. Historical-case product binding (source body: 202608040006).  Two
--    corrections, both preserving unique-or-null semantics: (a) a product_sku
--    that matches zero products no longer early-returns null, so the
--    marketplace key is reachable again; (b) the marketplace key also matches
--    a digit-only products.sku equal to the case's WB article.  Return values
--    keep the existing enum ('late_unique_product_sku' /
--    'late_unique_marketplace_sku'), so evidence-count consumers keep working.
create or replace function
  content_factory_private.ai_historical_case_product_binding_method(
    p_organization_id uuid,
    p_case_id uuid,
    p_product_id uuid
  )
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  historical_case_row content_factory.ai_historical_case_events%rowtype;
  product_row content_factory.products%rowtype;
  product_sku_match_count integer := 0;
  product_sku_match_id uuid;
  marketplace_match_count integer := 0;
  marketplace_match_id uuid;
  product_sku_conflict boolean := false;
  marketplace_conflict boolean := false;
begin
  select historical_case.*
  into historical_case_row
  from content_factory.ai_historical_case_events historical_case
  where historical_case.organization_id = p_organization_id
    and historical_case.case_id = p_case_id;
  select product.*
  into product_row
  from content_factory.products product
  where product.organization_id = p_organization_id
    and product.id = p_product_id;
  if historical_case_row.id is null
     or product_row.id is null
     or historical_case_row.resolution_status <> 'matched' then
    return null;
  end if;
  if historical_case_row.product_id is not null then
    return case when historical_case_row.product_id = p_product_id
      then 'exact_product_id' else null end;
  end if;
  if historical_case_row.resolution_method not in (
    'source_external_sku', 'source_marketplace_sku'
  ) then
    return null;
  end if;

  if historical_case_row.product_sku is not null then
    select count(*)::integer
    into product_sku_match_count
    from content_factory.products product
    where product.organization_id = p_organization_id
      and product.sku = historical_case_row.product_sku;
    -- More than one product for one source SKU stays ambiguous and fails
    -- closed.  A zero-match source SKU no longer vetoes the case: the
    -- marketplace key below remains authoritative for late binding.
    if product_sku_match_count > 1 then
      return null;
    end if;
    if product_sku_match_count = 1 then
      select product.id
      into product_sku_match_id
      from content_factory.products product
      where product.organization_id = p_organization_id
        and product.sku = historical_case_row.product_sku;
    end if;
    select count(distinct (
      lower(other_case.product_title) || chr(31) || lower(other_case.brand)
    )) > 1
    into product_sku_conflict
    from content_factory.ai_historical_case_events other_case
    where other_case.organization_id = p_organization_id
      and other_case.resolution_status = 'matched'
      and other_case.product_sku = historical_case_row.product_sku;
  end if;

  if historical_case_row.marketplace_sku is not null then
    -- Owners demonstrably register WB products with the raw article digits
    -- as products.sku (live row: products.sku = '518413561').  The
    -- marketplace key therefore matches either the explicit
    -- current_wb_article alias or a digit-only sku, and the combined
    -- candidate set must still resolve to exactly one product.
    select count(*)::integer
    into marketplace_match_count
    from content_factory.products product
    where product.organization_id = p_organization_id
      and (
        product.current_wb_article = historical_case_row.marketplace_sku
        or (
          product.sku = historical_case_row.marketplace_sku
          and product.sku ~ '^[0-9]{4,20}$'
        )
      );
    if marketplace_match_count <> 1 then
      return null;
    end if;
    select product.id
    into marketplace_match_id
    from content_factory.products product
    where product.organization_id = p_organization_id
      and (
        product.current_wb_article = historical_case_row.marketplace_sku
        or (
          product.sku = historical_case_row.marketplace_sku
          and product.sku ~ '^[0-9]{4,20}$'
        )
      );
    select count(distinct (
      lower(other_case.product_title) || chr(31) || lower(other_case.brand)
    )) > 1
    into marketplace_conflict
    from content_factory.ai_historical_case_events other_case
    where other_case.organization_id = p_organization_id
      and other_case.resolution_status = 'matched'
      and other_case.marketplace_sku = historical_case_row.marketplace_sku;
  end if;

  if coalesce(product_sku_conflict, false)
     or coalesce(marketplace_conflict, false)
     or (product_sku_match_id is not null
       and product_sku_match_id <> p_product_id)
     or (marketplace_match_id is not null
       and marketplace_match_id <> p_product_id) then
    return null;
  end if;
  if product_sku_match_id = p_product_id then
    return 'late_unique_product_sku';
  end if;
  if marketplace_match_id = p_product_id then
    return 'late_unique_marketplace_sku';
  end if;
  return null;
end;
$$;

revoke all on function
  content_factory_private.ai_historical_case_product_binding_method(
    uuid, uuid, uuid
  )
  from public, anon, authenticated, service_role;

-- 3. Product-scoped evidence (source body: 202608040006).  Both
--    candidate_cases preselects mirror the widened marketplace key so
--    digit-sku late bindings reach the authoritative lateral binding_method
--    filter.  Thresholds are unchanged: confirm-decision heads only,
--    score >= 2 per direction, 100-case bound.
create or replace function
  content_factory_private.ai_historical_product_case_evidence(
    p_organization_id uuid,
    p_product_category text,
    p_product_id uuid
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  eligible_total_count_value integer := 0;
  considered_count_value integer := 0;
  distinct_platform_count_value integer := 0;
  direct_product_binding_count_value integer := 0;
  late_exact_sku_binding_count_value integer := 0;
  angles_value jsonb := '[]'::jsonb;
  case_refs_value jsonb := '[]'::jsonb;
  maximum_score_value integer;
  maximum_score_tie_count integer := 0;
  minimum_score_value integer;
  minimum_score_tie_count integer := 0;
  preferred_angle_value text;
  avoid_angle_value text;
  evidence_hash_value text;
  target_product_row content_factory.products%rowtype;
begin
  select product.*
  into target_product_row
  from content_factory.products product
  where product.organization_id = p_organization_id
    and product.id = p_product_id;
  if p_product_id is null or target_product_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'ai_historical_case_product_invalid';
  end if;

  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      category_value
    ) semantic_head
  ), candidate_cases as materialized (
    select historical_case.case_id
    from content_factory.ai_historical_case_events historical_case
    join semantic_heads semantic_head
      on semantic_head.case_id = historical_case.case_id
     and semantic_head.decision = 'confirm'
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
      and historical_case.resolution_status = 'matched'
      and historical_case.creative_angle is not null
      and historical_case.outcome in ('good', 'bad')
      and (
        historical_case.product_id = p_product_id
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and (
            historical_case.product_sku = target_product_row.sku
            or (
              target_product_row.current_wb_article is not null
              and historical_case.marketplace_sku =
                target_product_row.current_wb_article
            )
          )
        )
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and target_product_row.sku ~ '^[0-9]{4,20}$'
          and historical_case.marketplace_sku = target_product_row.sku
        )
      )
  )
  select count(*)::integer
  into eligible_total_count_value
  from candidate_cases candidate_case
  cross join lateral (
    select content_factory_private
      .ai_historical_case_product_binding_method(
        p_organization_id,
        candidate_case.case_id,
        p_product_id
      ) as binding_method
  ) binding
  where binding.binding_method is not null;

  with semantic_heads as materialized (
    select semantic_head.*
    from content_factory_private.ai_historical_semantic_decision_heads(
      p_organization_id,
      category_value
    ) semantic_head
  ), candidate_cases as materialized (
    select
      historical_case.case_id,
      historical_case.case_hash,
      historical_case.creative_angle,
      historical_case.outcome,
      historical_case.platform,
      semantic_head.decision_hash,
      semantic_head.decision_event_cursor as event_cursor
    from content_factory.ai_historical_case_events historical_case
    join semantic_heads semantic_head
      on semantic_head.case_id = historical_case.case_id
     and semantic_head.decision = 'confirm'
    where historical_case.organization_id = p_organization_id
      and historical_case.product_category = category_value
      and historical_case.resolution_status = 'matched'
      and historical_case.creative_angle is not null
      and historical_case.outcome in ('good', 'bad')
      and (
        historical_case.product_id = p_product_id
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and (
            historical_case.product_sku = target_product_row.sku
            or (
              target_product_row.current_wb_article is not null
              and historical_case.marketplace_sku =
                target_product_row.current_wb_article
            )
          )
        )
        or (
          historical_case.product_id is null
          and historical_case.resolution_method in (
            'source_external_sku', 'source_marketplace_sku'
          )
          and target_product_row.sku ~ '^[0-9]{4,20}$'
          and historical_case.marketplace_sku = target_product_row.sku
        )
      )
  ), eligible as materialized (
    select
      candidate_case.case_id,
      candidate_case.case_hash,
      candidate_case.creative_angle,
      candidate_case.outcome,
      candidate_case.platform,
      binding.binding_method,
      candidate_case.decision_hash,
      candidate_case.event_cursor
    from candidate_cases candidate_case
    cross join lateral (
      select content_factory_private
        .ai_historical_case_product_binding_method(
          p_organization_id,
          candidate_case.case_id,
          p_product_id
        ) as binding_method
    ) binding
    where binding.binding_method is not null
    order by candidate_case.event_cursor desc
    limit 100
  ), angle_summary as (
    select
      eligible.creative_angle,
      count(*)::integer as confirmed_case_count,
      count(*) filter (where eligible.outcome = 'good')::integer
        as good_case_count,
      count(*) filter (where eligible.outcome = 'bad')::integer
        as bad_case_count,
      count(distinct eligible.platform)::integer
        as distinct_platform_count
    from eligible
    group by eligible.creative_angle
  )
  select
    (select count(*)::integer from eligible),
    (select count(distinct eligible.platform)::integer from eligible),
    (select count(*) filter (
       where eligible.binding_method = 'exact_product_id'
     )::integer from eligible),
    (select count(*) filter (
       where eligible.binding_method in (
         'late_unique_product_sku', 'late_unique_marketplace_sku'
       )
     )::integer from eligible),
    coalesce((select jsonb_agg(jsonb_build_object(
      'creative_angle', angle_summary.creative_angle,
      'confirmed_case_count', angle_summary.confirmed_case_count,
      'good_case_count', angle_summary.good_case_count,
      'bad_case_count', angle_summary.bad_case_count,
      'score', angle_summary.good_case_count - angle_summary.bad_case_count,
      'distinct_platform_count', angle_summary.distinct_platform_count
    ) order by angle_summary.creative_angle) from angle_summary), '[]'::jsonb),
    coalesce((select jsonb_agg(jsonb_build_object(
      'case_id', bounded.case_id,
      'case_hash', bounded.case_hash,
      'decision_hash', bounded.decision_hash,
      'binding_method', bounded.binding_method,
      'decision_event_cursor', bounded.event_cursor
    ) order by bounded.event_cursor desc)
    from (
      select eligible.*
      from eligible
      order by eligible.event_cursor desc
      limit 20
    ) bounded), '[]'::jsonb)
  into
    considered_count_value,
    distinct_platform_count_value,
    direct_product_binding_count_value,
    late_exact_sku_binding_count_value,
    angles_value,
    case_refs_value;

  select max((angle ->> 'score')::integer)
  into maximum_score_value
  from jsonb_array_elements(angles_value) angle;
  if maximum_score_value is not null then
    select count(*)::integer
    into maximum_score_tie_count
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = maximum_score_value;
  end if;
  if maximum_score_value >= 2 and maximum_score_tie_count = 1 then
    select angle ->> 'creative_angle'
    into preferred_angle_value
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = maximum_score_value
    limit 1;
  end if;

  select min((angle ->> 'score')::integer)
  into minimum_score_value
  from jsonb_array_elements(angles_value) angle;
  if minimum_score_value is not null then
    select count(*)::integer
    into minimum_score_tie_count
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = minimum_score_value;
  end if;
  if minimum_score_value <= -2 and minimum_score_tie_count = 1 then
    select angle ->> 'creative_angle'
    into avoid_angle_value
    from jsonb_array_elements(angles_value) angle
    where (angle ->> 'score')::integer = minimum_score_value
      and angle ->> 'creative_angle' is distinct from preferred_angle_value
    limit 1;
  end if;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'product_category', category_value,
    'product_id', p_product_id,
    'angles', angles_value,
    'case_refs', case_refs_value,
    'maximum_cases_considered', 100
  ));

  return jsonb_build_object(
    'version', 'ai-historical-product-case-evidence-v1',
    'product_category', category_value,
    'product_id', p_product_id,
    'eligible_total_case_count', eligible_total_count_value,
    'considered_case_count', considered_count_value,
    'maximum_cases_considered', 100,
    'evidence_truncated', eligible_total_count_value > 100,
    'distinct_product_count', case when considered_count_value > 0 then 1 else 0 end,
    'distinct_platform_count', distinct_platform_count_value,
    'direct_product_binding_case_count',
      direct_product_binding_count_value,
    'late_exact_sku_binding_case_count',
      late_exact_sku_binding_count_value,
    'angles', angles_value,
    'bounded_case_refs', case_refs_value,
    'bounded_case_ref_limit', 20,
    'advisory_preferred_creative_angle', preferred_angle_value,
    'advisory_avoid_creative_angle', avoid_angle_value,
    'preferred_score', maximum_score_value,
    'preferred_score_tie_count', maximum_score_tie_count,
    'avoid_score', minimum_score_value,
    'avoid_score_tie_count', minimum_score_tie_count,
    'minimum_absolute_score', 2,
    'evidence_hash', evidence_hash_value,
    'exact_product_scope', true,
    'semantic_identity', 'product_category+external_case_id+row_hash',
    'semantic_duplicate_cases_collapsed', true,
    'latest_semantic_human_decision_only', true,
    'late_binding_exact_unique_sku_only', true,
    'fuzzy_binding_forbidden', true,
    'conflicting_external_identities_excluded', true,
    'raw_prose_excluded', true,
    'urls_excluded', true,
    'metrics_excluded', true,
    'hook_patterns', '[]'::jsonb,
    'pending_cases_excluded', true,
    'quarantined_cases_excluded', true,
    'rejected_heads_excluded', true,
    'provider_action', false,
    'generation_action', false,
    'spend_action', false
  );
end;
$$;

revoke all on function
  content_factory_private.ai_historical_product_case_evidence(uuid, text, uuid)
  from public, anon, authenticated, service_role;

-- 4. Surface the reopened legacy intake to the browser while keeping the
--    research-inbox lockdown (202608100008) fully intact.  Intake mutations
--    stay role-gated server-side (owner/admin/producer via can_mutate,
--    202608040002); creator_decide_ai_research_receipt stays service-only.
create or replace function public.creator_ai_learning_control_room(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  base_value jsonb;
begin
  base_value := content_factory_private
    .creator_ai_learning_control_room_pre_research_inbox_v1(p_payload);
  return base_value || jsonb_build_object(
    'research_inbox', '[]'::jsonb,
    'research_decisions', '[]'::jsonb,
    'category_detail', coalesce(base_value -> 'category_detail', '{}'::jsonb)
      || jsonb_build_object(
        'research_inbox', '[]'::jsonb,
        'research_decisions', '[]'::jsonb,
        'research_inbox_count', 0,
        'research_decision_count', 0
      ),
    'capabilities', coalesce(base_value -> 'capabilities', '{}'::jsonb)
      || jsonb_build_object(
        'can_read_research_inbox', false,
        'can_decide_research_inbox', false,
        'legacy_intake_read_only', false
      ),
    'guidance', coalesce(base_value -> 'guidance', '{}'::jsonb)
      || jsonb_build_object('research_inbox_next_action', null)
  );
end;
$$;

revoke all on function public.creator_ai_learning_control_room(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_learning_control_room(jsonb)
  to authenticated, service_role;

-- Fail closed if any of the four reinstalled bodies drifted.
do $verify_ai_learning_prompt_reactivation$
declare
  pre_project_definition text;
  binding_definition text;
  evidence_definition text;
  control_room_definition text;
begin
  pre_project_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  ));
  binding_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.ai_historical_case_product_binding_method(uuid,uuid,uuid)'::regprocedure
  ));
  evidence_definition := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.ai_historical_product_case_evidence(uuid,text,uuid)'::regprocedure
  ));
  control_room_definition := lower(pg_catalog.pg_get_functiondef(
    'public.creator_ai_learning_control_room(jsonb)'::regprocedure
  ));

  if strpos(pre_project_definition, 'ai_effective_category_policies') = 0
     or strpos(
       pre_project_definition,
       'creator_generation_learning_policy_pre_ai_control_room_v8'
     ) = 0
     or strpos(
       pre_project_definition, 'generation-learning-v9-ai-teaching'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'ai_learning_prompt_reactivation_teaching_overlay_missing';
  end if;

  if strpos(binding_definition, '[0-9]{4,20}') = 0
     or strpos(binding_definition, 'product_sku_match_count > 1') = 0
     or strpos(binding_definition, 'late_unique_marketplace_sku') = 0 then
    raise exception using
      errcode = '55000',
      message = 'ai_learning_prompt_reactivation_binding_fallthrough_missing';
  end if;

  if (
    select count(*)
    from regexp_matches(
      evidence_definition,
      'historical_case\.marketplace_sku = target_product_row\.sku',
      'g'
    )
  ) <> 2 then
    raise exception using
      errcode = '55000',
      message = 'ai_learning_prompt_reactivation_evidence_preselect_missing';
  end if;

  if strpos(control_room_definition, '''legacy_intake_read_only'', false') = 0
     or strpos(
       control_room_definition, '''can_decide_research_inbox'', false'
     ) = 0 then
    raise exception using
      errcode = '55000',
      message = 'ai_learning_prompt_reactivation_capability_missing';
  end if;
end;
$verify_ai_learning_prompt_reactivation$;

notify pgrst, 'reload schema';

commit;
