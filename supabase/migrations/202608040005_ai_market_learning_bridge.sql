begin;

-- The research subsystem is the only evidence/readiness authority for market
-- categories.  This read model exposes every product's current dynamic
-- category binding to the AI control room without copying the parser, source
-- ledger or score formula into the legacy eight-category teaching subsystem.
create or replace function public.creator_ai_learning_market_scope_index(
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
  user_id uuid;
  organization_id_value uuid;
  limit_value integer := 50;
  numeric_value numeric;
  as_of_value timestamptz := statement_timestamp();
  scopes_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_learning_market_scope_index_payload_invalid';
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  if not exists (
    select 1
    from content_factory.organizations organization
    join content_factory.memberships membership
      on membership.organization_id = organization.id
     and membership.profile_id = user_id
     and membership.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where organization.id = organization_id_value
      and organization.status = 'active'
  ) then
    raise exception using
      errcode = '42501', message = 'organization_access_denied';
  end if;

  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number' then
      raise exception using
        errcode = '22023',
        message = 'ai_learning_market_scope_index_limit_invalid';
    end if;
    begin
      numeric_value := (p_payload ->> 'limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023',
        message = 'ai_learning_market_scope_index_limit_invalid';
    end;
    if numeric_value <> trunc(numeric_value)
       or numeric_value not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'ai_learning_market_scope_index_limit_invalid';
    end if;
    limit_value := numeric_value::integer;
  end if;

  with current_bindings as (
    select distinct on (binding.product_id) binding.*
    from content_factory.research_product_market_category_bindings binding
    where binding.organization_id = organization_id_value
    order by binding.product_id, binding.binding_version desc, binding.id desc
  ), bounded_bindings as (
    select binding.*
    from current_bindings binding
    join content_factory.products product
      on product.organization_id = binding.organization_id
     and product.id = binding.product_id
     and product.status <> 'archived'
    join content_factory.research_market_categories category
      on category.organization_id = binding.organization_id
     and category.id = binding.category_id
     and category.status = 'active'
    order by binding.confirmed_at desc, binding.id desc
    limit limit_value
  ), readiness_categories as materialized (
    select distinct binding.category_id
    from bounded_bindings binding
  ), readiness_by_category as materialized (
    select
      category.category_id,
      content_factory_private.research_category_evidence_readiness(
        organization_id_value, category.category_id, as_of_value
      ) as value
    from readiness_categories category
  ), exact_scopes as (
    select
      binding.*,
      product.title as product_name,
      product.status as product_status,
      category.canonical_name,
      category.definition,
      source_run.id as run_id,
      source_run.status as run_status,
      source_run.finished_at as run_finished_at,
      readiness.value as readiness_value
    from bounded_bindings binding
    join content_factory.products product
      on product.organization_id = binding.organization_id
     and product.id = binding.product_id
    join content_factory.research_market_categories category
      on category.organization_id = binding.organization_id
     and category.id = binding.category_id
    join content_factory.product_research_runs source_run
      on source_run.organization_id = binding.organization_id
     and source_run.product_id = binding.product_id
     and source_run.id = binding.source_run_id
    join readiness_by_category readiness
      on readiness.category_id = binding.category_id
    where readiness.value ->> 'metric_kind'
        = 'category_evidence_readiness_not_model_iq'
      and readiness.value ->> 'definition_version'
        = 'category-evidence-readiness-v3'
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'scope_id', scope.id,
    'product_id', scope.product_id,
    'product_name', scope.product_name,
    'product_status', scope.product_status,
    'market_category_id', scope.category_id,
    'canonical_name', scope.canonical_name,
    'definition', scope.definition,
    'binding_id', scope.id,
    'binding_version', scope.binding_version,
    'run_id', scope.run_id,
    'run_status', scope.run_status,
    'run_finished_at', scope.run_finished_at,
    'readiness', jsonb_build_object(
      'metric_kind', scope.readiness_value ->> 'metric_kind',
      'definition_version', scope.readiness_value ->> 'definition_version',
      'score', (scope.readiness_value ->> 'score')::integer,
      'dimensions', scope.readiness_value -> 'dimensions',
      'weights_total', (scope.readiness_value ->> 'weights_total')::integer,
      'evidence_hash', scope.readiness_value ->> 'evidence_hash',
      'as_of', scope.readiness_value -> 'as_of'
    ),
    'guidance', jsonb_build_object(
      'status', case
        when (scope.readiness_value ->> 'score')::integer >= 80
          then 'strong_evidence'
        when (scope.readiness_value ->> 'score')::integer >= 50
          then 'developing_evidence'
        else 'insufficient_evidence'
      end,
      'gaps', coalesce((
        select jsonb_agg(item.dimension order by item.ordinal)
        from jsonb_array_elements(scope.readiness_value -> 'dimensions')
          with ordinality item(dimension, ordinal)
        where (item.dimension ->> 'missing')::integer > 0
      ), '[]'::jsonb),
      'recommended_next_action', (
        select item.dimension ->> 'next_action'
        from jsonb_array_elements(scope.readiness_value -> 'dimensions')
          with ordinality item(dimension, ordinal)
        where (item.dimension ->> 'missing')::integer > 0
        order by item.ordinal
        limit 1
      )
    )
  ) order by scope.confirmed_at desc, scope.id desc), '[]'::jsonb)
  into scopes_value
  from exact_scopes scope;

  return jsonb_build_object(
    'ok', true,
    'version', 'ai-learning-market-scope-index-v1',
    'organization_id', organization_id_value,
    'metric_kind', 'category_evidence_readiness_not_model_iq',
    'as_of', as_of_value,
    'scopes', scopes_value,
    'limits', jsonb_build_object(
      'item_limit', limit_value,
      'detail_rpc', 'creator_research_category_learning_status',
      'score_is_model_iq', false,
      'status_read_only', true,
      'external_call_started', false
    )
  );
end;
$$;

revoke all on function public.creator_ai_learning_market_scope_index(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_learning_market_scope_index(jsonb)
  to authenticated;

-- The legacy teaching-card overlay can reach a strong/high-confidence policy
-- without one parsed source because its old score counts registrations and
-- rejected cards.  Keep its append-only history readable, but remove it from
-- paid generation until a future exact dynamic-category policy carries
-- research readiness and source-analysis lineage.  The audited v8 policy
-- chain remains the authoritative generation policy in the meantime.
create or replace function public.creator_generation_learning_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  base_policy jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  base_policy := content_factory_private
    .creator_generation_learning_policy_pre_ai_control_room_v8(p_payload);
  return base_policy;
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

comment on function public.creator_ai_learning_market_scope_index(jsonb) is
  'Read-only dynamic market-category index. Scores are research evidence readiness v3, never model IQ and never legacy knowledge-source inventory.';
comment on function public.creator_generation_learning_policy(jsonb) is
  'Authoritative pre-legacy generation-learning policy; ungrounded static AI teaching history is audit-only and cannot affect paid generation.';

notify pgrst, 'reload schema';

commit;
